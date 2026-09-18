# 계정 관리 및 로그인.
#
# 자유 회원가입은 제공하지 않는다.(03_BACKEND_PROMPT.md §10)
# 계정은 관리자 API 또는 seed script 로만 생성된다.

from datetime import datetime, timedelta, timezone
from secrets import compare_digest
from typing import List, Optional

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.enums import AuditAction, UserRole
from app.core.errors import APIError, ErrorCode, conflict
from app.core.password_policy import validate_password
from app.core.security import hash_password, verify_password
from app.models.user import User
from app.models.user_password_history import UserPasswordHistory
from app.schemas.auth import PasswordChangeRequest, UserCreateRequest
from app.services import audit_service


# =========================================================
# 공통
# =========================================================

def as_utc(value: Optional[datetime]) -> Optional[datetime]:
    """
    SQLite 는 시간대 없이 돌려준다. 저장은 UTC 이므로 UTC 로 본다.
    PostgreSQL 은 시간대를 그대로 돌려주므로 값이 바뀌지 않는다.
    """

    if value is None:
        return None

    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def active_admin_count(db: Session) -> int:
    """지금 로그인할 수 있는 관리자 수."""

    return (
        db.scalar(
            select(func.count())
            .select_from(User)
            .where(
                User.role == UserRole.ADMIN,
                User.is_active.is_(True),
                User.dormant_at.is_(None),
                User.anonymized_at.is_(None),
            )
        )
        or 0
    )


def _is_locked(user: User, now: datetime) -> bool:
    """
    잠금 여부.

    `LOGIN_LOCK_MINUTES` 가 0 이면 시간으로 풀리지 않으므로 실패 횟수가 기준이다.
    0 보다 크면 그 시각까지만 잠긴다.
    """

    locked_until = as_utc(user.locked_until)

    if locked_until is not None:
        return locked_until > now

    return user.failed_login_count >= settings.LOGIN_MAX_FAILURES


def _should_become_dormant(db: Session, user: User, now: datetime) -> bool:
    reference = as_utc(user.last_login_at) or as_utc(user.created_at)

    if reference is None:
        return False

    if now - reference <= timedelta(days=settings.DORMANT_AFTER_DAYS):
        return False

    # 관리자가 전부 휴면이 되면 아무도 풀 수 없다.
    if user.role == UserRole.ADMIN and active_admin_count(db) <= 1:
        return False

    return True


def _temp_password_expired(user: User, now: datetime) -> bool:
    if not user.must_change_password:
        return False

    issued_at = as_utc(user.password_changed_at)

    if issued_at is None:
        return False

    return now - issued_at > timedelta(hours=settings.TEMP_PASSWORD_VALID_HOURS)


