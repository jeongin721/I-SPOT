# 아이 앱(콩콩) 연결 · 질문 · 답변(API_CONTRACT 24절). 문항과 판정 기준은 콩콩 디자인 그대로다.
#
# 살펴볼 답 · 바로 확인은 서버가 계산한다. 앱이 보낸 값으로 판정하지 않는다.

import hashlib
import secrets
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.enums import (
    AuditAction,
    CaseStatus,
    ChildAnswerLevel,
    ChildAppEventKind,
    ChildAppLinkStatus,
    ChildQuestionSetStatus,
    ScheduleConsultType,
    ScheduleKind,
)
from app.core.config import settings
from app.core.errors import APIError, ErrorCode, bad_request, conflict, forbidden, not_found, unauthorized
from app.models.audit_log import AuditLog
from app.models.case import Case
from app.models.child_app import ChildAppEvent, ChildAppLink, ChildQuestionSet
from app.models.schedule import ScheduleEvent
from app.models.user import User
from app.schemas.child_app import ChildAnswerInput, ChildAppCaseResponse, ChildHomeResponse
from app.services import audit_service, signup_service

CODE_ALPHABET = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"
CODE_LENGTH = 6
CODE_TTL = timedelta(hours=72)
LINK_IP_LIMIT = 20
FEED_LIMIT = 100
# 화면이 30초마다 다시 받으므로 열람 기록은 같은 사람 · 사례에 이 시간 안 1줄만 남긴다.
# 그사이 새로 온 내용이 있으면(마지막 기록 뒤 생긴 피드 줄) 시간 안이어도 새로 남긴다.
FEED_VIEW_LOG_WINDOW = timedelta(minutes=10)
# 아이가 급하다고 알린 뒤 앱 홈에 확인 여부를 보이는 시간, 확인 전이면 112 안내를 다시 띄우는 시간(멘토 피드백 11/12, 경진 11/13 "10분은 길다" → 5분).
ALERT_STATUS_SHOWN = timedelta(hours=24)
ALERT_OVERDUE_AFTER = timedelta(minutes=5)
OPEN_ALERT_LIMIT = 50
LIST_LIMIT = 200
RECENT_DAYS = 21
AI_QUESTION_PREFIX = "ai_"
CONTACT_REQUEST_CHIP = "전화로 연락받고 싶어요"
SKIP_TEXT = "답하기 어려워요"
LOCAL_TZ = ZoneInfo("Asia/Seoul")

_SCALE_FACES = ["good", "okay", "meh", "worried", "sad"]

QUESTION_BANK: List[Dict[str, Any]] = [
    {"id": "sleep", "category": "생활", "type": "scale", "text": "최근 일주일 동안 잠은 잘 잤나요?", "short": "수면",
     "options": ["잘 잤어요", "괜찮았어요", "보통이에요", "잘 못 잤어요", "거의 못 잤어요"],
     "faces": ["good", "okay", "meh", "tired", "sad"], "flag": 3},
    {"id": "meal", "category": "생활", "type": "choice", "text": "최근 일주일 동안 끼니는 잘 챙겨 먹었나요?", "short": "식사",
     "options": ["거의 매일 잘 먹었어요", "하루 한두 끼만 먹었어요", "굶은 날이 많았어요"], "flag": 2},
    {"id": "home", "category": "집", "type": "choice", "text": "이번 주에 집에서 마음이 불편했던 날이 있었나요?", "short": "집에서 불편했던 날",
     "options": ["없었어요", "1~2일", "3일 이상", "거의 매일"],
     "note": "어떤 일이었는지는 다음 상담 때 이야기해도 괜찮아요.", "flag": 2},
    {"id": "safe", "category": "안전", "type": "choice", "text": "지금 지내는 곳이 안전하다고 느끼나요?", "short": "지내는 곳 안전감",
     "options": ["안전해요", "조금 불안해요", "안전하지 않아요"], "flag": 1, "red": 2},
    {"id": "school", "category": "학교", "type": "scale", "text": "요즘 학교생활은 어떤가요?", "short": "학교생활",
     "options": ["좋아요", "괜찮아요", "보통이에요", "힘들어요", "많이 힘들어요"], "faces": _SCALE_FACES, "flag": 3},
    {"id": "friend", "category": "마음", "type": "choice", "text": "힘들 때 이야기할 수 있는 사람이 있나요?", "short": "이야기할 사람",
     "options": ["있어요", "잘 모르겠어요", "없어요"], "flag": 2},
    {"id": "week", "category": "마음", "type": "scale", "text": "이번 주 기분은 전반적으로 어땠나요?", "short": "이번 주 기분",
     "options": ["좋았어요", "괜찮았어요", "보통이었어요", "힘들었어요", "많이 힘들었어요"], "faces": _SCALE_FACES, "flag": 3},
    {"id": "free", "category": "마음", "type": "text", "text": "상담 선생님께 더 전하고 싶은 말이 있나요?", "short": "전하고 싶은 말",
     "chips": ["없어요", "만나서 이야기할게요", CONTACT_REQUEST_CHIP, SKIP_TEXT]},
]
_BANK_BY_ID = {item["id"]: item for item in QUESTION_BANK}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _aware(value: datetime) -> datetime:
    # SQLite 는 시간대를 지우고 돌려준다.
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _normalize_code(code: str) -> str:
    return "".join(ch for ch in code.upper() if ch.isalnum())


