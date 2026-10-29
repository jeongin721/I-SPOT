# 승인한 추가 질문 Schema(18절).

import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from app.core.enums import FollowupQuestionKind, FollowupQuestionSource
from app.models.followup_question import (
    FOLLOWUP_QUESTION_SEGMENTS_MAX,
    FOLLOWUP_QUESTION_TEXT_MAX_LENGTH,
    FOLLOWUP_QUESTIONS_MAX,
)
from app.schemas.common import RequestModel

# 질문 은행 코드 길이 상한(예: QB-N-01). 은행이 생기면 형식을 다시 정한다.
BANK_CODE_MAX_LENGTH = 40
# 중복을 빼기 전 근거 번호 목록의 넉넉한 상한. 큰 목록이 validator 까지 오지 않게 막는다(민규 #112 R3).
SEGMENT_IDS_RAW_MAX = 1000


class FollowupQuestionIn(RequestModel):
    """
    승인한 질문 하나. approved_at 은 서버가 찍으므로 받지 않는다(보내도 무시).

    text 는 앞뒤 공백을 뺀 뒤 1~300자. bank_code 는 kind=BANK 일 때만 둔다.
    segment_ids 는 그 회차 최신 전사본에 있는 번호만 받는다(서비스에서 확인, 없으면 400).
    """

    # 길이 상한은 앞뒤 공백을 뺀 뒤 validator 에서 잰다(Field(max_length) 는 strip 전에 돌아 302자 공백 포함 질문을 막는다).
    text: str
    kind: FollowupQuestionKind
    source: FollowupQuestionSource
    # 개수 상한(20)은 중복 · 빈 번호를 뺀 뒤 validator 에서 잰다. 빼기 전 목록은 1000개까지만 받는다.
    segment_ids: List[str] = Field(default_factory=list, max_length=SEGMENT_IDS_RAW_MAX)
    bank_code: Optional[str] = Field(default=None, max_length=BANK_CODE_MAX_LENGTH)

    @field_validator("text")
    @classmethod
    def _strip_text(cls, value: str) -> str:
        value = value.strip()

        if not value:
            raise ValueError("질문 문장이 비어 있습니다.")

        if len(value) > FOLLOWUP_QUESTION_TEXT_MAX_LENGTH:
            raise ValueError(f"질문 문장은 {FOLLOWUP_QUESTION_TEXT_MAX_LENGTH}자까지 쓸 수 있습니다.")

        return value

    @field_validator("segment_ids")
    @classmethod
    def _dedupe_segment_ids(cls, value: List[str]) -> List[str]:
        # 순서를 지키며 같은 번호와 빈 번호를 뺀다. 확인은 set 으로 하고(목록 검사는 제곱 시간 — 민규 #112 R3),
        # 서로 다른 번호가 상한을 넘는 순간 바로 멈춘다.
        seen = set()
        ordered: List[str] = []

        for segment_id in value:
            segment_id = segment_id.strip()

            if not segment_id or segment_id in seen:
                continue

            if len(ordered) >= FOLLOWUP_QUESTION_SEGMENTS_MAX:
                raise ValueError(f"근거 발화 번호는 {FOLLOWUP_QUESTION_SEGMENTS_MAX}개까지 둘 수 있습니다.")

            seen.add(segment_id)
            ordered.append(segment_id)

        return ordered

    @field_validator("bank_code")
    @classmethod
    def _blank_bank_code_to_none(cls, value: Optional[str]) -> Optional[str]:
        if value is None or not value.strip():
            return None

        return value.strip()

    @model_validator(mode="after")
    def _bank_code_only_for_bank(self) -> "FollowupQuestionIn":
        if self.kind == FollowupQuestionKind.BANK and self.bank_code is None:
            raise ValueError("질문 은행 질문(BANK)에는 bank_code 가 필요합니다.")

        if self.kind != FollowupQuestionKind.BANK and self.bank_code is not None:
            raise ValueError("bank_code 는 질문 은행 질문(BANK)에만 둡니다.")

        return self


class FollowupQuestionsSaveRequest(RequestModel):
    """승인한 질문 목록 전체. 보낸 목록으로 통째 바꾼다(빈 목록은 모두 지움)."""

    questions: List[FollowupQuestionIn] = Field(max_length=FOLLOWUP_QUESTIONS_MAX)


class FollowupQuestionOut(BaseModel):
    text: str
    kind: FollowupQuestionKind
    source: FollowupQuestionSource
    segment_ids: List[str]
    bank_code: Optional[str]
    approved_at: datetime


class FollowupQuestionsResponse(BaseModel):
    """저장한 적이 없으면 questions 는 빈 목록, updated_at · updated_by_id 는 null 이다."""

    session_id: uuid.UUID
    questions: List[FollowupQuestionOut]
    updated_at: Optional[datetime]
    updated_by_id: Optional[uuid.UUID]
