# 아이 앱(콩콩) API 요청 · 응답(API_CONTRACT 24절).
#
# Child* 응답은 아이 기기로 간다. 이름 · 사례번호 · 위험 판정을 넣지 않는다.

import uuid
from datetime import datetime
from typing import Annotated, Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import ChildQuestionDeliver
from app.schemas.common import RequestModel


class ChildLinkRequest(RequestModel):
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


class ChildAlertStatus(BaseModel):
    # 아이가 급하다고 알린 시각, 선생님이 확인했는지, 확인 전으로 5분이 지났는지. 확인한 사람 · 시각은 넣지 않는다.
    sent_at: datetime
    acknowledged: bool
    overdue: bool


class ChildHomeResponse(BaseModel):
    pending: Optional[ChildPendingQuestions] = None
    next_consult: Optional[ChildNextConsult] = None
    alert: Optional[ChildAlertStatus] = None


class ChildAnswerInput(RequestModel):
    model_config = ConfigDict(extra="forbid")

    question_id: str = Field(max_length=40)
    choice_index: Optional[int] = Field(default=None, ge=0)
    skipped: bool = False
    text: Optional[str] = Field(default=None, max_length=200)
    chip: Optional[str] = Field(default=None, max_length=40)


class ChildAnswersRequest(RequestModel):
    answers: List[ChildAnswerInput] = Field(max_length=10)


class ChildAnswersResponse(BaseModel):
    ticket_awarded: int


class ChildAppInviteResponse(BaseModel):
    code: str
    expires_at: datetime


class ChildQuestionSendRequest(RequestModel):
    # 1개부터 문항 전체(8개)까지 고를 수 있다(11/10 경진님 — 처음엔 3~4개).
    question_ids: List[str] = Field(min_length=1, max_length=8)
    # NOW(기본)는 바로, EVENING 은 발송 예약(그날 CHILD_APP_DELIVER_HOUR 시부터 아이 앱에 보인다. 그 시가 지났으면 바로).
    deliver: ChildQuestionDeliver = ChildQuestionDeliver.NOW


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
    needs_ack: bool = False
    acknowledged_at: Optional[datetime] = None


class ChildAlertReceived(BaseModel):
    received: bool = True


class ChildOpenAlert(BaseModel):
    id: uuid.UUID
    case_id: uuid.UUID
    child_alias: str
    case_number: str
    reason: str
    urgent: bool = False
    can_ack: bool
    repeat_count: int = 0
    last_at: Optional[datetime] = None
    created_at: datetime


class ChildAiQuestion(BaseModel):
    id: str
    text: str
    options: List[str]
    edited: bool = False
    approved: bool = False
    answered: bool = False


class ChildAiDraftItem(BaseModel):
    question_id: str
    note: str
    note_edited: bool = False
    questions: List[ChildAiQuestion]


class ChildAiDraftResponse(BaseModel):
    id: uuid.UUID
    event_id: uuid.UUID
    items: List[ChildAiDraftItem]


class ChildAiNoteUpdateRequest(RequestModel):
    text: str = Field(min_length=1, max_length=500)


class ChildAiQuestionUpdateRequest(RequestModel):
    text: str = Field(min_length=1, max_length=200)
    options: List[Annotated[str, Field(min_length=1, max_length=40)]] = Field(min_length=2, max_length=6)


class ChildAiApprovalRequest(RequestModel):
    approved: bool


class ChildAppStats(BaseModel):
    sent: int
    answered: int
    linked_cases: int


class ChildAppCaseRow(BaseModel):
    case_id: uuid.UUID
    case_number: str
    child_alias: str
    child_birth_year: Optional[int] = None
    status: str
    # 최근 21일 답 묶음 수 · 가장 최근 답의 수준. 담당 상담사만(그 외 null).
    recent_answers: Optional[int] = None
    level: Optional[str] = None
    last_response_at: Optional[datetime] = None
    open_alert_at: Optional[datetime] = None
    open_alert_reason: Optional[str] = None
    open_alert_urgent: bool = False
    # 가장 최근 '확인이 필요한 알림 · 답'을 확인한 시각. 확인 전이거나 없으면 null.
    last_acked_at: Optional[datetime] = None


class ChildScheduledQuestions(BaseModel):
    """발송 예약해 둔(아직 아이에게 보이지 않은) 질문 묶음. id 로 예약을 취소한다."""

    id: uuid.UUID
    count: int
    deliver_at: datetime


class ChildAppCaseResponse(BaseModel):
    status: str
    code_expires_at: Optional[datetime] = None
    linked_at: Optional[datetime] = None
    last_response_at: Optional[datetime] = None
    next_consult: Optional[ChildNextConsult] = None
    has_pending_questions: bool
    # 담당 상담사만(그 외 null). 예약이 없으면 null.
    scheduled_questions: Optional[ChildScheduledQuestions] = None
    can_read_feed: bool
    open_alerts: List[ChildOpenAlert]
    last_acked_at: Optional[datetime] = None
    bank: List[ChildAppBankItem]
    feed: List[ChildAppEventResponse]
    ai_enabled: bool = False
    ai_draft: Optional[ChildAiDraftResponse] = None
