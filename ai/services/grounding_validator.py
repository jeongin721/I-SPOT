# LLM이 생성한 요약이 실제 상담 Transcript에 근거하는지 1차 검증한다.
# 원문과 지나치게 동떨어진 요약은 warnings에 추가 확인 필요 항목으로 표시한다.

import re
from typing import List

from ai.schemas.analysis import Summary, Transcript


class GroundingValidationError(Exception):
    """요약 결과의 원문 근거 검증 오류."""


def normalize_text(text: str) -> str:
    """
    비교를 위해 문자열을 단순 정규화한다.
    """

    text = text.lower()

    text = re.sub(
        r"[^\w가-힣\s]",
        " ",
        text,
    )

    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    return text.strip()


def extract_words(text: str) -> set[str]:
    """
    너무 짧은 표현을 제외한 단어 집합을 반환한다.
    """

    normalized = normalize_text(text)

    return {
        word
        for word in normalized.split()
        if len(word) >= 2
    }


def build_source_text(
    transcript: Transcript,
) -> str:
    """
    Transcript 전체 발화를 하나의 문자열로 만든다.
    """

    return " ".join(
        segment.text
        for segment in transcript.segments
        if segment.text.strip()
    )


def calculate_grounding_score(
    text: str,
    transcript: Transcript,
) -> float:
    """
    요약 문장의 단어 중 Transcript에서도 확인되는
    단어의 비율을 계산한다.

    완전한 hallucination 판별기가 아니라
    1차 방어용 휴리스틱이다.
    """

    summary_words = extract_words(text)

    if not summary_words:
        return 1.0

    source_words = extract_words(
        build_source_text(transcript)
    )

    matched_words = (
        summary_words & source_words
    )

    return len(matched_words) / len(
        summary_words
    )


def validate_summary_grounding(
    summary: Summary,
    transcript: Transcript,
    threshold: float = 0.3,
) -> List[str]:
    """
    overview와 key_points가 Transcript와 지나치게
    동떨어진 경우 warning을 생성한다.

    자동으로 사실 여부를 확정하지 않고
    상담사 검토가 필요하다는 warning만 반환한다.
    """

    warnings: List[str] = []

    overview_score = calculate_grounding_score(
        summary.overview,
        transcript,
    )

    if (
        summary.overview.strip()
        and overview_score < threshold
    ):
        warnings.append(
            "요약 내용의 원문 근거가 부족하여 추가 확인 필요"
        )

    for index, key_point in enumerate(
        summary.key_points,
        start=1,
    ):
        score = calculate_grounding_score(
            key_point,
            transcript,
        )

        if score < threshold:
            warnings.append(
                f"핵심 내용 {index}의 원문 근거가 부족하여 추가 확인 필요"
            )

    return warnings