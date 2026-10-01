# 인증 Schema. 자유 회원가입 endpoint 는 제공하지 않는다.

import uuid
from datetime import datetime

from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.core.enums import AuditAction, UserRole


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=1, max_length=128)


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    name: str
    role: UserRole
    is_active: bool
    created_at: datetime

    # 관리자 화면이 "왜 로그인이 안 되는지" 를 구분해 보여줄 수 있어야 한다.
    # is_active(관리자 정지) · is_locked(실패 잠금) · dormant_at(미접속) 은 뜻이 다르다.
    last_login_at: Optional[datetime] = None
    must_change_password: bool = False
    # 잠김 여부는 is_locked 로 본다. 기본 설정(LOGIN_LOCK_MINUTES=0)에서는 시간으로 풀리지 않아
    # locked_until 이 비어 있다. locked_until 은 시간 잠금일 때 풀리는 시각이다.
    is_locked: bool = False
    locked_until: Optional[datetime] = None
    dormant_at: Optional[datetime] = None


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserResponse


class UserCreateRequest(BaseModel):
    """
    관리자 전용 계정 생성 요청.

    password 의 최소 길이는 여기서 보지 않는다. 짧은 것도 다른 규칙 위반과 같이
    WEAK_PASSWORD 와 한국어 사유(details.reasons)로 알리기 위해서다.(app/core/password_policy.py)
    """

    email: EmailStr
    password: str = Field(..., min_length=1, max_length=128)
    name: str = Field(..., min_length=1, max_length=100)
    role: UserRole = UserRole.COUNSELOR


class PasswordChangeRequest(BaseModel):
    """
    본인 비밀번호 변경. 새 비밀번호 규칙은 app/core/password_policy.py 에 있다.

    new_password 의 최소 길이도 그 규칙이 본다(UserCreateRequest 와 같은 이유).
    """

    current_password: str = Field(..., min_length=1, max_length=128)
    new_password: str = Field(..., min_length=1, max_length=128)


class UserUpdateRequest(BaseModel):
    """관리자 전용 계정 수정. 비밀번호는 여기서 바꾸지 않는다."""

    is_active: Optional[bool] = None
    role: Optional[UserRole] = None
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)


class TemporaryPasswordResponse(BaseModel):
    """임시 비밀번호는 이 응답에서 한 번만 나간다. 다시 조회할 수 없다."""

    temporary_password: str
    expires_at: datetime
    must_change_password: bool = True


class AuditLogResponse(BaseModel):
    """감사 로그 조회용. 상담 원문과 아동 실명은 담기지 않는다."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    action: AuditAction
    status: str
    error_code: Optional[str] = None
    actor_id: Optional[uuid.UUID] = None
    actor_name: Optional[str] = None
    entity_type: str
    entity_id: Optional[uuid.UUID] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    detail: Optional[Dict[str, Any]] = None
    created_at: datetime
