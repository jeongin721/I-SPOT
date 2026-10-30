# 다음 상담 전 확인할 사항 Schema(18.1절, 2026-10-30). 추가 질문(followup_question.py)과 같은 꼴.

import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator

from app.core.enums import FollowupQuestionSource
from app.models.followup_check import (
    FOLLOWUP_CHECK_SEGMENTS_MAX,
    FOLLOWUP_CHECK_TEXT_MAX_LENGTH,
    FOLLOWUP_CHECKS_MAX,
)
from app.schemas.common import RequestModel
from app.schemas.followup_question import SEGMENT_IDS_RAW_MAX


class FollowupCheckIn(RequestModel):
    """
    확인 사항 하나. text 는 앞뒤 공백을 뺀 뒤 1~300자.

    source 는 AI(AI 확인 메모에서 옴 — 고쳐도 AI) · COUNSELOR(상담사가 직접 추가). edited 는 AI 메모를 상담사가 고쳤는가.
    in_briefing 은 상담 전 브리핑에 넣기. segment_ids 는 그 회차 최신 전사본에 있는 번호만 받는다(서비스에서 확인, 없으면 422).
    """

    text: str
    source: FollowupQuestionSource
    segment_ids: List[str] = Field(default_factory=list, max_length=SEGMENT_IDS_RAW_MAX)
    edited: bool = False
    in_briefing: bool = False

    @field_validator("text")
    @classmethod
    def _strip_text(cls, value: str) -> str:
        value = value.strip()

        if not value:
            raise ValueError("확인 사항 문장이 비어 있습니다.")

        if len(value) > FOLLOWUP_CHECK_TEXT_MAX_LENGTH:
            raise ValueError(f"확인 사항은 {FOLLOWUP_CHECK_TEXT_MAX_LENGTH}자까지 쓸 수 있습니다.")

        return value

    @field_validator("segment_ids")
    @classmethod
    def _dedupe_segment_ids(cls, value: List[str]) -> List[str]:
        seen = set()
        ordered: List[str] = []

        for segment_id in value:
            segment_id = segment_id.strip()

            if not segment_id or segment_id in seen:
                continue

            if len(ordered) >= FOLLOWUP_CHECK_SEGMENTS_MAX:
                raise ValueError(f"근거 발화 번호는 {FOLLOWUP_CHECK_SEGMENTS_MAX}개까지 둘 수 있습니다.")

            seen.add(segment_id)
            ordered.append(segment_id)

        return ordered


class FollowupChecksSaveRequest(RequestModel):
    """확인 사항 목록 전체. 보낸 목록으로 통째 바꾼다(빈 목록은 '확인 사항 없음' 으로 저장)."""

    items: List[FollowupCheckIn] = Field(max_length=FOLLOWUP_CHECKS_MAX)


class FollowupCheckOut(BaseModel):
    text: str
    source: FollowupQuestionSource
    segment_ids: List[str]
    edited: bool
    in_briefing: bool


class FollowupChecksResponse(BaseModel):
    """저장한 적이 없으면 saved=false · items 빈 목록 · updated_at · updated_by_id null(화면은 AI 확인 메모 초안을 보인다)."""

    session_id: uuid.UUID
    saved: bool
    items: List[FollowupCheckOut]
    updated_at: Optional[datetime]
    updated_by_id: Optional[uuid.UUID]
