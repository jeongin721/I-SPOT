# I-SPOT AI 파이프라인에서 공통으로 사용하는 Transcript 및 AI 분석 결과 Schema.
# TranscriptSegment, Summary, AIAnalysisOutput 등의 데이터 구조를 정의한다.

from typing import Any, Dict, List, Literal

from pydantic import BaseModel, Field


Speaker = Literal[
    "COUNSELOR",
    "CHILD",
    "GUARDIAN",
    "OTHER",
    "UNKNOWN",
]


class TranscriptSegment(BaseModel):
    segment_id: str = Field(..., min_length=1)
    speaker: Speaker
    start_ms: int = Field(..., ge=0)
    end_ms: int = Field(..., ge=0)
    text: str
    confidence: float = Field(..., ge=0.0, le=1.0)


class Transcript(BaseModel):
    schema_version: Literal["1.0"] = "1.0"
    segments: List[TranscriptSegment] = Field(default_factory=list)


class SummaryAssessmentField(BaseModel):
    """상담 요약 사정 관점 한 칸. text 는 AI 초안 문장, segment_ids 는 근거 발화 번호(비어 올 수 있다)."""

    text: str = ""
    segment_ids: List[str] = Field(default_factory=list)


class SummaryAssessment(BaseModel):
    """상담 요약 사정 관점 4칸(2026-10-27, 10/27 디자인 NoteWrite).

    safety_changes: (안전관련) 조사 후 변화된 사항
    strengths_resources: 아동안전과 관련된 강점과 자원
    safety_risks: 아동안전과 관련된 위험요인(최상위 risk_factors 와 다른 칸이다)
    desired_changes: 앞으로 원하는 변화 · 원하는 서비스/지원
    없으면 모두 빈 칸이다. 이 필드가 없던 때 저장한 결과도 그대로 읽힌다.
    """

    safety_changes: SummaryAssessmentField = Field(default_factory=SummaryAssessmentField)
    strengths_resources: SummaryAssessmentField = Field(default_factory=SummaryAssessmentField)
    safety_risks: SummaryAssessmentField = Field(default_factory=SummaryAssessmentField)
    desired_changes: SummaryAssessmentField = Field(default_factory=SummaryAssessmentField)


class Summary(BaseModel):
    overview: str = ""
    key_points: List[str] = Field(default_factory=list)
    assessment: SummaryAssessment = Field(default_factory=SummaryAssessment)


class AIAnalysisOutput(BaseModel):
    schema_version: Literal["1.0"] = "1.0"
    summary: Summary = Field(default_factory=Summary)
    risk_utterances: List[Dict[str, Any]] = Field(default_factory=list)
    abuse_signals: List[Dict[str, Any]] = Field(default_factory=list)
    risk_factors: List[Dict[str, Any]] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)