def _new_code() -> str:
    return "KONG-" + "".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))


def _add_event(
    db: Session,
    case_id: uuid.UUID,
    kind: ChildAppEventKind,
    payload: Dict[str, Any],
    level: ChildAnswerLevel = ChildAnswerLevel.NONE,
    needs_ack: bool = False,
) -> None:
    db.add(ChildAppEvent(case_id=case_id, kind=kind, level=level, payload=payload, needs_ack=needs_ack))


def ensure_enabled() -> None:
    if not settings.CHILD_APP_ENABLED:
        raise APIError(ErrorCode.CHILD_APP_DISABLED, "아이 앱 기능이 꺼져 있습니다.", status_code=503)


def ensure_assigned(case: Case, user: User) -> None:
    # 코드 발급 · 질문은 담당 상담사의 일이다. 관리자가 코드를 다시 만들면 상담사가 준 코드가 무효가 된다.
    if case.counselor_id != user.id:
        raise forbidden("담당 상담사만 할 수 있습니다.")


def ensure_active(case: Case) -> None:
    if case.status != CaseStatus.ACTIVE:
        raise conflict(ErrorCode.INVALID_CASE_STATE, "종결된 사례에는 아이 앱을 사용할 수 없습니다.")


def link_row(db: Session, case_id: uuid.UUID, *, lock: bool = False) -> Optional[ChildAppLink]:
    statement = select(ChildAppLink).where(ChildAppLink.case_id == case_id)

    return db.scalar(statement.with_for_update() if lock else statement)


# =========================================================
# 상담사 웹
# =========================================================

def create_invite(db: Session, case: Case, user: User, ip_address: Optional[str]) -> Dict[str, Any]:
    ensure_assigned(case, user)
    ensure_active(case)
    link = link_row(db, case.id, lock=True)

    if link is not None and link.status == ChildAppLinkStatus.LINKED:
        raise conflict(ErrorCode.DUPLICATE_RESOURCE, "이미 앱이 연결된 사례입니다.")

    code = _new_code()
    expires_at = _utcnow() + CODE_TTL

    if link is None:
        link = ChildAppLink(case_id=case.id)
        db.add(link)

    link.status = ChildAppLinkStatus.INVITED
    link.code_hash = _hash(_normalize_code(code))
    link.code_expires_at = expires_at
    audit_service.record(
        db,
        action=AuditAction.CHILD_APP_INVITED,
        entity_type="child_app_link",
        actor_id=user.id,
        case_id=case.id,
        ip_address=ip_address,
    )
    db.commit()

    return {"code": code, "expires_at": expires_at}


def send_questions(
    db: Session,
    case: Case,
    user: User,
    question_ids: List[str],
    ip_address: Optional[str],
) -> None:
    ensure_assigned(case, user)
    ensure_active(case)

    if len(set(question_ids)) != len(question_ids) or any(item not in _BANK_BY_ID for item in question_ids):
        raise bad_request(ErrorCode.VALIDATION_ERROR, "보낼 수 없는 질문이 들어 있습니다.")

    link = link_row(db, case.id, lock=True)

    if link is None or link.status != ChildAppLinkStatus.LINKED:
        raise conflict(ErrorCode.INVALID_CASE_STATE, "앱이 연결된 뒤에 질문을 보낼 수 있습니다.")

    # 답하지 않은 질문은 새 질문으로 바뀐다(디자인 안내 문구).
    db.execute(
        update(ChildQuestionSet)
        .where(ChildQuestionSet.case_id == case.id, ChildQuestionSet.status == ChildQuestionSetStatus.PENDING)
        .values(status=ChildQuestionSetStatus.REPLACED)
    )
    db.add(
        ChildQuestionSet(
            case_id=case.id,
            sent_by_id=user.id,
            questions=[dict(_BANK_BY_ID[item]) for item in question_ids],
        )
    )
    _add_event(db, case.id, ChildAppEventKind.QUESTIONS_SENT, {"count": len(question_ids)})
    audit_service.record(
        db,
        action=AuditAction.CHILD_APP_QUESTIONS_SENT,
        entity_type="child_question_set",
        actor_id=user.id,
        case_id=case.id,
        detail={"count": len(question_ids)},
        ip_address=ip_address,
    )
    db.commit()


