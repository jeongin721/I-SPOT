from __future__ import annotations

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from .config import CHUNK_OVERLAP, CHUNK_SIZE
from .metadata import make_chunk_id


SEPARATORS = ["\n\n", "\n", ". ", "다. ", "한다. ", " ", ""]


def split_documents(documents: list[Document]) -> list[Document]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=SEPARATORS,
        length_function=len,
    )

    chunks: list[Document] = []

    for doc in documents:
        if not doc.page_content.strip():
            continue

        page_chunks = splitter.split_documents([doc])
        for index, chunk in enumerate(page_chunks, start=1):
            metadata = dict(chunk.metadata)
            document_id = str(metadata.get("document_id", "document"))
            page = int(metadata.get("page", 0) or 0)
            metadata["chunk_id"] = make_chunk_id(document_id, page, index)

            chunks.append(
                Document(
                    page_content=chunk.page_content.strip(),
                    metadata=metadata,
                )
            )

    return chunks
