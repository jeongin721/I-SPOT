# 상담 기록 문서에서 글자만 뽑는다(녹취 · 자료 올리기 '문서 파일', 2026-11-02, API_CONTRACT 21절).
#
# 받는 형식: .txt(UTF-8 · CP949) · .docx · .hwpx · .pdf(글자가 든 PDF). 원본 파일은 저장하지 않고 글자만 쓴다.
# .hwp(한글 97~2018 바이너리)는 읽지 못한다 — 한글에서 'HWPX' 나 PDF 로 저장해 올리게 안내한다.
# 스캔한 PDF(그림만 있는 쪽)는 글자가 없어 422 다(OCR 은 하지 않는다).
# docx · hwpx 는 zip 안의 XML 이라 표준 라이브러리로 읽는다. zip 폭탄을 막으려고 읽는 XML 크기에 상한을 둔다.

import io
import logging
import re
import warnings
import zipfile
import zlib
from typing import List
from xml.etree import ElementTree

from app.core.errors import APIError, ErrorCode

#: 올릴 수 있는 문서 크기(바이트).
MAX_DOCUMENT_BYTES = 10 * 1024 * 1024
#: 뽑은 글자 상한. 넘으면 422(앞부분만 쓰지 않는다 — 상담 기록이 잘리면 칸이 빠진다).
MAX_DOCUMENT_CHARS = 30000
#: docx · hwpx 안에서 읽는 XML 전체 크기 상한(압축을 푼 크기).
MAX_XML_BYTES = 40 * 1024 * 1024
#: PDF 쪽 수 상한. 남이 만든 PDF 를 서버에서 여는 것이라(깨진 파일의 무한 반복 · 메모리 폭주 보안 공지가 여러 번 나온 영역)
#: 쪽 수와 뽑은 글자 수를 먼저 막고, 글자 뽑기 전체에는 따로 제한 시간을 둔다(source_document_service, 민규 의견).
MAX_PDF_PAGES = 50

ALLOWED_EXTENSIONS = (".txt", ".docx", ".hwpx", ".pdf")

# pypdf 는 깨진 파일 · 글꼴 이름을 WARNING 으로 남기는데, 그 안에 파일에서 나온 글자(앞 몇 바이트 · 글꼴 인코딩 이름)가 섞인다.
# 서버 로그에 올린 문서 내용이 남지 않게 이 서버에서는 pypdf 로그를 끈다(민규 #137 R4). pypdf 는 여기서만 쓴다.
logging.getLogger("pypdf").setLevel(logging.CRITICAL + 1)


def _invalid(message: str) -> APIError:
    return APIError(ErrorCode.VALIDATION_ERROR, message, status_code=422)


def _too_long() -> APIError:
    return _invalid(f"문서 글자가 {MAX_DOCUMENT_CHARS:,}자를 넘습니다. 이 회차 상담 기록만 올려 주세요.")


