# 회원가입 — 이메일 인증번호 → 대기 신청 → 관리자 승인(2026-11-02, API_CONTRACT 3절 '회원가입').
#
# 지키는 것
#  - 계정이나 대기 신청이 이미 있는 이메일도 새 이메일과 **같은 DB 작업**(인증번호 행 만들기 · 고치기)을 하고 같은 응답을 받는다.
#    다른 것은 메일을 보내느냐 하나이고, 메일은 요청과 떨어진 전용 스레드에서 보낸다(queue_code_mail). 그래서 응답 ·
#    요청 수 제한 · 응답 시간으로 계정 존재가 드러나지 않는다. 번호를 받지 못하니 그 이메일로는 확인 토큰까지 갈 수 없다.
#  - 인증번호 · 확인 토큰 · 비밀번호 원문은 DB · 로그 · 감사 기록 · 오류 문구 어디에도 남기지 않는다(해시만).
#    이메일 · 이름도 로그 · 감사 기록에 넣지 않는다(로그인 실패 기록에 이메일을 넣지 않는 것과 같은 이유).
#  - 횟수 제한은 조건을 건 UPDATE 로 센다(파이썬에서 읽고 더하지 않는다). 번호 대조는 대조하기 **전에** 틀린 횟수를 먼저
#    올려 둔다. 동시에 몰려 와도 기준을 넘지 않는다(user_service._reserve_login_attempt 와 같은 방식).
#  - users 행은 관리자가 승인할 때만 만든다(user_service.add_user — 관리자 계정 생성과 같은 길).

import hashlib
import hmac
import logging
import math
import secrets
import threading
import time
import uuid
from collections import defaultdict, deque
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Deque, Dict, List, Optional, Tuple

from sqlalchemy import case, delete, func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.adapters.mail_adapter import MailMessage, failure_cause, get_mail_sender
from app.core.config import settings
from app.core.database import SessionLocal
from app.core.email_address import canonical_email
from app.core.enums import AuditAction, SignupRequestStatus, UserRole
from app.core.errors import APIError, ErrorCode, conflict, not_found
from app.core.password_policy import validate_password
from app.core.security import hash_password
from app.models.base import as_utc
from app.models.signup import SignupEmailCode, SignupRequest
from app.models.user import User
from app.services import audit_service, user_service

logger = logging.getLogger(__name__)

# ---------------------------------------------------------
# 팀과 정한 숫자(11/02 이경진 님께 보낸 답). 서버마다 바꿀 값이 아니라 설정이 아닌 상수다. 시험은 이 값을 바꿔 본다.
# ---------------------------------------------------------
CODE_DIGITS = 6
CODE_TTL = timedelta(minutes=5)
RESEND_INTERVAL = timedelta(seconds=60)
# '하루' 는 달력 날짜가 아니라 그 이메일의 첫 보내기부터 24시간이다.
SEND_WINDOW = timedelta(hours=24)
DAILY_SEND_LIMIT = 5
MAX_CODE_ATTEMPTS = 5
TOKEN_TTL = timedelta(minutes=30)

# IP 당 시간당 요청 수. 확인(verify)은 합의 표에 없어 스펙에서 정했다 — 남의 이메일 번호를 여러 이메일에 걸쳐 맞혀 보는 것을 늦춘다.
IP_WINDOW_SECONDS = 3600.0
SEND_IP_LIMIT = 20
VERIFY_IP_LIMIT = 30

# 보관 기한(스펙에서 정함). 인증번호 행은 마지막 보내기에서 24시간 뒤면 번호 · 토큰 · 하루 횟수가 모두 끝나 있다.
CODE_ROW_KEEP = SEND_WINDOW
PENDING_KEEP = timedelta(days=14)
DECIDED_KEEP = timedelta(days=30)

# 감사 기록의 entity_type.
CODE_ENTITY = "SignupEmailCode"
REQUEST_ENTITY = "SignupRequest"

DISABLED_MESSAGE = "회원가입이 꺼져 있습니다. 관리자에게 계정을 요청해 주세요."
DOMAIN_NOT_ALLOWED_MESSAGE = "이 이메일 도메인으로는 가입할 수 없습니다. 기관 이메일을 써 주세요."
RATE_LIMITED_MESSAGE = "요청이 너무 잦습니다. 잠시 후 다시 시도해 주세요."
CODE_MISMATCH_MESSAGE = "인증번호가 맞지 않습니다."
CODE_MISMATCH_LAST_MESSAGE = "인증번호를 여러 번 틀렸습니다. 새 인증번호를 받아 주세요."
CODE_EXPIRED_MESSAGE = "인증번호가 만료되었거나 더 쓸 수 없습니다. 새 인증번호를 받아 주세요."
TOKEN_INVALID_MESSAGE = "인증이 만료되었습니다. 처음부터 다시 해 주세요."
DUPLICATE_MESSAGE = "이미 가입했거나 승인을 기다리는 이메일입니다."
ALREADY_DECIDED_MESSAGE = "이미 처리한 가입 신청입니다."
NOT_FOUND_MESSAGE = "가입 신청을 찾을 수 없습니다."

