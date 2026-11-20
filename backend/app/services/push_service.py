# 상담사 앱(폰) 알림 서비스 — 웹 푸시(API_CONTRACT 27절, 2026-11-19).
#
#  - 켜기: 폰이 브라우저 구독(endpoint · 키)과 이 폰의 알림 설정을 보낸다. endpoint 가 같으면 덮어쓰고, 다른 계정이 쓰던 폰이면
#    지금 계정으로 옮긴다. 한 사람 기기 10대를 넘으면 가장 오래 전에 고친 것을 지운다.
#  - 끄기 · 로그아웃: 그 endpoint 를 지운다(내 것만).
#  - 상담 30분 전: 실행기(run_push_loop, main.py lifespan)가 1분마다 '지금부터 30분 안에 시작하는 내 상담 일정' 을 찾아 보낸다.
#    같은 일정 · 같은 시각은 한 번만(push_deliveries 에 먼저 넣고, 겹치면 건너뜀 — 서버가 둘이어도 한 번).
#    시간이 없는 상담 일정 · 개인 · 기관 일정(OTHER)은 알리지 않는다. 일정을 만든 사람(owner)에게만 간다.
#  - 업로드 실패: 녹음은 폰에 있으므로 폰이 스스로 알린다. 서버는 그 설정(upload_failed)만 기억한다.
#  - 아이 긴급 알림(2026-11-20): 아이가 콩콩에서 '급해요' 를 눌러 새 알림이 생기면 그 사례 담당 상담사의 폰에 바로 알린다.
#    앱 설정에 따로 끄는 칸이 없으므로(디자인 그대로) 폰 알림을 켠 기기면 모두 받는다. 확인 전 알림에 다시 누른 것은
#    새로 알리지 않는다(같은 알림 · 횟수만 올라감). 같은 알림은 한 번만(push_deliveries).
#  - 잠금 화면에 보이므로 문구에 아이 이름 · 사례 · 일정 제목 · 장소를 넣지 않는다(시각만). 감사 기록에도 문구를 남기지 않는다.
import asyncio
import logging
import uuid
from datetime import date, datetime, time, timedelta, timezone
from typing import Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.enums import ScheduleKind
from app.core.errors import APIError, ErrorCode
from app.models.case import Case
from app.models.push import PUSH_SUBSCRIPTIONS_PER_USER_MAX, PushDelivery, PushSubscription
from app.models.schedule import ScheduleEvent
from app.models.user import User
from app.schemas.push import PushConfigResponse, PushSubscriptionRequest, PushSubscriptionResponse, PushTestResponse
from app.services import signup_service, webpush

logger = logging.getLogger(__name__)

LOCAL_TZ = ZoneInfo("Asia/Seoul")
KIND_BEFORE_SESSION = "before_session"
#: 연결 오류 · 5xx 가 이만큼 이어지면 그 구독을 지운다(폰을 버렸는데 푸시 서비스가 404 를 안 주는 경우).
MAX_FAILS = 10
#: '시험 알림 보내기' 를 사람마다 1시간에 이만큼.
TEST_HOURLY_LIMIT = 10
#: 보낸 기록을 이만큼 지나면 지운다(같은 일정을 다시 알릴 일이 없는 기간).
DELIVERY_KEEP_DAYS = 3
APP_SCHEDULE_URL = "/#/AppSchedule"
KIND_CHILD_ALERT = "child_alert"
#: 잠금 화면에 보이므로 아이 이름 · 사례 번호는 넣지 않는다. 누르면 그 아이 상세(사례 ID 는 화면에 안 보임).
CHILD_ALERT_TITLE = "긴급 알림"
CHILD_ALERT_BODY = "아이 앱에서 긴급 알림이 왔어요. 바로 확인해 주세요."


def _private_key():
    if not (settings.VAPID_PRIVATE_KEY and settings.VAPID_SUBJECT):
        return None

    try:
        return webpush.load_vapid_private_key(settings.VAPID_PRIVATE_KEY)
    except (webpush.WebPushError, ValueError):
        logger.error("VAPID_PRIVATE_KEY 를 읽지 못했습니다. 알림을 끈 채로 둡니다.")
        return None


def is_enabled() -> bool:
    return _private_key() is not None


def get_config() -> PushConfigResponse:
    key = _private_key()

    return PushConfigResponse(
        enabled=key is not None,
        public_key=webpush.vapid_public_key(key) if key is not None else None,
        before_session_minutes=settings.PUSH_BEFORE_SESSION_MINUTES,
        before_session_enabled=key is not None and settings.PUSH_LOOP_ENABLED,
    )


def _require_enabled() -> None:
    if not is_enabled():
        raise APIError(ErrorCode.PUSH_DISABLED, "알림 기능이 꺼져 있습니다.", status_code=503)


