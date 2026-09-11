from __future__ import annotations

from typing import Any

from .config import TOP_K
from .vector_store import get_vector_store


def _build_filter(
    source_type: str | None = None,
    abuse_type: str | None = None,
) -> dict[str, Any] | None:
    conditions: list[dict[str, Any]] = []

    if source_type:
        conditions.append({"source_type": source_type})

    if abuse_type:
        conditions.append({"abuse_type": abuse_type})

    if not conditions:
        return None

    if len(conditions) == 1:
        return conditions[0]

    return {"$and": conditions}


def search_evidence(
    query: str,
    *,
    top_k: int = TOP_K,
    source_type: str | None = None,
    abuse_type: str | None = None,
) -> list[dict[str, Any]]:
    vector_store = get_vector_store()

    search_kwargs: dict[str, Any] = {"k": top_k}
    metadata_filter = _build_filter(
        source_type=source_type,
        abuse_type=abuse_type,
    )

    if metadata_filter is not None:
        search_kwargs["filter"] = metadata_filter

    docs = vector_store.similarity_search(query, **search_kwargs)

    return [
        {
            "content": doc.page_content,
            "metadata": doc.metadata,
        }
        for doc in docs
    ]
