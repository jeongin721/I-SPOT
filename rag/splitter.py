from __future__ import annotations

import re

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from .config import CHUNK_OVERLAP, CHUNK_SIZE
from .metadata import enrich_chunk_metadata, infer_manual_screen, make_chunk_id, section_prefix


DEFAULT_SEPARATORS = ["\n\n", "\n", ". ", "다. ", "한다. ", " ", ""]

SECTION_PATTERNS: tuple[tuple[str, str], ...] = (
    ("physical", r"신체(?:적)?\s*학대"),
    ("emotional", r"정서(?:적)?\s*학대"),
    ("sexual", r"성(?:적)?\s*학대"),
    ("neglect", r"방임(?:\s*[·/]?\s*유기)?|유기(?:\s*[·/]?\s*방임)?"),
)


def _detect_section_type(text: str) -> str | None:
    for abuse_type, pattern in SECTION_PATTERNS:
        if re.search(pattern, text):
            return abuse_type
    return None


def _prepare_checklist_lines(text: str) -> list[str]:
    """PDF에서 추출된 체크리스트 텍스트를 항목 단위로 보기 쉽게 정규화한다."""
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")

    # 체크박스가 같은 줄에 연속되어 추출되어도 각각 별도 항목으로 분리한다.
    normalized = re.sub(r"\s*□\s*", "\n□ ", normalized)

    # 학대 유형 제목 앞에도 줄바꿈을 넣어 섹션 경계를 보존한다.
    for _, pattern in SECTION_PATTERNS:
        normalized = re.sub(
            rf"(?<!\n)({pattern})",
            r"\n\1",
            normalized,
        )

    return [line.strip() for line in normalized.split("\n") if line.strip()]


def _split_checklist_document(doc: Document) -> list[Document]:
    """체크리스트는 글자 수보다 '학대 유형 섹션 + 체크 항목'을 우선해 분할한다."""
    lines = _prepare_checklist_lines(doc.page_content)
    if not lines:
        return []

    chunks: list[Document] = []
    current_section: str | None = None
    current_item: list[str] = []
    current_item_type: str | None = None

    def flush_item() -> None:
        nonlocal current_item, current_item_type
        if not current_item:
            return

        content = "\n".join(current_item).strip()
        if not content:
            current_item = []
            current_item_type = None
            return

        metadata = dict(doc.metadata)
        metadata = enrich_chunk_metadata(metadata, content)

        # 현장조사 체크리스트처럼 섹션 제목이 명시된 경우에는
        # 주변 키워드보다 문서 구조를 우선한다.
        if current_item_type:
            metadata["abuse_type"] = current_item_type
            metadata["section"] = current_item_type

        chunks.append(Document(page_content=content, metadata=metadata))
        current_item = []
        current_item_type = None

    for line in lines:
        section_type = _detect_section_type(line)

        # 섹션 제목은 이전 항목을 끝낸 뒤 이후 체크항목의 문맥으로 유지한다.
        if section_type and not line.startswith("□"):
            flush_item()
            current_section = section_type
            current_item = [line]
            current_item_type = section_type
            continue

        # 새 체크박스는 새 항목의 시작이다.
        if line.startswith("□"):
            flush_item()
            current_item = [line]
            current_item_type = current_section or _detect_section_type(line)
            continue

        # 설명문/별표 문장은 현재 체크항목에 붙인다.
        if current_item:
            current_item.append(line)
        else:
            current_item = [line]
            current_item_type = current_section or section_type

    flush_item()

    return chunks


# ---------------------------------------------------------------------------
# 업무 매뉴얼 원문 정리
# PDF 추출 글자에는 쪽 머리말, 표 머리글, 한 글자씩 벌어진 글자, 서식 빈칸이 섞여 있어
# 임베딩이 뜻을 덜 잡는다(검색 유사도가 낮아진다). 색인 전에 뜻과 무관한 글자를 지운다.
# ---------------------------------------------------------------------------

# 줄 전체가 쪽 머리말: "268", "| 271", "288 |", "2026", "|". 1~2자리 숫자만 있는 줄은 서식 항목 번호라 남긴다.
_PAGE_HEADER_LINE = re.compile(r"^(?:\|\s*\d{0,4}\s*\|?|\d{1,4}\s*\||\d{3,4})$")
# 줄 앞의 쪽 머리말: "| 287 서식 15 …", "308 | 2026 서식 20 …"
_PAGE_HEADER_PREFIX = re.compile(r"^(?:\|\s*\d{1,3}\s+|\d{1,3}\s*\|\s*(?:2026\s*)?)")
# 점검표 표 머리글: "구분 평 가 항 목 평가 ∨ 특이사항", "항목 작성내용"
_TABLE_HEADER_LINE = re.compile(r"(평\s*가\s*항\s*목.*특이사항|^항목\s*작성내용$)")
# 한 글자씩 띄어 쓴 글자: "맞 춤 이", "불 분 명 함", "주 1 회 이 상" (공백을 한 칸으로 줄인 뒤 한 글자가 3개 이상 이어짐)
_SPACED_SYLLABLES = re.compile(r"(?<![가-힣0-9])[가-힣0-9](?: [가-힣0-9](?![가-힣0-9])){2,}")
# 서식 선택지 칸: "예 아니오 불분명함", "예아 니 오"
_ANSWER_CHOICES = re.compile(r"예\s*아\s*니\s*오(?:\s*불\s*분\s*명\s*함)?")
# 서식 빈칸 · 기호: □ ■ ∨, 빈 괄호, "년 월 일"
_FORM_MARKS = re.compile(r"[□■∨]|\(\s*\)|(?<!\S)년\s+월\s+일(?!\S)")