def _record_login(
    db: Session,
    *,
    user: Optional[User],
    status: str,
    error_code: Optional[ErrorCode] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> None:
    """
    로그인 시도 기록.

    이메일은 남기지 않는다. 계정을 못 찾은 실패는 actor 없이 남아
    관리자 화면에서 "unknown" 으로 보인다.
    """

    audit_service.record(
        db,
        action=AuditAction.LOGIN,
        entity_type="User",
        entity_id=user.id if user else None,
        actor_id=user.id if user else None,
        status=status,
        error_code=error_code.value if error_code else None,
        ip_address=ip_address,
        user_agent=user_agent,
    )


# =========================================================
# 로그인
# =========================================================

def authenticate(
    db: Session,
    email: str,
    password: str,
    *,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> User:
    """
    로그인 판정.

    **계정 상태는 비밀번호가 맞은 뒤에만 알려준다.** 먼저 알려주면 비밀번호를
    모르는 사람이 "이 이메일은 등록돼 있다" 를 알아내는 계정 열거가 된다.
    """

    now = datetime.now(timezone.utc)
    user = db.scalar(select(User).where(User.email == email.lower()))

    def reject(code: ErrorCode, message: str, status_code: int) -> APIError:
        _record_login(
            db,
            user=user,
            status="FAILURE",
            error_code=code,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        db.commit()

        return APIError(code, message, status_code=status_code)

    # 1. 비밀번호 확인 — 계정 존재 여부를 노출하지 않기 위해 동일한 오류를 반환한다.
    if user is None or not verify_password(password, user.hashed_password):
        if user is not None:
            user.failed_login_count += 1

            if user.failed_login_count == settings.LOGIN_MAX_FAILURES:
                if settings.LOGIN_LOCK_MINUTES:
                    user.locked_until = now + timedelta(
                        minutes=settings.LOGIN_LOCK_MINUTES
                    )

                audit_service.record(
                    db,
                    action=AuditAction.ACCOUNT_LOCKED,
                    entity_type="User",
                    entity_id=user.id,
                    actor_id=user.id,
                    detail={"failed_login_count": user.failed_login_count},
                    ip_address=ip_address,
                    user_agent=user_agent,
                )

        raise reject(
            ErrorCode.INVALID_CREDENTIALS,
            "이메일 또는 비밀번호가 올바르지 않습니다.",
            401,
        )

    # 2. 잠금 시간이 지났으면 먼저 푼다.
    locked_until = as_utc(user.locked_until)

    if locked_until is not None and locked_until <= now:
        user.locked_until = None
        user.failed_login_count = 0

    # 3. 계정 상태 — 비밀번호가 맞은 뒤에만 본다.
    if user.anonymized_at is not None:
        raise reject(
            ErrorCode.INVALID_CREDENTIALS,
            "이메일 또는 비밀번호가 올바르지 않습니다.",
            401,
        )

    if not user.is_active:
        raise reject(
            ErrorCode.INACTIVE_USER,
            "비활성화된 계정입니다. 관리자에게 문의하세요.",
            403,
        )

    if _is_locked(user, now):
        raise reject(
            ErrorCode.ACCOUNT_LOCKED,
            "로그인 실패가 반복되어 잠긴 계정입니다. 관리자에게 문의하세요.",
            403,
        )

    if user.dormant_at is None and _should_become_dormant(db, user, now):
        user.dormant_at = now

        audit_service.record(
            db,
            action=AuditAction.ACCOUNT_DORMANT,
            entity_type="User",
            entity_id=user.id,
            actor_id=user.id,
            detail={"dormant_after_days": settings.DORMANT_AFTER_DAYS},
            ip_address=ip_address,
            user_agent=user_agent,
        )

    if user.dormant_at is not None:
        raise reject(
            ErrorCode.ACCOUNT_DORMANT,
            "오래 접속하지 않아 휴면 처리된 계정입니다. 관리자에게 문의하세요.",
            403,
        )

    if _temp_password_expired(user, now):
        raise reject(
            ErrorCode.TEMP_PASSWORD_EXPIRED,
            "임시 비밀번호 사용 기간이 지났습니다. 관리자에게 재발급을 요청하세요.",
            403,
        )

    # 4. 성공
    user.failed_login_count = 0
    user.locked_until = None
    user.last_login_at = now

    _record_login(
        db,
        user=user,
        status="SUCCESS",
        ip_address=ip_address,
        user_agent=user_agent,
    )
    db.commit()

    return user


# =========================================================
# 계정 생성 / 조회
# =========================================================

def create_user(db: Session, payload: UserCreateRequest) -> User:
    validate_password(payload.password, email=payload.email, name=payload.name)

    user = User(
        email=payload.email.lower(),
        hashed_password=hash_password(payload.password),
        name=payload.name,
        role=payload.role,
        is_active=True,
        password_changed_at=datetime.now(timezone.utc),
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


# =========================================================
# 비밀번호 변경
# =========================================================

def _recent_password_hashes(db: Session, user: User) -> List[str]:
    if settings.PASSWORD_HISTORY_COUNT <= 0:
        return []

    return list(
        db.scalars(
            select(UserPasswordHistory.hashed_password)
            .where(UserPasswordHistory.user_id == user.id)
            .order_by(UserPasswordHistory.created_at.desc())
            .limit(settings.PASSWORD_HISTORY_COUNT)
        )
    )


def remember_password(db: Session, user: User, hashed_password: str) -> None:
    """바꾸기 전 비밀번호를 이력에 남기고 보관 개수만큼만 유지한다."""

    if settings.PASSWORD_HISTORY_COUNT <= 0:
        return

    db.add(UserPasswordHistory(user_id=user.id, hashed_password=hashed_password))
    db.flush()

    keep = list(
        db.scalars(
            select(UserPasswordHistory.id)
            .where(UserPasswordHistory.user_id == user.id)
            .order_by(UserPasswordHistory.created_at.desc())
            .limit(settings.PASSWORD_HISTORY_COUNT)
        )
    )

    stale = db.scalars(
        select(UserPasswordHistory).where(
            UserPasswordHistory.user_id == user.id,
            UserPasswordHistory.id.not_in(keep),
        )
    ).all()

    for row in stale:
        db.delete(row)


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

    # 현재 비밀번호가 맞는 것을 위에서 확인했으므로 평문 비교로 충분하다.
    # bcrypt 를 한 번 더 돌리면 요청당 0.3초가 그냥 늘어난다.
    # compare_digest 는 ASCII 가 아닌 문자열을 str 로 받지 못해 bytes 로 비교한다.
    if compare_digest(
        payload.new_password.encode("utf-8"),
        payload.current_password.encode("utf-8"),
    ):
        raise APIError(
            ErrorCode.SAME_PASSWORD,
            "이전과 다른 비밀번호를 정해 주세요.",
            status_code=422,
        )

    # 팀 회의 결정(2026-09-18): 이전 비밀번호 재사용 금지
    for previous in _recent_password_hashes(db, user):
        if verify_password(payload.new_password, previous):
            raise APIError(
                ErrorCode.PASSWORD_REUSED,
                "최근에 쓰던 비밀번호는 다시 쓸 수 없습니다.",
                status_code=422,
            )

    previous_hash = user.hashed_password

    user.hashed_password = hash_password(payload.new_password)
    user.password_changed_at = datetime.now(timezone.utc)
    user.must_change_password = False

    # 비밀번호를 바꾸면 다른 기기에 남은 Token 도 무효가 된다.
    user.token_version += 1

    remember_password(db, user, previous_hash)

    # detail 에 비밀번호를 담지 않는다.
    audit_service.record(
        db,
        action=AuditAction.PASSWORD_CHANGED,
        entity_type="User",
        entity_id=user.id,
        actor_id=user.id,
    )

    db.commit()
