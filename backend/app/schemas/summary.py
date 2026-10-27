# 상담사 검수용 Summary Schema.
#
# AI 원본은 AIAnalysis 에 보존되고, 여기서는 상담사가 수정하는 사본을 다룬다.

import uuid
from datetime import datetime
from typing import Any, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.enums import ReviewStatus, SessionStatus
from app.schemas.common import RequestModel, SessionErrorInfo
from app.schemas.contracts import SummaryAssessment, SummaryEvidenceItem


class SummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    session_id: uuid.UUID
    analysis_id: Optional[uuid.UUID]
    overview: str
    key_points: List[str]
    # 사정 관점 4칸. 2026-10-27 이전 요약(null)은 빈 칸으로 보인다.
    assessment: SummaryAssessment = Field(default_factory=SummaryAssessment)
    counselor_note: Optional[str]
    status: ReviewStatus
    is_edited: bool
    approved_at: Optional[datetime]
    approved_by_id: Optional[uuid.UUID]
    created_at: datetime
    updated_at: datetime


    @field_validator("assessment", mode="before")
    @classmethod
    def _empty_assessment(cls, value: Any) -> Any:
        return {} if value is None else value


class SummaryEnvelope(BaseModel):
    session_id: uuid.UUID
    session_status: SessionStatus
    summary: Optional[SummaryResponse] = None

    # AI 근거 발화(segment_id) 연결 정보. 검수 화면에서 근거 확인에 사용한다.
    summary_evidence: List[SummaryEvidenceItem] = Field(default_factory=list)
    error: Optional[SessionErrorInfo] = None


class SummaryAssessmentUpdate(RequestModel):
    """사정 관점 4칸 중 고칠 칸의 문장. 보낸 칸만 바꾸고 근거 번호(segment_ids)는 AI 초안 것을 둔다."""

    # 4칸 밖의 이름은 조용히 버리지 않고 422 로 알린다(오타로 저장이 안 된 줄 모르는 일이 없게).
    model_config = ConfigDict(extra="forbid")

    safety_changes: Optional[str] = Field(default=None, max_length=20000)
    strengths_resources: Optional[str] = Field(default=None, max_length=20000)
    safety_risks: Optional[str] = Field(default=None, max_length=20000)
    desired_changes: Optional[str] = Field(default=None, max_length=20000)

    @model_validator(mode="after")
    def _require_field(self) -> "SummaryAssessmentUpdate":
        # 빈 객체 · 네 칸 모두 null 은 고칠 것이 없는데도 바깥의 "최소 1개 필드" 검사를 통과해 200 으로 끝났다
        # (아무것도 안 바뀌는데 성공처럼 보임 — 민규 #86 리뷰, 2026-10-27). 칸이 하나도 없으면 422 로 알린다.
        if not self.model_dump(exclude_none=True):
            raise ValueError("assessment 에 고칠 칸을 최소 1개 지정해야 합니다.")

        return self


class SummaryUpdateRequest(RequestModel):
    overview: Optional[str] = Field(default=None, max_length=20000)
    key_points: Optional[List[str]] = None
    assessment: Optional[SummaryAssessmentUpdate] = None
    counselor_note: Optional[str] = Field(default=None, max_length=20000)

    @model_validator(mode="after")
    def _require_change(self) -> "SummaryUpdateRequest":
        if (
            self.overview is None
            and self.key_points is None
            and self.assessment is None
            and self.counselor_note is None
        ):
            raise ValueError("수정할 필드를 최소 1개 지정해야 합니다.")

        if self.key_points is not None and len(self.key_points) > 100:
            raise ValueError("key_points 는 최대 100개까지 저장할 수 있습니다.")

        return self
