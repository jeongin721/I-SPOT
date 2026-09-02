# I-SPOT의 AI 분석 과정을 하나로 연결하는 파이프라인 서비스.
# 상담 요약 결과를 생성하고 각 핵심 내용에 Transcript 근거 segment를 연결한다.

from typing import List

from pydantic import BaseModel

from ai.schemas.analysis import (
    AIAnalysisOutput,
    KeyPointItem,
    Transcript,
)
from ai.services.evidence_linker import (
    EvidenceLink,
    link_summary_evidence,
)
from ai.services.summary_service import (
    summarize_consultation,
)


class AnalysisPipelineResult(BaseModel):
    """
    AI 내부 파이프라인 결과.

    공통 AIAnalysisOutput Contract는 변경하지 않고,
    summary evidence를 내부 결과로 함께 관리한다.
    """

    analysis: AIAnalysisOutput
    summary_evidence: List[EvidenceLink]


def run_analysis_pipeline(
    transcript: Transcript,
) -> AnalysisPipelineResult:
    """
    I-SPOT 1차 AI 분석 파이프라인.

    Transcript
        ↓
    LLM Summary
        ↓
    Grounding Validation
        ↓
    Evidence Linking
        ↓
    Pipeline Result
    """

    # 1. 상담 요약 생성
    analysis = summarize_consultation(
        transcript
    )

    # 2. 각 key_point의 근거 segment 연결
    summary_evidence = link_summary_evidence(
        key_points=analysis.summary.key_points,
        transcript=transcript,
    )

    # 3. Evidence Linker가 검증/보완한 segment_ids를
    #    실제 Summary key_points에도 반영
    analysis.summary.key_points = [
        KeyPointItem(
            point=evidence.text,
            segment_ids=evidence.segment_ids,
        )
        for evidence in summary_evidence
    ]

    return AnalysisPipelineResult(
        analysis=analysis,
        summary_evidence=summary_evidence,
    )