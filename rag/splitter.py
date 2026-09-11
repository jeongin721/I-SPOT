from __future__ import annotations

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from .config import CHUNK_OVERLAP, CHUNK_SIZE
from .metadata import enrich_chunk_metadata, make_chunk_id


DEFAULT_SEPARATORS = ["\n\n", "\n", ". ", "다. ", "한다. ", " ", ""]
CHECKLIST_SEPARATORS = ["\n□", "□", "\n", ". ", " ", ""]


def _get_splitter(source_type: str) -> RecursiveCharacterTextSplitter:
    if source_type == "checklist":
        return RecursiveCharacterTextSplitter(
            chunk_size=420,
            chunk_overlap=60,
            separators=CHECKLIST_SEPARATORS,
            length_function=len,
        )

    return RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=DEFAULT_SEPARATORS,
        length_function=len,
    )


def split_documents(documents: list[Document]) -> list[Document]:
    chunks: list[Document] = []

    for doc in documents:
        if not doc.page_content.strip():
            continue

        source_type = str(doc.metadata.get("source_type", "reference"))
        splitter = _get_splitter(source_type)
        page_chunks = splitter.split_documents([doc])

        for index, chunk in enumerate(page_chunks, start=1):
            metadata = dict(chunk.metadata)
            document_id = str(metadata.get("document_id", "document"))
            page = int(metadata.get("page", 0) or 0)
            metadata["chunk_id"] = make_chunk_id(document_id, page, index)
            metadata = enrich_chunk_metadata(metadata, chunk.page_content)

            chunks.append(
                Document(
                    page_content=chunk.page_content.strip(),
                    metadata=metadata,
                )
            )

    return chunks