def subscribe(db: Session, user: User, payload: PushSubscriptionRequest) -> PushSubscriptionResponse:
    _require_enabled()

    for attempt in range(2):
        row = db.scalar(select(PushSubscription).where(PushSubscription.endpoint == payload.endpoint).with_for_update())

        if row is None:
            row = PushSubscription(endpoint=payload.endpoint, user_id=user.id, fail_count=0)
            db.add(row)

        row.user_id = user.id
        row.p256dh = payload.keys.p256dh
        row.auth = payload.keys.auth
        row.before_session = payload.before_session
        row.upload_failed = payload.upload_failed
        row.fail_count = 0

        try:
            db.flush()
        except IntegrityError:
            # 같은 폰이 동시에 두 번 켰다. 다시 읽어 덮어쓴다.
            db.rollback()
            if attempt == 0:
                continue
            raise

        _trim(db, user.id, keep=row.id)
        db.commit()

        return PushSubscriptionResponse(before_session=row.before_session, upload_failed=row.upload_failed)

    raise RuntimeError("unreachable")


def _trim(db: Session, user_id: uuid.UUID, *, keep: uuid.UUID) -> None:
    rows = db.scalars(
        select(PushSubscription).where(PushSubscription.user_id == user_id).order_by(PushSubscription.updated_at.desc())
    ).all()
    extra = [row for row in rows if row.id != keep][PUSH_SUBSCRIPTIONS_PER_USER_MAX - 1 :]

    for row in extra:
        db.delete(row)


def unsubscribe(db: Session, user: User, endpoint: str) -> None:
    db.execute(delete(PushSubscription).where(PushSubscription.endpoint == endpoint.strip(), PushSubscription.user_id == user.id))
    db.commit()


def _send_to(db: Session, rows: List[PushSubscription], message: dict, *, now: datetime) -> Tuple[int, int]:
    """구독들에 보내고 결과를 반영한다(없어진 구독 지우기 · 실패 횟수). 커밋은 하지 않는다."""
    key = _private_key()

    if key is None:
        return 0, len(rows)

    sent = failed = 0

    for row in rows:
        try:
            result = webpush.send(row.endpoint, row.p256dh, row.auth, message, private_key=key, subject=settings.VAPID_SUBJECT or "")
        except webpush.WebPushError:
            # 저장된 키가 깨졌다. 다시 켜야 한다.
            db.delete(row)
            failed += 1
            continue

        if result.ok:
            row.fail_count = 0
            row.last_sent_at = now
            sent += 1
        elif result.gone:
            db.delete(row)
            failed += 1
        elif result.auth_rejected:
            # 서버 키 설정 문제라 구독 탓이 아니다 — 실패 횟수에 넣지 않는다(민규 #186).
            failed += 1
            logger.warning("푸시 서비스가 서버 키를 거절 status=%s — VAPID 설정 확인", result.status)
        else:
            row.fail_count = (row.fail_count or 0) + 1
            failed += 1
            logger.warning("푸시 보내기 실패 status=%s fail_count=%s", result.status, row.fail_count)
            if row.fail_count >= MAX_FAILS:
                db.delete(row)

    return sent, failed


def send_test(db: Session, user: User, *, now: Optional[datetime] = None) -> PushTestResponse:
    _require_enabled()
    # 시험 보내기는 사람마다 1시간에 TEST_HOURLY_LIMIT 번까지(민규 #186).
    signup_service._check_ip("push_test", str(user.id), TEST_HOURLY_LIMIT)
    rows = db.scalars(select(PushSubscription).where(PushSubscription.user_id == user.id)).all()
    message = {"title": "I-SPOT", "body": "알림이 켜졌어요.", "url": "/#/AppSettings", "tag": "ispot-test"}
    sent, failed = _send_to(db, list(rows), message, now=now or datetime.now(timezone.utc))
    db.commit()

    return PushTestResponse(sent=sent, failed=failed)


def _start_of(event: ScheduleEvent) -> Optional[datetime]:
    if not event.event_time:
        return None

    try:
        hour, minute = (int(part) for part in event.event_time.split(":", 1))
        return datetime.combine(event.event_date, time(hour, minute), LOCAL_TZ)
    except ValueError:
        return None


def due_before_session(db: Session, now: datetime) -> List[Tuple[ScheduleEvent, datetime]]:
    """지금부터 PUSH_BEFORE_SESSION_MINUTES 안에 시작하는 상담 일정(시작 시각 순)."""
    local_now = now.astimezone(LOCAL_TZ)
    until = local_now + timedelta(minutes=settings.PUSH_BEFORE_SESSION_MINUTES)
    days: List[date] = sorted({local_now.date(), until.date()})
    events = db.scalars(
        select(ScheduleEvent).where(
            ScheduleEvent.kind == ScheduleKind.CONSULT,
            ScheduleEvent.event_date.in_(days),
            ScheduleEvent.event_time.is_not(None),
        )
    ).all()
    due = []

    for event in events:
        start = _start_of(event)

        if start is not None and local_now <= start <= until:
            due.append((event, start))

    return sorted(due, key=lambda pair: pair[1])


