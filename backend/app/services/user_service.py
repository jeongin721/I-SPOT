# 계정 관리 및 로그인.
#
# 자유 회원가입은 제공하지 않는다.(03_BACKEND_PROMPT.md §10)
# 계정은 관리자 API 또는 seed script 로만 생성된다.

from typing import List

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.enums import AuditAction
from app.core.errors import APIError, ErrorCode, conflict
from app.core.password_policy import validate_password
from app.core.security import hash_password, verify_password
from app.models.user import User
from app.schemas.auth import PasswordChangeRequest, UserCreateRequest
from app.services import audit_service


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
    validate_password(payload.password, email=payload.email, name=payload.name)

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


def change_password(
    db: Session,
    user: User,
    payload: PasswordChangeRequest,
) -> None:
    """
    본인 비밀번호 변경.

    현재 비밀번호를 함께 받는다. Token 만 훔친 사람이 비밀번호를 바꿔
    계정을 가져가는 것을 막는다.
    """

    if not verify_password(payload.current_password, user.hashed_password):
        raise APIError(
            ErrorCode.INVALID_CREDENTIALS,
            "현재 비밀번호가 올바르지 않습니다.",
            status_code=401,
        )

    validate_password(payload.new_password, email=user.email, name=user.name)

    if verify_password(payload.new_password, user.hashed_password):
        raise APIError(
            ErrorCode.SAME_PASSWORD,
            "이전과 다른 비밀번호를 정해 주세요.",
            status_code=422,
        )

    user.hashed_password = hash_password(payload.new_password)

    # detail 에 비밀번호를 담지 않는다.
    audit_service.record(
        db,
        action=AuditAction.PASSWORD_CHANGED,
        entity_type="User",
        entity_id=user.id,
        actor_id=user.id,
    )

    db.commit()
