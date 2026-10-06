# 계정 관리 및 로그인.
#
# 자유 회원가입은 제공하지 않는다.(03_BACKEND_PROMPT.md §10)
# 계정은 관리자 API 또는 seed script 로만 생성된다.

from datetime import datetime, timedelta, timezone
from functools import lru_cache
from secrets import compare_digest, token_urlsafe
from typing import List, Optional

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.enums import AuditAction, UserRole
from app.core.errors import APIError, ErrorCode, conflict, unauthorized
from app.core.password_policy import validate_password
from app.core.security import hash_password, verify_password
from app.models.audit_log import AuditLog
from app.models.base import as_utc
from app.models.user import User
from app.models.user_password_history import UserPasswordHistory
from app.schemas.auth import PasswordChangeRequest, UserCreateRequest
from app.services import audit_service

# 틀린 비밀번호 · 없는 계정 · 잠긴 계정이 모두 이 문구를 받는다. 잠긴 사람도 안내받도록
# 잠김 안내를 늘 함께 싣는다. 잠겼을 때만 붙이면 그것으로 잠김 여부가 드러난다.
INVALID_CREDENTIALS_MESSAGE = (
    "이메일 또는 비밀번호가 올바르지 않습니다. "
    "여러 번 틀려 잠겼다면 관리자에게 문의하세요."
)

# 비밀번호 변경 창구에서 현재 비밀번호를 기준만큼 틀려 Token 을 끊을 때의 문구.
PASSWORD_FAILURE_LOGOUT_MESSAGE = "현재 비밀번호를 여러 번 틀려 로그아웃했습니다. 다시 로그인해 주세요."


# =========================================================
# 공통
# =========================================================

def active_admin_count(db: Session, now: Optional[datetime] = None) -> int:
    """
    지금 로그인할 수 있는 관리자 수.

    실패 잠금된 관리자는 뺀다. 잠금 판정(User.is_locked_at)은 시각 비교가 있어 SQL 로 옮기면
    SQLite 의 시간대 처리가 PostgreSQL 과 달라진다. 관리자는 몇 명 안 되므로 불러와서 거른다.
    """

    now = now or datetime.now(timezone.utc)

    admins = db.scalars(
        select(User).where(
            User.role == UserRole.ADMIN,
            User.is_active.is_(True),
            User.dormant_at.is_(None),
            User.anonymized_at.is_(None),
        )
    )

    return sum(1 for admin in admins if not admin.is_locked_at(now))


def _is_locked(user: User, now: datetime) -> bool:
    """잠금 여부. 판정 규칙은 User.is_locked_at 한 곳에 있다(계정 응답의 is_locked 와 같은 기준)."""

    return user.is_locked_at(now)


