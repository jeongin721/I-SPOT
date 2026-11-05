# 종결 검토 요약 · 보고서 Schema(API_CONTRACT 4절 closure-summary, 2026-10-30).

import uuid
from datetime import date, datetime
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, field_validator

from app.models.closure_review import CLOSURE_TEXT_MAX_LENGTH
from app.schemas.common import IsoDate, RequestModel


class ClosureItem(BaseModel):
    key: str
    text: str
    sessions: List[int]


class ClosureGroup(BaseModel):
    title: str
    items: List[ClosureItem]


class ClosureDraft(BaseModel):
    text: str
    sessions: List[int]


class ClosureSafetySuggestion(BaseModel):
    index: int
    level: Literal["HIGH", "MEDIUM", "LOW"]
    basis: str
    sessions: List[int]


class ClosureSuggestions(BaseModel):
    """종결보고서 안전평가 11문항 · Key Person 의 AI 제안(2026-11-04). 화면은 칩 · 근거로만 보이고 칸은 상담원이 고른다."""

    safety: List[ClosureSafetySuggestion] = []
    key_person: Optional[ClosureDraft] = None


class ClosureSummary(BaseModel):
    # AI: 종결 요약 AI 초안 · APPROVED_SUMMARIES: LLM 없이 승인 요약 4칸을 묶은 것(AI 생성 아님).
    source: Literal["AI", "APPROVED_SUMMARIES"]
    model: Optional[str] = None
    generated_at: datetime
    sessions: List[int]
    groups: List[ClosureGroup]
    report: Dict[str, Optional[ClosureDraft]]
    suggestions: Optional[ClosureSuggestions] = None


# 종결보고서(서식 29) 상담원 판단 칸(2026-11-03): 종결사유 5개 · 안전평가 11문항 · Key Person · 안전점수 3줄.
CLOSURE_REASON_COUNT = 5
CLOSURE_SAFETY_ITEM_COUNT = 11
CLOSURE_SAFETY_SCORE_COUNT = 3
CLOSURE_SHORT_TEXT_MAX_LENGTH = 300

SafetyLevel = Literal["HIGH", "MEDIUM", "LOW"]


class ClosureSafetyScore(BaseModel):
    score: Optional[int] = None
    reason: str = ""


class ClosureReport(BaseModel):
    initial_situation: Optional[str] = None
    closing_situation: Optional[str] = None
    opinion: Optional[str] = None
    review_date: Optional[date] = None
    closing_date: Optional[date] = None
    reasons: Optional[List[bool]] = None
    safety: Optional[List[Optional[SafetyLevel]]] = None
    key_person: Optional[str] = None
    safety_scores: Optional[List[ClosureSafetyScore]] = None
    # 사례관리 제공 요약 · 제공된 서비스 내용 및 총량(11/04). 화면이 회차 기록(상담 유형별 수)으로 먼저 채우고 상담원이 고친다.
    services: Optional[str] = None


class ClosureSafetyScoreIn(RequestModel):
    # 모르는 칸('reson' 오타 등)은 422, 점수는 숫자만(true · "3" 을 바꿔 받지 않음, 민규 #140 교차검증 L2 · L4).
    model_config = ConfigDict(extra="forbid")

    score: Optional[StrictInt] = Field(default=None, ge=1, le=10)
    reason: str = Field(default="", max_length=CLOSURE_SHORT_TEXT_MAX_LENGTH)


class ClosureReportIn(RequestModel):
    """저장 요청의 보고서 칸(요청 본문은 RequestModel — 저장할 수 없는 글자 등을 거른다). 보낸 칸만 바뀐다.

    목록은 문항 수 그대로 보낸다. 서버는 칸을 채우지 않는다 — 화면이 보인 처음 값은 report_defaults(빈 칸에만)로 온다.
    """

    initial_situation: Optional[str] = None
    closing_situation: Optional[str] = None
    opinion: Optional[str] = None
    review_date: Optional[IsoDate] = None
    closing_date: Optional[IsoDate] = None
    model_config = ConfigDict(extra="forbid")

    reasons: Optional[List[StrictBool]] = Field(
        default=None, min_length=CLOSURE_REASON_COUNT, max_length=CLOSURE_REASON_COUNT
    )
    safety: Optional[List[Optional[SafetyLevel]]] = Field(
        default=None, min_length=CLOSURE_SAFETY_ITEM_COUNT, max_length=CLOSURE_SAFETY_ITEM_COUNT
    )
    key_person: Optional[str] = Field(default=None, max_length=CLOSURE_SHORT_TEXT_MAX_LENGTH)
    services: Optional[str] = Field(default=None, max_length=CLOSURE_SHORT_TEXT_MAX_LENGTH)
    safety_scores: Optional[List[ClosureSafetyScoreIn]] = Field(
        default=None, min_length=CLOSURE_SAFETY_SCORE_COUNT, max_length=CLOSURE_SAFETY_SCORE_COUNT
    )


class ClosureSummaryResponse(BaseModel):
    """만들기 전이면 summary null, checks · edits {}, report 빈 칸."""

    case_id: uuid.UUID
    summary: Optional[ClosureSummary]
    checks: Dict[str, bool]
    edits: Dict[str, str]
    report: ClosureReport
    updated_at: Optional[datetime]


class ClosureSummarySaveRequest(RequestModel):
    """보낸 칸만 바꾼다. checks · edits 는 지금 요약의 문장 key 만 받는다(없는 key 는 422). edits 의 빈 글은 고침 취소."""

    checks: Optional[Dict[str, bool]] = Field(default=None, max_length=100)
    edits: Optional[Dict[str, str]] = Field(default=None, max_length=100)
    report: Optional[ClosureReportIn] = None
    # 화면이 고치지 않고 보여 주기만 한 처음 값(AI 초안 · 회차 기록 · 1차 판단, 2026-11-05). 저장된 값이 아직 없는(null) 칸에만 쓴다 —
    # 다른 창이 먼저 저장한 칸을 이 창의 처음 값으로 되돌리지 않게(민규 #140 교차검증). report 에도 있는 칸은 report 가 이긴다.
    report_defaults: Optional[ClosureReportIn] = None

    @field_validator("edits")
    @classmethod
    def _limit_edits(cls, value: Optional[Dict[str, str]]) -> Optional[Dict[str, str]]:
        if value is not None and any(len(text) > CLOSURE_TEXT_MAX_LENGTH for text in value.values()):
            raise ValueError(f"문장은 {CLOSURE_TEXT_MAX_LENGTH}자까지 쓸 수 있습니다.")
        return value

    @field_validator("report", "report_defaults")
    @classmethod
    def _limit_report(cls, value: Optional[ClosureReportIn]) -> Optional[ClosureReportIn]:
        if value is not None:
            for text in (value.initial_situation, value.closing_situation, value.opinion):
                if text is not None and len(text) > CLOSURE_TEXT_MAX_LENGTH:
                    raise ValueError(f"보고서 칸은 {CLOSURE_TEXT_MAX_LENGTH}자까지 쓸 수 있습니다.")
        return value
