# 상담 Session Schema.

import uuid
from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.enums import SessionStatus
from app.models.base import to_utc
from app.schemas.common import SessionErrorInfo


# 상담 시각으로 받는 범위(UTC 기준, 아래 끝은 포함하지 않음). API_CONTRACT 1.5.
# 범위를 두지 않으면 9999-12-31T23:00:00 같은 값이 저장된 뒤 PostgreSQL(Asia/Seoul)이 읽을 때
# 10000년이 되어 psycopg 가 실패하고, 그 사례의 목록 · 상세가 계속 500 이 된다.
_CONSULTED_AT_MIN = datetime(1900, 1, 1, tzinfo=timezone.utc)
_CONSULTED_AT_MAX_EXCLUSIVE = datetime(2101, 1, 1, tzinfo=timezone.utc)


def _consulted_at_as_utc(value: Optional[datetime]) -> Optional[datetime]:
    """
    받은 상담 시각을 UTC 로 바꿔 저장한다(API_CONTRACT 1.5).

    SQLite 는 오프셋을 버리고 글자만 저장하고, PostgreSQL 은 표시 없는 값을 연결 시간대로
    읽는다. 둘 다 `+09:00` · 표시 없는 값에서 DB 마다 다른 순간이 저장되므로 DB 에 닿기 전에
    맞춘다. 표시 없는 값은 UTC 로 본다.

    UTC 로 바꾼 값이 1900-01-01 ~ 2100-12-31 밖이면 저장하기 전에 거절한다(422).
    to_utc 는 날짜 범위를 넘는 값을 가장 이른 · 늦은 시각으로 자르는데(비교용), 그 값도
    이 범위 밖이라 여기서 거절된다.
    """

    converted = to_utc(value)

    if converted is not None and not (
        _CONSULTED_AT_MIN <= converted < _CONSULTED_AT_MAX_EXCLUSIVE
    ):
        raise ValueError(
            "상담 시각은 UTC 기준 1900-01-01 부터 2100-12-31 까지만 쓸 수 있습니다."
        )

    return converted


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
