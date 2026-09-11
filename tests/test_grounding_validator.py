# Grounding Validator가 원문 기반 요약과 원문에 없는 요약을 구분하는지 테스트한다.
# Grounding score와 warning 생성 동작을 검증한다.

from ai.schemas.analysis import (
    Summary,
    Transcript,
    TranscriptSegment,
)
from ai.services.grounding_validator import (
    calculate_grounding_score,
    validate_summary_grounding,
)


def make_transcript():
    return Transcript(
        schema_version="1.0",
        segments=[
            TranscriptSegment(
                segment_id="seg_001",
                speaker="COUNSELOR",
                start_ms=0,
                end_ms=2000,
                text="학교생활은 어때?",
                confidence=1.0,
            ),
            TranscriptSegment(
                segment_id="seg_002",
                speaker="CHILD",
                start_ms=3000,
                end_ms=6000,
                text="수학 숙제가 많아서 힘들어요.",
                confidence=1.0,
            ),
        ],
    )


def test_grounded_summary():
    transcript = make_transcript()

    summary = Summary(
        overview="수학 숙제가 많아서 힘들다고 말했다.",
        key_points=[
            "수학 숙제가 많다고 말했다."
        ],
    )

    warnings = validate_summary_grounding(
        summary,
        transcript,
    )

    assert warnings == []


def test_hallucinated_summary():
    transcript = make_transcript()

    summary = Summary(
        overview=(
            "아동은 주말마다 축구대회에 참가하고 "
            "해외여행을 준비하고 있다고 말했다."
        ),
        key_points=[
            "해외여행을 준비하고 있다고 말했다."
        ],
    )

    warnings = validate_summary_grounding(
        summary,
        transcript,
    )

    assert len(warnings) > 0

    assert any(
        "원문 근거가 부족" in warning
        for warning in warnings
    )


def test_grounding_score():
    transcript = make_transcript()

    grounded_score = calculate_grounding_score(
        "수학 숙제가 많아서 힘들어요.",
        transcript,
    )

    hallucinated_score = calculate_grounding_score(
        "해외여행과 축구대회를 준비하고 있어요.",
        transcript,
    )

    assert grounded_score > hallucinated_score


def test_empty_summary():
    transcript = make_transcript()

    summary = Summary(
        overview="",
        key_points=[],
    )

    warnings = validate_summary_grounding(
        summary,
        transcript,
    )

    assert warnings == []