def _clean(text: str) -> str:
    lines = [" ".join(line.split()) for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    text = "\n".join(lines)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    # 저장할 수 없는 글자(NUL)를 뺀다.
    return text.replace("\x00", "")


#: PDF 줄을 앞줄에 잇지 않는 줄 머리 — 글머리표 · 번호 · '[칸 이름]' · '칸 이름:'(새 항목이다).
#: 읽기 좋게 잇지 않는 쪽으로만 쓰인다(잇지 않은 줄도 원문 복사 검사가 덩어리로 묶어 본다 — 안전 판정은 document_note_llm._starts_item).
_PDF_ITEM_START = re.compile(r"(?:[-–—•·∙*▪◦○●■□◆◇▶►※→]|\(?\d{1,3}[.)](?!\d)|\[|[^\s:：\[\]][^:：\[\]]{0,19}[:：])")
#: 이 글자로 끝난 줄은 다음 줄에 잇지 않는다(문장 · 칸 이름이 끝났다).
_PDF_LINE_END = (".", "!", "?", "。", ":", "：")
#: 쪽에서 가장 긴 줄의 이 비율 이상이면 줄 너비가 차서 꺾인 줄로 본다.
_PDF_WRAP_RATIO = 0.7


def _join_wrapped(text: str) -> str:
    """PDF 는 눈에 보이는 줄마다 줄을 바꾼다. 줄 너비가 차서 꺾인 줄은 다음 줄에 이어 한 줄로 만든다.

    읽기 좋게 잇는 것이고, 안전은 원문 복사 검사(document_note_llm._source_runs)가 맡는다 — 마침표 없이 바뀐 줄(여기서 잇지
    못한 줄 · 쪽 사이 포함)은 다음 줄과 한 덩어리로 보아, 꺾인 줄 앞 조각만 옮긴 것('아동은 맞았다⏎고 말하지 않았다' →
    '아동은 맞았다.')은 버리고 통째로 옮긴 문장은 남긴다(민규 #137 보완 · 교차검증 11/05).
    문장이 끝난 줄 · 짧은 줄(문단 끝) · 새 항목으로 시작하는 줄은 잇지 않는다. docx · hwpx 는 문단이 한 줄로 나와 이 처리를 하지 않는다.
    """

    lines = text.split("\n")
    width = max((len(line) for line in lines), default=0)
    out: List[str] = []
    previous = ""
    for line in lines:
        wrapped = (
            out
            and line
            and previous
            and not previous.endswith(_PDF_LINE_END)
            and len(previous) >= width * _PDF_WRAP_RATIO
            and not _PDF_ITEM_START.match(line)
        )
        if wrapped:
            out[-1] = f"{out[-1]} {line}"
        else:
            out.append(line)
        previous = line
    return "\n".join(out)


def _txt(data: bytes) -> str:
    for encoding in ("utf-8-sig", "cp949"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise _invalid("글자 인코딩을 읽지 못했습니다. UTF-8 로 저장해 다시 올려 주세요.")


def _zip_xml(data: bytes, names: List[str]) -> List[bytes]:
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as error:
        raise _invalid("문서 파일이 손상됐거나 형식이 맞지 않습니다.") from error
    total = 0
    out = []
    with archive:
        for name in names:
            info = archive.getinfo(name)
            total += info.file_size
            if total > MAX_XML_BYTES:
                raise _invalid("문서가 너무 큽니다.")
            # 압축 본문이 깨졌거나(zlib · CRC) 지원하지 않는 압축 · 암호가 걸린 파일도 422 다(500 이 아니다, 민규 #137 낮음 1).
            try:
                out.append(archive.read(name))
            except (zipfile.BadZipFile, zlib.error, NotImplementedError, RuntimeError, EOFError) as error:
                raise _invalid("문서 파일이 손상됐거나 형식이 맞지 않습니다.") from error
    return out


def _paragraph_text(xml: bytes, paragraph_tag: str, text_tag: str) -> List[str]:
    """글자 조각(text_tag)을 가장 가까운 문단(paragraph_tag)별로 모은다. 표 안 문단이 바깥 문단과 겹쳐 두 번 나오지 않게 한다."""

    try:
        root = ElementTree.fromstring(xml)
    except ElementTree.ParseError as error:
        raise _invalid("문서 파일이 손상됐거나 형식이 맞지 않습니다.") from error
    local = lambda node: node.tag.rsplit("}", 1)[-1]  # noqa: E731
    parents = {child: parent for parent in root.iter() for child in parent}
    paragraphs: dict = {}
    for node in root.iter():
        if local(node) != text_tag:
            continue
        owner = parents.get(node)
        while owner is not None and local(owner) != paragraph_tag:
            owner = parents.get(owner)
        paragraphs.setdefault(owner, []).append(node.text or "")
    return ["".join(parts) for parts in paragraphs.values()]


def _docx(data: bytes) -> str:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            if "word/document.xml" not in archive.namelist():
                raise _invalid("Word(.docx) 문서가 아닙니다.")
    except zipfile.BadZipFile as error:
        raise _invalid("문서 파일이 손상됐거나 형식이 맞지 않습니다.") from error
    (xml,) = _zip_xml(data, ["word/document.xml"])
    return "\n".join(_paragraph_text(xml, "p", "t"))


def _hwpx(data: bytes) -> str:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            # 번호는 6자리까지만 본다(아주 긴 숫자를 정수로 바꾸다 500 이 나지 않게, 민규 #137 R8).
            sections = sorted(
                (name for name in archive.namelist() if re.fullmatch(r"Contents/section\d{1,6}\.xml", name)),
                key=lambda name: int(re.search(r"\d+", name.rsplit("/", 1)[-1]).group()),
            )
    except zipfile.BadZipFile as error:
        raise _invalid("문서 파일이 손상됐거나 형식이 맞지 않습니다.") from error
    if not sections:
        raise _invalid("한글(.hwpx) 문서가 아닙니다.")
    return "\n".join(line for xml in _zip_xml(data, sections) for line in _paragraph_text(xml, "p", "t"))


def _pdf(data: bytes) -> str:
    try:
        from pypdf import PdfReader
        from pypdf.errors import PdfReadError
    except ImportError as error:  # pragma: no cover — requirements.txt 에 있다
        raise _invalid("PDF 를 읽을 수 없는 서버입니다. Word · 한글(HWPX) · 텍스트 파일로 올려 주세요.") from error
    try:
        with warnings.catch_warnings():
            # 경고 문구에도 파일 내용이 섞일 수 있다(R4).
            warnings.simplefilter("ignore")
            return _pdf_pages(PdfReader, data)
    except (PdfReadError, ValueError, KeyError, TypeError, RecursionError) as error:
        # 깨진 PDF 는 pypdf 안에서 여러 종류 예외로 끝난다. 문구는 고정(원인 문구에 파일 내용이 섞일 수 있다).
        raise _invalid("PDF 파일이 손상됐거나 형식이 맞지 않습니다.") from error


def _pdf_pages(reader_class, data: bytes) -> str:
    reader = reader_class(io.BytesIO(data))
    if reader.is_encrypted:
        raise _invalid("암호가 걸린 PDF 는 읽지 못합니다. 암호를 풀어 다시 올려 주세요.")
    if len(reader.pages) > MAX_PDF_PAGES:
        raise _invalid(f"PDF 가 {MAX_PDF_PAGES}쪽을 넘습니다. 이 회차 상담 기록만 올려 주세요.")
    parts: List[str] = []
    total = 0
    for page in reader.pages:
        text = _join_wrapped(_clean(page.extract_text() or ""))
        parts.append(text)
        total += len(text)
        # 정리한 글자 수로 센다. 상한을 넘으면 더 읽지 않고 422 다 — 앞 쪽만 저장하면 뒤 쪽이 조용히 빠진다(민규 #137 R2).
        if total > MAX_DOCUMENT_CHARS:
            raise _too_long()
    return "\n".join(parts)


def extract_text(filename: str, data: bytes) -> str:
    """파일 이름의 확장자로 형식을 고르고 글자를 뽑는다. 형식 · 크기 · 빈 글 · 너무 긴 글은 422."""

    name = (filename or "").lower()
    if name.endswith(".hwp"):
        raise _invalid("HWP 파일은 읽지 못합니다. 한글에서 '다른 이름으로 저장' → HWPX 나 PDF 로 저장해 올려 주세요.")
    if not name.endswith(ALLOWED_EXTENSIONS):
        raise _invalid("문서는 .txt · .docx · .hwpx · .pdf 만 올릴 수 있습니다.")
    if len(data) > MAX_DOCUMENT_BYTES:
        raise _invalid("문서는 10 MB 까지 올릴 수 있습니다.")
    if not data:
        raise _invalid("빈 파일입니다.")

    if name.endswith(".txt"):
        text = _txt(data)
    elif name.endswith(".docx"):
        text = _docx(data)
    elif name.endswith(".hwpx"):
        text = _hwpx(data)
    else:
        text = _pdf(data)

    text = _clean(text)
    if not text:
        raise _invalid("문서에서 글자를 찾지 못했습니다(스캔한 그림 PDF 는 읽지 못합니다).")
    if len(text) > MAX_DOCUMENT_CHARS:
        raise _too_long()
    return text
