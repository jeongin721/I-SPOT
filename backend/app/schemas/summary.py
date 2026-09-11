# 상담사 검수용 Summary Schema.
#
# AI 원본은 AIAnalysis 에 보존되고, 여기서는 상담사가 수정하는 사본을 다룬다.

import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.core.enums import ReviewStatus, SessionStatus
from app.schemas.common import SessionErrorInfo
from app.schemas.contracts import SummaryEvidenceItem


class SummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    session_id: uuid.UUID
    analysis_id: Optional[uuid.UUID]
    overview: str
    key_points: List[str]
    counselor_note: Optional[str]
    status: ReviewStatus
    is_edited: bool
    approved_at: Optional[datetime]
    approved_by_id: Optional[uuid.UUID]
    created_at: datetime
    updated_at: datetime


class SummaryEnvelope(BaseModel):
    session_id: uuid.UUID
    session_status: SessionStatus
    summary: Optional[SummaryResponse] = None

    # AI 근거 발화(segment_id) 연결 정보. 검수 화면에서 근거 확인에 사용한다.
    summary_evidence: List[SummaryEvidenceItem] = Field(default_factory=list)
    error: Optional[SessionErrorInfo] = None


class SummaryUpdateRequest(BaseModel):
    overview: Optional[str] = Field(default=None, max_length=20000)
    key_points: Optional[List[str]] = None
    counselor_note: Optional[str] = Field(default=None, max_length=20000)

    @model_validator(mode="after")
    def _require_change(self) -> "SummaryUpdateRequest":
        if self.overview is None and self.key_points is None and self.counselor_note is None:
            raise ValueError("수정할 필드를 최소 1개 지정해야 합니다.")

        if self.key_points is not None and len(self.key_points) > 100:
            raise ValueError("key_points 는 최대 100개까지 저장할 수 있습니다.")

        return self
