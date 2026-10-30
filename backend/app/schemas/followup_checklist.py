# 다음 상담 체크리스트 Schema(19절, specs followup-rag-checklist).
#
# result 칸은 rag 결과를 그대로 두지 않고 여기 모양으로 정리해 저장한다(adapters/followup_checklist_adapter.normalize_rag_output).
# 공식 근거(type 이 case 가 아닌 basis)는 rag 의 검토(연결 → 코드 검사 → 검토)를 통과한 것만 들어온다.

import uuid
from datetime import datetime
from typing import Dict, List, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import AnalysisStatus
from app.schemas.common import SessionErrorInfo

SCHEMA_VERSION = "1.0"

CheckKind = Literal["info_gap", "plan_followup", "change", "inconsistency", "checklist_gap"]
CheckPriority = Literal["high", "medium"]


class ChecklistBasis(BaseModel):
    """근거 하나. type=case 는 사례 기록(이번 · 앞 회차 발화 · 요약), 그 밖은 공식 근거(manual · checklist · law · precedent 등).

    case 는 segment_id 가 있으면 그 발화(STT 검수), session_id 만 있으면 그 회차로 연다.
    공식 근거는 url(법령 · 판례)이 있으면 새 창으로 열고, 없으면 excerpt(rag 가 LLM 에 준 발췌)를 펼쳐 보인다.
    why 는 질문에 붙인 공식 근거의 연결 이유(검토 통과)다.
    """

    model_config = ConfigDict(extra="ignore")

    type: str = Field(min_length=1, max_length=30)
    ref: Optional[str] = Field(default=None, max_length=40)
    label: Optional[str] = Field(default=None, max_length=300)
    session_no: Optional[int] = None
    session_id: Optional[str] = Field(default=None, max_length=64)
    segment_id: Optional[str] = Field(default=None, max_length=64)
    start_ms: Optional[int] = None
    source: Optional[str] = Field(default=None, max_length=300)
    page: Optional[Union[int, str]] = None
    url: Optional[str] = Field(default=None, max_length=1000)
    # 사례 근거의 excerpt 는 그 기록 원문(앞 회차 요약은 길 수 있다)이라 길이를 막지 않는다.
    excerpt: Optional[str] = None
    why: Optional[str] = Field(default=None, max_length=500)

    @property
    def is_case(self) -> bool:
        return self.type == "case"


class ChecklistItem(BaseModel):
    """다음 상담 전 확인할 사항 하나(rag check_item). 화면에서 AI 확인 메모와 한 목록으로 합쳐 보인다."""

    id: str = Field(min_length=1, max_length=40)
    text: str = Field(min_length=1, max_length=300)
    kind: CheckKind
    priority: CheckPriority
    reason: str = Field(default="", max_length=500)
    basis: List[ChecklistBasis] = Field(min_length=1)


class QuestionEvidence(BaseModel):
    """추가 질문 AI 초안(분석 result.followup_questions[draft_index])에 붙인 공식 근거.

    text 는 만들 때의 초안 문장 그대로다. 화면은 지금 초안 문장이 이것과 똑같을 때만 공식 근거를 보인다.
    """

    draft_index: int = Field(ge=0)
    text: str = Field(min_length=1)
    basis: List[ChecklistBasis] = Field(min_length=1)


class ChecklistResult(BaseModel):
    schema_version: str = SCHEMA_VERSION
    check_items: List[ChecklistItem] = Field(default_factory=list)
    question_evidence: List[QuestionEvidence] = Field(default_factory=list)
    notice: Optional[str] = None
    # 뺀 수(문장은 싣지 않는다): no_basis · judgment · invalid · official_unlinked · official_review_rejected
    dropped: Dict[str, int] = Field(default_factory=dict)


class FollowupChecklistOut(BaseModel):
    status: AnalysisStatus
    attempt: int
    analysis_id: Optional[uuid.UUID]
    transcript_version: Optional[int]
    provider: Optional[str]
    result: Optional[ChecklistResult]
    error: Optional[SessionErrorInfo]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]


class FollowupChecklistEnvelope(BaseModel):
    """enabled=false 면 서버에서 꺼져 있다(만들기 단추를 보이지 않는다). checklist 는 만든 적이 없으면 null."""

    enabled: bool
    checklist: Optional[FollowupChecklistOut]
