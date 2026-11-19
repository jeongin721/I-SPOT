# Case Schema.
# 개인정보 최소 저장 원칙에 따라 일반 사례 응답에는 아동 실명 필드를 두지 않는다.
# 실명 · 생년월일 · 가족 정보는 암호화해 따로 두고(case_personal_info.py) 전용 창구로만 오간다.
# 예외: 새 사례 등록의 personal_info(요청), 목록 with_child_name=true 의 child_name(CaseListItemResponse).

import uuid
from datetime import date, datetime
from typing import Annotated, List, Optional

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from app.core.enums import (
    CaseStatus,
    ChildActionResult,
    FamilyType,
    GuardianType,
    RiskLevel,
    TargetActionResult,
)
from app.core.intake import (
    INTAKE_CHILD_TRAITS,
    INTAKE_FAMILY_SITUATIONS,
    normalize_intake,
)
from app.schemas.auth import UserResponse
from app.schemas.case_personal_info import PersonalInfoRequest
from app.schemas.common import IsoDate, RequestModel

# 초기면접 고르기 항목 한 개 · 한 칸에 보낼 수 있는 개수. 서식 항목보다 넉넉하게 두고 실제 값은 normalize_intake 가 거른다.
IntakeItem = Annotated[str, StringConstraints(max_length=50)]
_INTAKE_MAX_ITEMS = 100


def _intake(values: Optional[List[str]], field: str) -> Optional[List[str]]:
    """초기면접 칸 검사. null 은 그대로 둔다(수정 요청의 null 은 _CASE_NOT_NULLABLE_FIELDS 가 거부한다)."""

    if values is None:
        return None

    if field == "intake_child_traits":
        return normalize_intake(values, INTAKE_CHILD_TRAITS, "아동 특성")

    return normalize_intake(values, INTAKE_FAMILY_SITUATIONS, "가정상황")


class GuardianFields(RequestModel):
    """
    보호자 유형.

    목록에 없는 관계는 guardian_type=OTHER 로 두고 guardian_note 에 적는다.
    보호자 실명은 저장하지 않는다(아동 실명과 같은 원칙).
    """

    guardian_type: Optional[GuardianType] = None
    guardian_note: Optional[str] = Field(default=None, max_length=100)

    @model_validator(mode="after")
    def _check_note_usage(self) -> "GuardianFields":
        if self.guardian_note and self.guardian_type != GuardianType.OTHER:
            raise ValueError(
                "guardian_note 는 guardian_type 이 OTHER 일 때만 사용합니다."
            )

        return self


# 서식 4 ① 날짜 셋(2026-10-30). 'YYYY-MM-DD' 날짜만, 1900-01-01 ~ 2100-12-31.
CASE_DATE_FIELDS = ("report_date", "linked_date", "first_interview_date")
_CASE_DATE_MIN = date(1900, 1, 1)
_CASE_DATE_MAX = date(2100, 12, 31)


def _case_date(value: Optional[date]) -> Optional[date]:
    if value is not None and not (_CASE_DATE_MIN <= value <= _CASE_DATE_MAX):
        raise ValueError("날짜는 1900-01-01 부터 2100-12-31 까지만 쓸 수 있습니다.")
    return value


# 서식 4 의 '준비 중' 칸(2026-11-05). 고르기 칸은 목록 값만, 글 칸은 2000자까지. 모두 비울 수 있다.
CASE_FORM_CHOICE_FIELDS = (
    "child_action_result",
    "target_action_result",
    "counselor_risk_level",
    "intake_family_type",
)
CASE_FORM_TEXT_FIELDS = (
    "linked_background",
    "intake_guardian_relation",
    "intake_problem",
    "intake_attitude",
    "intake_environment",
    "intake_opinion",
)
CASE_FORM_FIELDS = CASE_FORM_CHOICE_FIELDS + CASE_FORM_TEXT_FIELDS
CASE_FORM_TEXT_MAX = 2000


