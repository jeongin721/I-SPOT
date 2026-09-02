# Summary key_point가 적절한 Transcript segment_id와 연결되는지 테스트한다.
# LLM이 제공한 segment_id가 유효하면 유지되는지 확인하고,
# 근거가 없는 경우 빈 결과를 반환하는지도 검증한다.

from ai.schemas.analysis import (
    KeyPointItem,
    Transcript,
    TranscriptSegment,
)
from ai.services.evidence_linker import (
    calculate_similarity,
    find_evidence_segments,
    link_summary_evidence,
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
                text="학교생활은 요즘 어때?",
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
            TranscriptSegment(
                segment_id="seg_003",
                speaker="COUNSELOR",
                start_ms=7000,
                end_ms=9000,
                text="집에서는 어떻게 지내?",
                confidence=1.0,
            ),
            TranscriptSegment(
                segment_id="seg_004",
                speaker="CHILD",
                start_ms=10000,
                end_ms=13000,
                text="엄마랑 이야기를 많이 해요.",
                confidence=1.0,
            ),
        ],
    )


def test_similarity():
    score = calculate_similarity(
        "수학 숙제가 많아서 힘들다고 말했다.",
        "수학 숙제가 많아서 힘들어요.",
    )

    assert score > 0


def test_find_evidence_segment():
    transcript = make_transcript()

    result = find_evidence_segments(
        text="수학 숙제가 많아서 힘들다고 말했다.",
        transcript=transcript,
    )

    assert "seg_002" in result.segment_ids
    assert result.score > 0


def test_multiple_key_points():
    transcript = make_transcript()

    key_points = [
        KeyPointItem(
            point="수학 숙제가 많아서 힘들다고 말했다.",
            segment_ids=[],
        ),
        KeyPointItem(
            point="엄마와 이야기를 많이 한다고 말했다.",
            segment_ids=[],
        ),
    ]

    results = link_summary_evidence(
        key_points=key_points,
        transcript=transcript,
    )

    assert len(results) == 2
    assert "seg_002" in results[0].segment_ids
    assert "seg_004" in results[1].segment_ids


def test_existing_segment_id_is_preserved():
    transcript = make_transcript()

    key_points = [
        KeyPointItem(
            point="수학 숙제가 많아서 힘들다고 말했다.",
            segment_ids=["seg_002"],
        )
    ]

    results = link_summary_evidence(
        key_points=key_points,
        transcript=transcript,
    )

    assert len(results) == 1
    assert results[0].segment_ids == ["seg_002"]
    assert results[0].score == 1.0


def test_invalid_existing_segment_id_is_replaced():
    transcript = make_transcript()

    key_points = [
        KeyPointItem(
            point="수학 숙제가 많아서 힘들다고 말했다.",
            segment_ids=["seg_999"],
        )
    ]

    results = link_summary_evidence(
        key_points=key_points,
        transcript=transcript,
    )

    assert len(results) == 1
    assert "seg_002" in results[0].segment_ids
    assert "seg_999" not in results[0].segment_ids


def test_no_evidence():
    transcript = make_transcript()

    result = find_evidence_segments(
        text=(
            "아동은 해외여행을 준비하고 "
            "축구대회에 참가했다."
        ),
        transcript=transcript,
    )

    assert result.segment_ids == []
    assert result.score == 0.0