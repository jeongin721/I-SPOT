# 아이 앱(콩콩) AI 초안 — 확인해 볼 점 · 추가 질문(API_CONTRACT 24절, 2026-11-09).
#
# 가장 최근 답에서 확인이 필요한 항목만, 담당 상담사가 화면을 열 때 만든다. 사례의 등록 이름은 메모리에서만 가리기에 넘긴다.
# 초안은 상담사가 승인해야 아이 앱으로 간다. 승인하면 답하지 않은 질문 묶음에 더하고, 승인을 풀면 그 묶음에서 뺀다(이미 답했으면 409).
# 감사 기록에는 수만 남긴다(메모 · 질문 문장은 넣지 않는다).

import copy
import threading
import time
import uuid
from typing import Any, Callable, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.adapters.module_loader import ModuleLoadError, load_callable
from app.core.concurrency import OperationTimeout, run_with_timeout
from app.core.config import settings
from app.core.enums import AuditAction, ChildAnswerLevel, ChildAppEventKind, ChildAppLinkStatus, ChildQuestionSetStatus
from app.core.errors import APIError, ErrorCode, conflict, not_found
from app.models.case import Case
from app.models.child_app import ChildAppAiDraft, ChildAppEvent, ChildQuestionSet
from app.models.user import User
from app.schemas.child_app import ChildAiDraftResponse, ChildAiQuestionUpdateRequest
from app.services import audit_service, child_app_service, personal_info_service

MODULE = "ai.modeling.abuse.child_answer_llm"
MAX_SET_QUESTIONS = 8
PREVIOUS_ANSWERS = 3
HISTORY_LIMIT = 50
_FLAGGED = {ChildAnswerLevel.RED.value, ChildAnswerLevel.AMBER.value}

_override: Optional[Callable[..., List[Dict[str, Any]]]] = None


def set_generator_override(generator: Optional[Callable[..., List[Dict[str, Any]]]]) -> None:
    """시험에서 성공 · 실패를 넣는 hook."""

    global _override
    _override = generator


def is_enabled() -> bool:
    return _override is not None or settings.CHILD_APP_AI_PROVIDER != "off"


class _Limits:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.running: set = set()
        self.slots = threading.BoundedSemaphore(settings.CHILD_APP_AI_MAX_CONCURRENCY)


_limits = _Limits()


def reset_limits() -> None:
    global _limits
    _limits = _Limits()


def _mock(items: List[Dict[str, Any]], **_: Any) -> List[Dict[str, Any]]:
    return [
        {
            "question_id": item["question_id"],
            "note": f"(예시) '{item['answer']}' 답을 다음 상담에서 살펴봐 주세요.",
            "questions": [{"text": "(예시) 요즘 가장 마음 쓰이는 일은 언제 있었나요?", "options": ["오늘", "이번 주", "말하기 어려워요"]}],
        }
        for item in items
    ]


def _generator() -> Callable[..., List[Dict[str, Any]]]:
    if _override is not None:
        return _override

    if settings.CHILD_APP_AI_PROVIDER == "mock":
        return _mock

    return load_callable(MODULE, "generate_child_answer_drafts")


def _run_ai(case_id: uuid.UUID, items: List[Dict[str, Any]], written: Optional[str], names: List[str]) -> List[Dict[str, Any]]:
    limits = _limits

    with limits.lock:
        if case_id in limits.running:
            raise APIError(ErrorCode.RATE_LIMITED, "이 사례의 AI 초안을 만들고 있습니다. 잠시 후 새로고침해 주세요.", status_code=429)

        if not limits.slots.acquire(blocking=False):
            raise APIError(ErrorCode.RATE_LIMITED, "다른 AI 초안을 만드는 중입니다. 잠시 후 다시 시도해 주세요.", status_code=429)

        limits.running.add(case_id)

    started = threading.Event()
    released: List[bool] = []

    def release() -> None:
        with limits.lock:
            if released:
                return

            released.append(True)
            limits.running.discard(case_id)

        limits.slots.release()

    try:
        deadline = time.monotonic() + settings.CHILD_APP_AI_TIMEOUT_SECONDS
        run = _generator()
    except BaseException:
        release()
        raise

    def work() -> List[Dict[str, Any]]:
        started.set()

        try:
            return run(items, written=written, known_identifiers=names, deadline=deadline)
        finally:
            release()

    try:
        return run_with_timeout(work, settings.CHILD_APP_AI_TIMEOUT_SECONDS)
    finally:
        if not started.is_set():
            release()


