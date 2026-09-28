# I-SPOT의 AI 분석 과정을 하나로 연결하는 파이프라인 서비스.
# 상담 요약 결과를 생성하고 각 핵심 내용에 Transcript 근거 segment를 연결한다.

from typing import List

from pydantic import BaseModel

from ai.schemas.analysis import (
    AIAnalysisOutput,
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

    analysis = summarize_consultation(
        transcript
    )

    summary_evidence = link_summary_evidence(
        key_points=analysis.summary.key_points,
        transcript=transcript,
    )

    return AnalysisPipelineResult(
        analysis=analysis,
        summary_evidence=summary_evidence,
    )