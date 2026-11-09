# 아이 앱(콩콩) API 요청 · 응답(API_CONTRACT 22절).
#
# Child* 응답은 아이 기기로 간다. 이름 · 사례번호 · 위험 판정을 넣지 않는다.

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class ChildLinkRequest(BaseModel):
    code: str = Field(min_length=1, max_length=40)


class ChildLinkResponse(BaseModel):
    device_token: str


class ChildQuestion(BaseModel):
    id: str
    type: str
    text: str
    options: List[str] = Field(default_factory=list)
    faces: List[str] = Field(default_factory=list)
    chips: List[str] = Field(default_factory=list)
    note: Optional[str] = None


class ChildPendingQuestions(BaseModel):
    id: uuid.UUID
    questions: List[ChildQuestion]


class ChildNextConsult(BaseModel):
    date: str
    time: Optional[str] = None
    place: Optional[str] = None


class ChildHomeResponse(BaseModel):
    pending: Optional[ChildPendingQuestions] = None
    next_consult: Optional[ChildNextConsult] = None


class ChildAnswerInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question_id: str = Field(max_length=40)
    choice_index: Optional[int] = Field(default=None, ge=0)
    skipped: bool = False
    text: Optional[str] = Field(default=None, max_length=200)
    chip: Optional[str] = Field(default=None, max_length=40)


class ChildAnswersRequest(BaseModel):
    answers: List[ChildAnswerInput] = Field(max_length=10)


class ChildAnswersResponse(BaseModel):
    ticket_awarded: int


class ChildAppInviteResponse(BaseModel):
    code: str
    expires_at: datetime


class ChildQuestionSendRequest(BaseModel):
    question_ids: List[str] = Field(min_length=3, max_length=4)


class ChildAppBankItem(BaseModel):
    id: str
    category: str
    type: str
    text: str


class ChildAppEventResponse(BaseModel):
    id: uuid.UUID
    kind: str
    level: str
    payload: Dict[str, Any]
    created_at: datetime


class ChildAppCaseResponse(BaseModel):
    status: str
    code_expires_at: Optional[datetime] = None
    linked_at: Optional[datetime] = None
    last_response_at: Optional[datetime] = None
    has_pending_questions: bool
    can_read_feed: bool
    bank: List[ChildAppBankItem]
    feed: List[ChildAppEventResponse]
