from __future__ import annotations

from typing import Any

from .config import TOP_K
from .vector_store import get_vector_store


def _build_filter(
    source_type: str | None = None,
    abuse_type: str | None = None,
    screen: str | None = None,
    screen_section: str | None = None,
) -> dict[str, Any] | None:
    conditions: list[dict[str, Any]] = []

    if source_type:
        conditions.append({"source_type": source_type})

    if abuse_type:
        conditions.append({"abuse_type": abuse_type})

    if screen:
        conditions.append({"screen": screen})

    if screen_section:
        conditions.append({"screen_section": screen_section})

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
    screen: str | None = None,
    screen_section: str | None = None,
    min_similarity: float | None = None,
) -> list[dict[str, Any]]:
    """질문과 가까운 조각을 찾는다. 각 결과의 similarity 는 코사인 유사도(1 에 가까울수록 비슷함)다.

    min_similarity 를 주면 그보다 낮은 결과는 뺀다(맞는 내용이 없으면 빈 목록).
    """
    vector_store = get_vector_store()

    search_kwargs: dict[str, Any] = {"k": top_k}
    metadata_filter = _build_filter(
        source_type=source_type,
        abuse_type=abuse_type,
        screen=screen,
        screen_section=screen_section,
    )

    if metadata_filter is not None:
        search_kwargs["filter"] = metadata_filter

    scored = vector_store.similarity_search_with_score(query, **search_kwargs)

    results = []
    for doc, distance in scored:
        similarity = _cosine_similarity(distance)
        if min_similarity is not None and similarity < min_similarity:
            continue
        results.append(
            {
                "content": doc.page_content,
                "metadata": doc.metadata,
                "similarity": similarity,
            }
        )
    return results


def _cosine_similarity(distance: float) -> float:
    """Chroma 기본 거리(제곱 유클리드)를 코사인 유사도로 바꾼다.

    OpenAI 임베딩은 길이가 1 로 정규화되어 있어 거리² = 2 − 2·cos 이므로 cos = 1 − 거리² / 2 다.
    """
    return round(1.0 - float(distance) / 2.0, 4)