def _answer_events(db: Session, case_id: uuid.UUID) -> List[ChildAppEvent]:
    return list(
        db.scalars(
            select(ChildAppEvent)
            .where(ChildAppEvent.case_id == case_id, ChildAppEvent.kind == ChildAppEventKind.ANSWERS)
            .order_by(ChildAppEvent.created_at.desc(), ChildAppEvent.id.desc())
            .limit(HISTORY_LIMIT)
        )
    )


def _items_of(event: ChildAppEvent) -> List[Dict[str, Any]]:
    items = event.payload.get("items")

    return items if isinstance(items, list) else []


def _draft_for_event(db: Session, event_id: uuid.UUID, *, lock: bool = False) -> Optional[ChildAppAiDraft]:
    query = select(ChildAppAiDraft).where(ChildAppAiDraft.event_id == event_id)

    return db.scalar(query.with_for_update() if lock else query)


def to_response(db: Session, row: ChildAppAiDraft) -> ChildAiDraftResponse:
    set_ids = {
        uuid.UUID(question["question_set_id"])
        for item in row.items
        for question in item["questions"]
        if question.get("question_set_id")
    }
    statuses = (
        dict(db.execute(select(ChildQuestionSet.id, ChildQuestionSet.status).where(ChildQuestionSet.id.in_(set_ids))).all())
        if set_ids
        else {}
    )

    def state(question: Dict[str, Any]) -> Optional[ChildQuestionSetStatus]:
        set_id = question.get("question_set_id")

        return statuses.get(uuid.UUID(set_id)) if set_id else None

    return ChildAiDraftResponse(
        id=row.id,
        event_id=row.event_id,
        items=[
            {
                "question_id": item["question_id"],
                "note": item["note"],
                "note_edited": bool(item.get("note_edited")),
                "questions": [
                    {
                        "id": question["id"],
                        "text": question["text"],
                        "options": question["options"],
                        "edited": bool(question.get("edited")),
                        # 새 질문을 보내 대체됐으면 앱에 없으니 승인 전으로 보인다.
                        "approved": state(question) in (ChildQuestionSetStatus.PENDING, ChildQuestionSetStatus.ANSWERED),
                        "answered": state(question) == ChildQuestionSetStatus.ANSWERED,
                    }
                    for question in item["questions"]
                ],
            }
            for item in row.items
        ],
    )


def latest_draft(db: Session, case_id: uuid.UUID) -> Optional[ChildAiDraftResponse]:
    event = db.scalar(
        select(ChildAppEvent)
        .where(ChildAppEvent.case_id == case_id, ChildAppEvent.kind == ChildAppEventKind.ANSWERS)
        .order_by(ChildAppEvent.created_at.desc(), ChildAppEvent.id.desc())
        .limit(1)
    )
    row = _draft_for_event(db, event.id) if event else None

    return to_response(db, row) if row else None


def create_draft(db: Session, case: Case, user: User) -> ChildAppAiDraft:
    """가장 최근 답의 초안을 만든다. 이미 있으면 그대로 돌려준다."""

    child_app_service.ensure_assigned(case, user)
    # 종결 사례의 아이 답은 외부로 보내지 않는다(민규 #165 리뷰 2).
    child_app_service.ensure_active(case)

    if not is_enabled():
        raise APIError(ErrorCode.CHILD_APP_AI_DISABLED, "AI 초안 기능이 꺼져 있습니다.", status_code=503)

    events = _answer_events(db, case.id)

    if not events:
        raise conflict(ErrorCode.INVALID_CASE_STATE, "아이가 보낸 답이 아직 없습니다.")

    latest = events[0]
    existing = _draft_for_event(db, latest.id)

    if existing is not None:
        return existing

    def previous_of(question_id: str) -> List[str]:
        answers = [
            item["answer"] for event in events[1:] for item in _items_of(event) if item.get("question_id") == question_id
        ][:PREVIOUS_ANSWERS]

        return list(reversed(answers))

    flagged = [
        {
            "question_id": item["question_id"],
            "question": child_app_service.question_text(item),
            "answer": item["answer"],
            "previous": previous_of(item["question_id"]),
        }
        for item in _items_of(latest)
        if item.get("level") in _FLAGGED
    ]

    if not flagged:
        raise conflict(ErrorCode.INVALID_CASE_STATE, "확인이 필요한 답이 없습니다.")

    written = next((item.get("written") for item in _items_of(latest) if item.get("written")), None)
    names = personal_info_service.known_identifiers(db, case.id, extra=[case.child_alias])
    event_id = latest.id
    db.rollback()  # AI 를 기다리는 동안 DB 연결 · 거래를 쥐지 않는다.

    try:
        generated = _run_ai(case.id, flagged, written, names)
    except APIError:
        raise
    except OperationTimeout as error:
        raise APIError(ErrorCode.AI_TIMEOUT, "AI 초안이 제한 시간 안에 끝나지 않았습니다. 다시 시도해 주세요.", status_code=504) from error
    except (ModuleLoadError, Exception) as error:  # noqa: BLE001 — 이유(이름 가리기 막힘 등)와 글은 응답에 싣지 않는다.
        raise APIError(ErrorCode.AI_FAILED, "AI 초안을 만들지 못했습니다. 다시 시도해 주세요.", status_code=502) from error

    allowed = {item["question_id"] for item in flagged}
    items = [
        {
            "question_id": entry["question_id"],
            "note": entry["note"],
            "note_edited": False,
            "questions": [
                {
                    "id": f"ai_{uuid.uuid4().hex[:16]}",
                    "text": question["text"],
                    "options": list(question["options"]),
                    "edited": False,
                    "question_set_id": None,
                }
                for question in entry.get("questions", [])
            ],
        }
        for entry in generated
        if entry.get("question_id") in allowed
    ]
    row = ChildAppAiDraft(case_id=case.id, event_id=event_id, items=items, created_by_id=user.id)
    db.add(row)

    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        winner = _draft_for_event(db, event_id)

        if winner is None:
            raise

        return winner

    audit_service.record(
        db,
        action=AuditAction.CHILD_APP_AI_DRAFT_CREATED,
        entity_type="child_app_ai_draft",
        entity_id=row.id,
        actor_id=user.id,
        case_id=case.id,
        detail={"flagged": len(flagged), "notes": len(items), "questions": sum(len(item["questions"]) for item in items)},
    )
    db.commit()
    db.refresh(row)

    return row