def clean_manual_text(text: str) -> str:
    lines: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or _PAGE_HEADER_LINE.match(line) or _TABLE_HEADER_LINE.search(line):
            continue
        line = _PAGE_HEADER_PREFIX.sub("", line)
        line = " ".join(_FORM_MARKS.sub(" ", " ".join(line.split())).split())
        line = _SPACED_SYLLABLES.sub(lambda match: match.group(0).replace(" ", ""), line)
        line = " ".join(_ANSWER_CHOICES.sub(" ", line).split())
        if line:
            lines.append(line)
    return "\n".join(lines)


# 서식 평가 항목 번호. "7 연령에 …", "9정 학 …", "12" 처럼 줄 맨 앞의 1~2자리 숫자.
_ITEM_NUMBER = re.compile(r"^(\d{1,2})(?!\d)\s*(.*)$")
_MIN_FORM_ITEMS = 3


def _split_numbered_items(doc: Document) -> list[Document] | None:
    """서식 점검표 쪽을 번호 항목 하나씩으로 나눈다.

    한 쪽 전체를 한 조각으로 두면 항목 8~10개가 섞여 검색 점수가 흐려진다.
    번호가 1씩 늘어나는 줄만 항목 시작으로 보므로 쪽 번호("268", "2026")는 걸리지 않는다.
    차례로 이어지는 항목이 _MIN_FORM_ITEMS 개보다 적은 쪽(기재란 양식 등)은 None 을 돌려 기본 분할을 쓴다.
    """
    items: list[tuple[int, list[str]]] = []
    expected: int | None = None

    for raw_line in doc.page_content.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        match = _ITEM_NUMBER.match(line)
        if match:
            number = int(match.group(1))
            if (expected is None and number <= 40) or number == expected:
                items.append((number, [match.group(2)] if match.group(2) else []))
                expected = number + 1
                continue

        # 첫 항목 앞의 표 머리("구분 평 가 항 목 …")와 쪽 머리말은 버린다.
        if items:
            items[-1][1].append(line)

    if len(items) < _MIN_FORM_ITEMS:
        return None

    chunks: list[Document] = []
    for number, lines in items:
        content = "\n".join(lines).strip()
        if not content:
            continue
        metadata = dict(doc.metadata)
        metadata["item_no"] = number
        chunks.append(Document(page_content=content, metadata=metadata))
    return chunks


def _get_default_splitter() -> RecursiveCharacterTextSplitter:
    return RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=DEFAULT_SEPARATORS,
        length_function=len,
    )


def split_documents(documents: list[Document]) -> list[Document]:
    chunks: list[Document] = []
    default_splitter = _get_default_splitter()

    for doc in documents:
        if not doc.page_content.strip():
            continue

        source_type = str(doc.metadata.get("source_type", "reference"))
        _, screen_section = infer_manual_screen(
            str(doc.metadata.get("source", "")),
            int(doc.metadata.get("page", 0) or 0),
        )

        if source_type == "manual":
            doc = Document(page_content=clean_manual_text(doc.page_content), metadata=doc.metadata)
            if not doc.page_content:
                continue

        if source_type == "checklist":
            page_chunks = _split_checklist_document(doc)
        else:
            page_chunks = None
            if screen_section.startswith("[서식"):
                page_chunks = _split_numbered_items(doc)
            if page_chunks is None:
                page_chunks = default_splitter.split_documents([doc])

        for index, chunk in enumerate(page_chunks, start=1):
            metadata = dict(chunk.metadata)
            document_id = str(metadata.get("document_id", "document"))
            page = int(metadata.get("page", 0) or 0)
            metadata["chunk_id"] = make_chunk_id(document_id, page, index)

            # 일반 문서는 여기서 분류하고, 체크리스트는 위에서 구조 기반 분류를 이미 적용한다.
            if source_type != "checklist":
                metadata = enrich_chunk_metadata(metadata, chunk.page_content)

            # 화면용 구간 조각은 구간 이름을 앞에 붙여 색인한다(화면에 보일 때는 strip_section_prefix 로 뗀다).
            content = section_prefix(screen_section) + chunk.page_content.strip()

            chunks.append(
                Document(
                    page_content=content,
                    metadata=metadata,
                )
            )

    return chunks
