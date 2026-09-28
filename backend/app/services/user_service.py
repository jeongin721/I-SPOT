# 계정 관리 및 로그인.
#
# 자유 회원가입은 제공하지 않는다.(03_BACKEND_PROMPT.md §10)
# 계정은 관리자 API 또는 seed script 로만 생성된다.

from typing import List

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import APIError, ErrorCode, conflict
from app.core.security import hash_password, verify_password
from app.models.user import User
from app.schemas.auth import UserCreateRequest


def authenticate(db: Session, email: str, password: str) -> User:
    user = db.scalar(select(User).where(User.email == email.lower()))

    # 계정 존재 여부를 노출하지 않기 위해 동일한 오류를 반환한다.
    if user is None or not verify_password(password, user.hashed_password):
        raise APIError(
            ErrorCode.INVALID_CREDENTIALS,
            "이메일 또는 비밀번호가 올바르지 않습니다.",
            status_code=401,
        )

    if not user.is_active:
        raise APIError(
            ErrorCode.INACTIVE_USER,
            "비활성화된 계정입니다. 관리자에게 문의하세요.",
            status_code=403,
        )

    return user


def create_user(db: Session, payload: UserCreateRequest) -> User:
    user = User(
        email=payload.email.lower(),
        hashed_password=hash_password(payload.password),
        name=payload.name,
        role=payload.role,
        is_active=True,
    )

    db.add(user)

    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()

        raise conflict(
            ErrorCode.DUPLICATE_RESOURCE,
            "이미 등록된 이메일입니다.",
        ) from error

    db.refresh(user)

    return user


def list_users(db: Session) -> List[User]:
    return list(db.scalars(select(User).order_by(User.created_at.asc())))
