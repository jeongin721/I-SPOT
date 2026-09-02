# Summary → Evidence Linking으로 이어지는 전체 AI 분석 파이프라인을 테스트한다.
# 분석 결과와 근거 segment가 함께 정상 반환되는지 검증한다.

from unittest.mock import patch

from ai.schemas.analysis import (
    AIAnalysisOutput,
    KeyPointItem,
    Summary,
    Transcript,
    TranscriptSegment,
)
from ai.services.analysis_pipeline import (
    AnalysisPipelineResult,
    run_analysis_pipeline,
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


@patch(
    "ai.services.analysis_pipeline.summarize_consultation"
)
def test_analysis_pipeline(
    mock_summary,
):
    transcript = make_transcript()

    mock_summary.return_value = AIAnalysisOutput(
        schema_version="1.0",
        summary=Summary(
            overview=(
                "아동은 수학 숙제로 힘들어하며 "
                "엄마와 이야기를 많이 한다고 말했다."
            ),
            key_points=[
                KeyPointItem(
                    point="수학 숙제가 많아서 힘들다고 말했다.",
                    segment_ids=[],
                ),
                KeyPointItem(
                    point="엄마와 이야기를 많이 한다고 말했다.",
                    segment_ids=[],
                ),
            ],
        ),
        risk_utterances=[],
        abuse_signals=[],
        risk_factors=[],
        warnings=[],
    )

    result = run_analysis_pipeline(
        transcript
    )

    assert isinstance(
        result,
        AnalysisPipelineResult,
    )

    assert result.analysis.schema_version == "1.0"

    assert len(
        result.analysis.summary.key_points
    ) == 2

    assert len(
        result.summary_evidence
    ) == 2

    assert "seg_002" in (
        result.summary_evidence[0].segment_ids
    )

    assert "seg_004" in (
        result.summary_evidence[1].segment_ids
    )

    # Evidence Linker에서 찾은 segment_id가
    # 최종 analysis.summary에도 반영되는지 확인
    assert "seg_002" in (
        result.analysis.summary.key_points[0].segment_ids
    )

    assert "seg_004" in (
        result.analysis.summary.key_points[1].segment_ids
    )

    assert result.analysis.risk_utterances == []
    assert result.analysis.abuse_signals == []
    assert result.analysis.risk_factors == []


@patch(
    "ai.services.analysis_pipeline.summarize_consultation"
)
def test_pipeline_no_evidence(
    mock_summary,
):
    transcript = make_transcript()

    mock_summary.return_value = AIAnalysisOutput(
        schema_version="1.0",
        summary=Summary(
            overview="상담 내용을 요약했다.",
            key_points=[
                KeyPointItem(
                    point="해외여행을 준비하고 있다고 말했다.",
                    segment_ids=[],
                )
            ],
        ),
        risk_utterances=[],
        abuse_signals=[],
        risk_factors=[],
        warnings=[],
    )

    result = run_analysis_pipeline(
        transcript
    )

    assert (
        result.summary_evidence[0].segment_ids
        == []
    )

    assert (
        result.summary_evidence[0].score
        == 0.0
    )

    assert (
        result.analysis.summary.key_points[0].segment_ids
        == []
    )


@patch(
    "ai.services.analysis_pipeline.summarize_consultation"
)
def test_pipeline_existing_evidence_is_preserved(
    mock_summary,
):
    transcript = make_transcript()

    mock_summary.return_value = AIAnalysisOutput(
        schema_version="1.0",
        summary=Summary(
            overview="아동은 수학 숙제로 힘들다고 말했다.",
            key_points=[
                KeyPointItem(
                    point="수학 숙제가 많아서 힘들다고 말했다.",
                    segment_ids=["seg_002"],
                )
            ],
        ),
        risk_utterances=[],
        abuse_signals=[],
        risk_factors=[],
        warnings=[],
    )

    result = run_analysis_pipeline(
        transcript
    )

    assert result.summary_evidence[0].segment_ids == [
        "seg_002"
    ]

    assert result.summary_evidence[0].score == 1.0

    assert (
        result.analysis.summary.key_points[0].segment_ids
        == ["seg_002"]
    )


@patch(
    "ai.services.analysis_pipeline.summarize_consultation"
)
def test_pipeline_empty_summary(
    mock_summary,
):
    transcript = make_transcript()

    mock_summary.return_value = AIAnalysisOutput(
        schema_version="1.0",
        summary=Summary(
            overview="",
            key_points=[],
        ),
        risk_utterances=[],
        abuse_signals=[],
        risk_factors=[],
        warnings=[
            "추가 확인 필요"
        ],
    )

    result = run_analysis_pipeline(
        transcript
    )

    assert result.summary_evidence == []

    assert "추가 확인 필요" in (
        result.analysis.warnings
    )