def list_cases(db: Session, user: User) -> List[Dict[str, Any]]:
    """아이 연계 목록. 상담사는 담당 사례, 관리자는 전체. 종결 사례는 뺀다. 답 내용은 담당 상담사에게만 준다."""

    query = select(Case).where(Case.status == CaseStatus.ACTIVE)

    if not user.is_admin:
        query = query.where(Case.counselor_id == user.id)

    cases = list(db.scalars(query.order_by(Case.created_at.desc()).limit(LIST_LIMIT)))
    ids = [case.id for case in cases]
    links = {row.case_id: row for row in db.scalars(select(ChildAppLink).where(ChildAppLink.case_id.in_(ids)))} if ids else {}
    since = _utcnow() - timedelta(days=RECENT_DAYS)
    latest_level: Dict[uuid.UUID, str] = {}
    recent: Dict[uuid.UUID, int] = {}

    if ids:
        answered = db.execute(
            select(ChildAppEvent.case_id, ChildAppEvent.level, ChildAppEvent.created_at)
            .where(ChildAppEvent.case_id.in_(ids), ChildAppEvent.kind == ChildAppEventKind.ANSWERS)
            .order_by(ChildAppEvent.created_at.desc())
        ).all()

        for case_id, level, created_at in answered:
            latest_level.setdefault(case_id, level.value)

            if _aware(created_at) >= since:
                recent[case_id] = recent.get(case_id, 0) + 1

    alerts: Dict[uuid.UUID, Dict[str, Any]] = {}

    for alert in list_open_alerts(db, user):
        # 사례마다 긴급 알림을 먼저, 없으면 가장 최근 알림.
        current = alerts.get(alert["case_id"])
        if current is None or (alert["urgent"] and not current["urgent"]):
            alerts[alert["case_id"]] = alert

    acked = _last_acked(db, ids)
    rows = []

    for case in cases:
        link = links.get(case.id)
        assigned = case.counselor_id == user.id
        alert = alerts.get(case.id)
        rows.append(
            {
                "case_id": case.id,
                "case_number": case.case_number,
                "child_alias": case.child_alias,
                "child_birth_year": case.child_birth_year,
                "status": link.status.value if link else "NOT_LINKED",
                "recent_answers": recent.get(case.id, 0) if assigned else None,
                "level": latest_level.get(case.id) if assigned else None,
                "last_response_at": link.last_response_at if link else None,
                "open_alert_at": (alert["last_at"] or alert["created_at"]) if alert else None,
                "open_alert_reason": alert["reason"] if alert else None,
                "open_alert_urgent": bool(alert and alert["urgent"]),
                "last_acked_at": acked.get(case.id),
            }
        )

    return rows


def stats(db: Session, date_from: date, date_to: date) -> Dict[str, int]:
    """관리자 통계 '아이 앱 응답률'. 기간(한국 날짜, 끝 날 포함) 안에 보낸 질문 묶음과 그중 아이가 답한 묶음, 지금 연결된 사례 수.
    대체된 묶음(답하기 전 새 질문으로 바뀜)도 보낸 것으로 센다. 답 내용은 세지 않는다."""

    start = datetime.combine(date_from, datetime.min.time(), tzinfo=LOCAL_TZ)
    end = datetime.combine(date_to + timedelta(days=1), datetime.min.time(), tzinfo=LOCAL_TZ)
    rows = db.execute(
        select(ChildQuestionSet.status, func.count())
        .join(Case, Case.id == ChildQuestionSet.case_id)
        .where(ChildQuestionSet.created_at >= start, ChildQuestionSet.created_at < end)
        .group_by(ChildQuestionSet.status)
    ).all()
    counts = {status.value: int(count) for status, count in rows}
    linked = db.scalar(select(func.count()).select_from(ChildAppLink).where(ChildAppLink.status == ChildAppLinkStatus.LINKED))

    return {
        "sent": sum(counts.values()),
        "answered": counts.get(ChildQuestionSetStatus.ANSWERED.value, 0),
        "linked_cases": int(linked or 0),
    }


def question_text(item: Dict[str, Any]) -> str:
    """답 한 줄의 질문 문장. 문항 목록에 없으면(AI 추가 질문) 답에 복사해 둔 글을 쓴다."""

    return _BANK_BY_ID.get(item["question_id"], {}).get("text") or item["question"]


def get_case_view(db: Session, case: Case, user: User) -> ChildAppCaseResponse:
    link = link_row(db, case.id)
    # 아이에게 "담당 선생님만 본다" 고 안내한다. 담당이 아닌 관리자는 연결 상태와 응답 시각만 본다.
    can_read_feed = case.counselor_id == user.id
    pending = db.scalar(
        select(ChildQuestionSet.id).where(
            ChildQuestionSet.case_id == case.id,
            ChildQuestionSet.status == ChildQuestionSetStatus.PENDING,
        ).limit(1)
    )
    rows = []

    if can_read_feed:
        rows = db.scalars(
            select(ChildAppEvent)
            .where(ChildAppEvent.case_id == case.id)
            .order_by(ChildAppEvent.created_at.desc(), ChildAppEvent.id.desc())
            .limit(FEED_LIMIT)
        ).all()

        if rows:
            _record_feed_view(db, case, user, rows)

    return ChildAppCaseResponse(
        status=link.status.value if link else "NOT_LINKED",
        code_expires_at=link.code_expires_at if link and link.status == ChildAppLinkStatus.INVITED else None,
        linked_at=link.linked_at if link else None,
        last_response_at=link.last_response_at if link else None,
        # 담당 상담사의 아이 상세 머리글에 보인다. 담당이 아닌 관리자는 연결 상태와 응답 시각만 본다.
        next_consult=_next_consult(db, case.id, datetime.now(LOCAL_TZ).date()) if can_read_feed else None,
        has_pending_questions=pending is not None,
        can_read_feed=can_read_feed,
        open_alerts=_open_alerts(db, user, case_id=case.id),
        last_acked_at=_last_acked(db, [case.id]).get(case.id),
        bank=[
            {"id": item["id"], "category": item["category"], "type": item["type"], "text": item["text"]}
            for item in QUESTION_BANK
        ],
        ai_enabled=child_app_ai_service.is_enabled() and can_read_feed,
        ai_draft=child_app_ai_service.latest_draft(db, case.id) if can_read_feed else None,
        feed=[
            {
                "id": row.id,
                "kind": row.kind.value,
                "level": row.level.value,
                "payload": row.payload,
                "created_at": row.created_at,
                "needs_ack": row.needs_ack,
                "acknowledged_at": row.acknowledged_at,
            }
            for row in rows
        ],
    )