def run_before_session(db: Session, now: Optional[datetime] = None) -> int:
    """알릴 일정을 찾아 보낸다. 보낸 일정 수를 돌려준다. 켜진 구독이 없는 사람은 기록도 남기지 않는다."""
    if not is_enabled():
        return 0

    now = now or datetime.now(timezone.utc)
    due = due_before_session(db, now)

    if not due:
        return 0

    owners = {event.owner_id for event, _ in due}
    subs: Dict[uuid.UUID, List[PushSubscription]] = {}

    for row in db.scalars(
        select(PushSubscription)
        .join(User, User.id == PushSubscription.user_id)
        .where(PushSubscription.user_id.in_(owners), PushSubscription.before_session.is_(True), User.is_active.is_(True))
    ).all():
        subs.setdefault(row.user_id, []).append(row)

    count = 0

    for event, start in due:
        rows = subs.get(event.owner_id)

        if not rows:
            continue

        clock = start.strftime("%H:%M")
        delivery = PushDelivery(user_id=event.owner_id, kind=KIND_BEFORE_SESSION, ref_key=f"{event.id}@{start.isoformat()}", sent=0)
        db.add(delivery)

        try:
            db.commit()
        except IntegrityError:
            # 이미 알렸다(이 서버 또는 다른 서버).
            db.rollback()
            continue

        message = {
            "title": "상담 일정 알림",
            "body": f"{clock} 상담 일정이 있어요.",
            "url": APP_SCHEDULE_URL,
            "tag": f"before-session-{event.id}",
        }
        # 커밋 뒤 행이 만료되었으므로 다시 읽는다.
        live = db.scalars(select(PushSubscription).where(PushSubscription.id.in_([row.id for row in rows]))).all()
        sent, _ = _send_to(db, list(live), message, now=now)
        delivery.sent = sent
        db.commit()
        count += 1

    return count


def send_child_alert(db: Session, case_id: uuid.UUID, alert_id: uuid.UUID, *, now: Optional[datetime] = None) -> int:
    """새 아이 긴급 알림을 담당 상담사 폰에 보낸다. 보낸 기기 수를 돌려준다."""
    if not is_enabled():
        return 0

    case = db.get(Case, case_id)

    if case is None or case.counselor_id is None:
        return 0

    owner = case.counselor_id
    rows = db.scalars(
        select(PushSubscription)
        .join(User, User.id == PushSubscription.user_id)
        .where(PushSubscription.user_id == owner, User.is_active.is_(True))
    ).all()

    if not rows:
        return 0

    delivery = PushDelivery(user_id=owner, kind=KIND_CHILD_ALERT, ref_key=str(alert_id), sent=0)
    db.add(delivery)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return 0

    message = {
        "title": CHILD_ALERT_TITLE,
        "body": CHILD_ALERT_BODY,
        "url": f"/#/ChildDetail?case={case_id}",
        "tag": f"child-alert-{alert_id}",
    }
    live = db.scalars(select(PushSubscription).where(PushSubscription.id.in_([row.id for row in rows]))).all()
    sent, _ = _send_to(db, list(live), message, now=now or datetime.now(timezone.utc))
    delivery.sent = sent
    db.commit()

    return sent


def notify_child_alert(case_id: uuid.UUID, alert_id: uuid.UUID) -> None:
    """응답을 보낸 뒤 돌린다(BackgroundTasks). 아이의 '급해요' 응답을 푸시 서비스 때문에 늦추거나 실패시키지 않는다."""
    from app.core.database import SessionLocal

    db = SessionLocal()

    try:
        send_child_alert(db, case_id, alert_id)
    except Exception:  # noqa: BLE001 — 알림 실패가 아이 앱 응답 · 실행기에 번지지 않게
        db.rollback()
        logger.exception("아이 긴급 알림 푸시 실패")
    finally:
        db.close()


def cleanup_deliveries(db: Session, now: Optional[datetime] = None) -> None:
    now = now or datetime.now(timezone.utc)
    db.execute(delete(PushDelivery).where(PushDelivery.created_at < now - timedelta(days=DELIVERY_KEEP_DAYS)))
    db.commit()


def _tick() -> None:
    from app.core.database import SessionLocal

    db = SessionLocal()

    try:
        run_before_session(db)
        cleanup_deliveries(db)
    finally:
        db.close()


async def run_push_loop() -> None:
    """
    main.py lifespan 이 띄운다. PUSH_LOOP_ENABLED 가 꺼져 있거나 키가 없으면 바로 끝난다. 한 번 실패해도 다음 차례에 다시 한다.
    보내기(바깥 푸시 서비스로 가는 HTTP)는 스레드에서 한다 — 이벤트 루프를 막지 않아 다른 API 응답이 기다리지 않는다.
    """
    if not settings.PUSH_LOOP_ENABLED or not is_enabled():
        return

    while True:
        try:
            await asyncio.to_thread(_tick)
        except Exception:  # noqa: BLE001 — 실행기는 멈추지 않는다
            logger.exception("상담 전 알림 실행기 오류")

        await asyncio.sleep(settings.PUSH_LOOP_SECONDS)
