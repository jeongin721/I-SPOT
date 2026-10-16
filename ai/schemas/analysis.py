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


class Summary(BaseModel):
    overview: str = ""
    key_points: List[str] = Field(default_factory=list)


class AIAnalysisOutput(BaseModel):
    schema_version: Literal["1.0"] = "1.0"
    summary: Summary = Field(default_factory=Summary)
    risk_utterances: List[Dict[str, Any]] = Field(default_factory=list)
    abuse_signals: List[Dict[str, Any]] = Field(default_factory=list)
    risk_factors: List[Dict[str, Any]] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)