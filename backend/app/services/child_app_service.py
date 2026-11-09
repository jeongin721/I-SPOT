# 아이 앱(콩콩) 연결 · 질문 · 답변(API_CONTRACT 23절). 문항과 판정 기준은 콩콩 디자인 그대로다.
#
# 살펴볼 답 · 바로 확인은 서버가 계산한다. 앱이 보낸 값으로 판정하지 않는다.

import hashlib
import secrets
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

from sqlalchemy import select, update
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
OPEN_ALERT_LIMIT = 50
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


def _ensure_assigned(case: Case, user: User) -> None:
    # 코드 발급 · 질문은 담당 상담사의 일이다. 관리자가 코드를 다시 만들면 상담사가 준 코드가 무효가 된다.
    if case.counselor_id != user.id:
        raise forbidden("담당 상담사만 할 수 있습니다.")


def _ensure_active(case: Case) -> None:
    if case.status != CaseStatus.ACTIVE:
        raise conflict(ErrorCode.INVALID_CASE_STATE, "종결된 사례에는 아이 앱을 사용할 수 없습니다.")


def _link_row(db: Session, case_id: uuid.UUID, *, lock: bool = False) -> Optional[ChildAppLink]:
    statement = select(ChildAppLink).where(ChildAppLink.case_id == case_id)

    return db.scalar(statement.with_for_update() if lock else statement)


# =========================================================
# 상담사 웹
# =========================================================

def create_invite(db: Session, case: Case, user: User, ip_address: Optional[str]) -> Dict[str, Any]:
    _ensure_assigned(case, user)
    _ensure_active(case)
    link = _link_row(db, case.id, lock=True)

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
    _ensure_assigned(case, user)
    _ensure_active(case)

    if len(set(question_ids)) != len(question_ids) or any(item not in _BANK_BY_ID for item in question_ids):
        raise bad_request(ErrorCode.VALIDATION_ERROR, "보낼 수 없는 질문이 들어 있습니다.")

    link = _link_row(db, case.id, lock=True)

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


def get_case_view(db: Session, case: Case, user: User) -> ChildAppCaseResponse:
    link = _link_row(db, case.id)
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


    return ChildAppCaseResponse(
        status=link.status.value if link else "NOT_LINKED",
        code_expires_at=link.code_expires_at if link and link.status == ChildAppLinkStatus.INVITED else None,
        linked_at=link.linked_at if link else None,
        last_response_at=link.last_response_at if link else None,
        has_pending_questions=pending is not None,
        can_read_feed=can_read_feed,
        open_alerts=_open_alerts(db, user, case_id=case.id),
        bank=[
            {"id": item["id"], "category": item["category"], "type": item["type"], "text": item["text"]}
            for item in QUESTION_BANK
        ],
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


def _alert_reason(event: ChildAppEvent, case: Case, viewer: User) -> str:
    if event.kind == ChildAppEventKind.ALERT:
        return "ALERT"

    # 담당이 아닌 관리자에게는 답의 성격을 알리지 않고 확인이 필요하다는 사실만 보인다.
    if case.counselor_id != viewer.id:
        return "NEEDS_CHECK"

    return "RED_ANSWER" if event.level == ChildAnswerLevel.RED else "CONTACT_REQUEST"


def _open_alerts(
    db: Session,
    viewer: User,
    *,
    case_id: Optional[uuid.UUID] = None,
    counselor_id: Optional[uuid.UUID] = None,
) -> List[Dict[str, Any]]:
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
            "created_at": event.created_at,
        }
        for event, case in db.execute(statement).all()
    ]


def list_open_alerts(db: Session, user: User) -> List[Dict[str, Any]]:
    """담당 상담사는 자기 사례, 관리자는 전체. 담당자가 자리에 없을 때 놓치지 않게 관리자에게도 보인다."""

    return _open_alerts(db, user, counselor_id=None if user.is_admin else user.id)


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
    )


def _grade(question: Dict[str, Any], answer: ChildAnswerInput) -> Dict[str, Any]:
    item = {"question_id": question["id"], "question": question["short"]}
    skip = {**item, "answer": SKIP_TEXT, "level": ChildAnswerLevel.SKIP.value}

    if question["type"] == "text":
        if answer.chip is not None and answer.chip not in question["chips"]:
            raise bad_request(ErrorCode.VALIDATION_ERROR, "보낼 수 없는 답이 들어 있습니다.")

        if answer.skipped or answer.chip == SKIP_TEXT:
            return skip

        text = (answer.text or "").strip()

        return {**item, "answer": answer.chip or text or "(비워 둠)", "level": ChildAnswerLevel.NONE.value}

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
    expected = [question["id"] for question in row.questions]

    if len(answers) != len(expected) or set(by_id) != set(expected):
        raise bad_request(ErrorCode.VALIDATION_ERROR, "모든 질문의 답을 보내 주세요.")

    items = [_grade(question, by_id[question["id"]]) for question in row.questions]
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
    wants_contact = any(item["answer"] == CONTACT_REQUEST_CHIP for item in items)
    _add_event(
        db,
        link.case_id,
        ChildAppEventKind.ANSWERS,
        {"items": items},
        level=worst,
        needs_ack=worst == ChildAnswerLevel.RED or wants_contact,
    )
    db.commit()