def _locked_draft(db: Session, case: Case, user: User, draft_id: uuid.UUID) -> ChildAppAiDraft:
    child_app_service.ensure_assigned(case, user)
    # 답 제출과 같은 순서로 잠근다: 연결 행 → (묶음) → 초안.
    child_app_service.link_row(db, case.id, lock=True)
    row = db.scalar(
        select(ChildAppAiDraft)
        .where(ChildAppAiDraft.id == draft_id, ChildAppAiDraft.case_id == case.id)
        .with_for_update()
    )

    if row is None:
        raise not_found(ErrorCode.NOT_FOUND, "AI 초안을 찾을 수 없습니다.")

    return row


def _audit_edit(db: Session, case: Case, user: User, row: ChildAppAiDraft, what: str, ip_address: Optional[str]) -> None:
    audit_service.record(
        db,
        action=AuditAction.CHILD_APP_AI_DRAFT_EDITED,
        entity_type="child_app_ai_draft",
        entity_id=row.id,
        actor_id=user.id,
        case_id=case.id,
        detail={"what": what},
        ip_address=ip_address,
    )


def update_note(
    db: Session, case: Case, user: User, draft_id: uuid.UUID, question_id: str, text: str, ip_address: Optional[str]
) -> ChildAppAiDraft:
    row = _locked_draft(db, case, user, draft_id)
    items = copy.deepcopy(row.items)
    item = next((entry for entry in items if entry["question_id"] == question_id), None)

    if item is None:
        raise not_found(ErrorCode.NOT_FOUND, "초안 항목을 찾을 수 없습니다.")

    item["note"] = text
    item["note_edited"] = True
    row.items = items
    _audit_edit(db, case, user, row, "note", ip_address)
    db.commit()
    db.refresh(row)

    return row


def _find_question(items: List[Dict[str, Any]], question_id: str) -> Dict[str, Any]:
    for item in items:
        for question in item["questions"]:
            if question["id"] == question_id:
                return question

    raise not_found(ErrorCode.NOT_FOUND, "추가 질문을 찾을 수 없습니다.")


def move_questions(db: Session, case_id: uuid.UUID, question_ids: set, set_id: uuid.UUID) -> None:
    """아이가 답한 묶음에서 다음 묶음으로 넘긴 AI 질문이 초안에서도 새 묶음을 가리키게 한다."""

    for row in db.scalars(select(ChildAppAiDraft).where(ChildAppAiDraft.case_id == case_id).with_for_update()):
        items = copy.deepcopy(row.items)
        changed = False

        for item in items:
            for question in item["questions"]:
                if question["id"] in question_ids:
                    question["question_set_id"] = str(set_id)
                    changed = True

        if changed:
            row.items = items


