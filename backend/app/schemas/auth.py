# 인증 Schema. 자유 회원가입 endpoint 는 제공하지 않는다.

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.core.enums import UserRole


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
