from __future__ import annotations

import re

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from .config import CHUNK_OVERLAP, CHUNK_SIZE
from .metadata import enrich_chunk_metadata, make_chunk_id


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

        if source_type == "checklist":
            page_chunks = _split_checklist_document(doc)
        else:
            page_chunks = default_splitter.split_documents([doc])

        for index, chunk in enumerate(page_chunks, start=1):
            metadata = dict(chunk.metadata)
            document_id = str(metadata.get("document_id", "document"))
            page = int(metadata.get("page", 0) or 0)
            metadata["chunk_id"] = make_chunk_id(document_id, page, index)

            # 일반 문서는 여기서 분류하고, 체크리스트는 위에서 구조 기반 분류를 이미 적용한다.
            if source_type != "checklist":
                metadata = enrich_chunk_metadata(metadata, chunk.page_content)

            chunks.append(
                Document(
                    page_content=chunk.page_content.strip(),
                    metadata=metadata,
                )
            )

    return chunks
