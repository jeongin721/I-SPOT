# Case Schema.
# 개인정보 최소 저장 원칙에 따라 아동 실명 필드를 두지 않는다.

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import CaseStatus
from app.schemas.auth import UserResponse


class CaseCreateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    child_alias: str = Field(..., min_length=1, max_length=100)
    child_birth_year: Optional[int] = Field(default=None, ge=1900, le=2100)
    child_gender: Optional[str] = Field(default=None, max_length=10)
    notes: Optional[str] = Field(default=None, max_length=4000)

    # 지정하지 않으면 요청자 본인이 담당 상담사가 된다. 지정은 관리자만 가능하다.
    counselor_id: Optional[uuid.UUID] = None

    # 미지정 시 Backend 가 C-YYYY-NNNN 형식으로 생성한다.
    case_number: Optional[str] = Field(default=None, min_length=1, max_length=50)


class CaseUpdateRequest(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=200)
    child_alias: Optional[str] = Field(default=None, min_length=1, max_length=100)
    child_birth_year: Optional[int] = Field(default=None, ge=1900, le=2100)
    child_gender: Optional[str] = Field(default=None, max_length=10)
    notes: Optional[str] = Field(default=None, max_length=4000)
    status: Optional[CaseStatus] = None
    counselor_id: Optional[uuid.UUID] = None


class CaseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    case_number: str
    title: str
    child_alias: str
    child_birth_year: Optional[int]
    child_gender: Optional[str]
    status: CaseStatus
    notes: Optional[str]
    counselor_id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class CaseDetailResponse(CaseResponse):
    counselor: Optional[UserResponse] = None
    session_count: int = 0