def _should_become_dormant(db: Session, user: User, now: datetime) -> bool:
    reference = as_utc(user.last_login_at) or as_utc(user.created_at)

    if reference is None:
        return False

    if now - reference <= timedelta(days=settings.DORMANT_AFTER_DAYS):
        return False

    # 관리자가 전부 휴면이 되면 아무도 풀 수 없다. 잠긴 관리자는 풀어 줄 수 없으므로 세지 않는다.
    if user.role == UserRole.ADMIN and active_admin_count(db, now) <= 1:
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
) -> AuditLog:
    """
    로그인 시도 기록.

    이메일은 남기지 않는다. 계정을 못 찾은 실패는 actor 없이 남아
    관리자 화면에서 "unknown" 으로 보인다.
    """

    return audit_service.record(
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


@lru_cache(maxsize=1)
def _dummy_password_hash() -> str:
    """
    응답 시간을 맞추는 데만 쓰는 해시.

    없는 계정과 잠긴 계정은 비밀번호를 확인하지 않는다. bcrypt 비교(약 0.3초)를 건너뛰면
    응답이 눈에 띄게 빨라져 "이 이메일은 없다 / 잠겼다" 가 드러나므로 이 해시와 한 번 비교한다.
    처음 필요할 때 한 번만 만든다. import 때 만들면 서버 시작과 테스트가 그만큼 느려진다.
    """

    return hash_password(token_urlsafe(32))


def _clear_expired_lock(db: Session, user: User, now: datetime) -> None:
    """
    시간 잠금(LOGIN_LOCK_MINUTES > 0)이 지났으면 풀고 실패 횟수도 비운다. 안 비우면 횟수가 기준을
    넘은 채로 남아, 다시 틀려도 잠기지 않는다.

    **처음 읽은 잠금 시각이 그대로일 때만 푼다**(비교 후 교체). 잠금이 풀리는 순간 몰려 든 요청이
    저마다 읽은 "지난 잠금" 을 보고 조건 없이 횟수를 0 으로 되돌리면, 앞 요청들이 예약해 둔 횟수를
    지워 기준보다 많이 대조하고, 그사이 다시 걸린 잠금도 지운다. 그래서 하나의 요청만 풀고, 늦게 온
    요청은 아무것도 바꾸지 않는다. 어느 쪽이든 지금 값을 다시 읽어 그 값으로 잠금을 판정한다.

    커밋은 호출 측(authenticate)이 이번 시도 기록과 함께 한다.
    """

    seen = user.locked_until
    locked_until = as_utc(seen)

    if locked_until is None or locked_until > now:
        return

    # 읽은 값 그대로와 비교한다. SQLite 는 시간대 없이 돌려주므로 as_utc 로 바꾼 값을 쓰면
    # 저장된 값과 같게 맞지 않을 수 있다.
    db.execute(
        update(User)
        .where(User.id == user.id, User.locked_until == seen)
        .values(locked_until=None, failed_login_count=0)
        .execution_options(synchronize_session=False)
    )
    db.refresh(user)


def _reserve_login_attempt(db: Session, user: User) -> Optional[int]:
    """
    비밀번호를 대조하기 **전에** 실패 횟수를 1 올린다(시도 예약). 올린 뒤 횟수를 돌려준다.

    대조(bcrypt 약 0.3초)한 뒤에 세면, 그 사이 함께 들어온 요청이 모두 "아직 안 잠김" 을 보고
    대조까지 가서 기준(LOGIN_MAX_FAILURES)보다 훨씬 많이 맞혀 볼 수 있다. 조건을 건 UPDATE 하나로
    올리므로 동시에 몇 개가 들어와도 기준 횟수만큼만 예약된다. 이미 기준에 닿았으면 None 이다.

    파이썬에서 += 1 하면 동시에 들어온 요청이 같은 값을 읽어 횟수가 빠지므로 DB 에서 더한다.
    다른 요청이 바로 보도록 대조 전에 커밋하는데, 커밋은 호출 측(authenticate)이 이번 시도 기록과
    함께 한 번에 한다. 객체의 failed_login_count 는 다시 읽지 않는다(성공하면 _release_login_attempt 가 읽는다).
    """

    return db.execute(
        update(User)
        .where(
            User.id == user.id,
            User.failed_login_count < settings.LOGIN_MAX_FAILURES,
        )
        .values(failed_login_count=User.failed_login_count + 1)
        .returning(User.failed_login_count)
        .execution_options(synchronize_session=False)
    ).scalar_one_or_none()


def _release_login_attempt(db: Session, user: User) -> None:
    """
    비밀번호가 맞은 시도는 실패가 아니므로 예약한 1 을 되돌린다.

    되돌린 뒤 **실패 횟수와 잠금 시각만** 다시 읽는다. 성공 처리(authenticate 7단계)에서 두 값을
    비울 때 메모리 값이 낡아 있으면(이미 0 · None) 바뀐 것이 없다고 보고 UPDATE 에서 빠진다.

    계정 전체를 다시 읽으면 안 된다. 대조하는 사이 본인이 비밀번호를 바꿨으면(Token 버전 + 1)
    옛 비밀번호로 확인된 이 로그인이 새 버전으로 Token 을 받아, 바꾼 뒤에도 쓸 수 있게 된다.
    나머지 값(Token 버전 · 계정 상태)은 대조한 해시와 같은 때 읽은 값으로 둔다. 그사이 관리자가
    정지 · 임시 비밀번호 발급 · 강제 로그아웃을 했으면 Token 버전이 올라 이 로그인의 Token 은 401 이 된다.
    """

    db.execute(
        update(User)
        .where(User.id == user.id, User.failed_login_count > 0)
        .values(failed_login_count=User.failed_login_count - 1)
        .execution_options(synchronize_session=False)
    )
    db.refresh(user, ["failed_login_count", "locked_until"])


def _lock_if_limit_reached(
    db: Session,
    user: User,
    reserved: int,
    now: datetime,
    *,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> None:
    """
    틀린 시도가 기준 횟수째 예약이었으면 잠그고 커밋한다.

    예약은 원자적이라 기준 횟수째를 받는 요청은 하나뿐이다. 그래서 동시에 틀린 요청이 여러 개여도
    잠금은 한 번만 남는다. 잠긴 계정과 기준을 넘은 시도는 예약되지 않아 여기까지 오지 않는다.

    잠금 시각(LOGIN_LOCK_MINUTES > 0)은 실패 횟수가 아직 기준 이상일 때만 쓴다. 대조하는 사이
    관리자가 풀었으면(횟수 0) 다시 잠그지 않는다. 횟수와 잠금이 어긋난 상태가 생기지 않게 한다.
    잠그지 않는 틀린 시도는 대조 뒤에 아무것도 쓰지 않는다(authenticate 참고).
    """

    if reserved < settings.LOGIN_MAX_FAILURES:
        return

    locked = True

    if settings.LOGIN_LOCK_MINUTES:
        locked = bool(
            db.execute(
                update(User)
                .where(
                    User.id == user.id,
                    User.failed_login_count >= settings.LOGIN_MAX_FAILURES,
                )
                .values(locked_until=now + timedelta(minutes=settings.LOGIN_LOCK_MINUTES))
                .execution_options(synchronize_session=False)
            ).rowcount
        )

    if locked:
        audit_service.record(
            db,
            action=AuditAction.ACCOUNT_LOCKED,
            entity_type="User",
            entity_id=user.id,
            actor_id=user.id,
            detail={"failed_login_count": reserved},
            ip_address=ip_address,
            user_agent=user_agent,
        )

    db.commit()


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

    **실패 잠금은 비밀번호가 맞아도 알려주지 않는다.** 잠긴 계정은 비밀번호를 확인하지 않고
    틀린 비밀번호와 같은 401 을 준다. 잠김을 따로 알려주면 잠긴 뒤에도 계속 맞혀 보다가
    응답이 바뀌는 순간 정답을 알게 된다. 관리자는 감사 로그의 error_code(ACCOUNT_LOCKED)로 구분한다.

    **없는 계정 · 잠긴 계정 · 틀린 비밀번호는 같은 순서로 DB 에 쓴다.** 비밀번호를 대조하기 전에
    이번 시도 기록(과 있는 계정이면 시도 예약)을 한 번에 커밋하고, 대조 뒤에는 잠글 때 말고는 쓰지
    않는다. 커밋(디스크 기록)은 몇 ms 걸리므로, 있는 계정만 커밋을 더 하면 bcrypt 시간을 맞춰도
    응답 시간 차이로 계정이 있는지 드러난다.
    """

    now = datetime.now(timezone.utc)
    user = db.scalar(select(User).where(User.email == email.lower()))

    def invalid_credentials() -> APIError:
        return APIError(
            ErrorCode.INVALID_CREDENTIALS,
            INVALID_CREDENTIALS_MESSAGE,
            status_code=401,
        )

    # 1~4. 대조 전 — 무엇과 대조할지 정한다. 예약(reserved)이 없으면 진짜 해시와 대조하지 않는다.
    reserved: Optional[int] = None
    audit_code = ErrorCode.INVALID_CREDENTIALS

    if user is not None:
        # 2. 잠금 시간이 지났으면 먼저 푼다(_clear_expired_lock).
        _clear_expired_lock(db, user, now)

        # 3. 잠긴 계정 — 비밀번호는 확인하지 않는다.
        if _is_locked(user, now):
            audit_code = ErrorCode.ACCOUNT_LOCKED
        else:
            # 4. 시도 예약 — 비밀번호를 대조하기 전에 실패 횟수를 먼저 센다(_reserve_login_attempt).
            #    함께 들어온 다른 요청이 이미 기준을 채웠으면 예약되지 않는다. 잠긴 계정과 같게 거절한다.
            reserved = _reserve_login_attempt(db, user)

            if reserved is None:
                audit_code = ErrorCode.ACCOUNT_LOCKED

    # 이번 시도를 실패로 먼저 남기고 예약과 함께 커밋한다. 비밀번호가 맞으면 아래에서 고친다
    # (성공으로, 또는 계정 상태 오류 코드로).
    attempt = _record_login(
        db,
        user=user,
        status="FAILURE",
        error_code=audit_code,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    db.commit()

    # 1 · 3 · 4. 없는 계정 · 잠긴 계정 · 예약되지 않은 시도 — 가짜 해시와 한 번 비교해 있는 계정과
    #           같은 시간이 걸리게 하고, 틀린 비밀번호와 같은 응답을 준다.
    if user is None or reserved is None:
        verify_password(password, _dummy_password_hash())

        raise invalid_credentials()

    # 5. 비밀번호 확인 — 계정 존재 여부를 노출하지 않기 위해 동일한 오류를 반환한다.
    if not verify_password(password, user.hashed_password):
        _lock_if_limit_reached(
            db, user, reserved, now, ip_address=ip_address, user_agent=user_agent
        )

        raise invalid_credentials()

    _release_login_attempt(db, user)

    def reject(code: ErrorCode, message: str, status_code: int) -> APIError:
        attempt.error_code = code.value
        db.commit()

        return APIError(code, message, status_code=status_code)

    # 6. 계정 상태 — 비밀번호가 맞은 뒤에만 본다.
    if user.anonymized_at is not None:
        raise reject(ErrorCode.INVALID_CREDENTIALS, INVALID_CREDENTIALS_MESSAGE, 401)

    if not user.is_active:
        raise reject(
            ErrorCode.INACTIVE_USER,
            "비활성화된 계정입니다. 관리자에게 문의하세요.",
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

    # 7. 성공 — 미리 남긴 시도 기록을 성공으로 바꾼다.
    user.failed_login_count = 0
    user.locked_until = None
    user.last_login_at = now

    attempt.status = "SUCCESS"
    attempt.error_code = None
    db.commit()

    return user


# =========================================================
# 계정 생성 / 조회
# =========================================================

def create_user(
    db: Session,
    payload: UserCreateRequest,
    actor: Optional[User] = None,
) -> User:
    """
    계정 생성. 누가 만들었는지 감사 로그(USER_CREATED)에 남긴다.

    actor 는 만든 관리자다. 서버에서 직접 만드는 경로는 actor 없이 남는다.
    """

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

    # 감사 로그에 계정 id 가 필요해 먼저 보낸다. 이메일 중복도 여기서 걸린다.
    try:
        db.flush()
    except IntegrityError as error:
        db.rollback()

        raise conflict(
            ErrorCode.DUPLICATE_RESOURCE,
            "이미 등록된 이메일입니다.",
        ) from error

    # 이메일 · 이름은 남기지 않는다. 계정 id 와 역할만 남긴다.
    audit_service.record(
        db,
        action=AuditAction.USER_CREATED,
        entity_type="User",
        entity_id=user.id,
        actor_id=actor.id if actor else None,
        detail={"role": user.role.value},
    )

    db.commit()
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


def _password_change_failures(db: Session, user: User) -> int:
    """
    마지막 로그인(또는 비밀번호 변경) 뒤로 현재 비밀번호 확인에 실패한 시도 수. 감사 로그로 센다.

    실패는 어차피 감사 로그에 남기므로 따로 칸을 두지 않는다. 대조 중인 시도도 미리 남기므로
    (_reserve_password_attempt) 함께 들어온 요청도 바로 센다. 기준을 넘었는지만 알면 되므로
    최근 기록을 기준 횟수 + 1 개만 읽는다. 시각 비교는 파이썬에서 한다(SQLite 는 시간대 없이 돌려준다).
    """

    since = max(
        (
            value
            for value in (as_utc(user.last_login_at), as_utc(user.password_changed_at))
            if value is not None
        ),
        default=None,
    )

    recent = db.scalars(
        select(AuditLog.created_at)
        .where(
            AuditLog.action == AuditAction.PASSWORD_CHANGED,
            AuditLog.status == "FAILURE",
            AuditLog.actor_id == user.id,
        )
        .order_by(AuditLog.created_at.desc())
        .limit(settings.LOGIN_MAX_FAILURES + 1)
    ).all()

    return sum(1 for at in recent if since is None or as_utc(at) >= since)


def _reserve_password_attempt(
    db: Session,
    user: User,
    *,
    ip_address: Optional[str],
    user_agent: Optional[str],
) -> AuditLog:
    """
    현재 비밀번호를 대조하기 **전에** 이번 시도를 실패로 남기고 커밋한다(시도 예약).

    대조(bcrypt 약 0.3초)한 뒤에 남기면, 그 사이 함께 들어온 요청이 모두 "아직 기준 전" 을 보고
    대조까지 가서 기준보다 많이 맞혀 볼 수 있다. 결과가 나오면 이 기록을 고친다
    (맞으면 성공으로, 이전 비밀번호라 거절되면 지운다).
    """

    attempt = audit_service.record(
        db,
        action=AuditAction.PASSWORD_CHANGED,
        entity_type="User",
        entity_id=user.id,
        actor_id=user.id,
        status="FAILURE",
        error_code=ErrorCode.INVALID_CURRENT_PASSWORD.value,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    db.commit()

    return attempt


def _logout_after_failures(
    db: Session,
    user: User,
    token_version: int,
    failures: int,
    *,
    ip_address: Optional[str],
    user_agent: Optional[str],
) -> APIError:
    """
    현재 비밀번호를 기준(LOGIN_MAX_FAILURES)만큼 틀렸다. 그 계정의 Token 을 모두 끊고 401 을 만든다.

    토큰만 가진 사람이 이 창구로 현재 비밀번호를 끝없이 맞혀 보지 못하게 하기 위해서다.
    계정은 잠그지 않는다. 다시 로그인하면 되고, 로그인 쪽에는 이미 실패 잠금이 있다.

    이 요청의 Token 버전일 때만 올린다. 함께 들어온 요청이 이미 끊었으면 다시 올리지 않으므로
    LOGOUT_ALL 은 한 번만 남는다.
    """

    revoked = db.execute(
        update(User)
        .where(User.id == user.id, User.token_version == token_version)
        .values(token_version=User.token_version + 1)
        .execution_options(synchronize_session=False)
    ).rowcount

    if revoked:
        audit_service.record(
            db,
            action=AuditAction.LOGOUT_ALL,
            entity_type="User",
            entity_id=user.id,
            actor_id=user.id,
            detail={
                "reason": "PASSWORD_CHANGE_FAILURES",
                "failed_attempts": min(failures, settings.LOGIN_MAX_FAILURES),
            },
            ip_address=ip_address,
            user_agent=user_agent,
        )

    db.commit()

    return APIError(
        ErrorCode.UNAUTHORIZED,
        PASSWORD_FAILURE_LOGOUT_MESSAGE,
        status_code=401,
    )


def change_password(
    db: Session,
    user: User,
    payload: PasswordChangeRequest,
    *,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> None:
    """
    본인 비밀번호 변경.

    현재 비밀번호를 함께 받는다. Token 만 훔친 사람이 비밀번호를 바꿔
    계정을 가져가는 것을 막는다.

    현재 비밀번호가 틀리면 401 이 아니라 400 이다. Frontend 는 401 을 로그인 만료로 보고
    로그인 화면으로 보내므로(client.ts isUnauthorized), 입력 실수로 쫓겨나지 않게 한다.
    단, 정해진 횟수만큼 틀리면 Token 을 끊고 401 을 준다(_logout_after_failures).
    """

    # 이 요청 Token 의 버전(get_current_user 가 같은지 확인했다). 대조하는 사이 다른 요청이
    # Token 을 끊었는지 저장할 때 다시 본다.
    token_version = user.token_version

    # 새 비밀번호 규칙 · 같은 비밀번호 검사는 현재 비밀번호를 확인하기 전에 한다.
    # 확인한 뒤에 하면 "현재 비밀번호가 맞으면 422, 틀리면 400" 이 되어, 비밀번호를 바꾸지 않고도
    # 정답인지 알아내는 수단이 된다. 이 두 검사는 현재 비밀번호와 관계없이 같은 답을 준다.
    validate_password(payload.new_password, email=user.email, name=user.name)

    # 입력한 두 값끼리의 비교라 평문 비교로 충분하다(bcrypt 를 돌리면 요청당 0.3초가 그냥 늘어난다).
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

    attempt = _reserve_password_attempt(
        db, user, ip_address=ip_address, user_agent=user_agent
    )
    failures = _password_change_failures(db, user)

    # 함께 들어온 다른 요청들이 이미 기준을 채웠다. 대조하지 않고 끊는다(대조하면 기준을 넘어 맞혀 보는 것이 된다).
    if failures > settings.LOGIN_MAX_FAILURES:
        attempt.error_code = ErrorCode.UNAUTHORIZED.value

        raise _logout_after_failures(
            db, user, token_version, failures, ip_address=ip_address, user_agent=user_agent
        )

    if not verify_password(payload.current_password, user.hashed_password):
        if failures < settings.LOGIN_MAX_FAILURES:
            raise APIError(
                ErrorCode.INVALID_CURRENT_PASSWORD,
                "현재 비밀번호가 올바르지 않습니다.",
                status_code=400,
            )

        raise _logout_after_failures(
            db, user, token_version, failures, ip_address=ip_address, user_agent=user_agent
        )

    # 팀 회의 결정(2026-09-18): 이전 비밀번호 재사용 금지
    # 이전 비밀번호를 알려 주는 셈이 되므로 현재 비밀번호를 확인한 뒤에만 검사한다.
    # 현재 비밀번호는 맞았으므로 미리 남긴 실패 기록은 지운다(예전처럼 기록하지 않는다).
    for previous in _recent_password_hashes(db, user):
        if verify_password(payload.new_password, previous):
            db.delete(attempt)
            db.commit()

            raise APIError(
                ErrorCode.PASSWORD_REUSED,
                "최근에 쓰던 비밀번호는 다시 쓸 수 없습니다.",
                status_code=422,
            )

    previous_hash = user.hashed_password
    was_temporary = user.must_change_password

    # Token 버전이 그대로일 때만 바꾼다. 대조하는 사이 함께 보낸 다른 추측이 기준을 채워 Token 을
    # 끊었으면(또는 강제 로그아웃 등) 바꾸지 않는다. 이미 끊긴 Token 으로 계정을 가져가지 못하게 한다.
    # 비밀번호를 바꾸면 다른 기기에 남은 Token 도 무효가 된다(버전 + 1).
    changed = db.execute(
        update(User)
        .where(User.id == user.id, User.token_version == token_version)
        .values(
            hashed_password=hash_password(payload.new_password),
            password_changed_at=datetime.now(timezone.utc),
            must_change_password=False,
            token_version=User.token_version + 1,
        )
        .execution_options(synchronize_session=False)
    ).rowcount

    if not changed:
        attempt.error_code = ErrorCode.UNAUTHORIZED.value
        db.commit()

        # 실패 때문에 끊긴 것이면 그 응답과 같은 문구를 준다. 다르면 이 추측이 맞았다는 것이 드러난다.
        if _password_change_failures(db, user) >= settings.LOGIN_MAX_FAILURES:
            raise APIError(
                ErrorCode.UNAUTHORIZED, PASSWORD_FAILURE_LOGOUT_MESSAGE, status_code=401
            )

        raise unauthorized("다시 로그인해 주세요.")

    # 미리 남긴 시도 기록을 성공으로 바꾼다. detail 에 비밀번호를 담지 않는다.
    attempt.status = "SUCCESS"
    attempt.error_code = None

    # 임시 비밀번호는 이력에 남기지 않는다. 사람이 정한 비밀번호가 아니라 이력 칸만 차지한다.
    # 임시 비밀번호로 바뀌기 전 비밀번호는 발급할 때 남겼다(account_service.issue_temporary_password).
    if not was_temporary:
        remember_password(db, user, previous_hash)

    db.commit()
    db.refresh(user)