MAIL_SUBJECT = "[I-SPOT] 회원가입 인증번호"


def _mail_body(code: str) -> str:
    return (
        f"I-SPOT 회원가입 인증번호: {code}\n"
        "\n"
        f"{int(CODE_TTL.total_seconds() // 60)}분 안에 입력해 주세요.\n"
        "요청하지 않았다면 이 메일은 무시하셔도 됩니다.\n"
    )


# =========================================================
# 공통
# =========================================================

def _now() -> datetime:
    return datetime.now(timezone.utc)


def _seconds(delta: timedelta) -> int:
    return int(delta.total_seconds())


def normalize_email(email: str) -> str:
    """요청 모델이 이미 정규형으로 맞춰 온다(schemas/signup.py). 서비스를 직접 부를 때도 같은 꼴이 되게 한 번 더 맞춘다."""

    return canonical_email(email)


def _code_hash(email: str, code: str) -> str:
    """
    인증번호 해시. 번호는 경우의 수가 100만뿐이라 그냥 SHA-256 이면 DB 사본만으로 바로 역산된다.

    서버 비밀키(JWT_SECRET_KEY)를 섞은 HMAC 이라 DB 만으로는 풀 수 없다. 운영에서는 이 키가 공개 안 된 32자 이상으로
    강제된다(config._require_private_jwt_secret_in_production). 앞말로 용도를 나눠 토큰 서명과 섞이지 않게 한다.
    이메일을 같이 넣어 같은 번호라도 이메일마다 해시가 다르다.
    """

    message = b"ispot-signup-code\0" + email.encode("utf-8") + b"\0" + code.encode("ascii")

    return hmac.new(settings.JWT_SECRET_KEY.encode("utf-8"), message, hashlib.sha256).hexdigest()


def _token_hash(token: str) -> str:
    """확인 토큰은 경우의 수가 커서(32바이트) 비밀키 없이 SHA-256 으로 충분하다."""

    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _new_code() -> str:
    return f"{secrets.randbelow(10 ** CODE_DIGITS):0{CODE_DIGITS}d}"


def _ensure_enabled() -> None:
    if not settings.SIGNUP_ENABLED:
        raise APIError(ErrorCode.SIGNUP_DISABLED, DISABLED_MESSAGE, status_code=503)


def _rate_limited(retry_after_seconds: int) -> APIError:
    return APIError(
        ErrorCode.RATE_LIMITED,
        RATE_LIMITED_MESSAGE,
        status_code=429,
        details={"retry_after_seconds": max(1, retry_after_seconds)},
    )


def _ceil_seconds(delta: timedelta) -> int:
    return math.ceil(delta.total_seconds())


# =========================================================
# IP 당 요청 수 (프로세스 메모리)
# =========================================================
#
# 법령 질문 창구(law_guide_service._allow_call)와 같은 방식이다. 데모 서버는 uvicorn 프로세스 하나라 정확하다
# (deploy/web-deploy.sh, --workers 없음). 서버를 다시 켜면 비워지고, 프로세스를 여럿으로 늘리면 프로세스마다 따로 센다 —
# 그때는 DB 로 옮긴다. 이메일 쪽 제한(60초 · 하루 5번 · 틀림 5번)은 DB 라 다시 켜도 그대로다.

# 이보다 많은 IP 를 기억하게 되면 1시간 넘게 조용한 IP 를 지운다(여러 IP 로 쏟아부어 메모리가 늘지 않게).
_IP_TABLE_PRUNE_AT = 4096


class _IpLimits:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.calls: Dict[Tuple[str, str], Deque[float]] = defaultdict(deque)


_ip_limits = _IpLimits()


def reset_limits() -> None:
    """시험용. IP 별 요청 기록을 비운다."""

    global _ip_limits
    _ip_limits = _IpLimits()


def _take_ip_slot(kind: str, ip: Optional[str], limit: int) -> Optional[int]:
    """지난 1시간 안의 kind 요청이 limit 미만이면 이번 요청을 세고 None. 넘으면 다시 될 때까지 남은 초."""

    now = time.monotonic()
    limits = _ip_limits

    with limits.lock:
        if len(limits.calls) > _IP_TABLE_PRUNE_AT:
            for key in [key for key, calls in limits.calls.items() if not calls or now - calls[-1] >= IP_WINDOW_SECONDS]:
                del limits.calls[key]

        calls = limits.calls[(kind, ip or "unknown")]

        while calls and now - calls[0] >= IP_WINDOW_SECONDS:
            calls.popleft()

        if len(calls) >= limit:
            return math.ceil(IP_WINDOW_SECONDS - (now - calls[0]))

        calls.append(now)

    return None


