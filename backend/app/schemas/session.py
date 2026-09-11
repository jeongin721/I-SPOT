# 상담 Session Schema.

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import SessionStatus
from app.schemas.common import SessionErrorInfo


class SessionCreateRequest(BaseModel):
    title: Optional[str] = Field(default=None, max_length=200)
    consulted_at: Optional[datetime] = None
    location: Optional[str] = Field(default=None, max_length=200)
    memo: Optional[str] = Field(default=None, max_length=4000)


class SessionUpdateRequest(BaseModel):
    title: Optional[str] = Field(default=None, max_length=200)
    consulted_at: Optional[datetime] = None
    location: Optional[str] = Field(default=None, max_length=200)
    memo: Optional[str] = Field(default=None, max_length=4000)


class SessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    case_id: uuid.UUID
    session_number: int
    title: Optional[str]
    status: SessionStatus
    counselor_id: uuid.UUID
    consulted_at: Optional[datetime]
    location: Optional[str]
    memo: Optional[str]
    created_at: datetime
    updated_at: datetime

    stt_started_at: Optional[datetime] = None
    stt_completed_at: Optional[datetime] = None
    ai_started_at: Optional[datetime] = None
    ai_completed_at: Optional[datetime] = None
    approved_at: Optional[datetime] = None


class SessionDetailResponse(SessionResponse):
    """
    새로고침 후 상태 복원을 위해 진행 상황 요약을 함께 반환한다.
    (04_FRONTEND_PROMPT.md §9)
    """

    has_audio: bool = False
    has_transcript: bool = False
    transcript_version: Optional[int] = None
    transcript_confirmed: bool = False
    has_analysis: bool = False
    has_summary: bool = False
    summary_approved: bool = False
    error: Optional[SessionErrorInfo] = None
