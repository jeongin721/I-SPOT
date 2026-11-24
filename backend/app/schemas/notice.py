# 사내 공지사항(API_CONTRACT 28절, 2026-11-20).

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from app.models.notice import NOTICE_BODY_MAX_LENGTH, NOTICE_TEAM_MAX_LENGTH, NOTICE_TITLE_MAX_LENGTH
from app.schemas.common import RequestModel


def _required(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None

    text = value.strip()

    if not text:
        raise ValueError("빈 글은 보낼 수 없습니다.")

    return text


def _optional(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None

    return value.strip() or None


class NoticeCreateRequest(RequestModel):
    title: str = Field(min_length=1, max_length=NOTICE_TITLE_MAX_LENGTH)
    body: str = Field(min_length=1, max_length=NOTICE_BODY_MAX_LENGTH)
    important: bool = False
    # 공지를 낸 부서. 빼면 쓴 사람 이름을 보인다.
    team: Optional[str] = Field(default=None, max_length=NOTICE_TEAM_MAX_LENGTH)

    _text = field_validator("title", "body")(_required)
    _team = field_validator("team")(_optional)


class NoticeUpdateRequest(RequestModel):
    """보낸 칸만 바뀐다. team 을 null 로 보내면 부서를 지운다."""

    title: Optional[str] = Field(default=None, min_length=1, max_length=NOTICE_TITLE_MAX_LENGTH)
    body: Optional[str] = Field(default=None, min_length=1, max_length=NOTICE_BODY_MAX_LENGTH)
    important: Optional[bool] = None
    team: Optional[str] = Field(default=None, max_length=NOTICE_TEAM_MAX_LENGTH)

    @field_validator("title", "body", "important")
    @classmethod
    def _not_null(cls, value):
        if value is None:
            raise ValueError("null 로 보낼 수 없습니다. 바꾸지 않으려면 빼고 보냅니다.")

        return _required(value) if isinstance(value, str) else value

    _team = field_validator("team")(_optional)


class NoticeResponse(BaseModel):
    id: uuid.UUID
    title: str
    body: str
    important: bool
    team: Optional[str]
    author_name: Optional[str]
    created_at: datetime
    updated_at: datetime