def _check_ip(kind: str, ip: Optional[str], limit: int) -> None:
    retry_after = _take_ip_slot(kind, ip, limit)

    if retry_after is not None:
        # 이메일 · IP 는 남기지 않는다(접속 IP 는 서버 접속 기록에 이미 있다). 감사 기록도 쓰지 않는다 — 마구 보내는
        # 요청 하나하나가 DB 쓰기가 되지 않게.
        logger.warning("회원가입 요청 수 제한(IP). kind=%s", kind)

        raise _rate_limited(retry_after)


# =========================================================
# 보관 기한
# =========================================================

def purge_expired(db: Session, now: Optional[datetime] = None) -> None:
    """
    보관 기한이 지난 행을 지우고 커밋한다. 서버에 예약 작업이 없어 보내기 요청과 관리자 목록 · 승인 · 거절 때 부른다
    (휴면을 로그인 때 계산하는 것과 같은 방식). 감사 기록은 지우지 않는다(이메일 · 이름이 없다).
    """

    now = now or _now()

    db.execute(
        delete(SignupEmailCode)
        .where(SignupEmailCode.last_sent_at < now - CODE_ROW_KEEP)
        .execution_options(synchronize_session=False)
    )
    db.execute(
        delete(SignupRequest)
        .where(
            SignupRequest.status == SignupRequestStatus.PENDING,
            SignupRequest.created_at < now - PENDING_KEEP,
        )
        .execution_options(synchronize_session=False)
    )
    db.execute(
        delete(SignupRequest)
        .where(
            SignupRequest.status != SignupRequestStatus.PENDING,
            SignupRequest.decided_at < now - DECIDED_KEEP,
        )
        .execution_options(synchronize_session=False)
    )
    db.commit()


# =========================================================
# 공개 창구
# =========================================================

@dataclass(frozen=True)
class CodeSendResult:
    """
    보내기 결과. 응답에는 쓰지 않는다.

    mail 이 None 이면 보내지 않는다(계정이나 대기 신청이 이미 있는 이메일). 그래도 메일 일은 똑같이 하나 넣는다(queue_code_mail).
    code_hash 는 이 번호의 해시다. 대기열에서 차례가 왔을 때 아직 쓸 수 있는 번호인지 본다(Codex #139 L2).
    """

    code_id: uuid.UUID
    code_hash: str
    mail: Optional[MailMessage]


def _email_is_taken(db: Session, email: str) -> bool:
    """
    계정이 있거나 대기 신청이 있는 이메일인가. 새 이메일이든 아니든 같은 조회 둘을 한다.

    계정은 user_service.email_is_registered 로 본다(대소문자 · 유니코드 도메인만 다른 옛 계정도 같게, Codex #139 M2).
    대기 신청은 회원가입 창구가 늘 같은 꼴(ASCII 소문자, schemas/signup.py)로 넣어 그대로 비교한다.
    """

    has_user = user_service.email_is_registered(db, email)
    has_pending = db.scalar(
        select(func.count())
        .select_from(SignupRequest)
        .where(SignupRequest.email == email, SignupRequest.status == SignupRequestStatus.PENDING)
    ) or 0

    return bool(has_user or has_pending)


def _domain_allowed(email: str) -> bool:
    allowed = settings.SIGNUP_ALLOWED_EMAIL_DOMAINS

    if not allowed:
        return True

    return email.rsplit("@", 1)[-1] in allowed


def _send_limit_retry_after(row: SignupEmailCode, now: datetime) -> int:
    """막힌 보내기가 다시 될 때까지 남은 초. 60초 간격과 하루 횟수 중 늦은 쪽이다."""

    waits = [as_utc(row.last_sent_at) + RESEND_INTERVAL - now]
    window_started = as_utc(row.window_started_at)

    if window_started + SEND_WINDOW > now and row.send_count >= DAILY_SEND_LIMIT:
        waits.append(window_started + SEND_WINDOW - now)

    return _ceil_seconds(max(waits))


