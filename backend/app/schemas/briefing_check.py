# 상담 전 브리핑 '확인할 사항' 체크(API_CONTRACT 26절, 2026-11-11).

import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator

from app.models.briefing_check import BRIEFING_CHECK_TEXT_MAX_LENGTH, BRIEFING_VISIBLE_MAX
from app.schemas.common import RequestModel


class BriefingCheckToggleRequest(RequestModel):
    """문장 하나를 확인함으로 켜거나 끈다. 웹 · 폰이 동시에 눌러도 서로 덮어쓰지 않게 목록을 통째로 보내지 않는다."""

    text: str = Field(min_length=1, max_length=BRIEFING_CHECK_TEXT_MAX_LENGTH)
    checked: bool
    # 지금 화면에 보이는 확인 사항 문장들(있으면). 서버는 여기 없는 옛 문장(목록을 고쳐 사라진 줄)의 체크를 지운다(민규 #176 1).
    visible: Optional[List[str]] = Field(default=None, max_length=BRIEFING_VISIBLE_MAX)

    @field_validator("text")
    @classmethod
    def _strip(cls, value: str) -> str:
        text = value.strip()

        if not text:
            raise ValueError("확인 사항 문장이 비었습니다.")

        return text

    @field_validator("visible")
    @classmethod
    def _strip_visible(cls, value: Optional[List[str]]) -> Optional[List[str]]:
        if value is None:
            return None

        # 너무 긴 문장은 어차피 체크될 수 없으니 버린다(422 로 막지 않는다 — 화면이 보낸 목록 하나 때문에 체크가 실패하지 않게).
        return [text.strip() for text in value if text.strip() and len(text.strip()) <= BRIEFING_CHECK_TEXT_MAX_LENGTH]


class BriefingChecksResponse(BaseModel):
    session_id: uuid.UUID
    # 확인함으로 표시한 문장들(켠 순서).
    checked: List[str]
    updated_at: Optional[datetime]
    updated_by_id: Optional[uuid.UUID]
