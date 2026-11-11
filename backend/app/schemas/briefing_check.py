# 상담 전 브리핑 '확인할 사항' 체크(API_CONTRACT 26절, 2026-11-11).

import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator

from app.models.briefing_check import BRIEFING_CHECK_TEXT_MAX_LENGTH
from app.schemas.common import RequestModel


class BriefingCheckToggleRequest(RequestModel):
    """문장 하나를 확인함으로 켜거나 끈다. 웹 · 폰이 동시에 눌러도 서로 덮어쓰지 않게 목록을 통째로 보내지 않는다."""

    text: str = Field(min_length=1, max_length=BRIEFING_CHECK_TEXT_MAX_LENGTH)
    checked: bool

    @field_validator("text")
    @classmethod
    def _strip(cls, value: str) -> str:
        text = value.strip()

        if not text:
            raise ValueError("확인 사항 문장이 비었습니다.")

        return text


class BriefingChecksResponse(BaseModel):
    session_id: uuid.UUID
    # 확인함으로 표시한 문장들(켠 순서).
    checked: List[str]
    updated_at: Optional[datetime]
    updated_by_id: Optional[uuid.UUID]
