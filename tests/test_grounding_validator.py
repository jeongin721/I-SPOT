# Grounding Validator가 원문 기반 요약과 원문에 없는 요약을 구분하는지 테스트한다.
# Grounding score, segment_id 검증, 정보 부족 예외 처리 동작을 검증한다.

from ai.schemas.analysis import (
    KeyPointItem,
    Summary,
    Transcript,
    TranscriptSegment,
)
from ai.services.grounding_validator import (
    calculate_grounding_score,
    extract_words,
    normalize_text,
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
            KeyPointItem(
                point="수학 숙제가 많다고 말했다.",
                segment_ids=["seg_002"],
            )
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
            KeyPointItem(
                point="해외여행을 준비하고 있다고 말했다.",
                segment_ids=[],
            )
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

    source_full_text = normalize_text(
        " ".join(
            segment.text
            for segment in transcript.segments
            if segment.text.strip()
        )
    )

    source_words = extract_words(
        source_full_text
    )

    grounded_score = calculate_grounding_score(
        "수학 숙제가 많아서 힘들어요.",
        source_words,
        source_full_text,
    )

    hallucinated_score = calculate_grounding_score(
        "해외여행과 축구대회를 준비하고 있어요.",
        source_words,
        source_full_text,
    )

    assert grounded_score > hallucinated_score


def test_invalid_segment_id():
    transcript = make_transcript()

    summary = Summary(
        overview="수학 숙제가 많아서 힘들다고 말했다.",
        key_points=[
            KeyPointItem(
                point="수학 숙제가 많다고 말했다.",
                segment_ids=["seg_999"],
            )
        ],
    )

    warnings = validate_summary_grounding(
        summary,
        transcript,
    )

    assert any(
        "유효하지 않은 segment_id(seg_999)"
        in warning
        for warning in warnings
    )


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


def test_insufficient_information_summary():
    transcript = make_transcript()

    summary = Summary(
        overview="상담 내용만으로 구체적인 상태를 파악하기 어렵다.",
        key_points=[],
    )

    warnings = validate_summary_grounding(
        summary,
        transcript,
    )

    assert warnings == []