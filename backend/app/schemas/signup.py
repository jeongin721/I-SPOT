# 회원가입 Schema(2026-11-02, API_CONTRACT 3절 '회원가입').
#
# 신청하는 사람은 역할을 보내지 않는다. 승인할 때 관리자가 정한다(SignupApproveRequest).
# 응답에는 인증번호 · 비밀번호 해시가 담기지 않는다. 확인 토큰은 verify-code 응답에서 한 번만 나간다.

import uuid
from datetime import datetime
from typing import Annotated, Any, List, Optional

from email_validator import EmailNotValidError, validate_email
from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, field_validator

from app.core.email_address import canonical_email
from app.core.enums import SignupRequestStatus, UserRole
from app.schemas.common import RequestModel

EMAIL_INVALID_MESSAGE = "이메일 형식이 올바르지 않습니다. 영문 주소만 받습니다."


def _signup_email(value: Any) -> str:
    """
    회원가입 이메일. SES 가 받는 꼴(아이디는 ASCII, 도메인은 IDNA ASCII — punycode)로 바꾸고 소문자로 맞춘다(Codex #139 M4).

    EmailStr 을 쓰지 않는다. 그 오류 문구는 입력 일부(대괄호 안 주소 · 잘못된 글자)를 그대로 담아 422 응답에 되돌아간다
    (Codex #139 L1). 여기서는 어떤 형식 오류든 위 고정 문구 하나다. 아이디에 한글 등 ASCII 가 아닌 글자가 있는 주소,
    표시 이름(`이름 <주소>`) · 대괄호 IP 주소도 같은 오류다. 가입 여부와 상관없이 같은 입력은 같은 답을 받는다.
    """

    if not isinstance(value, str):
        raise ValueError(EMAIL_INVALID_MESSAGE)

    try:
        checked = validate_email(value.strip(), check_deliverability=False, allow_smtputf8=False)
    except EmailNotValidError:
        raise ValueError(EMAIL_INVALID_MESSAGE) from None

    # 저장 · 비교하는 꼴(아이디 소문자 + IDNA 2008 punycode 도메인)과 똑같이 맞춘다 — 로그인 · 관리자 생성도 이 꼴을 쓴다.
    return canonical_email(checked.ascii_email)


# OpenAPI 에는 지금처럼 이메일 칸으로 보이게 format 을 적는다.
SignupEmail = Annotated[str, BeforeValidator(_signup_email), Field(json_schema_extra={"format": "email"})]


class SignupSettingsResponse(BaseModel):
    """화면이 회원가입 단추를 보일지 정하는 값. 로그인 없이 읽는다."""

    enabled: bool
    # 비면 모든 도메인을 받는다.
    allowed_email_domains: List[str]


class SignupCodeSendRequest(RequestModel):
    email: SignupEmail


class SignupCodeSendResponse(BaseModel):
    """받아들인 보내기 요청은 이메일이 새것이든 아니든 늘 이 모양이다(계정 존재가 드러나지 않게)."""

    resend_after_seconds: int
    expires_in_seconds: int


class SignupCodeVerifyRequest(RequestModel):
    email: SignupEmail
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
