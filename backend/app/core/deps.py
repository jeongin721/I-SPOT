# FastAPI Dependency.
#
# 권한 검사는 항상 Backend 에서 수행한다.
# Frontend 메뉴 숨김만으로 권한을 처리하지 않는다.(03_BACKEND_PROMPT.md §10)

import uuid
from typing import Annotated, Optional

from fastapi import Depends
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


def get_current_user(
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

    if not user.is_active:
        raise APIError(
            ErrorCode.INACTIVE_USER,
            "비활성화된 계정입니다. 관리자에게 문의하세요.",
            status_code=403,
        )

    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_admin(current_user: CurrentUser) -> User:
    if current_user.role != UserRole.ADMIN:
        raise forbidden("관리자만 수행할 수 있는 작업입니다.")

    return current_user


AdminUser = Annotated[User, Depends(require_admin)]