def send_code(
    db: Session,
    email: str,
    *,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    now: Optional[datetime] = None,
) -> CodeSendResult:
    """
    인증번호를 만들어 해시를 저장한다. 메일은 보내지 않고 돌려준다 — 호출 측이 queue_code_mail 로 넣는다.

    막히면 429(60초 간격 · 하루 횟수 · IP). 계정 · 대기 신청이 있는 이메일도 똑같이 번호를 만들고 똑같이 막힌다.
    """

    _ensure_enabled()

    email = normalize_email(email)

    if not _domain_allowed(email):
        raise APIError(ErrorCode.SIGNUP_EMAIL_DOMAIN_NOT_ALLOWED, DOMAIN_NOT_ALLOWED_MESSAGE, status_code=422)

    _check_ip("send", ip_address, SEND_IP_LIMIT)

    now = now or _now()
    purge_expired(db, now)

    taken = _email_is_taken(db, email)
    live_hash = db.scalar(
        select(SignupEmailCode.code_hash).where(
            SignupEmailCode.email == email,
            SignupEmailCode.code_expires_at > now,
        )
    )
    code = _new_code()
    code_hash = _code_hash(email, code)

    # 지금 살아 있는 번호를 또 뽑으면 앞 메일의 번호가 그대로 맞아 '새로 보내면 앞 번호 무효' 가 깨진다(Codex #139 L4).
    while code_hash == live_hash:
        code = _new_code()
        code_hash = _code_hash(email, code)

    window_over = SignupEmailCode.window_started_at <= now - SEND_WINDOW

    # 60초가 지났고 · 하루 횟수가 남았거나 하루가 지났을 때만 새 번호를 쓴다. SET 의 오른쪽은 고치기 전 값을 본다
    # (PostgreSQL · SQLite 모두). 앞 번호는 덮어써 무효가 되고, 틀린 횟수도 0 부터 센다. 이미 받은 확인 토큰은 두는데,
    # 토큰은 '이 메일함 주인' 이라는 증명이라 새 번호와 상관없다.
    code_id = db.execute(
        update(SignupEmailCode)
        .where(
            SignupEmailCode.email == email,
            SignupEmailCode.last_sent_at <= now - RESEND_INTERVAL,
            or_(window_over, SignupEmailCode.send_count < DAILY_SEND_LIMIT),
        )
        .values(
            code_hash=code_hash,
            code_expires_at=now + CODE_TTL,
            failed_attempts=0,
            last_sent_at=now,
            window_started_at=case((window_over, now), else_=SignupEmailCode.window_started_at),
            send_count=case((window_over, 1), else_=SignupEmailCode.send_count + 1),
            updated_at=now,
        )
        .returning(SignupEmailCode.id)
        .execution_options(synchronize_session=False)
    ).scalar_one_or_none()

    if code_id is None:
        row = db.scalar(select(SignupEmailCode).where(SignupEmailCode.email == email))

        if row is not None:
            db.rollback()
            logger.warning("회원가입 요청 수 제한(이메일).")

            raise _rate_limited(_send_limit_retry_after(row, now))

        row = SignupEmailCode(
            email=email,
            code_hash=code_hash,
            code_expires_at=now + CODE_TTL,
            failed_attempts=0,
            last_sent_at=now,
            window_started_at=now,
            send_count=1,
        )
        db.add(row)

        try:
            db.flush()
        except IntegrityError:
            # 같은 이메일의 첫 보내기가 동시에 들어와 다른 요청이 먼저 넣었다. 그 요청이 방금 보냈으니 60초 간격과 같은 응답이다.
            db.rollback()
            logger.warning("회원가입 요청 수 제한(이메일).")

            raise _rate_limited(_seconds(RESEND_INTERVAL)) from None

        code_id = row.id

    audit_service.record(
        db,
        action=AuditAction.SIGNUP_CODE_SENT,
        entity_type=CODE_ENTITY,
        entity_id=code_id,
        # SKIPPED: 계정이나 대기 신청이 있어 보내지 않음. 관리자만 보는 기록이라 둔다(남용 살피기).
        detail={"mail": "SKIPPED" if taken else "QUEUED"},
        ip_address=ip_address,
        user_agent=user_agent,
    )
    db.commit()

    mail = None if taken else MailMessage(to=email, subject=MAIL_SUBJECT, body=_mail_body(code))

    return CodeSendResult(code_id=code_id, code_hash=code_hash, mail=mail)


# ---------------------------------------------------------
# 메일 보내기 — 전용 스레드
# ---------------------------------------------------------
#
# FastAPI BackgroundTasks 로 보내지 않는다. Starlette 는 응답을 보낸 뒤 같은 요청 처리 안에서 백그라운드 작업을 기다려
# (starlette/responses.py), 메일을 다 보낼 때까지 그 연결이 붙잡힌다. 그러면 같은 연결로 보낸 다음 요청이 SES 호출 시간만큼 늦어져
# '메일을 보냈는지'(= 새 이메일인지)가 드러나고, 느린 SES 호출이 요청 처리와 같은 스레드 풀을 차지한다(스펙 보완 사항 R1).
# 그래서 전용 스레드에 넣고 바로 돌아온다. 대기가 MAIL_QUEUE_LIMIT 를 넘으면 넣지 않는다(쏟아부어도 메모리가 늘지 않게).
#
# 보낼 메일이 없는 이메일(계정 · 대기 신청이 있음)도 **같은 일 하나**를 넣고, 일 하나는 보내든 안 보내든 MAIL_JOB_SECONDS 동안
# 일꾼을 붙잡는다. 새 이메일만 대기 칸을 쓰거나 일꾼을 오래 붙잡으면, 자기 주소로 보낸 메일이 늦게 오거나(일꾼이 바쁨)
# 안 오는(대기가 참) 것으로 그 사이에 보낸 다른 주소의 가입 여부가 드러난다(Codex #139 M1). SES 호출이 MAIL_JOB_SECONDS 보다
# 오래 걸리면(제한 시간 · 재시도) 그만큼은 차이가 남는다 — 알려진 한계.

