# 상담 Session Schema.

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.enums import SessionStatus
from app.models.base import to_utc
from app.schemas.common import SessionErrorInfo


def _consulted_at_as_utc(value: Optional[datetime]) -> Optional[datetime]:
    """
    받은 상담 시각을 UTC 로 바꿔 저장한다(API_CONTRACT 1.5).

    SQLite 는 오프셋을 버리고 글자만 저장하고, PostgreSQL 은 표시 없는 값을 연결 시간대로
    읽는다. 둘 다 `+09:00` · 표시 없는 값에서 DB 마다 다른 순간이 저장되므로 DB 에 닿기 전에
    맞춘다. 표시 없는 값은 UTC 로 본다.
    """

    return to_utc(value)


class SessionCreateRequest(BaseModel):
    title: Optional[str] = Field(default=None, max_length=200)
    consulted_at: Optional[datetime] = None
    location: Optional[str] = Field(default=None, max_length=200)
    memo: Optional[str] = Field(default=None, max_length=4000)

    _normalize_consulted_at = field_validator("consulted_at")(_consulted_at_as_utc)


class SessionUpdateRequest(BaseModel):
    title: Optional[str] = Field(default=None, max_length=200)
    consulted_at: Optional[datetime] = None
    location: Optional[str] = Field(default=None, max_length=200)
    memo: Optional[str] = Field(default=None, max_length=4000)

    _normalize_consulted_at = field_validator("consulted_at")(_consulted_at_as_utc)


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
