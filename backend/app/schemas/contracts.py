# 팀 공통 Contract 의 Pydantic 표현.
#
# 이 파일의 필드는 docs/02_ARCHITECTURE.md §6 (STT Contract), §7 (AI Output Contract)
# 와 1:1 로 대응한다. Backend 단독으로 이 구조를 변경하지 않는다.
# 팀 B 의 ai/schemas/analysis.py 와 동일한 형태를 유지한다.

from typing import Any, Dict, List, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.core.enums import Speaker

SCHEMA_VERSION = "1.0"


# =========================================================
# STT Contract
# =========================================================

class STTSegment(BaseModel):
    """STT Contract 의 segment. 필드를 추가하거나 제거하지 않는다."""

    segment_id: str = Field(..., min_length=1, max_length=50)
    speaker: Speaker
    start_ms: int = Field(..., ge=0)
    end_ms: int = Field(..., ge=0)
    text: str
    confidence: float = Field(..., ge=0.0, le=1.0)

    @model_validator(mode="after")
    def _check_time_range(self) -> "STTSegment":
        if self.end_ms < self.start_ms:
            raise ValueError("end_ms 는 start_ms 보다 작을 수 없습니다.")

        return self


class STTResult(BaseModel):
    """STT Adapter 가 반환해야 하는 최상위 구조."""

    schema_version: Literal["1.0"] = SCHEMA_VERSION
    segments: List[STTSegment] = Field(default_factory=list)

    @field_validator("segments")
    @classmethod
    def _check_unique_segment_ids(cls, segments: List[STTSegment]) -> List[STTSegment]:
        seen = {segment.segment_id for segment in segments}

        if len(seen) != len(segments):
            raise ValueError("segment_id 가 중복되었습니다.")

        return segments


# =========================================================
# AI Output Contract
# =========================================================

class AISummaryBody(BaseModel):
    overview: str = ""
    key_points: List[str] = Field(default_factory=list)


class AIAnalysisResult(BaseModel):
    """
    AI 담당의 Structured JSON Contract.

    9월에는 위험 관련 필드가 빈 배열일 수 있다.
    Backend 는 내용을 판단하지 않고 그대로 저장/전달한다.
    """

    schema_version: Literal["1.0"] = SCHEMA_VERSION
    summary: AISummaryBody = Field(default_factory=AISummaryBody)
    risk_utterances: List[Dict[str, Any]] = Field(default_factory=list)
    abuse_signals: List[Dict[str, Any]] = Field(default_factory=list)
    risk_factors: List[Dict[str, Any]] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


class SummaryEvidenceItem(BaseModel):
    """
    AI 파이프라인 내부 결과인 근거 연결 정보.

    공통 Contract 에는 포함되지 않으므로 별도 필드로 전달한다.
    팀 B 의 EvidenceLink(text/segment_ids/score) 를 API 용으로 옮긴 구조다.
    """

    key_point: str = ""
    segment_ids: List[str] = Field(default_factory=list)
    score: float = 0.0
