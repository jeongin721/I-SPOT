from __future__ import annotations

from typing import Any

from .config import TOP_K
from .vector_store import get_vector_store


def search_evidence(
    query: str,
    *,
    top_k: int = TOP_K,
    source_type: str | None = None,
    abuse_type: str | None = None,
) -> list[dict[str, Any]]:
    filters: dict[str, Any] = {}
    if source_type:
        filters["source_type"] = source_type
    if abuse_type:
        filters["abuse_type"] = abuse_type

    vector_store = get_vector_store()

    search_kwargs: dict[str, Any] = {"k": top_k}
    if filters:
        search_kwargs["filter"] = filters

    docs = vector_store.similarity_search(query, **search_kwargs)

    return [
        {
            "content": doc.page_content,
            "metadata": doc.metadata,
        }
        for doc in docs
    ]
