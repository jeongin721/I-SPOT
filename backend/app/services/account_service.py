# 관리자의 계정 관리.
#
# 계정 활성화 · 비활성화, 역할 변경, 임시 비밀번호 재발급, 잠금 해제,
# 휴면 해제, 강제 로그아웃, 감사 로그 조회.
#
# 마지막 활성 관리자를 잠그는 동작은 모두 막는다. 아무도 풀 수 없게 되기 때문이다.

import uuid
from datetime import datetime, timezone
from typing import List, Optional, Tuple

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.enums import AuditAction, UserRole
from app.core.errors import ErrorCode, conflict, not_found
from app.core.password_policy import generate_password
from app.core.security import hash_password
from app.models.audit_log import AuditLog
from app.models.user import User
from app.schemas.auth import UserUpdateRequest
from app.services import audit_service, user_service


def get_user_or_404(db: Session, user_id: uuid.UUID) -> User:
    user = db.get(User, user_id)

    if user is None:
        raise not_found(ErrorCode.USER_NOT_FOUND, "계정을 찾을 수 없습니다.")

    return user


def _is_last_active_admin(db: Session, user: User) -> bool:
    if user.role != UserRole.ADMIN:
        return False

    if not user.is_active or user.dormant_at is not None or user.anonymized_at is not None:
        return False

    return user_service.active_admin_count(db) <= 1


def _issue_temporary_password(user: User) -> str:
    """
    임시 비밀번호를 만들어 계정에 건다.

    돌려준 값은 이 응답에서 한 번만 나가고 다시 조회할 수 없다. DB 에는 해시만 남는다.
    """

    temporary = generate_password()

    user.hashed_password = hash_password(temporary)
    user.must_change_password = True
    user.password_changed_at = datetime.now(timezone.utc)
    user.failed_login_count = 0
    user.locked_until = None

    # 이전에 발급된 Token 을 모두 무효로 만든다.
    user.token_version += 1

    return temporary


def reset_password(db: Session, actor: User, user: User) -> str:
    temporary = _issue_temporary_password(user)

    audit_service.record(
        db,
        action=AuditAction.PASSWORD_RESET,
        entity_type="User",
        entity_id=user.id,
        actor_id=actor.id,
    )
    db.commit()

    return temporary


def unlock(db: Session, actor: User, user: User) -> None:
    user.failed_login_count = 0
    user.locked_until = None

    audit_service.record(
        db,
        action=AuditAction.ACCOUNT_UNLOCKED,
        entity_type="User",
        entity_id=user.id,
        actor_id=actor.id,
    )
    db.commit()


def reactivate(db: Session, actor: User, user: User) -> str:
    """
    휴면 해제.

    오래 쓰지 않은 계정이라 비밀번호도 함께 새로 발급한다.
    """

    user.dormant_at = None
    user.last_login_at = None

    temporary = _issue_temporary_password(user)

    audit_service.record(
        db,
        action=AuditAction.ACCOUNT_REACTIVATED,
        entity_type="User",
        entity_id=user.id,
        actor_id=actor.id,
    )
    db.commit()

    return temporary


def logout_all(db: Session, actor: User, user: User) -> None:
    if user.id == actor.id:
        raise conflict(
            ErrorCode.VALIDATION_ERROR,
            "자기 계정은 강제 로그아웃할 수 없습니다.",
        )

    user.token_version += 1

    audit_service.record(
        db,
        action=AuditAction.LOGOUT_ALL,
        entity_type="User",
        entity_id=user.id,
        actor_id=actor.id,
    )
    db.commit()


def update_user(
    db: Session,
    actor: User,
    user: User,
    payload: UserUpdateRequest,
) -> User:
    data = payload.model_dump(exclude_unset=True)
    changed: List[str] = []

    if "is_active" in data and data["is_active"] is not None:
        if data["is_active"] is False and _is_last_active_admin(db, user):
            raise conflict(
                ErrorCode.VALIDATION_ERROR,
                "마지막 관리자 계정은 비활성화할 수 없습니다.",
            )

        if user.is_active != data["is_active"]:
            user.is_active = data["is_active"]
            changed.append("is_active")

    if "role" in data and data["role"] is not None:
        if data["role"] != UserRole.ADMIN and _is_last_active_admin(db, user):
            raise conflict(
                ErrorCode.VALIDATION_ERROR,
                "마지막 관리자 계정의 역할은 바꿀 수 없습니다.",
            )

        if user.role != data["role"]:
            user.role = data["role"]
            changed.append("role")

    if "name" in data and data["name"] is not None and user.name != data["name"]:
        user.name = data["name"]
        changed.append("name")

    if changed:
        # 역할이 바뀌면 이미 발급된 Token 의 권한 정보가 낡는다.
        if "role" in changed or "is_active" in changed:
            user.token_version += 1

        audit_service.record(
            db,
            action=AuditAction.USER_UPDATED,
            entity_type="User",
            entity_id=user.id,
            actor_id=actor.id,
            detail={"changed_fields": changed},
        )

    db.commit()
    db.refresh(user)

    return user


def list_audit_logs(
    db: Session,
    *,
    offset: int,
    limit: int,
    action: Optional[AuditAction] = None,
    status: Optional[str] = None,
    actor_id: Optional[uuid.UUID] = None,
    since: Optional[datetime] = None,
    until: Optional[datetime] = None,
) -> Tuple[List[AuditLog], int]:
    conditions = []

    if action is not None:
        conditions.append(AuditLog.action == action)

    if status is not None:
        conditions.append(AuditLog.status == status)

    if actor_id is not None:
        conditions.append(AuditLog.actor_id == actor_id)

    if since is not None:
        conditions.append(AuditLog.created_at >= since)

    if until is not None:
        conditions.append(AuditLog.created_at <= until)

    total = db.scalar(
        select(func.count()).select_from(AuditLog).where(*conditions)
    ) or 0

    rows = list(
        db.scalars(
            select(AuditLog)
            .where(*conditions)
            .order_by(AuditLog.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
    )

    return rows, total