class CaseFormFields(RequestModel):
    """
    서식 4 ① 조치결과 · 위험도(우선) · 사례연계 경위, ② 가족유형 · 초기면접 글 칸(2026-11-05).

    모두 상담원이 고르거나 적는 값이다. AI 가 미리 고르거나 채우지 않고 AI 입력(case_context_service)에도 넘기지 않는다.
    위험도(우선)는 상담원이 고른 사례 위험도(상 · 중 · 하)로, 회차 AI 신호 · 회차 위험도 판단과 맞추지 않는다.
    글 칸은 앞뒤 빈칸을 지우고, 빈 글은 null 로 저장한다. 수정 요청의 null 은 그 칸을 비운다.
    """

    child_action_result: Optional[ChildActionResult] = None
    target_action_result: Optional[TargetActionResult] = None
    counselor_risk_level: Optional[RiskLevel] = None
    intake_family_type: Optional[FamilyType] = None
    linked_background: Optional[str] = Field(default=None, max_length=CASE_FORM_TEXT_MAX)
    intake_guardian_relation: Optional[str] = Field(default=None, max_length=CASE_FORM_TEXT_MAX)
    intake_problem: Optional[str] = Field(default=None, max_length=CASE_FORM_TEXT_MAX)
    intake_attitude: Optional[str] = Field(default=None, max_length=CASE_FORM_TEXT_MAX)
    intake_environment: Optional[str] = Field(default=None, max_length=CASE_FORM_TEXT_MAX)
    intake_opinion: Optional[str] = Field(default=None, max_length=CASE_FORM_TEXT_MAX)

    @field_validator(*CASE_FORM_TEXT_FIELDS)
    @classmethod
    def _blank_as_none(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        return value.strip() or None


class CaseCreateRequest(GuardianFields, CaseFormFields):
    # personal_info(실명 · 가족)를 실을 수 있어 검증 오류 문구에 입력값을 넣지 않는다 — 하위 모델만 가리면 부모 오류에 값이
    # 남는다(Codex #127 재검증 R4). 422 응답은 원래 값을 빼고 보낸다(main.py).
    model_config = ConfigDict(hide_input_in_errors=True)

    title: str = Field(..., min_length=1, max_length=200)
    child_alias: str = Field(..., min_length=1, max_length=100)
    child_birth_year: Optional[int] = Field(default=None, ge=1900, le=2100)
    child_gender: Optional[str] = Field(default=None, max_length=10)
    notes: Optional[str] = Field(default=None, max_length=4000)
    # 신고접수일 · 사례연계일 · 최초면접일(서식 4 ①). 비우면 null.
    report_date: Optional[IsoDate] = None
    linked_date: Optional[IsoDate] = None
    first_interview_date: Optional[IsoDate] = None

    # 초기면접(서식 4 ②)에서 고른 아동 특성 · 가정상황. 서식 항목만 받고(그 밖은 422) 겹친 항목은 하나로 합친다.
    intake_child_traits: List[IntakeItem] = Field(
        default_factory=list, max_length=_INTAKE_MAX_ITEMS
    )
    intake_family_situations: List[IntakeItem] = Field(
        default_factory=list, max_length=_INTAKE_MAX_ITEMS
    )

    # 지정하지 않으면 요청자 본인이 담당 상담사가 된다. 지정은 관리자만 가능하다.
    counselor_id: Optional[uuid.UUID] = None

    # 미지정 시 Backend 가 C-YYYY-NNNN 형식으로 생성한다.
    case_number: Optional[str] = Field(default=None, min_length=1, max_length=50)

    # 새 사례 등록 화면의 실명 · 생년월일 · 가족 정보(API_CONTRACT 4절 '개인 식별 정보'). 사례와 한 거래로 암호화해 저장한다. 응답에는 싣지 않는다.
    personal_info: Optional[PersonalInfoRequest] = None

    @field_validator("intake_child_traits", "intake_family_situations")
    @classmethod
    def _check_intake(cls, values: List[str], info) -> List[str]:
        return _intake(values, info.field_name)

    @field_validator(*CASE_DATE_FIELDS)
    @classmethod
    def _check_date(cls, value: Optional[date]) -> Optional[date]:
        return _case_date(value)


# 초기면접 칸은 비울 때 빈 목록을 보낸다(null 은 거부).
_CASE_NOT_NULLABLE_FIELDS = (
    "title",
    "child_alias",
    "status",
    "counselor_id",
    "intake_child_traits",
    "intake_family_situations",
)


class CaseUpdateRequest(GuardianFields, CaseFormFields):
    title: Optional[str] = Field(default=None, min_length=1, max_length=200)
    child_alias: Optional[str] = Field(default=None, min_length=1, max_length=100)
    child_birth_year: Optional[int] = Field(default=None, ge=1900, le=2100)
    child_gender: Optional[str] = Field(default=None, max_length=10)
    notes: Optional[str] = Field(default=None, max_length=4000)
    status: Optional[CaseStatus] = None
    counselor_id: Optional[uuid.UUID] = None
    # 날짜 셋(서식 4 ①). null 을 보내면 비운다.
    report_date: Optional[IsoDate] = None
    linked_date: Optional[IsoDate] = None
    first_interview_date: Optional[IsoDate] = None
    # 보내면 저장된 목록을 통째로 바꾼다(빈 목록 = 모두 지움).
    intake_child_traits: Optional[List[IntakeItem]] = Field(
        default=None, max_length=_INTAKE_MAX_ITEMS
    )
    intake_family_situations: Optional[List[IntakeItem]] = Field(
        default=None, max_length=_INTAKE_MAX_ITEMS
    )

    @field_validator("intake_child_traits", "intake_family_situations")
    @classmethod
    def _check_intake(cls, values: Optional[List[str]], info) -> Optional[List[str]]:
        return _intake(values, info.field_name)

    @field_validator(*CASE_DATE_FIELDS)
    @classmethod
    def _check_date(cls, value: Optional[date]) -> Optional[date]:
        return _case_date(value)

    @model_validator(mode="after")
    def _check_note_usage(self) -> "CaseUpdateRequest":
        """
        GuardianFields 의 같은 이름 검사를 대신한다.

        수정은 보낸 필드만 바뀐다. 메모만 보내면 저장된 유형과 합쳐서 판단해야 하므로
        여기서는 유형을 함께 보냈을 때만 검사하고, 나머지는 case_service.update_case 가 검사한다.
        """

        if (
            self.guardian_note
            and "guardian_type" in self.model_fields_set
            and self.guardian_type != GuardianType.OTHER
        ):
            raise ValueError(
                "guardian_note 는 guardian_type 이 OTHER 일 때만 사용합니다."
            )

        # 비울 수 없는 필드를 null 로 보내면 DB 저장에서 500 이 난다. 요청 단계에서 거부한다.
        for field in _CASE_NOT_NULLABLE_FIELDS:
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(
                    f"{field} 는 null 로 보낼 수 없습니다. 바꾸지 않으려면 보내지 않습니다."
                )

        return self


class CaseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    case_number: str
    title: str
    child_alias: str
    child_birth_year: Optional[int]
    child_gender: Optional[str]
    guardian_type: Optional[GuardianType]
    guardian_note: Optional[str]
    # 초기면접에서 고른 항목(서식 4 의 이름 그대로). 고르지 않았거나 칸이 생기기 전 사례면 빈 목록.
    intake_child_traits: List[str] = Field(default_factory=list)
    intake_family_situations: List[str] = Field(default_factory=list)
    # 신고접수일 · 사례연계일 · 최초면접일(서식 4 ①, 2026-10-30). 넣지 않았으면 null.
    report_date: Optional[date] = None
    linked_date: Optional[date] = None
    first_interview_date: Optional[date] = None
    # 서식 4 ① 조치결과 · 위험도(우선) · 사례연계 경위, ② 가족유형 · 초기면접 글 칸(2026-11-05). 넣지 않았으면 null.
    child_action_result: Optional[ChildActionResult] = None
    target_action_result: Optional[TargetActionResult] = None
    counselor_risk_level: Optional[RiskLevel] = None
    linked_background: Optional[str] = None
    intake_family_type: Optional[FamilyType] = None
    intake_guardian_relation: Optional[str] = None
    intake_problem: Optional[str] = None
    intake_attitude: Optional[str] = None
    intake_environment: Optional[str] = None
    intake_opinion: Optional[str] = None
    # 종결 검토에 등록한 시각(2026-10-30). 등록 전 · 취소하면 null.
    closure_review_at: Optional[datetime] = None
    status: CaseStatus
    notes: Optional[str]
    counselor_id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    # Case List 화면의 "최근 상담일". Session 이 없으면 null 이다.
    last_session_at: Optional[datetime] = None

    # Case List 화면이 담당자를 이름으로 표시한다. counselor_id(UUID)만으로는
    # Frontend 가 사용자 조회를 다시 해야 하므로 목록에서 함께 내려준다.
    counselor_name: Optional[str] = None

    @field_validator("intake_child_traits", "intake_family_situations", mode="before")
    @classmethod
    def _null_as_empty(cls, value):
        return [] if value is None else value


class CaseListItemResponse(CaseResponse):
    # 아동 실명(API_CONTRACT 4절 '개인 식별 정보'). GET /cases?with_child_name=true 일 때만 채운다(그때 열람 기록 1줄). 없거나 안 물으면 null.
    # repr · str 에는 넣지 않는다(디버그 로그에 객체를 찍어도 실명이 새지 않게, Codex #127 R4).
    child_name: Optional[str] = Field(default=None, repr=False)
    # 분석이 끝난 가장 최근 회차의 상담원 판단(회차 전체 상 · 중 · 하). 판단 전이면 null. AI 심각도로 채우지 않는다.
    risk_level: Optional[RiskLevel] = None


class CaseDetailResponse(CaseResponse):
    counselor: Optional[UserResponse] = None
    session_count: int = 0