def _last_acked(db: Session, case_ids: List[uuid.UUID]) -> Dict[uuid.UUID, datetime]:
    """사례마다 가장 최근 '확인이 필요한 알림 · 답'이 확인됐으면 그 시각. 확인 전이거나 없으면 빠진다."""

    if not case_ids:
        return {}

    # 사례마다 확인이 필요한 줄 중 가장 최근 시각만 골라 그 줄만 읽는다(줄이 쌓여도 사례 수만큼만, 민규 #175 리뷰 4).
    newest = (
        select(ChildAppEvent.case_id, func.max(ChildAppEvent.created_at).label("at"))
        .where(ChildAppEvent.case_id.in_(case_ids), ChildAppEvent.needs_ack.is_(True))
        .group_by(ChildAppEvent.case_id)
        .subquery()
    )
    rows = db.execute(
        select(ChildAppEvent.case_id, ChildAppEvent.acknowledged_at)
        .join(newest, and_(ChildAppEvent.case_id == newest.c.case_id, ChildAppEvent.created_at == newest.c.at))
        .where(ChildAppEvent.needs_ack.is_(True))
        .order_by(ChildAppEvent.id.desc())
    ).all()

    latest: Dict[uuid.UUID, Optional[datetime]] = {}
    for case_id, acknowledged_at in rows:
        # 같은 시각 줄이 둘이면 하나라도 확인 전이면 확인 전으로 본다.
        if case_id in latest and (latest[case_id] is None or acknowledged_at is None):
            latest[case_id] = None
        else:
            latest.setdefault(case_id, acknowledged_at)

    return {case_id: _aware(at) for case_id, at in latest.items() if at is not None}


def _record_feed_view(db: Session, case: Case, user: User, rows: List[ChildAppEvent]) -> None:
    """아이가 보낸 내용을 담당 상담사에게 내줄 때 열람 기록. 내용은 넣지 않고 줄 수 · 가장 최근 줄 ID 만."""

    last = db.scalar(
        select(AuditLog.created_at)
        .where(
            AuditLog.actor_id == user.id,
            AuditLog.case_id == case.id,
            AuditLog.action == AuditAction.CHILD_APP_FEED_VIEWED,
        )
        .order_by(AuditLog.created_at.desc())
        .limit(1)
    )
    now = _utcnow()

    if last is not None and now - _aware(last) < FEED_VIEW_LOG_WINDOW and _aware(rows[0].created_at) <= _aware(last):
        return

    audit_service.record(
        db,
        action=AuditAction.CHILD_APP_FEED_VIEWED,
        entity_type="ChildAppEvent",
        entity_id=rows[0].id,
        actor_id=user.id,
        case_id=case.id,
        detail={"events": len(rows)},
    )
    db.commit()


def _alert_reason(event: ChildAppEvent, case: Case, viewer: User) -> str:
    if event.kind == ChildAppEventKind.ALERT:
        return "ALERT"

    # 담당이 아닌 관리자에게는 답의 성격을 알리지 않고 확인이 필요하다는 사실만 보인다.
    if case.counselor_id != viewer.id:
        return "NEEDS_CHECK"

    return "RED_ANSWER" if event.level == ChildAnswerLevel.RED else event.payload.get("alert_reason", "CONTACT_REQUEST")


def _is_urgent(event: ChildAppEvent) -> bool:
    """긴급 알림 · 바로 확인 답 · 아이의 연락 요청. 글 · 추가 질문 답은 확인 필요다."""

    return (
        event.kind == ChildAppEventKind.ALERT
        or event.level == ChildAnswerLevel.RED
        or event.payload.get("alert_reason") == "CONTACT_REQUEST"
    )


def _open_alerts(
    db: Session,
    viewer: User,
    *,
    case_id: Optional[uuid.UUID] = None,
    counselor_id: Optional[uuid.UUID] = None,
) -> List[Dict[str, Any]]:
    now = _utcnow()
    statement = (
        select(ChildAppEvent, Case)
        .join(Case, Case.id == ChildAppEvent.case_id)
        .where(
            ChildAppEvent.needs_ack.is_(True),
            ChildAppEvent.acknowledged_at.is_(None),
            Case.status == CaseStatus.ACTIVE,
        )
        # 최신부터. 상한을 넘어도 새 알림이 빠지지 않게 한다.
        .order_by(ChildAppEvent.created_at.desc(), ChildAppEvent.id.desc())
        .limit(OPEN_ALERT_LIMIT)
    )

    if case_id is not None:
        statement = statement.where(ChildAppEvent.case_id == case_id)

    if counselor_id is not None:
        statement = statement.where(Case.counselor_id == counselor_id)

    return [
        {
            "id": event.id,
            "case_id": case.id,
            "child_alias": case.child_alias,
            "case_number": case.case_number,
            "reason": _alert_reason(event, case, viewer),
            # 바로 연락을 판단해야 하는 알림. 담당이 아닌 관리자도 이유(NEEDS_CHECK)와 따로 이 값으로 긴급을 안다(민규 #165 재리뷰).
            "urgent": _is_urgent(event),
            # 답 기반 알림은 내용을 볼 수 있는 담당 상담사만 닫는다.
            "can_ack": event.kind == ChildAppEventKind.ALERT or case.counselor_id == viewer.id,
            "repeat_count": int(event.payload.get("repeat_count", 0)),
            "last_at": event.payload.get("last_at"),
            "created_at": event.created_at,
            "escalated": _is_escalated(event, now),
            "handed_over": False,
            "counselor_name": None,
        }
        for event, case in db.execute(statement).all()
    ]


