from __future__ import annotations

from typing import Any


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _find_law_root(payload: dict[str, Any]) -> dict[str, Any]:
    if isinstance(payload.get("법령"), dict):
        return payload["법령"]

    law_service = payload.get("LawService")
    if isinstance(law_service, dict) and isinstance(law_service.get("법령"), dict):
        return law_service["법령"]

    return payload


def _collect_text(value: Any) -> list[str]:
    """조문/항/호/목의 내용 필드를 재귀적으로 모은다."""
    texts: list[str] = []

    if isinstance(value, dict):
        for key, child in value.items():
            if key.endswith("내용") and isinstance(child, str):
                text = " ".join(child.split())
                if text and text not in texts:
                    texts.append(text)
            elif isinstance(child, (dict, list)):
                for text in _collect_text(child):
                    if text not in texts:
                        texts.append(text)
    elif isinstance(value, list):
        for child in value:
            for text in _collect_text(child):
                if text not in texts:
                    texts.append(text)

    return texts


def _law_name(root: dict[str, Any], fallback: str = "") -> str:
    basic = root.get("기본정보") if isinstance(root.get("기본정보"), dict) else {}
    for container in (basic, root):
        for key in ("법령명_한글", "법령명한글", "법령명"):
            value = container.get(key)
            if value:
                return str(value).strip()
    return fallback


def extract_articles(
    payload: dict[str, Any],
    *,
    fallback_law_name: str = "",
) -> list[dict[str, Any]]:
    """국가법령정보센터 본문 JSON을 조문 단위의 평탄한 목록으로 변환한다."""
    root = _find_law_root(payload)
    law_name = _law_name(root, fallback_law_name)

    jo_container = root.get("조문") if isinstance(root.get("조문"), dict) else {}
    units = jo_container.get("조문단위") or root.get("조문단위")

    articles: list[dict[str, Any]] = []
    for unit in _as_list(units):
        if not isinstance(unit, dict):
            continue

        number = str(unit.get("조문번호", "")).strip()
        if not number:
            continue

        branch = str(unit.get("조문가지번호", "")).strip()
        title = str(unit.get("조문제목", "")).strip()
        texts = _collect_text(unit)
        content = "\n".join(texts).strip()

        display_number = f"제{number}조"
        if branch and branch not in {"0", "00"}:
            display_number += f"의{branch.lstrip('0') or branch}"

        articles.append(
            {
                "law_name": law_name,
                "article_number": number,
                "article_branch": branch,
                "article": display_number,
                "title": title,
                "content": content,
                "effective_date": str(unit.get("조문시행일자", "")).strip(),
                "article_key": str(unit.get("조문키", "")).strip(),
            }
        )

    return articles