MAIL_WORKERS = 2
MAIL_QUEUE_LIMIT = 100
# SES 샌드박스는 초당 1통이라 일꾼 2개 × 2초면 그 한도와 같다. 시험은 0 으로 바꾼다.
MAIL_JOB_SECONDS = 2.0

_mail_pool = ThreadPoolExecutor(max_workers=MAIL_WORKERS, thread_name_prefix="signup-mail")
_mail_idle = threading.Condition()
_mail_pending = 0


def _record_mail_failure(
    result: CodeSendResult,
    provider: str,
    cause: str,
    *,
    ip_address: Optional[str],
    user_agent: Optional[str],
) -> None:
    """메일 실패 감사 기록. 요청과 다른 스레드에서도 쓰므로 세션을 따로 연다. 기록이 실패해도 올리지 않는다."""

    logger.warning("회원가입 인증번호 메일을 보내지 못했습니다. provider=%s cause=%s", provider, cause)

    db = SessionLocal()

    try:
        audit_service.record(
            db,
            action=AuditAction.SIGNUP_CODE_SENT,
            entity_type=CODE_ENTITY,
            entity_id=result.code_id,
            status="FAILURE",
            error_code=ErrorCode.MAIL_SEND_FAILED.value,
            detail={"provider": provider, "cause": cause},
            ip_address=ip_address,
            user_agent=user_agent,
        )
        db.commit()
    except Exception as audit_error:  # noqa: BLE001
        logger.warning("메일 실패 감사 기록을 남기지 못했습니다. type=%s", type(audit_error).__name__)
    finally:
        db.close()


def _code_still_usable(result: CodeSendResult) -> bool:
    """
    차례가 왔을 때 이 번호를 아직 쓸 수 있는가 — 5분 안이고, 새 번호로 바뀌지 않았고, 맞히거나 기준만큼 틀리지 않았다.

    대기열에서 기다리는 사이 쓸 수 없게 된 번호를 보내면 받은 사람은 맞는 번호를 넣고도 '만료' 를 받는다(Codex #139 L2).
    이미 SES 로 넘긴 메일이 늦게 도착하는 것은 여기서 막을 수 없다. 조회가 실패하면 보내지 않는다.
    """

    db = SessionLocal()

    try:
        row = db.execute(
            select(
                SignupEmailCode.code_hash,
                SignupEmailCode.code_expires_at,
                SignupEmailCode.failed_attempts,
            ).where(SignupEmailCode.id == result.code_id)
        ).one_or_none()
    except Exception as error:  # noqa: BLE001
        logger.warning("회원가입 인증번호 상태를 읽지 못해 메일을 보내지 않습니다. type=%s", type(error).__name__)

        return False
    finally:
        db.close()

    if row is None:
        return False

    code_hash, expires, attempts = row

    return (
        code_hash == result.code_hash
        and expires is not None
        and as_utc(expires) > _now()
        and attempts < MAX_CODE_ATTEMPTS
    )


