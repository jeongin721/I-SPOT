# Case Schema.
# 개인정보 최소 저장 원칙에 따라 일반 사례 응답에는 아동 실명 필드를 두지 않는다.
# 실명 · 생년월일 · 가족 정보는 암호화해 따로 두고(case_personal_info.py) 전용 창구로만 오간다.
# 예외: 새 사례 등록의 personal_info(요청), 목록 with_child_name=true 의 child_name(CaseListItemResponse).

import uuid
from datetime import datetime
from typing import Annotated, List, Optional

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from app.core.enums import CaseStatus, GuardianType
from app.core.intake import (
    INTAKE_CHILD_TRAITS,
    INTAKE_FAMILY_SITUATIONS,
    normalize_intake,
)
from app.schemas.auth import UserResponse
from app.schemas.case_personal_info import PersonalInfoRequest
from app.schemas.common import RequestModel

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


class CaseCreateRequest(GuardianFields):
    title: str = Field(..., min_length=1, max_length=200)
    child_alias: str = Field(..., min_length=1, max_length=100)
    child_birth_year: Optional[int] = Field(default=None, ge=1900, le=2100)
    child_gender: Optional[str] = Field(default=None, max_length=10)
    notes: Optional[str] = Field(default=None, max_length=4000)

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


# 초기면접 칸은 비울 때 빈 목록을 보낸다(null 은 거부).
_CASE_NOT_NULLABLE_FIELDS = (
    "title",
    "child_alias",
    "status",
    "counselor_id",
    "intake_child_traits",
    "intake_family_situations",
)


class CaseUpdateRequest(GuardianFields):
    title: Optional[str] = Field(default=None, min_length=1, max_length=200)
    child_alias: Optional[str] = Field(default=None, min_length=1, max_length=100)
    child_birth_year: Optional[int] = Field(default=None, ge=1900, le=2100)
    child_gender: Optional[str] = Field(default=None, max_length=10)
    notes: Optional[str] = Field(default=None, max_length=4000)
    status: Optional[CaseStatus] = None
    counselor_id: Optional[uuid.UUID] = None
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
    child_name: Optional[str] = None


class CaseDetailResponse(CaseResponse):
    counselor: Optional[UserResponse] = None
    session_count: int = 0
