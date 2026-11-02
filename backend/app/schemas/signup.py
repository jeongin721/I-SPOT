# 회원가입 Schema(2026-11-02, API_CONTRACT 3절 '회원가입').
#
# 신청하는 사람은 역할을 보내지 않는다. 승인할 때 관리자가 정한다(SignupApproveRequest).
# 응답에는 인증번호 · 비밀번호 해시가 담기지 않는다. 확인 토큰은 verify-code 응답에서 한 번만 나간다.

import uuid
from datetime import datetime
from typing import Any, List, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.core.enums import SignupRequestStatus, UserRole
from app.schemas.common import RequestModel


class SignupSettingsResponse(BaseModel):
    """화면이 회원가입 단추를 보일지 정하는 값. 로그인 없이 읽는다."""

    enabled: bool
    # 비면 모든 도메인을 받는다.
    allowed_email_domains: List[str]


class SignupCodeSendRequest(RequestModel):
    email: EmailStr


class SignupCodeSendResponse(BaseModel):
    """받아들인 보내기 요청은 이메일이 새것이든 아니든 늘 이 모양이다(계정 존재가 드러나지 않게)."""

    resend_after_seconds: int
    expires_in_seconds: int


class SignupCodeVerifyRequest(RequestModel):
    email: EmailStr
    # ASCII 숫자 6자리만 받는다. 전각 숫자 · 5자리 · 7자리는 형식 오류(422 VALIDATION_ERROR)다.
    code: str = Field(..., pattern=r"^[0-9]{6}$")


class SignupCodeVerifyResponse(BaseModel):
    verification_token: str
    expires_in_seconds: int


class SignupRequestCreate(RequestModel):
    """
    대기 신청. 비밀번호 규칙은 계정 생성과 같다(app/core/password_policy.py).

    password 의 최소 길이는 여기서 보지 않는다. 짧은 것도 WEAK_PASSWORD 와 사유로 알린다(UserCreateRequest 와 같은 이유).
    """

    verification_token: str = Field(..., min_length=1, max_length=128)
    name: str = Field(..., min_length=1, max_length=100)
    password: str = Field(..., min_length=1, max_length=128)

    @field_validator("name", mode="before")
    @classmethod
    def _strip_name(cls, value: Any) -> Any:
        """앞뒤 공백을 떼고 길이를 본다. 공백만 있는 이름은 빈 값(422)이다."""

        return value.strip() if isinstance(value, str) else value


class SignupRequestCreated(BaseModel):
    status: SignupRequestStatus


class SignupApproveRequest(RequestModel):
    # 기본값을 두지 않는다. 승인하는 관리자가 매번 고른다.
    role: UserRole


class SignupRequestResponse(BaseModel):
    """관리자 목록 · 승인 · 거절 응답. 비밀번호 해시는 담지 않는다."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    name: str
    status: SignupRequestStatus
    created_at: datetime
    # PENDING 이 보관 기한으로 지워지는 시각. 처리된 신청은 null.
    expires_at: Optional[datetime] = None
    decided_at: Optional[datetime] = None
    decided_by_id: Optional[uuid.UUID] = None
    decided_by_name: Optional[str] = None
    role: Optional[UserRole] = None
    user_id: Optional[uuid.UUID] = None