def deliver_code_mail(
    result: CodeSendResult,
    *,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> None:
    """
    인증번호 메일을 보낸다(메일 전용 스레드에서). 보낼 메일이 없어도 같은 조회를 한다(일 하나의 일을 같게).

    실패해도 다시 올리지 않는다 — 응답은 이미 나갔고, 올리면 예외 문구(받는 주소가 들 수 있다)가 찍힌다.
    감사 기록(FAILURE · MAIL_SEND_FAILED)과 경고 로그에는 실패 이유 코드만 남긴다.
    """

    usable = _code_still_usable(result)

    if result.mail is None:
        return

    if not usable:
        logger.info("회원가입 인증번호가 보내기 전에 쓸 수 없게 되어 보내지 않았습니다.")

        return

    sender = get_mail_sender()

    try:
        sender.send(result.mail)
    except Exception as error:  # noqa: BLE001 — 어떤 실패든 문구 없이 코드만 남긴다
        _record_mail_failure(
            result, sender.name, failure_cause(error), ip_address=ip_address, user_agent=user_agent
        )


def queue_code_mail(
    result: CodeSendResult,
    *,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> None:
    """
    메일 일을 전용 스레드에 넣고 바로 돌아온다. 보낼 메일이 없는 이메일(계정 · 대기 신청이 있음)도 같은 일 하나를 넣는다.

    대기가 MAIL_QUEUE_LIMIT 에 닿았으면 넣지 않는다(응답은 그대로 202 — 60초 뒤 다시 보내면 된다). 그때는 감사 기록 없이
    서버 로그 경고만 남긴다. 새 이메일만 감사 기록을 쓰면 요청 처리 시간이 갈린다.
    """

    global _mail_pending

    with _mail_idle:
        full = _mail_pending >= MAIL_QUEUE_LIMIT

        if not full:
            _mail_pending += 1

    if full:
        logger.warning("회원가입 메일 대기가 가득 차 넣지 못했습니다. limit=%s", MAIL_QUEUE_LIMIT)

        return

    def run() -> None:
        global _mail_pending

        started = time.monotonic()

        try:
            deliver_code_mail(result, ip_address=ip_address, user_agent=user_agent)
        except Exception as error:  # noqa: BLE001 — 일꾼 스레드의 예외는 아무 데도 찍히지 않는다
            logger.warning("회원가입 메일 일에서 예상하지 못한 오류. type=%s", type(error).__name__)
        finally:
            rest = MAIL_JOB_SECONDS - (time.monotonic() - started)

            if rest > 0:
                time.sleep(rest)

            with _mail_idle:
                _mail_pending -= 1
                _mail_idle.notify_all()

    _mail_pool.submit(run)


def wait_for_mail(timeout: float = 10.0) -> bool:
    """시험용. 넣은 메일을 다 보낼(또는 실패할) 때까지 기다린다. 시간 안에 끝나면 True."""

    with _mail_idle:
        return _mail_idle.wait_for(lambda: _mail_pending == 0, timeout)


@dataclass(frozen=True)
class VerifyResult:
    token: str
    expires_in_seconds: int


def verify_code(
    db: Session,
    email: str,
    code: str,
    *,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    now: Optional[datetime] = None,
) -> VerifyResult:
    """
    인증번호를 확인하고 맞으면 확인 토큰을 준다. 번호는 한 번만 맞힐 수 있다.

    틀리면 422 VERIFICATION_CODE_MISMATCH(남은 횟수), 살아 있는 번호가 없으면 422 VERIFICATION_CODE_EXPIRED
    (5분 지남 · 이미 씀 · 기준만큼 틀림 · 새 번호로 바뀜 · 요청한 적 없음 모두 같다).
    """

    _ensure_enabled()
    _check_ip("verify", ip_address, VERIFY_IP_LIMIT)

    email = normalize_email(email)
    now = now or _now()

    # 대조하기 전에 틀린 횟수를 먼저 1 올린다(시도 예약). 대조한 뒤에 세면 함께 들어온 요청이 모두 '아직 기준 전' 을 보고
    # 대조까지 가서 기준보다 많이 맞혀 볼 수 있다. 대조할 해시도 같이 돌려받아, 그사이 새 번호가 와도 이번 대조는 예약한 번호로 한다.
    reserved = db.execute(
        update(SignupEmailCode)
        .where(
            SignupEmailCode.email == email,
            SignupEmailCode.code_hash.is_not(None),
            SignupEmailCode.code_expires_at > now,
            SignupEmailCode.failed_attempts < MAX_CODE_ATTEMPTS,
        )
        .values(failed_attempts=SignupEmailCode.failed_attempts + 1)
        .returning(SignupEmailCode.id, SignupEmailCode.code_hash, SignupEmailCode.failed_attempts)
        .execution_options(synchronize_session=False)
    ).one_or_none()

    # 다른 요청이 예약을 바로 보도록 대조 전에 커밋한다.
    db.commit()

    if reserved is None:
        raise APIError(ErrorCode.VERIFICATION_CODE_EXPIRED, CODE_EXPIRED_MESSAGE, status_code=422)

    code_id, reserved_hash, attempts = reserved

    # compare_digest 는 ASCII 가 아닌 str 을 받지 못한다. 둘 다 hex 라 ASCII 다.
    if not hmac.compare_digest(reserved_hash, _code_hash(email, code)):
        remaining = max(0, MAX_CODE_ATTEMPTS - attempts)

        audit_service.record(
            db,
            action=AuditAction.SIGNUP_CODE_VERIFIED,
            entity_type=CODE_ENTITY,
            entity_id=code_id,
            status="FAILURE",
            error_code=ErrorCode.VERIFICATION_CODE_MISMATCH.value,
            detail={"failed_attempts": attempts},
            ip_address=ip_address,
            user_agent=user_agent,
        )
        db.commit()

        raise APIError(
            ErrorCode.VERIFICATION_CODE_MISMATCH,
            CODE_MISMATCH_MESSAGE if remaining else CODE_MISMATCH_LAST_MESSAGE,
            status_code=422,
            details={"remaining_attempts": remaining},
        )

    token = secrets.token_urlsafe(32)

    # 예약한 번호가 그대로일 때만 쓴다. 그사이 새 번호가 왔거나 같은 번호로 다른 요청이 먼저 맞혔으면 0 줄이다.
    consumed = db.execute(
        update(SignupEmailCode)
        .where(SignupEmailCode.id == code_id, SignupEmailCode.code_hash == reserved_hash)
        .values(
            code_hash=None,
            code_expires_at=None,
            token_hash=_token_hash(token),
            token_expires_at=now + TOKEN_TTL,
            updated_at=now,
        )
        .execution_options(synchronize_session=False)
    ).rowcount

    if not consumed:
        db.rollback()

        raise APIError(ErrorCode.VERIFICATION_CODE_EXPIRED, CODE_EXPIRED_MESSAGE, status_code=422)

    audit_service.record(
        db,
        action=AuditAction.SIGNUP_CODE_VERIFIED,
        entity_type=CODE_ENTITY,
        entity_id=code_id,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    db.commit()

    return VerifyResult(token=token, expires_in_seconds=_seconds(TOKEN_TTL))


def _spend_token(db: Session, code_id: uuid.UUID, token_hash: str, now: datetime) -> bool:
    """토큰이 그대로이고 만료 전일 때만 지운다(한 번만 쓰게). 지웠으면 True. 커밋은 호출 측이 한다."""

    return bool(
        db.execute(
            update(SignupEmailCode)
            .where(
                SignupEmailCode.id == code_id,
                SignupEmailCode.token_hash == token_hash,
                SignupEmailCode.token_expires_at > now,
            )
            .values(token_hash=None, token_expires_at=None, updated_at=now)
            .execution_options(synchronize_session=False)
        ).rowcount
    )


def submit_request(
    db: Session,
    token: str,
    name: str,
    password: str,
    *,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    now: Optional[datetime] = None,
) -> SignupRequest:
    """
    확인 토큰 · 이름 · 비밀번호로 대기 신청(PENDING)을 만든다. 계정(users)은 만들지 않는다.

    순서(Codex #139 M3):
      ① 토큰이 살아 있는지 — 아니면 422(bcrypt 없이).
      ② 이미 계정이나 대기 신청이 있는 이메일인지 — 그러면 토큰을 쓰고(다시 못 씀) 409(bcrypt 없이). 이 사람은 번호를 받아
         메일함 주인임을 증명했으므로 '이미 있음' 을 알려도 된다.
      ③ 비밀번호 규칙 — 약하면 422 이고 토큰은 남는다(같은 토큰으로 다시 낸다).
      ④ 토큰을 먼저 쓰고 커밋 — 동시에 같은 토큰으로 들어온 요청은 여기서 하나만 남아 bcrypt 는 토큰당 한 번이다.
      ⑤ bcrypt → 신청 저장. 그사이 같은 이메일 신청이 먼저 들어왔으면 부분 유일 색인에 걸려 409(토큰은 이미 썼다).
    """

    _ensure_enabled()

    now = now or _now()
    token_hash = _token_hash(token)

    row = db.scalar(
        select(SignupEmailCode).where(
            SignupEmailCode.token_hash == token_hash,
            SignupEmailCode.token_expires_at > now,
        )
    )

    if row is None:
        raise APIError(ErrorCode.SIGNUP_TOKEN_INVALID, TOKEN_INVALID_MESSAGE, status_code=422)

    email = row.email
    code_id = row.id

    if _email_is_taken(db, email):
        _spend_token(db, code_id, token_hash, now)
        db.commit()

        raise conflict(ErrorCode.DUPLICATE_RESOURCE, DUPLICATE_MESSAGE)

    validate_password(password, email=email, name=name)

    if not _spend_token(db, code_id, token_hash, now):
        db.rollback()

        raise APIError(ErrorCode.SIGNUP_TOKEN_INVALID, TOKEN_INVALID_MESSAGE, status_code=422)

    # 다른 요청이 바로 보도록 bcrypt(약 0.3초) 전에 커밋한다.
    db.commit()

    hashed = hash_password(password)

    request = SignupRequest(
        email=email,
        name=name,
        hashed_password=hashed,
        status=SignupRequestStatus.PENDING,
    )
    db.add(request)

    # 이메일당 대기 신청 하나(부분 유일 색인). 동시에 두 신청이 들어오면 하나만 남는다.
    try:
        db.flush()
    except IntegrityError:
        db.rollback()

        raise conflict(ErrorCode.DUPLICATE_RESOURCE, DUPLICATE_MESSAGE) from None

    audit_service.record(
        db,
        action=AuditAction.SIGNUP_REQUESTED,
        entity_type=REQUEST_ENTITY,
        entity_id=request.id,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    db.commit()
    db.refresh(request)

    return request


# =========================================================
# 관리자 창구
# =========================================================

def expires_at(request: SignupRequest) -> Optional[datetime]:
    """대기 신청이 보관 기한으로 지워지는 시각. 처리된 신청은 None."""

    if request.status != SignupRequestStatus.PENDING:
        return None

    return as_utc(request.created_at) + PENDING_KEEP


def list_requests(
    db: Session,
    *,
    status: SignupRequestStatus,
    offset: int,
    limit: int,
) -> Tuple[List[Tuple[SignupRequest, Optional[str]]], int]:
    """오래된 신청부터. (신청, 처리한 관리자 이름) 목록과 전체 수."""

    purge_expired(db)

    total = db.scalar(
        select(func.count()).select_from(SignupRequest).where(SignupRequest.status == status)
    ) or 0

    rows = db.execute(
        select(SignupRequest, User.name)
        .outerjoin(User, User.id == SignupRequest.decided_by_id)
        .where(SignupRequest.status == status)
        .order_by(SignupRequest.created_at.asc(), SignupRequest.id.asc())
        .offset(offset)
        .limit(limit)
    ).all()

    return [(request, decided_by_name) for request, decided_by_name in rows], total


def _get_or_404(db: Session, request_id: uuid.UUID) -> SignupRequest:
    request = db.get(SignupRequest, request_id)

    if request is None:
        raise not_found(ErrorCode.NOT_FOUND, NOT_FOUND_MESSAGE)

    return request


def _already_decided() -> APIError:
    return conflict(ErrorCode.SIGNUP_ALREADY_DECIDED, ALREADY_DECIDED_MESSAGE)


def approve(
    db: Session,
    admin: User,
    request_id: uuid.UUID,
    role: UserRole,
    *,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> SignupRequest:
    """
    승인: 신청 때 비밀번호 해시 그대로 계정을 만들고, 신청 행은 APPROVED · 해시를 지운다. 한 트랜잭션이다.

    PENDING 일 때만 바꾸는 조건부 UPDATE 라 두 관리자가 동시에 눌러도 하나만 된다. 그사이 같은 이메일 계정이 생겼으면
    모두 되돌리고 409 DUPLICATE_RESOURCE(신청은 PENDING 그대로 — 관리자가 거절하면 된다).
    """

    purge_expired(db)

    request = _get_or_404(db, request_id)

    if request.status != SignupRequestStatus.PENDING or request.hashed_password is None:
        raise _already_decided()

    email, name, hashed = request.email, request.name, request.hashed_password
    submitted_at = as_utc(request.created_at)
    now = _now()

    claimed = db.execute(
        update(SignupRequest)
        .where(SignupRequest.id == request_id, SignupRequest.status == SignupRequestStatus.PENDING)
        .values(
            status=SignupRequestStatus.APPROVED,
            role=role,
            hashed_password=None,
            decided_by_id=admin.id,
            decided_at=now,
            updated_at=now,
        )
        .execution_options(synchronize_session=False)
    ).rowcount

    if not claimed:
        db.rollback()

        raise _already_decided()

    # 대소문자 · 유니코드 도메인만 다른 옛 계정(seed script · 예전 데이터)은 유일 제약에 걸리지 않아 먼저 본다(Codex #139 M2).
    if user_service.email_is_registered(db, email):
        db.rollback()

        raise conflict(ErrorCode.DUPLICATE_RESOURCE, user_service.DUPLICATE_EMAIL_MESSAGE)

    # 그사이 같은 이메일이 들어오면 add_user 가 위 UPDATE 까지 되돌리고 409 를 올린다.
    user = user_service.add_user(
        db,
        email=email,
        hashed_password=hashed,
        name=name,
        role=role,
        actor=admin,
        password_changed_at=submitted_at,
        via="signup_request",
    )

    db.execute(
        update(SignupRequest)
        .where(SignupRequest.id == request_id)
        .values(user_id=user.id)
        .execution_options(synchronize_session=False)
    )
    audit_service.record(
        db,
        action=AuditAction.SIGNUP_APPROVED,
        entity_type=REQUEST_ENTITY,
        entity_id=request_id,
        actor_id=admin.id,
        detail={"role": role.value, "user_id": str(user.id)},
        ip_address=ip_address,
        user_agent=user_agent,
    )
    db.commit()
    db.refresh(request)

    return request


def reject(
    db: Session,
    admin: User,
    request_id: uuid.UUID,
    *,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> SignupRequest:
    """거절: 신청 행을 REJECTED 로 바꾸고 비밀번호 해시를 지운다. 신청자에게 알리지 않는다(스펙 비목표)."""

    purge_expired(db)

    request = _get_or_404(db, request_id)

    if request.status != SignupRequestStatus.PENDING:
        raise _already_decided()

    now = _now()

    claimed = db.execute(
        update(SignupRequest)
        .where(SignupRequest.id == request_id, SignupRequest.status == SignupRequestStatus.PENDING)
        .values(
            status=SignupRequestStatus.REJECTED,
            hashed_password=None,
            decided_by_id=admin.id,
            decided_at=now,
            updated_at=now,
        )
        .execution_options(synchronize_session=False)
    ).rowcount

    if not claimed:
        db.rollback()

        raise _already_decided()

    audit_service.record(
        db,
        action=AuditAction.SIGNUP_REJECTED,
        entity_type=REQUEST_ENTITY,
        entity_id=request_id,
        actor_id=admin.id,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    db.commit()
    db.refresh(request)

    return request
