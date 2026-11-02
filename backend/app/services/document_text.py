# 상담 기록 문서에서 글자만 뽑는다(녹취 · 자료 올리기 '문서 파일', 2026-11-02, API_CONTRACT 20절).
#
# 받는 형식: .txt(UTF-8 · CP949) · .docx · .hwpx · .pdf(글자가 든 PDF). 원본 파일은 저장하지 않고 글자만 쓴다.
# .hwp(한글 97~2018 바이너리)는 읽지 못한다 — 한글에서 'HWPX' 나 PDF 로 저장해 올리게 안내한다.
# 스캔한 PDF(그림만 있는 쪽)는 글자가 없어 422 다(OCR 은 하지 않는다).
# docx · hwpx 는 zip 안의 XML 이라 표준 라이브러리로 읽는다. zip 폭탄을 막으려고 읽는 XML 크기에 상한을 둔다.

import io
import re
import zipfile
from typing import List
from xml.etree import ElementTree

from app.core.errors import APIError, ErrorCode

#: 올릴 수 있는 문서 크기(바이트).
MAX_DOCUMENT_BYTES = 10 * 1024 * 1024
#: 뽑은 글자 상한. 넘으면 422(앞부분만 쓰지 않는다 — 상담 기록이 잘리면 칸이 빠진다).
MAX_DOCUMENT_CHARS = 30000
#: docx · hwpx 안에서 읽는 XML 전체 크기 상한(압축을 푼 크기).
MAX_XML_BYTES = 40 * 1024 * 1024

ALLOWED_EXTENSIONS = (".txt", ".docx", ".hwpx", ".pdf")


def _invalid(message: str) -> APIError:
    return APIError(ErrorCode.VALIDATION_ERROR, message, status_code=422)


def _clean(text: str) -> str:
    lines = [" ".join(line.split()) for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    text = "\n".join(lines)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    # 저장할 수 없는 글자(NUL)를 뺀다.
    return text.replace("\x00", "")


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
            out.append(archive.read(name))
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
            sections = sorted(
                (name for name in archive.namelist() if re.fullmatch(r"Contents/section\d+\.xml", name)),
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
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            raise _invalid("암호가 걸린 PDF 는 읽지 못합니다. 암호를 풀어 다시 올려 주세요.")
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    except PdfReadError as error:
        raise _invalid("PDF 파일이 손상됐거나 형식이 맞지 않습니다.") from error


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
        raise _invalid(f"문서 글자가 {MAX_DOCUMENT_CHARS:,}자를 넘습니다. 이 회차 상담 기록만 올려 주세요.")
    return text
