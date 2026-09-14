from __future__ import annotations

from typing import Any


def _shorten(text: str, limit: int = 700) -> str:
    normalized = " ".join((text or "").split())
    if len(normalized) <= limit:
        return normalized
    return normalized[: limit - 1].rstrip() + "…"


def build_reference_materials(
    checklist_results: list[dict[str, Any]],
    law_articles: list[dict[str, Any]],
    supplementary_results: list[dict[str, Any]],
    *,
    limit: int = 3,
) -> list[dict[str, Any]]:
    """상담사에게 보여줄 핵심 참고자료 2~3개를 출처 유형별로 균형 있게 선택한다."""
    materials: list[dict[str, Any]] = []
    seen_keys: set[tuple[str, str, str]] = set()

    def add(item: dict[str, Any], key: tuple[str, str, str]) -> None:
        if len(materials) >= limit or key in seen_keys:
            return
        materials.append(item)
        seen_keys.add(key)

    # 1순위: 상담 내용과 직접 일치한 공식 체크리스트
    ordered_checklists = sorted(
        [
            item
            for item in checklist_results
            if item.get("status") in {"matched", "needs_confirmation"}
        ],
        key=lambda item: 0 if item.get("status") == "matched" else 1,
    )

    for item in ordered_checklists:
        source = str(item.get("source", ""))
        page = str(item.get("page", ""))
        add(
            {
                "type": "checklist",
                "title": source or "공식 체크리스트",
                "summary": _shorten(str(item.get("item", ""))),
                "status": item.get("status"),
                "source": source,
                "organization": item.get("organization", ""),
                "page": item.get("page"),
                "chunk_id": item.get("chunk_id", ""),
            },
            ("checklist", source, page),
        )
        if materials:
            break

    # 2순위: 현행 법령 관련 조문
    for article in law_articles:
        law_name = str(article.get("law_name", ""))
        article_name = str(article.get("article", ""))
        add(
            {
                "type": "law",
                "title": law_name,
                "article": article_name,
                "article_title": article.get("title", ""),
                "summary": _shorten(str(article.get("content", ""))),
                "matched_keywords": article.get("matched_keywords", []),
                "effective_date": article.get("effective_date", ""),
                "source": "국가법령정보센터",
            },
            ("law", law_name, article_name),
        )
        if any(material.get("type") == "law" for material in materials):
            break

    # 3순위: 업무 매뉴얼/가이드 등 RAG 자료
    for result in supplementary_results:
        metadata = result.get("metadata", {})
        source = str(metadata.get("source", ""))
        page = str(metadata.get("page", ""))
        source_type = str(metadata.get("source_type", "reference"))
        add(
            {
                "type": source_type,
                "title": source or "공식 참고자료",
                "summary": _shorten(str(result.get("content", ""))),
                "source": source,
                "organization": metadata.get("organization", ""),
                "page": metadata.get("page"),
                "chunk_id": metadata.get("chunk_id", ""),
            },
            (source_type, source, page),
        )
        if len(materials) >= limit:
            break

    # 특정 출처가 비어 2개 미만이면 남은 체크리스트로 보충한다.
    if len(materials) < min(2, limit):
        for item in ordered_checklists:
            source = str(item.get("source", ""))
            page = str(item.get("page", ""))
            add(
                {
                    "type": "checklist",
                    "title": source or "공식 체크리스트",
                    "summary": _shorten(str(item.get("item", ""))),
                    "status": item.get("status"),
                    "source": source,
                    "organization": item.get("organization", ""),
                    "page": item.get("page"),
                    "chunk_id": item.get("chunk_id", ""),
                },
                ("checklist", source, page),
            )
            if len(materials) >= limit:
                break

    return materials[:limit]
