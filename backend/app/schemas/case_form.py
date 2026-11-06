# 기관 서식 Schema(API_CONTRACT 22절, 2026-11-02).
#
# 요청의 values 는 서식 종류마다 꼴이 다르다. 종류는 만들 때 보내고(고칠 때는 행의 종류), 서비스가 normalize_values 로
# 종류에 맞는 *Values 모델로 검사해 빈 칸을 채운 사전으로 바꿔 저장한다. 모든 칸은 비워 둘 수 있다(null · 빈 글) —
# 임시 저장은 쓰다 만 서식도 받는다.

import uuid
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional, Type

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.enums import CaseFormType, ReviewStatus
from app.schemas.common import RequestModel

# 서식 문항 수(디자인 · 매뉴얼 서식 그대로).
SAFETY_ITEM_COUNT = 11  # 사정기록지 안전영역: 피해아동 3 · 가족구성원 5 · 사례관리대상자 3
SAFETY_SCORE_COUNT = 3  # 안전점수: 피해아동 · 가족구성원 · 사례관리대상자 응답
CHECKLIST_ITEM_COUNT = 9  # 사례관리 점검표(서식 27)
RISK_SCALE_ITEM_COUNT = 43  # 위험수준별 개입 사정 척도(참고자료 3)
RISK_SCALE_RISK_LAST = 21  # 1~21 위험요인, 22~43 보호요인
FAMILY_SCALE_ITEM_COUNT = 15  # 축약형 가족관계 척도(참고자료 1)

FORM_TEXT_MAX_LENGTH = 5000  # 소견 · 추후 계획
FORM_SHORT_TEXT_MAX_LENGTH = 300  # 안전점수 이유
FORM_PLACE_MAX_LENGTH = 100  # 점검장소

Level = Literal["HIGH", "MEDIUM", "LOW"]
YesNo = Literal["YES", "NO"]


def _fixed(count: int, default: Any = None):
    """문항 수가 정해진 목록. 보내지 않으면 빈 칸(null)으로 채운다."""

    return Field(default_factory=lambda: [default] * count, min_length=count, max_length=count)


class _Values(RequestModel):
    # strict: true → 1 · "3" → 3 처럼 타입을 바꿔 받지 않는다(민규 #140 교차검증 L2).
    model_config = ConfigDict(extra="forbid", strict=True)


class SafetyScore(_Values):
    score: Optional[int] = Field(default=None, ge=1, le=10)
    reason: str = Field(default="", max_length=FORM_SHORT_TEXT_MAX_LENGTH)


class SafetyAssessmentValues(_Values):
    """사정기록지 안전영역(서식 6)."""

    items: List[Optional[Level]] = _fixed(SAFETY_ITEM_COUNT)
    key_person: Optional[Literal["YES", "NO"]] = None
    scores: List[SafetyScore] = Field(
        default_factory=lambda: [SafetyScore() for _ in range(SAFETY_SCORE_COUNT)],
        min_length=SAFETY_SCORE_COUNT,
        max_length=SAFETY_SCORE_COUNT,
    )
    opinion: str = Field(default="", max_length=FORM_TEXT_MAX_LENGTH)
    # 사정결과(상담원 판정): 집중관리 · 일반관리 · 모니터링관리 사례
    result: Optional[Literal["INTENSIVE", "GENERAL", "MONITORING"]] = None


class ManagementChecklistValues(_Values):
    """사례관리 점검표(서식 27)."""

    place: str = Field(default="", max_length=FORM_PLACE_MAX_LENGTH)
    checks: List[Optional[YesNo]] = _fixed(CHECKLIST_ITEM_COUNT)
    opinion: str = Field(default="", max_length=FORM_TEXT_MAX_LENGTH)
    plan: str = Field(default="", max_length=FORM_TEXT_MAX_LENGTH)


