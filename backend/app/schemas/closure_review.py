# 종결 검토 요약 · 보고서 Schema(API_CONTRACT 4절 closure-summary, 2026-10-30).

import uuid
from datetime import date, datetime
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator

from app.models.closure_review import CLOSURE_TEXT_MAX_LENGTH
from app.schemas.common import RequestModel


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


class ClosureReport(BaseModel):
    initial_situation: Optional[str] = None
    closing_situation: Optional[str] = None
    opinion: Optional[str] = None
    review_date: Optional[date] = None
    closing_date: Optional[date] = None


class ClosureReportIn(RequestModel):
    """저장 요청의 보고서 칸(요청 본문은 RequestModel — 저장할 수 없는 글자 등을 거른다). 보낸 칸만 바뀐다."""

    initial_situation: Optional[str] = None
    closing_situation: Optional[str] = None
    opinion: Optional[str] = None
    review_date: Optional[date] = None
    closing_date: Optional[date] = None


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