def _escalate_after() -> timedelta:
    return timedelta(minutes=settings.CHILD_APP_ESCALATE_MINUTES)


def _is_escalated(event: ChildAppEvent, now: datetime) -> bool:
    """아이가 직접 '급하다고 알리기' 를 보냈는데 정한 시간 넘게 아무도 확인하지 않았다."""

    return (
        event.kind == ChildAppEventKind.ALERT
        and event.acknowledged_at is None
        and now - _aware(event.created_at) >= _escalate_after()
    )


def _handed_over_alerts(db: Session, viewer: User) -> List[Dict[str, Any]]:
    """다른 상담사 사례의 긴급 알림 중 정한 시간 넘게 확인 전인 것(멘토 피드백 11/12 B안).

    사례를 열 권한이 없으니 아이 이름 · 내용은 주지 않고 사례 번호와 담당 상담사만 준다. 확인 처리도 못 한다.
    담당 상담사나 관리자에게 바로 알리게 하는 것이 목적이다."""

    now = _utcnow()
    rows = db.execute(
        select(ChildAppEvent, Case, User.name)
        .join(Case, Case.id == ChildAppEvent.case_id)
        .outerjoin(User, User.id == Case.counselor_id)
        .where(
            ChildAppEvent.kind == ChildAppEventKind.ALERT,
            ChildAppEvent.needs_ack.is_(True),
            ChildAppEvent.acknowledged_at.is_(None),
            ChildAppEvent.created_at <= now - _escalate_after(),
            Case.status == CaseStatus.ACTIVE,
            or_(Case.counselor_id.is_(None), Case.counselor_id != viewer.id),
        )
        .order_by(ChildAppEvent.created_at.desc(), ChildAppEvent.id.desc())
        .limit(OPEN_ALERT_LIMIT)
    ).all()

    return [
        {
            "id": event.id,
            "case_id": case.id,
            "child_alias": "",
            "case_number": case.case_number,
            "reason": "ALERT",
            "urgent": True,
            "can_ack": False,
            "repeat_count": int(event.payload.get("repeat_count", 0)),
            "last_at": event.payload.get("last_at"),
            "created_at": event.created_at,
            "escalated": True,
            "handed_over": True,
            "counselor_name": counselor_name,
        }
        for event, case, counselor_name in rows
    ]


def list_open_alerts(db: Session, user: User) -> List[Dict[str, Any]]:
    """담당 상담사는 자기 사례, 관리자는 전체. 담당자가 자리에 없을 때 놓치지 않게 관리자에게도 보인다.
    상담사에게는 다른 상담사 사례의 긴급 알림도 정한 시간 넘게 확인 전이면 보인다(넘기기, B안)."""

    if user.is_admin:
        return _open_alerts(db, user)

    return _open_alerts(db, user, counselor_id=user.id) + _handed_over_alerts(db, user)


def acknowledge_alert(
    db: Session,
    case: Case,
    user: User,
    alert_id: uuid.UUID,
    ip_address: Optional[str],
) -> None:
    event = db.scalar(
        select(ChildAppEvent)
        .where(
            ChildAppEvent.id == alert_id,
            ChildAppEvent.case_id == case.id,
            ChildAppEvent.needs_ack.is_(True),
        )
        .with_for_update()
    )

    if event is None:
        raise not_found(ErrorCode.NOT_FOUND, "긴급 알림을 찾을 수 없습니다.")

    if event.kind != ChildAppEventKind.ALERT:
        ensure_assigned(case, user)

    # 두 사람이 함께 눌러도 먼저 확인한 사람의 기록을 남긴다.
    if event.acknowledged_at is not None:
        return

    event.acknowledged_at = _utcnow()
    event.acknowledged_by_id = user.id
    audit_service.record(
        db,
        action=AuditAction.CHILD_APP_ALERT_ACKED,
        entity_type="child_app_event",
        entity_id=event.id,
        actor_id=user.id,
        case_id=case.id,
        ip_address=ip_address,
    )
    db.commit()


# =========================================================
# 아이 앱
# =========================================================

