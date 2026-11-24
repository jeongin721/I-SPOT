# 아이 앱(콩콩) API 요청 · 응답(API_CONTRACT 24절).
#
# Child* 응답은 아이 기기로 간다. 이름 · 사례번호 · 위험 판정을 넣지 않는다.

import uuid
from datetime import datetime
from typing import Annotated, Any, Dict, List, Literal, Optional

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


class ChildStaffHours(BaseModel):
    """상담사가 바로 볼 수 있는 시간인지. 밖이면 앱이 112 · 1388 을 먼저 안내한다."""

    on_duty: bool
    label: str


class ChildHomeResponse(BaseModel):
    pending: Optional[ChildPendingQuestions] = None
    next_consult: Optional[ChildNextConsult] = None
    # 다가오는 상담(가까운 순, 3개까지). 첫째가 next_consult 와 같다.
    upcoming_consults: List[ChildNextConsult] = Field(default_factory=list)
    alert: Optional[ChildAlertStatus] = None
    staff_hours: Optional[ChildStaffHours] = None


class ChildAnswerInput(RequestModel):
    model_config = ConfigDict(extra="forbid")

    question_id: str = Field(max_length=40)
    choice_index: Optional[int] = Field(default=None, ge=0)
    skipped: bool = False
    text: Optional[str] = Field(default=None, max_length=200)
    chip: Optional[str] = Field(default=None, max_length=40)


class ChildAnswersRequest(RequestModel):
    answers: List[ChildAnswerInput] = Field(max_length=10)


class ChildMoodRequest(RequestModel):
    """'지금 기분 기록하기'. mood 는 콩콩 표정 12개 중 하나."""

    model_config = ConfigDict(extra="forbid")

    mood: str = Field(min_length=1, max_length=20)
    why: Optional[str] = Field(default=None, max_length=60)


class ChildNoteRequest(RequestModel):
    """'선생님께 메시지'. 글이나 칩 중 하나는 있어야 한다."""

    model_config = ConfigDict(extra="forbid")

    text: Optional[str] = Field(default=None, max_length=200)
    chip: Optional[str] = Field(default=None, max_length=40)


class ChildScheduleRequest(RequestModel):
    """일정 탭 '참석이 어려워요'. 다음 상담 하나에 대해 이유를 알린다."""

    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=1, max_length=40)
    etc: Optional[str] = Field(default=None, max_length=60)


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
    # 담당 상담사가 CHILD_APP_ESCALATE_MINUTES 넘게 확인하지 않은 긴급 알림(B안). 다른 상담사에게도 보인다.
    escalated: bool = False
    # 담당이 아닌 상담사에게 넘어간 알림이면 true. 사례를 열 수 없으니 담당 상담사 · 관리자에게 알리게 한다.
    handed_over: bool = False
    # 넘어간 알림에서만 — 누구에게 연락할지.
    counselor_name: Optional[str] = None


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


SilentDays = Literal[5, 7, 10]
DEFAULT_SILENT_DAYS = 7


class ChildSilentDaysRequest(RequestModel):
    """아이 연계 응답 상태의 '기준' 일수."""

    days: SilentDays


class ChildAppCaseRow(BaseModel):
    case_id: uuid.UUID
    case_number: str
    child_alias: str
    child_birth_year: Optional[int] = None
    status: str
    # 최근 21일 답 묶음 수 · 가장 최근 답의 수준. 담당 상담사만(그 외 null).
    recent_answers: Optional[int] = None
    level: Optional[str] = None
    # 가장 최근 답 묶음을 상담사가 확인한 시각(바로 확인 · 살펴볼 답). 확인 전이면 null. 담당 상담사만.
    answer_acked_at: Optional[datetime] = None
    last_response_at: Optional[datetime] = None
    open_alert_at: Optional[datetime] = None
    open_alert_reason: Optional[str] = None
    open_alert_urgent: bool = False
    # 가장 최근 '확인이 필요한 알림 · 답'을 확인한 시각. 확인 전이거나 없으면 null.
    last_acked_at: Optional[datetime] = None
    # 관리자 · 아이 연계 앱 관리(11/17 디자인 AdminApp): 연결일 · 담당 상담사 · 장기 무응답 안부 연락.
    linked_at: Optional[datetime] = None
    counselor_name: Optional[str] = None
    # 마지막 응답(없으면 연결) 뒤에 남긴 가장 최근 안부 연락. 그 뒤 아이가 답하면 다시 null.
    welfare_status: Optional[Literal["OPEN", "TRIED", "DONE"]] = None
    # 응답 상태 '기준' 일수(연결 전이면 기본 7). 장기 무응답 판단에도 쓴다.
    silent_days: int = DEFAULT_SILENT_DAYS
    welfare_note: Optional[str] = None
    welfare_at: Optional[datetime] = None


class ChildWelfareCheckRequest(RequestModel):
    """장기 무응답 아이 안부 연락 처리. OPEN 은 '미처리로 되돌리기'."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["OPEN", "TRIED", "DONE"]
    note: Optional[str] = Field(default=None, max_length=200)


class ChildRecentAlert(BaseModel):
    """관리자 홈 '긴급 알림 현황'(11/17 디자인 AdminHome): 오늘 · 어제 긴급 알림과 그 전에 남은 확인 전 알림."""

    id: uuid.UUID
    case_id: uuid.UUID
    case_number: str
    child_alias: str
    reason: str
    repeat_count: int = 0
    created_at: datetime
    last_at: Optional[datetime] = None
    counselor_name: Optional[str] = None
    acknowledged_at: Optional[datetime] = None
    acknowledged_by_name: Optional[str] = None


class ChildScheduledQuestions(BaseModel):
    """발송 예약해 둔(아직 아이에게 보이지 않은) 질문 묶음. id 로 예약을 취소한다."""

    id: uuid.UUID
    count: int
    deliver_at: datetime


class ChildSessionQuestionItem(BaseModel):
    id: str
    category: str
    type: str
    text: str
    options: List[str] = Field(default_factory=list)
    # 상담사에게만 보인다(이번 회차의 어떤 내용과 이어지는지).
    reason: str = ""


class ChildSessionQuestions(BaseModel):
    """이번 회차 맞춤 질문(API_CONTRACT 24절). 가장 최근 분석 회차로 만든 AI 초안."""

    session_id: uuid.UUID
    session_label: str
    created_at: datetime
    items: List[ChildSessionQuestionItem]


class ChildAppCaseResponse(BaseModel):
    status: str
    code_expires_at: Optional[datetime] = None
    linked_at: Optional[datetime] = None
    last_response_at: Optional[datetime] = None
    # 응답 상태 '기준' 일수(5 · 7 · 10, 연결 전이면 기본 7).
    silent_days: int = DEFAULT_SILENT_DAYS
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
    session_questions: Optional[ChildSessionQuestions] = None
    session_questions_available: bool = False
