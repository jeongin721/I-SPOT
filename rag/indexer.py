from __future__ import annotations

from dotenv import load_dotenv

from .config import RAG_DATA_DIR
from .loader import load_all_pdfs
from .precedents import build_precedent_documents
from .splitter import split_documents
from .vector_store import get_vector_store


def build_index() -> dict[str, int]:
    load_dotenv()

    pages = load_all_pdfs(RAG_DATA_DIR)
    # 가이드북 등의 '판례로 보는 사례'는 쪽 조각과 별도로 사건 하나당 조각 하나를 더 만든다.
    chunks = split_documents(pages) + build_precedent_documents(pages)

    if not chunks:
        return {"pages": len(pages), "chunks": 0}

    vector_store = get_vector_store()
    ids = [str(chunk.metadata["chunk_id"]) for chunk in chunks]
    vector_store.add_documents(documents=chunks, ids=ids)

    # 분할 방식이 바뀌어 쪽마다 조각 수가 줄면 예전 조각이 남는다. 이번에 만들지 않은 조각은 지운다.
    current = set(ids)
    stale = [chunk_id for chunk_id in vector_store.get(include=[])["ids"] if chunk_id not in current]
    if stale:
        vector_store.delete(ids=stale)

    return {
        "pages": len(pages),
        "chunks": len(chunks),
        "removed": len(stale),
    }


if __name__ == "__main__":
    result = build_index()
    print(
        f"Indexed pages={result['pages']}, chunks={result['chunks']}, "
        f"removed={result.get('removed', 0)}"
    )