def send_alert(db: Session, link: ChildAppLink) -> None:
    # 같은 기기의 동시 요청을 줄 세워 알림이 두 건 생기지 않게 한다.
    locked = db.scalar(
        select(ChildAppLink)
        .where(ChildAppLink.id == link.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    # 인증을 통과한 뒤 그사이 해지가 끝났으면 연결 행이 없다. 500 대신 다시 연결하라고 돌려준다(민규 #167).
    if locked is None:
        db.rollback()
        raise unauthorized("앱을 다시 연결해 주세요.")
    now = _utcnow()
    # 확인 전 알림이 있으면 새 줄을 만들지 않고 횟수만 올린다. 한 기기가 목록을 채우지 못한다.
    # 확인한 뒤에 보낸 알림은 시간과 상관없이 새 알림이다.
    current = db.scalar(
        select(ChildAppEvent)
        .where(
            ChildAppEvent.case_id == locked.case_id,
            ChildAppEvent.kind == ChildAppEventKind.ALERT,
            ChildAppEvent.acknowledged_at.is_(None),
        )
        .order_by(ChildAppEvent.created_at.desc())
        .limit(1)
    )
    locked.last_response_at = now

    if current is None:
        _add_event(db, locked.case_id, ChildAppEventKind.ALERT, {}, level=ChildAnswerLevel.RED, needs_ack=True)
    else:
        current.payload = {
            **current.payload,
            "repeat_count": int(current.payload.get("repeat_count", 0)) + 1,
            "last_at": now.isoformat(),
        }

    db.commit()


def unlink_device(db: Session, link: ChildAppLink, ip_address: Optional[str]) -> None:
    """아이가 앱 설정에서 해지한다. 연결 행을 지워 상담사가 새 코드를 만들 수 있게 하고, 답하지 않은 질문은 거둔다.
    받은 답 · 알림 기록(피드)은 그대로 둔다."""

    case_id = link.case_id
    # 다른 요청과 같은 순서(연결 행 → 질문 묶음)로 잠근다. 질문 묶음을 먼저 바꾸면 PostgreSQL 에서 질문 보내기 ·
    # 추가 질문 승인과 서로 기다리다 교착(500)이 나고, 그사이 보낸 질문이 연결 없이 남았다(11/10 동시 요청 시험).
    # 이미 해지됐으면 할 일이 없다.
    locked = db.scalar(
        select(ChildAppLink)
        .where(ChildAppLink.id == link.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if locked is None:
        db.rollback()
        return
    link = locked
    db.execute(
        update(ChildQuestionSet)
        .where(ChildQuestionSet.case_id == case_id, ChildQuestionSet.status == ChildQuestionSetStatus.PENDING)
        .values(status=ChildQuestionSetStatus.REPLACED)
    )
    _add_event(db, case_id, ChildAppEventKind.UNLINKED, {})
    audit_service.record(
        db,
        action=AuditAction.CHILD_APP_UNLINKED,
        entity_type="child_app_link",
        entity_id=link.id,
        case_id=case_id,
        detail={"by": "device"},
        ip_address=ip_address,
    )
    db.delete(link)
    db.commit()


def link_device(db: Session, code: str, ip_address: Optional[str]) -> str:
    signup_service._check_ip("child_app_link", ip_address, LINK_IP_LIMIT)
    invalid = APIError(ErrorCode.INVALID_CHILD_CODE, "연결 코드를 다시 확인해 주세요.", status_code=400)
    link = db.scalar(
        select(ChildAppLink).where(ChildAppLink.code_hash == _hash(_normalize_code(code))).with_for_update()
    )

    if (
        link is None
        or link.status != ChildAppLinkStatus.INVITED
        or link.code_expires_at is None
        or _aware(link.code_expires_at) <= _utcnow()
    ):
        raise invalid

    case = db.get(Case, link.case_id)

    if case is None or case.status != CaseStatus.ACTIVE:
        raise invalid

    token = secrets.token_urlsafe(32)
    link.status = ChildAppLinkStatus.LINKED
    link.device_token_hash = _hash(token)
    link.code_hash = None
    link.code_expires_at = None
    link.linked_at = _utcnow()
    _add_event(db, link.case_id, ChildAppEventKind.LINKED, {})

    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise invalid from error

    return token


def get_link_by_token(db: Session, token: str) -> ChildAppLink:
    link = db.scalar(select(ChildAppLink).where(ChildAppLink.device_token_hash == _hash(token)))

    if link is None or link.status != ChildAppLinkStatus.LINKED:
        raise unauthorized("앱을 다시 연결해 주세요.")

    case = db.get(Case, link.case_id)

    if case is None or case.status != CaseStatus.ACTIVE:
        raise unauthorized("앱을 다시 연결해 주세요.")

    return link


def _next_consult(db: Session, case_id: uuid.UUID, today: date) -> Optional[Dict[str, Any]]:
    event = db.scalar(
        select(ScheduleEvent)
        .where(
            ScheduleEvent.case_id == case_id,
            ScheduleEvent.kind == ScheduleKind.CONSULT,
            ScheduleEvent.event_date >= today,
        )
        .order_by(ScheduleEvent.event_date, ScheduleEvent.event_time)
        .limit(1)
    )

    if event is None:
        return None

    # 방문 · 전화 상담의 장소 칸은 집 주소나 메모일 수 있어 아이 기기로 보내지 않는다.
    institutional = event.consult_type in (
        ScheduleConsultType.REGULAR,
        ScheduleConsultType.INITIAL,
        ScheduleConsultType.CLOSING,
    )

    return {"date": event.event_date.isoformat(), "time": event.event_time, "place": event.place if institutional else None}


def get_home(db: Session, link: ChildAppLink) -> ChildHomeResponse:
    row = db.scalar(
        select(ChildQuestionSet)
        .where(
            ChildQuestionSet.case_id == link.case_id,
            ChildQuestionSet.status == ChildQuestionSetStatus.PENDING,
        )
        .order_by(ChildQuestionSet.created_at.desc())
        .limit(1)
    )
    pending = None

    if row is not None:
        # flag · red 는 판정 기준이라 앱으로 보내지 않는다.
        hidden = {"flag", "red", "category", "short"}
        pending = {
            "id": row.id,
            "questions": [{key: value for key, value in item.items() if key not in hidden} for item in row.questions],
        }

    return ChildHomeResponse(
        pending=pending,
        next_consult=_next_consult(db, link.case_id, datetime.now(LOCAL_TZ).date()),
        alert=_child_alert_status(db, link),
        staff_hours=staff_hours(),
    )


def staff_hours(now: Optional[datetime] = None) -> Dict[str, Any]:
    """상담사가 바로 볼 수 있는 시간인지(한국 시간, CHILD_APP_STAFF_HOURS · CHILD_APP_STAFF_DAYS)."""

    local = (now or _utcnow()).astimezone(LOCAL_TZ)
    start, end = settings.CHILD_APP_STAFF_HOURS.split("-")
    days = {int(day) for day in settings.CHILD_APP_STAFF_DAYS.split(",")}
    minute = local.hour * 60 + local.minute

    def _minutes(text: str) -> int:
        hour, mins = text.split(":")
        return int(hour) * 60 + int(mins)

    on_duty = local.weekday() in days and _minutes(start) <= minute < _minutes(end)
    weekdays = "평일" if days == {0, 1, 2, 3, 4} else "".join("월화수목금토일"[day] for day in sorted(days))

    return {"on_duty": on_duty, "label": f"{weekdays} {start}~{end}"}


def _alert_pressed_at(event: ChildAppEvent) -> datetime:
    """아이가 마지막으로 누른 시각. 확인 전에 다시 누르면 새 줄 없이 payload.last_at 만 오른다(send_alert)."""

    last_at = (event.payload or {}).get("last_at")
    if last_at:
        try:
            return _aware(datetime.fromisoformat(last_at))
        except (TypeError, ValueError):
            pass
    return _aware(event.created_at)


def _child_alert_status(db: Session, link: ChildAppLink) -> Optional[Dict[str, Any]]:
    """이 기기가 마지막으로 급하다고 알린 것을 선생님이 확인했는지. 누가 · 언제 확인했는지는 보내지 않는다.

    확인 전 알림은 사례에 하나뿐이고 늘 가장 최근 알림 줄이다(send_alert). 그래서 가장 최근 줄 하나만 본다.
    - 이 기기가 연결된 뒤에 누른 적이 있어야 보인다(마지막으로 누른 시각 기준). 예전 기기의 알림은 숨기되,
      새 기기에서 다시 누르면 같은 줄이라도 보인다(민규 #175 리뷰 1).
    - 확인한 알림은 마지막으로 누른 뒤 24시간만 보인다. 확인 전이면 시간이 지나도 남아 112 · 1388 안내를 이어 간다.
    """

    now = _utcnow()
    event = db.scalar(
        select(ChildAppEvent)
        .where(ChildAppEvent.case_id == link.case_id, ChildAppEvent.kind == ChildAppEventKind.ALERT)
        .order_by(ChildAppEvent.created_at.desc(), ChildAppEvent.id.desc())
        .limit(1)
    )

    if event is None:
        return None

    pressed_at = _alert_pressed_at(event)
    if link.linked_at is not None and pressed_at < _aware(link.linked_at):
        return None

    acknowledged = event.acknowledged_at is not None
    if acknowledged and now - pressed_at > ALERT_STATUS_SHOWN:
        return None

    return {
        "sent_at": pressed_at,
        "acknowledged": acknowledged,
        # 처음 알린 뒤로 확인 전인 시간으로 잰다(다시 눌러도 줄지 않는다). 서버 시계라 폰 시계가 틀려도 같다.
        "overdue": not acknowledged and now - _aware(event.created_at) >= ALERT_OVERDUE_AFTER,
    }


def _grade(question: Dict[str, Any], answer: ChildAnswerInput) -> Dict[str, Any]:
    item = {"question_id": question["id"], "question": question["short"]}
    skip = {**item, "answer": SKIP_TEXT, "level": ChildAnswerLevel.SKIP.value}

    if question["type"] == "text":
        if answer.chip is not None and answer.chip not in question["chips"]:
            raise bad_request(ErrorCode.VALIDATION_ERROR, "보낼 수 없는 답이 들어 있습니다.")

        text = (answer.text or "").strip()

        # 글을 함께 썼으면 '답하기 어려워요' 칩이어도 글을 남긴다.
        if answer.skipped or (answer.chip == SKIP_TEXT and not text):
            return skip

        shown = " · ".join(part for part in (text, answer.chip) if part) or "(비워 둠)"

        return {
            **item,
            "answer": shown,
            "wrote_text": bool(text),
            # 상담사 화면의 '아이가 쓴 글'에는 고른 칩을 빼고 아이가 쓴 글만 보인다.
            "written": text or None,
            "level": ChildAnswerLevel.NONE.value,
        }

    if answer.skipped:
        return skip

    options = question["options"]

    if answer.choice_index is None or answer.choice_index >= len(options):
        raise bad_request(ErrorCode.VALIDATION_ERROR, "보낼 수 없는 답이 들어 있습니다.")

    level = ChildAnswerLevel.NONE

    if question.get("red") is not None and answer.choice_index >= question["red"]:
        level = ChildAnswerLevel.RED
    elif question.get("flag") is not None and answer.choice_index >= question["flag"]:
        level = ChildAnswerLevel.AMBER

    return {**item, "answer": options[answer.choice_index], "level": level.value}


def submit_answers(
    db: Session,
    link: ChildAppLink,
    question_set_id: uuid.UUID,
    answers: List[ChildAnswerInput],
) -> None:
    # 잠금 순서: 연결 행 → 질문 묶음 → AI 초안. 승인 · 고치기도 연결 행을 먼저 잠가 서로 기다리게 한다(교착 방지, 민규 #165 재리뷰).
    db.scalar(select(ChildAppLink).where(ChildAppLink.id == link.id).with_for_update())
    row = db.scalar(
        select(ChildQuestionSet)
        .where(ChildQuestionSet.id == question_set_id, ChildQuestionSet.case_id == link.case_id)
        .with_for_update()
    )

    if row is None:
        raise not_found(ErrorCode.NOT_FOUND, "질문을 찾을 수 없습니다.")

    if row.status != ChildQuestionSetStatus.PENDING:
        raise conflict(ErrorCode.DUPLICATE_RESOURCE, "이미 끝난 질문입니다.")

    by_id = {answer.question_id: answer for answer in answers}
    expected = {question["id"] for question in row.questions}
    # 아이가 답하는 사이 상담사가 AI 추가 질문을 승인 · 취소하면 묶음이 바뀐다(민규 #165 리뷰 1).
    # 그때도 아이가 고른 답은 받는다: 취소된 AI 질문의 답은 버리고, 새로 더해진 AI 질문은 다음 묶음으로 넘긴다.
    extra = set(by_id) - expected
    missing = [question for question in row.questions if question["id"] not in by_id]
    answered_questions = [question for question in row.questions if question["id"] in by_id]

    if (
        len(by_id) != len(answers)
        or any(not question_id.startswith(AI_QUESTION_PREFIX) for question_id in extra)
        or any(not question["id"].startswith(AI_QUESTION_PREFIX) for question in missing)
        or not answered_questions
    ):
        raise bad_request(ErrorCode.VALIDATION_ERROR, "모든 질문의 답을 보내 주세요.")

    if missing:
        carried = ChildQuestionSet(case_id=row.case_id, sent_by_id=row.sent_by_id, questions=missing)
        db.add(carried)
        db.flush()
        row.questions = answered_questions
        child_app_ai_service.move_questions(db, row.case_id, {question["id"] for question in missing}, carried.id)

    items = [_grade(question, by_id[question["id"]]) for question in answered_questions]
    levels = {item["level"] for item in items}
    worst = ChildAnswerLevel.NONE

    if ChildAnswerLevel.RED.value in levels:
        worst = ChildAnswerLevel.RED
    elif ChildAnswerLevel.AMBER.value in levels:
        worst = ChildAnswerLevel.AMBER

    now = _utcnow()
    row.status = ChildQuestionSetStatus.ANSWERED
    row.answered_at = now
    link.last_response_at = now
    # 글은 판정하지 않는다. 글이 있으면 상담사가 읽도록 확인 필요로만 올린다.
    wants_contact = any(
        item["level"] != ChildAnswerLevel.SKIP.value and by_id[item["question_id"]].chip == CONTACT_REQUEST_CHIP
        for item in items
    )
    wrote_text = any(item.get("wrote_text") for item in items)
    # AI 추가 질문은 위험 답의 후속이라 답을 판정하지 않고 확인 필요로만 올린다(민규 #165 리뷰 5).
    followups = [item for item in items if item["question_id"].startswith(AI_QUESTION_PREFIX)]
    followup = bool(followups)
    payload: Dict[str, Any] = {"items": items}

    if wants_contact or wrote_text or followup:
        # 추가 질문을 모두 '답하기 어려워요' 로 넘겼으면 답했다고 하지 않는다.
        skipped = all(item["level"] == ChildAnswerLevel.SKIP.value for item in followups)
        payload["alert_reason"] = (
            "CONTACT_REQUEST" if wants_contact
            else "TEXT_ANSWER" if wrote_text
            else "FOLLOWUP_SKIPPED" if skipped
            else "FOLLOWUP_ANSWER"
        )

    _add_event(
        db,
        link.case_id,
        ChildAppEventKind.ANSWERS,
        payload,
        level=worst,
        needs_ack=worst == ChildAnswerLevel.RED or wants_contact or wrote_text or followup,
    )
    db.commit()


from app.services import child_app_ai_service  # noqa: E402 — 서로 부르므로 맨 끝에서 불러온다.
