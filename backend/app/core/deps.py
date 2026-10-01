# FastAPI Dependency.
#
# 권한 검사는 항상 Backend 에서 수행한다.
# Frontend 메뉴 숨김만으로 권한을 처리하지 않는다.(03_BACKEND_PROMPT.md §10)

import uuid
from typing import Annotated, Optional

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.enums import UserRole
from app.core.errors import APIError, ErrorCode, forbidden, unauthorized
from app.core.security import decode_access_token
from app.models.user import User

bearer_scheme = HTTPBearer(auto_error=False, description="로그인 후 발급받은 Access Token")

DbSession = Annotated[Session, Depends(get_db)]


# 임시 비밀번호 상태에서도 열어 두는 경로.
# 내 정보 확인은 화면이 "비밀번호를 바꿔야 한다" 를 보여주는 데 필요하다.
_PASSWORD_CHANGE_ALLOWED_PATHS = frozenset(
    {"/api/v1/auth/me", "/api/v1/auth/me/password"}
)


def client_ip(request: Request) -> Optional[str]:
    """
    접속 기록에 남길 IP.

    X-Forwarded-For 는 클라이언트가 마음대로 보낼 수 있어 쓰지 않는다.
    프록시 뒤에 두게 되면 신뢰할 프록시를 정한 뒤에 다시 본다.
    """

    return request.client.host if request.client else None


def user_agent(request: Request) -> Optional[str]:
    value = request.headers.get("user-agent")

    return value[:255] if value else None


def get_current_user(
    request: Request,
    db: DbSession,
    credentials: Annotated[
        Optional[HTTPAuthorizationCredentials], Depends(bearer_scheme)
    ] = None,
) -> User:
    if credentials is None or not credentials.credentials:
        raise unauthorized("Authorization 헤더가 없습니다.")

    payload = decode_access_token(credentials.credentials)
    subject = payload.get("sub")

    if not subject:
        raise unauthorized("토큰에 사용자 정보가 없습니다.")

    try:
        user_id = uuid.UUID(str(subject))
    except ValueError as error:
        raise unauthorized("토큰의 사용자 정보가 올바르지 않습니다.") from error

    user = db.scalar(select(User).where(User.id == user_id))

    if user is None:
        raise unauthorized("사용자를 찾을 수 없습니다.")

    # 발급 뒤에 비밀번호 변경 · 강제 로그아웃 · 역할 변경 · 정지가 있었으면 거부한다.
    # 정지 검사보다 먼저 본다. 관리자가 API 로 정지하면 토큰 버전도 오르므로(account_service)
    # 옛 토큰은 401 이 되고, 화면은 401 을 받아 로그인 화면으로 보낸다(API_CONTRACT 3절).
    # 정지 이유(INACTIVE_USER)는 다시 로그인할 때 알려준다.
    if int(payload.get("tv", 0)) != user.token_version:
        raise unauthorized("다시 로그인해 주세요.")

    # 토큰 버전을 올리지 않고 정지한 경우(DB 를 직접 고친 경우 등)도 막는다.
    if not user.is_active:
        raise APIError(
            ErrorCode.INACTIVE_USER,
            "비활성화된 계정입니다. 관리자에게 문의하세요.",
            status_code=403,
        )

    # 임시 비밀번호 상태에서는 비밀번호 변경 외에는 막는다.
    if user.must_change_password and request.url.path not in _PASSWORD_CHANGE_ALLOWED_PATHS:
        raise APIError(
            ErrorCode.PASSWORD_CHANGE_REQUIRED,
            "임시 비밀번호를 새 비밀번호로 바꾼 뒤에 이용할 수 있습니다.",
            status_code=403,
        )

    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_admin(current_user: CurrentUser) -> User:
    if current_user.role != UserRole.ADMIN:
        raise forbidden("관리자만 수행할 수 있는 작업입니다.")

    return current_user


AdminUser = Annotated[User, Depends(require_admin)]
