# 종결 검토 요약 · 보고서 Schema(API_CONTRACT 4절 closure-summary, 2026-10-30).

import uuid
from datetime import date, datetime
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator

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


class ClosureSummary(BaseModel):
    # AI: 종결 요약 AI 초안 · APPROVED_SUMMARIES: LLM 없이 승인 요약 4칸을 묶은 것(AI 생성 아님).
    source: Literal["AI", "APPROVED_SUMMARIES"]
    model: Optional[str] = None
    generated_at: datetime
    sessions: List[int]
    groups: List[ClosureGroup]
    report: Dict[str, Optional[ClosureDraft]]


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


class ClosureSafetyScoreIn(RequestModel):
    score: Optional[int] = Field(default=None, ge=1, le=10)
    reason: str = Field(default="", max_length=CLOSURE_SHORT_TEXT_MAX_LENGTH)


class ClosureReportIn(RequestModel):
    """저장 요청의 보고서 칸(요청 본문은 RequestModel — 저장할 수 없는 글자 등을 거른다). 보낸 칸만 바뀐다.

    종결사유 · 안전평가 · 안전점수는 상담원이 고른 값만 담는다(AI 가 채우지 않는다). 목록은 문항 수 그대로 보낸다.
    """

    initial_situation: Optional[str] = None
    closing_situation: Optional[str] = None
    opinion: Optional[str] = None
    review_date: Optional[IsoDate] = None
    closing_date: Optional[IsoDate] = None
    reasons: Optional[List[bool]] = Field(default=None, min_length=CLOSURE_REASON_COUNT, max_length=CLOSURE_REASON_COUNT)
    safety: Optional[List[Optional[SafetyLevel]]] = Field(
        default=None, min_length=CLOSURE_SAFETY_ITEM_COUNT, max_length=CLOSURE_SAFETY_ITEM_COUNT
    )
    key_person: Optional[str] = Field(default=None, max_length=CLOSURE_SHORT_TEXT_MAX_LENGTH)
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

    @field_validator("edits")
    @classmethod
    def _limit_edits(cls, value: Optional[Dict[str, str]]) -> Optional[Dict[str, str]]:
        if value is not None and any(len(text) > CLOSURE_TEXT_MAX_LENGTH for text in value.values()):
            raise ValueError(f"문장은 {CLOSURE_TEXT_MAX_LENGTH}자까지 쓸 수 있습니다.")
        return value

    @field_validator("report")
    @classmethod
    def _limit_report(cls, value: Optional[ClosureReportIn]) -> Optional[ClosureReportIn]:
        if value is not None:
            for text in (value.initial_situation, value.closing_situation, value.opinion):
                if text is not None and len(text) > CLOSURE_TEXT_MAX_LENGTH:
                    raise ValueError(f"보고서 칸은 {CLOSURE_TEXT_MAX_LENGTH}자까지 쓸 수 있습니다.")
        return value