class RiskScaleValues(_Values):
    """위험수준별 개입 사정 척도(참고자료 3). 0~3점."""

    scores: List[Optional[int]] = _fixed(RISK_SCALE_ITEM_COUNT)

    @field_validator("scores")
    @classmethod
    def _range(cls, value: List[Optional[int]]) -> List[Optional[int]]:
        if any(score is not None and not 0 <= score <= 3 for score in value):
            raise ValueError("척도 점수는 0~3 이거나 null 입니다.")
        return value


class FamilyScaleValues(_Values):
    """축약형 가족관계 척도(참고자료 1). 1~5점."""

    respondent: Optional[Literal["FATHER", "MOTHER", "CHILD"]] = None
    answers: List[Optional[int]] = _fixed(FAMILY_SCALE_ITEM_COUNT)

    @field_validator("answers")
    @classmethod
    def _range(cls, value: List[Optional[int]]) -> List[Optional[int]]:
        if any(answer is not None and not 1 <= answer <= 5 for answer in value):
            raise ValueError("가족관계 척도 응답은 1~5 이거나 null 입니다.")
        return value


VALUES_MODELS: Dict[CaseFormType, Type[_Values]] = {
    CaseFormType.SAFETY_ASSESSMENT: SafetyAssessmentValues,
    CaseFormType.MANAGEMENT_CHECKLIST: ManagementChecklistValues,
    CaseFormType.RISK_SCALE: RiskScaleValues,
    CaseFormType.FAMILY_SCALE: FamilyScaleValues,
}


def normalize_values(form_type: CaseFormType, raw: Dict[str, Any]) -> Dict[str, Any]:
    """종류에 맞게 검사하고 빈 칸을 채운 사전. 맞지 않으면 ValidationError."""

    return VALUES_MODELS[form_type].model_validate(raw).model_dump(mode="json")


def form_totals(form_type: CaseFormType, values: Dict[str, Any]) -> Dict[str, Any]:
    """저장하지 않고 응답 때 계산하는 값(점수 합계 · 응답 수). 판정(군 · 사정결과)은 계산하지 않는다 — 상담원이 고른다."""

    if form_type == CaseFormType.RISK_SCALE:
        scores = values.get("scores") or []
        risk = [score for score in scores[:RISK_SCALE_RISK_LAST] if score is not None]
        protect = [score for score in scores[RISK_SCALE_RISK_LAST:] if score is not None]
        return {"risk_sum": sum(risk), "protect_sum": sum(protect), "filled": len(risk) + len(protect)}
    if form_type == CaseFormType.FAMILY_SCALE:
        answers = [answer for answer in values.get("answers") or [] if answer is not None]
        return {"sum": sum(answers), "answered": len(answers)}
    if form_type == CaseFormType.MANAGEMENT_CHECKLIST:
        return {"answered": sum(1 for check in values.get("checks") or [] if check is not None)}
    return {"answered": sum(1 for item in values.get("items") or [] if item is not None)}


class CaseFormCreateRequest(RequestModel):
    form_type: CaseFormType
    values: Dict[str, Any] = Field(default_factory=dict)


class CaseFormUpdateRequest(RequestModel):
    values: Dict[str, Any]
    # 화면이 본 판(응답의 version). 서버의 지금 판과 다르면 409 STALE_VERSION.
    version: int = Field(..., ge=1)


class CaseFormConfirmRequest(RequestModel):
    version: int = Field(..., ge=1)


class CaseFormResponse(BaseModel):
    id: uuid.UUID
    case_id: uuid.UUID
    form_type: CaseFormType
    round: int
    status: ReviewStatus
    version: int
    values: Dict[str, Any]
    totals: Dict[str, Any]
    created_by_id: Optional[uuid.UUID]
    updated_by_id: Optional[uuid.UUID]
    confirmed_by_id: Optional[uuid.UUID]
    confirmed_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime


class CaseFormListResponse(BaseModel):
    items: List[CaseFormResponse]