def _unsend(db: Session, case: Case, user: User, question: Dict[str, Any], ip_address: Optional[str]) -> None:
    set_id = question.get("question_set_id")

    if not set_id:
        return

    target = db.scalar(select(ChildQuestionSet).where(ChildQuestionSet.id == uuid.UUID(set_id)).with_for_update())

    if target is not None and target.status == ChildQuestionSetStatus.ANSWERED:
        raise conflict(ErrorCode.INVALID_CASE_STATE, "아이가 이미 답한 질문은 되돌릴 수 없습니다.")

    if target is not None and target.status == ChildQuestionSetStatus.PENDING:
        remaining = [entry for entry in target.questions if entry.get("id") != question["id"]]
        target.questions = remaining

        if not remaining:
            target.status = ChildQuestionSetStatus.REPLACED

        # 피드에는 '보냈어요' 가 남아 있으니 취소도 한 줄 남기고, 감사 기록에도 남긴다(민규 #165 리뷰 낮음).
        db.add(ChildAppEvent(case_id=case.id, kind=ChildAppEventKind.QUESTIONS_SENT, payload={"count": 1, "withdrawn": True}))
        audit_service.record(
            db,
            action=AuditAction.CHILD_APP_QUESTION_WITHDRAWN,
            entity_type="child_question_set",
            entity_id=target.id,
            actor_id=user.id,
            case_id=case.id,
            detail={"count": 1},
            ip_address=ip_address,
        )

    question["question_set_id"] = None


def _send(db: Session, case: Case, user: User, question: Dict[str, Any], ip_address: Optional[str]) -> None:
    child_app_service.ensure_active(case)
    link = child_app_service.link_row(db, case.id, lock=True)

    if link is None or link.status != ChildAppLinkStatus.LINKED:
        raise conflict(ErrorCode.INVALID_CASE_STATE, "앱이 연결된 뒤에 질문을 보낼 수 있습니다.")

    copied = {
        "id": question["id"],
        "type": "choice",
        "category": "추가",
        "short": question["text"],
        "text": question["text"],
        "options": list(question["options"]),
    }
    target = db.scalar(
        select(ChildQuestionSet)
        .where(ChildQuestionSet.case_id == case.id, ChildQuestionSet.status == ChildQuestionSetStatus.PENDING)
        .with_for_update()
    )

    if target is None:
        target = ChildQuestionSet(case_id=case.id, sent_by_id=user.id, questions=[copied])
        db.add(target)
        db.flush()
    elif len(target.questions) >= MAX_SET_QUESTIONS:
        raise conflict(ErrorCode.INVALID_CASE_STATE, "아이가 아직 답하지 않은 질문이 너무 많습니다. 답을 받은 뒤 승인해 주세요.")
    else:
        target.questions = [*target.questions, copied]

    question["question_set_id"] = str(target.id)
    db.add(ChildAppEvent(case_id=case.id, kind=ChildAppEventKind.QUESTIONS_SENT, payload={"count": 1}))
    audit_service.record(
        db,
        action=AuditAction.CHILD_APP_QUESTIONS_SENT,
        entity_type="child_question_set",
        entity_id=target.id,
        actor_id=user.id,
        case_id=case.id,
        detail={"count": 1, "ai_draft": True},
        ip_address=ip_address,
    )


def _question_state(db: Session, question: Dict[str, Any]) -> Optional[ChildQuestionSetStatus]:
    set_id = question.get("question_set_id")

    return db.scalar(select(ChildQuestionSet.status).where(ChildQuestionSet.id == uuid.UUID(set_id))) if set_id else None


def update_question(
    db: Session,
    case: Case,
    user: User,
    draft_id: uuid.UUID,
    question_id: str,
    payload: ChildAiQuestionUpdateRequest,
    ip_address: Optional[str],
) -> ChildAppAiDraft:
    """고치면 승인 전으로 돌아간다(디자인 동작). 이미 앱에 갔으면 뺀 뒤 고친다."""

    row = _locked_draft(db, case, user, draft_id)
    items = copy.deepcopy(row.items)
    question = _find_question(items, question_id)
    _unsend(db, case, user, question, ip_address)
    question["text"] = payload.text
    question["options"] = payload.options
    question["edited"] = True
    row.items = items
    _audit_edit(db, case, user, row, "question", ip_address)
    db.commit()
    db.refresh(row)

    return row


def set_approval(
    db: Session, case: Case, user: User, draft_id: uuid.UUID, question_id: str, approved: bool, ip_address: Optional[str]
) -> ChildAppAiDraft:
    row = _locked_draft(db, case, user, draft_id)
    items = copy.deepcopy(row.items)
    question = _find_question(items, question_id)
    state = _question_state(db, question)
    live = state in (ChildQuestionSetStatus.PENDING, ChildQuestionSetStatus.ANSWERED)

    if approved == live:
        return row

    if approved:
        question["question_set_id"] = None
        _send(db, case, user, question, ip_address)
    else:
        _unsend(db, case, user, question, ip_address)

    row.items = items
    db.commit()
    db.refresh(row)

    return row
