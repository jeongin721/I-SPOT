from __future__ import annotations

from dotenv import load_dotenv

from .config import RAG_DATA_DIR
from .loader import load_all_pdfs
from .splitter import split_documents
from .vector_store import get_vector_store


def build_index() -> dict[str, int]:
    load_dotenv()

    pages = load_all_pdfs(RAG_DATA_DIR)
    chunks = split_documents(pages)

    if not chunks:
        return {"pages": len(pages), "chunks": 0}

    vector_store = get_vector_store()
    ids = [str(chunk.metadata["chunk_id"]) for chunk in chunks]
    vector_store.add_documents(documents=chunks, ids=ids)

    return {
        "pages": len(pages),
        "chunks": len(chunks),
    }


if __name__ == "__main__":
    result = build_index()
    print(f"Indexed pages={result['pages']}, chunks={result['chunks']}")
