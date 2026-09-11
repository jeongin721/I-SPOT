from __future__ import annotations

from pathlib import Path
from typing import Any

from .config import SOURCE_TYPE_MAP


def infer_source_type(file_path: Path) -> str:
    for part in file_path.parts:
        if part in SOURCE_TYPE_MAP:
            return SOURCE_TYPE_MAP[part]
    return "reference"


def infer_organization(filename: str) -> str:
    if "교육부" in filename:
        return "교육부"
    if "범죄수사규칙" in filename or "현장조사 체크리스트" in filename:
        return "경찰청"
    if "아동권리보장원" in filename or "판례" in filename:
        return "아동권리보장원"
    if "아동보호서비스 업무 매뉴얼" in filename:
        return "보건복지부·아동권리보장원"
    return "unknown"


ABUSE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "physical": (
        "신체학대", "신체적 학대", "폭행", "때리", "체벌", "멍", "상처", "화상",
        "신체에 가해", "도구를 사용", "완력을 사용",
    ),
    "emotional": (
        "정서학대", "정서적 학대", "폭언", "욕설", "위협", "강요", "감금", "억제",
        "가정폭력", "집 밖으로", "내쫓", "공포", "모욕", "두려움",
    ),
    "sexual": (
        "성학대", "성적 학대", "성적 노출", "성희롱", "성교", "성매매", "생식기",
        "성적행동", "성적 행동", "성적 수치심",
    ),
    "neglect": (
        "방임", "유기", "보호자 부재", "굶주림", "영양상태", "위생불량", "위생 불량",
        "결석", "의료적", "예방접종", "방치", "의식주",
    ),
}

CATEGORY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "definition": ("정의", "개념", "이란", "의미"),
    "abuse_sign": ("징후", "체크리스트", "현장확인", "의심", "상처", "폭언", "방임"),
    "investigation": ("조사", "확인경로", "현장조사", "진술", "CCTV"),
    "counseling": ("상담", "대화", "면담", "질문"),
    "reporting": ("신고", "112"),
    "response": ("응급조치", "긴급임시조치", "조치", "대응"),
    "protection": ("보호조치", "보호계획", "분리", "보호시설"),
    "case_management": ("사례관리", "사례회의", "사후관리"),
    "similar_case": ("판례", "사례 개요", "판정 사유", "판결"),
}


def infer_abuse_type(text: str) -> str:
    scores = {
        abuse_type: sum(text.count(keyword) for keyword in keywords)
        for abuse_type, keywords in ABUSE_KEYWORDS.items()
    }
    matched = [name for name, score in scores.items() if score > 0]
    if not matched:
        return "none"

    ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    best_type, best_score = ranked[0]
    second_score = ranked[1][1] if len(ranked) > 1 else 0

    # 여러 유형의 핵심어가 비슷한 비중으로 함께 있으면 중복학대로 표시한다.
    if len(matched) >= 2 and second_score > 0 and second_score >= best_score * 0.7:
        return "multiple"
    return best_type


def infer_category(text: str, source_type: str) -> str:
    # 체크리스트는 기본적으로 위험 신호/확인항목 성격이 강하다.
    if source_type == "checklist":
        if any(keyword in text for keyword in ("응급조치", "긴급임시조치", "판단/조치/결과")):
            return "response"
        if any(keyword in text for keyword in ("확인경로", "현장확인", "조사자")):
            return "investigation"
        return "abuse_sign"

    scores = {
        category: sum(text.count(keyword) for keyword in keywords)
        for category, keywords in CATEGORY_KEYWORDS.items()
    }
    best_category, best_score = max(scores.items(), key=lambda item: item[1])
    return best_category if best_score > 0 else "unknown"


def enrich_chunk_metadata(metadata: dict[str, Any], text: str) -> dict[str, Any]:
    enriched = dict(metadata)
    source_type = str(enriched.get("source_type", "reference"))
    enriched["category"] = infer_category(text, source_type)
    enriched["abuse_type"] = infer_abuse_type(text)
    return enriched


def build_base_metadata(file_path: Path) -> dict[str, Any]:
    stem = file_path.stem
    document_id = stem.lower().replace(" ", "_")
    source_type = infer_source_type(file_path)

    return {
        "document_id": document_id,
        "source": file_path.name,
        "organization": infer_organization(file_path.name),
        "source_type": source_type,
        "category": "unknown",
        "abuse_type": "none",
        "section": "",
        "subsection": "",
        "year": 0,
        "authority_level": "official" if source_type in {"guideline", "manual", "checklist"} else "reference",
    }


def make_chunk_id(document_id: str, page: int, index: int) -> str:
    return f"{document_id}_p{page:04d}_{index:04d}"
