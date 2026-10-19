from __future__ import annotations

from pathlib import Path
from typing import Iterable

from langchain_community.document_loaders import PyPDFLoader
from langchain_core.documents import Document

from .metadata import build_base_metadata


def iter_pdf_files(root_dir: Path) -> Iterable[Path]:
    yield from sorted(root_dir.rglob("*.pdf"))


def load_pdf(file_path: Path) -> list[Document]:
    base_metadata = build_base_metadata(file_path)
    pages = PyPDFLoader(str(file_path)).load()

    normalized: list[Document] = []
    for page_index, doc in enumerate(pages, start=1):
        metadata = dict(base_metadata)
        metadata.update(doc.metadata or {})
        metadata["page"] = page_index
        metadata["source_path"] = str(file_path)

        normalized.append(
            Document(
                page_content=(doc.page_content or "").strip(),
                metadata=metadata,
            )
        )

    return normalized


def load_all_pdfs(root_dir: Path) -> list[Document]:
    documents: list[Document] = []
    for file_path in iter_pdf_files(root_dir):
        documents.extend(load_pdf(file_path))
    return documents
