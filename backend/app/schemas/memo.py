# 상담사 메모(API_CONTRACT 25절, 2026-11-10).

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from app.models.counselor_memo import MEMO_TEXT_MAX_LENGTH
from app.schemas.common import RequestModel


def _strip_text(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None

    text = value.strip()

    if not text:
        raise ValueError("메모 내용을 적어 주세요.")

    return text


class MemoCreateRequest(RequestModel):
    text: str = Field(min_length=1, max_length=MEMO_TEXT_MAX_LENGTH)
    # 관련 사례. 빼거나 null 이면 사례 없는 메모. 볼 수 있는 사례만(없으면 404, 남의 사례면 403).
    case_id: Optional[uuid.UUID] = None

    _strip = field_validator("text")(_strip_text)


class MemoUpdateRequest(RequestModel):
    """보낸 칸만 바뀐다. case_id 를 null 로 보내면 사례를 뗀다."""

    text: Optional[str] = Field(default=None, min_length=1, max_length=MEMO_TEXT_MAX_LENGTH)
    case_id: Optional[uuid.UUID] = None

    @field_validator("text")
    @classmethod
    def _text(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            raise ValueError("메모 내용은 null 로 보낼 수 없습니다. 바꾸지 않으려면 빼고 보냅니다.")

        return _strip_text(value)


class MemoResponse(BaseModel):
    id: uuid.UUID
    case_id: Optional[uuid.UUID]
    # 관련 사례의 별칭(목록 표시용). 사례가 없으면 null. 실명은 싣지 않는다.
    child_alias: Optional[str]
    text: str
    created_at: datetime
    updated_at: datetime

