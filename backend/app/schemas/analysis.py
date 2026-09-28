# AI 분석 결과 Schema.
#
# result 는 AI 담당의 Structured JSON Contract 를 그대로 전달한다.
# Backend 는 내용을 재해석하거나 판단 필드를 추가하지 않는다.

import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import AnalysisStatus, SessionStatus
from app.schemas.common import SessionErrorInfo
from app.schemas.contracts import AIAnalysisResult, SummaryEvidenceItem


class AnalysisResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    session_id: uuid.UUID
    transcript_id: Optional[uuid.UUID]
    transcript_version: Optional[int]
    status: AnalysisStatus
    schema_version: str
    provider: Optional[str]
    model: Optional[str]
    created_at: datetime
    completed_at: Optional[datetime]

    result: Optional[AIAnalysisResult] = None
    summary_evidence: List[SummaryEvidenceItem] = Field(default_factory=list)
    error: Optional[SessionErrorInfo] = None


class AnalysisEnvelope(BaseModel):
    """Polling 대응 응답."""

    session_id: uuid.UUID
    session_status: SessionStatus
    analysis: Optional[AnalysisResponse] = None
    error: Optional[SessionErrorInfo] = None


class AnalysisRequestResponse(BaseModel):
    session_id: uuid.UUID
    session_status: SessionStatus
    analysis_id: uuid.UUID
    message: str
