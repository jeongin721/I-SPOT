from __future__ import annotations

from typing import Any


ABUSE_LAW_KEYWORDS: dict[str, list[str]] = {
    "physical": [
        "신체적 학대행위", "신체적 학대", "폭행", "상해", "체벌", "신체",
        "아동학대", "금지행위",
    ],
    "emotional": [
        "정서적 학대행위", "정서적 학대", "폭언", "위협", "모욕", "정신건강",
        "아동학대", "금지행위",
    ],
    "sexual": [
        "성적 학대행위", "성적 학대", "성폭력", "성적 행위", "성매매", "음란",
        "아동학대", "금지행위",
    ],
    "neglect": [
        "방임행위", "방임", "유기", "보호", "의식주", "의료", "교육",
        "아동학대", "금지행위",
    ],
}


TEXT_SIGNAL_MAP: dict[str, list[str]] = {
    "욕": ["폭언", "정서적 학대행위"],
    "욕설": ["폭언", "정서적 학대행위"],
    "모욕": ["모욕", "정서적 학대행위"],
    "쓸모없": ["모욕", "정서적 학대행위"],
    "위협": ["위협", "정서적 학대행위"],
    "쫓아": ["정서적 학대행위", "보호"],
    "때리": ["폭행", "신체적 학대행위"],
    "멍": ["상해", "신체적 학대행위"],
    "상처": ["상해", "신체적 학대행위"],
    "성적": ["성적 학대행위", "성폭력"],
    "만졌": ["성적 학대행위", "성폭력"],
    "굶": ["방임", "의식주"],
    "혼자": ["방임", "보호"],
    "병원": ["방임", "의료"],
    "치료": ["방임", "의료"],
    "결석": ["방임", "교육"],
}


def build_law_keywords(abuse_type: str, consultation_text: str = "") -> list[str]:
    if abuse_type == "multiple":
        base = [keyword for values in ABUSE_LAW_KEYWORDS.values() for keyword in values]
    else:
        base = list(ABUSE_LAW_KEYWORDS.get(abuse_type, ["아동학대", "금지행위"]))

    for signal, mapped in TEXT_SIGNAL_MAP.items():
        if signal in consultation_text:
            base.extend(mapped)

    result: list[str] = []
    for keyword in base:
        if keyword not in result:
            result.append(keyword)
    return result


def rank_law_articles(
    articles: list[dict[str, Any]],
    *,
    abuse_type: str,
    consultation_text: str,
    limit: int = 3,
) -> list[dict[str, Any]]:
    """학대유형과 상담 표현을 기반으로 관련 법 조문을 가볍게 랭킹한다."""
    keywords = build_law_keywords(abuse_type, consultation_text)
    ranked: list[dict[str, Any]] = []

    for article in articles:
        title = str(article.get("title", ""))
        content = str(article.get("content", ""))
        matched: list[str] = []
        score = 0.0

        for keyword in keywords:
            if keyword in title:
                score += 4.0
                matched.append(keyword)
            elif keyword in content:
                score += 2.0
                matched.append(keyword)

        if "금지행위" in title:
            score += 3.0
        if "아동학대" in title:
            score += 2.0

        if score <= 0:
            continue

        item = dict(article)
        item["relevance_score"] = score
        item["matched_keywords"] = list(dict.fromkeys(matched))
        ranked.append(item)

    ranked.sort(key=lambda item: float(item.get("relevance_score", 0)), reverse=True)
    return ranked[:limit]
