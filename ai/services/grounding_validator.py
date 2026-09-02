# LLM이 생성한 요약이 실제 상담 Transcript에 근거하는지 1차 검증한다.
# segment_id 유효성과 원문 어휘 일치도를 확인하여
# 근거가 부족한 경우 warnings에 추가 확인 필요 항목으로 표시한다.

import re
from typing import List, Set

from ai.schemas.analysis import Summary, Transcript


class GroundingValidationError(Exception):
    """요약 결과의 원문 근거 검증 오류."""


def normalize_text(text: str) -> str:
    """비교를 위해 문자열을 단순 정규화한다."""
    text = text.lower()
    text = re.sub(r"[^\w가-힣\s]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def extract_words(text: str) -> Set[str]:
    """2글자 이상의 의미 있는 단어 집합을 반환한다."""
    normalized = normalize_text(text)
    return {word for word in normalized.split() if len(word) >= 2}


def calculate_grounding_score(
    text: str,
    source_words: Set[str],
    source_full_text: str,
) -> float:
    """
    요약 문장의 단어가 원문에 존재하는지 검사한다.
    (조사 차이 극복을 위해 단어 일치 및 부분 문자열 포함 여부 결합)
    """
    summary_words = extract_words(text)
    if not summary_words:
        return 1.0

    matched_count = 0
    for word in summary_words:
        # 1. 단어 단위 완전 일치 검사
        if word in source_words:
            matched_count += 1
        # 2. 한국어 조사 차이 보정을 위한 부분 문자열 검사
        elif word in source_full_text:
            matched_count += 1

    return matched_count / len(summary_words)


def validate_summary_grounding(
    summary: Summary,
    transcript: Transcript,
    threshold: float = 0.3,
) -> List[str]:
    """
    overview와 key_points의 원문 근거를 검증하고,
    key_points에 연결된 segment_id의 유효성을 확인한다.
    """
    warnings: List[str] = []

    # 1. 정보 부족 상담 예외 처리
    # (key_points가 비어있고 안내성 overview인 경우 환각 검증 스킵)
    if not summary.key_points and (
        not summary.overview.strip()
        or "추가 확인 필요" in summary.overview
        or "파악하기 어렵" in summary.overview
    ):
        return warnings

    # 2. Transcript 소스 텍스트 및 단어 캐싱 (반복 연산 방지)
    valid_segment_ids = {seg.segment_id for seg in transcript.segments}
    source_full_text = normalize_text(" ".join(seg.text for seg in transcript.segments if seg.text.strip()))
    source_words = extract_words(source_full_text)

    # 3. overview 원문 근거 검증
    if summary.overview.strip() and summary.overview != "추가 확인 필요":
        overview_score = calculate_grounding_score(
            summary.overview,
            source_words,
            source_full_text,
        )
        if overview_score < threshold:
            warnings.append("요약 내용의 원문 근거가 부족하여 추가 확인 필요")

    # 4. key_points 검증
    for index, key_point in enumerate(summary.key_points, start=1):
        # segment_id 유효성 확인
        for segment_id in key_point.segment_ids:
            if segment_id not in valid_segment_ids:
                warnings.append(
                    f"핵심 내용 {index}에 유효하지 않은 segment_id({segment_id})가 연결되었습니다."
                )

        # 핵심 내용 자체의 원문 근거 확인
        score = calculate_grounding_score(
            key_point.point,
            source_words,
            source_full_text,
        )
        if score < threshold:
            warnings.append(
                f"핵심 내용 {index}의 원문 근거가 부족하여 추가 확인 필요"
            )

    return warnings