# Case Schema.
# 개인정보 최소 저장 원칙에 따라 아동 실명 필드를 두지 않는다.

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.core.enums import CaseStatus, GuardianType
from app.schemas.auth import UserResponse


class GuardianFields(BaseModel):
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

    # 지정하지 않으면 요청자 본인이 담당 상담사가 된다. 지정은 관리자만 가능하다.
    counselor_id: Optional[uuid.UUID] = None

    # 미지정 시 Backend 가 C-YYYY-NNNN 형식으로 생성한다.
    case_number: Optional[str] = Field(default=None, min_length=1, max_length=50)


_CASE_NOT_NULLABLE_FIELDS = ("title", "child_alias", "status")


class CaseUpdateRequest(GuardianFields):
    title: Optional[str] = Field(default=None, min_length=1, max_length=200)
    child_alias: Optional[str] = Field(default=None, min_length=1, max_length=100)
    child_birth_year: Optional[int] = Field(default=None, ge=1900, le=2100)
    child_gender: Optional[str] = Field(default=None, max_length=10)
    notes: Optional[str] = Field(default=None, max_length=4000)
    status: Optional[CaseStatus] = None
    counselor_id: Optional[uuid.UUID] = None

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


class CaseDetailResponse(CaseResponse):
    counselor: Optional[UserResponse] = None
    session_count: int = 0
