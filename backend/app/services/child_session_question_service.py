# 아이 앱 '이번 회차 맞춤 질문' AI 초안(API_CONTRACT 24절, 2026-11-24).
#
# 고정 8문항만 있어 한 아이의 1~3회차 질문이 늘 같았다(현장 문제 제기). 가장 최근 분석 회차(AI 검토 필요 · 승인)의
# '확인할 사항' · 상담원 추가 질문 · 승인된 요약과 초기면접지 단어 칸(case_context 와 같은 범위)을 보고 아이에게 물을 질문
# 3~5개를 만든다. 상담사가 질문 보내기에서 고정 문항과 함께 골라야 아이 앱으로 간다(child_app_service.send_questions).
#
# - 담당 상담사만 만들고 본다. 진행 중 사례만. AI 가 꺼져 있으면(CHILD_APP_AI_PROVIDER=off) 만들지 않는다.
# - 회차마다 한 행. 새 회차가 분석되면 화면이 그 회차로 새로 만든다. '다시 만들기'(regenerate)는 같은 행을 바꾼다.
# - 외부로 보내는 값: 나이대 · 성별 · 아동 특성 · 가정 상황(단어), 확인할 사항 · 추가 질문 · 요약 글(이름은 가린 뒤),
#   이미 보낸 질문 글. 이름 · 생년월일 · 연락처 · 사건번호 · 메모는 넣지 않는다.
# - 감사 기록에는 수만 남긴다(질문 · 이유 글은 넣지 않는다).

import copy
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.adapters.module_loader import ModuleLoadError, load_callable
from app.core.concurrency import OperationTimeout
from app.core.config import settings
from app.core.enums import AuditAction, SessionStatus
from app.core.errors import APIError, ErrorCode, bad_request, conflict, not_found
from app.models.case import Case
from app.models.child_app import ChildQuestionSet, ChildSessionQuestionDraft
from app.models.session import ConsultationSession
from app.models.user import User
from app.services import (
    audit_service,
    case_context_service,
    child_app_ai_service,
    child_app_service,
    followup_checklist_service,
    followup_question_service,
    personal_info_service,
)

MODULE = "ai.modeling.abuse.child_session_question_llm"
ID_PREFIX = "sq_"  # 프론트 counselor-web 질문 보내기가 같은 값으로 고정 문항과 구별한다.
ANALYZED = (SessionStatus.AI_REVIEW_REQUIRED, SessionStatus.APPROVED)
#: '이미 보낸 질문' 으로 넘기는 최근 질문 묶음 수(회차마다 같은 질문이 다시 나오지 않게).
RECENT_SETS = 3
MAX_CONTEXT_ITEMS = 8
MAX_SUMMARY_CHARS = 1200

_override: Optional[Callable[..., List[Dict[str, Any]]]] = None


def set_generator_override(generator: Optional[Callable[..., List[Dict[str, Any]]]]) -> None:
    """시험에서 성공 · 실패를 넣는 hook."""

    global _override
    _override = generator


def _mock(context: Dict[str, Any], **_: Any) -> List[Dict[str, Any]]:
    label = context.get("session_label") or "최근 회차"

    return [
        {
            "category": "마음",
            "type": "choice",
            "text": "(예시) 요즘 마음이 가장 편한 때는 언제인가요?",
            "options": ["학교에 있을 때", "집에 있을 때", "친구랑 있을 때"],
            "reason": f"(예시) {label} 확인할 사항과 이어지는 질문입니다.",
        },
        {
            "category": "마음",
            "type": "text",
            "text": "(예시) 이번 주에 기억에 남는 일을 짧게 알려 줄래요?",
            "options": [],
            "reason": f"(예시) {label} 뒤 지낸 이야기를 먼저 들어 봅니다.",
        },
    ]


def is_enabled() -> bool:
    return _override is not None or child_app_ai_service.is_enabled()


def _generator() -> Callable[..., List[Dict[str, Any]]]:
    if _override is not None:
        return _override

    if settings.CHILD_APP_AI_PROVIDER == "mock":
        return _mock

    return load_callable(MODULE, "generate_child_session_questions")


def latest_session(db: Session, case_id: uuid.UUID) -> Optional[ConsultationSession]:
    """분석이 끝난 가장 최근 회차(브리핑 · 사례 상세와 같은 기준)."""

    return db.scalar(
        select(ConsultationSession)
        .where(ConsultationSession.case_id == case_id, ConsultationSession.status.in_(ANALYZED))
        .order_by(ConsultationSession.session_number.desc())
        .limit(1)
    )


def _draft_for(db: Session, session_id: uuid.UUID, *, lock: bool = False) -> Optional[ChildSessionQuestionDraft]:
    query = select(ChildSessionQuestionDraft).where(ChildSessionQuestionDraft.session_id == session_id)

    return db.scalar(query.with_for_update() if lock else query)


def session_label(session: ConsultationSession) -> str:
    return f"{session.session_number}회차"


def to_view(row: ChildSessionQuestionDraft, session: ConsultationSession) -> Dict[str, Any]:
    return {
        "session_id": session.id,
        "session_label": session_label(session),
        "created_at": row.updated_at or row.created_at,
        "items": [
            {
                "id": item["id"],
                "category": item["category"],
                "type": item["type"],
                "text": item["text"],
                "options": list(item.get("options") or []),
                "reason": item.get("reason") or "",
                "edited": bool(item.get("edited")),
            }
            for item in row.items
        ],
    }


def view_for_case(db: Session, case: Case, user: User) -> Optional[Dict[str, Any]]:
    """질문 보내기 화면 값. 담당 상담사만. 만든 초안이 없으면 None(화면이 만들기를 부른다)."""

    if case.counselor_id != user.id:
        return None

    session = latest_session(db, case.id)
    row = _draft_for(db, session.id) if session is not None else None

    return to_view(row, session) if row is not None and session is not None else None


def can_create(db: Session, case: Case, user: User) -> bool:
    """화면이 '맞춤 질문 만들기' 를 부를지. 만들 수 있는 회차가 없거나 AI 가 꺼져 있으면 False."""

    return case.counselor_id == user.id and is_enabled() and latest_session(db, case.id) is not None


def _texts(values: Any) -> List[str]:
    return [str(value).strip() for value in values if str(value).strip()][:MAX_CONTEXT_ITEMS]


def _counselor_questions(db: Session, session: ConsultationSession, result: Any) -> List[str]:
    """상담원이 승인한 추가 질문. 없으면 AI 추가 질문 초안 — 단 승인한 회차만(민규 #195 리뷰: 승인 전 회차의
    상담사가 아직 보지 않은 AI 초안은 넣지 않는다)."""

    row = followup_question_service.get_row(db, session.id)
    approved = [item.get("text") for item in (row.questions if row is not None else []) or [] if isinstance(item, dict)]
    approved = [text for text in approved if text]

    if approved or session.status != SessionStatus.APPROVED:
        return _texts(approved)

    return _texts(draft["text"] for draft in followup_checklist_service.drafts_of(result))


def _sent_texts(db: Session, case_id: uuid.UUID) -> List[str]:
    rows = db.scalars(
        select(ChildQuestionSet)
        .where(ChildQuestionSet.case_id == case_id)
        .order_by(ChildQuestionSet.created_at.desc())
        .limit(RECENT_SETS)
    ).all()
    texts = [item["text"] for item in child_app_service.QUESTION_BANK]

    for row in rows:
        for question in row.questions or []:
            text = question.get("text") if isinstance(question, dict) else None

            if text and text not in texts:
                texts.append(text)

    return texts


def build_context(db: Session, case: Case, session: ConsultationSession) -> Dict[str, Any]:
    case_context = case_context_service.build_case_context(db, session) or {}
    analysis = followup_checklist_service._latest_analysis(db, session.id)
    result = analysis.result if analysis is not None and isinstance(analysis.result, dict) else {}
    summary = followup_checklist_service._summary_text(session.summary)

    return {
        "child": {
            "age_band": case_context.get("child_age_band"),
            "gender": case_context.get("child_gender"),
            "traits": list(case_context.get("intake_child_traits") or []),
            "family": list(case_context.get("intake_family_situations") or []),
        },
        "session_label": session_label(session),
        "checks": _texts(item["item"] for item in followup_checklist_service._check_items_of(db, session.id)),
        "counselor_questions": _counselor_questions(db, session, result),
        "summary": summary[:MAX_SUMMARY_CHARS],
        "sent": _sent_texts(db, case.id),
    }


def create_draft(db: Session, case: Case, user: User, *, regenerate: bool = False) -> Dict[str, Any]:
    """가장 최근 분석 회차의 맞춤 질문을 만든다. 이미 있으면 그대로 돌려준다(regenerate 면 새로 만든다)."""

    child_app_service.ensure_assigned(case, user)
    # 종결 사례의 회차 내용은 외부로 보내지 않는다(아이 답 초안과 같다).
    child_app_service.ensure_active(case)

    if not is_enabled():
        raise APIError(ErrorCode.CHILD_APP_AI_DISABLED, "AI 초안 기능이 꺼져 있습니다.", status_code=503)

    session = latest_session(db, case.id)

    if session is None:
        raise conflict(ErrorCode.INVALID_CASE_STATE, "분석이 끝난 회차가 아직 없습니다.")

    existing = _draft_for(db, session.id)

    if existing is not None and not regenerate:
        return to_view(existing, session)

    context = build_context(db, case, session)
    names = personal_info_service.known_identifiers(db, case.id, extra=[case.child_alias])
    session_id = session.id
    db.rollback()  # AI 를 기다리는 동안 DB 연결 · 거래를 쥐지 않는다.

    try:
        generated = child_app_ai_service.run_limited(
            case.id,
            lambda run, deadline: run(context, known_identifiers=names, deadline=deadline),
            _generator,
        )
    except APIError:
        raise
    except OperationTimeout as error:
        raise APIError(ErrorCode.AI_TIMEOUT, "AI 초안이 제한 시간 안에 끝나지 않았습니다. 다시 시도해 주세요.", status_code=504) from error
    except (ModuleLoadError, Exception) as error:  # noqa: BLE001 — 이유(이름 가리기 막힘 등)와 글은 응답에 싣지 않는다.
        raise APIError(ErrorCode.AI_FAILED, "AI 초안을 만들지 못했습니다. 다시 시도해 주세요.", status_code=502) from error

    items = [
        {
            "id": f"{ID_PREFIX}{uuid.uuid4().hex[:16]}",
            "category": entry["category"],
            "type": entry["type"],
            "text": entry["text"],
            "options": list(entry.get("options") or []),
            "reason": entry.get("reason") or "",
        }
        for entry in generated or []
    ]

    if not items:
        raise APIError(ErrorCode.AI_FAILED, "보낼 만한 맞춤 질문을 만들지 못했습니다. 다시 만들어 보거나 고정 문항을 골라 주세요.", status_code=502)

    session = db.get(ConsultationSession, session_id)
    row = _draft_for(db, session_id, lock=True)

    if row is None:
        row = ChildSessionQuestionDraft(case_id=case.id, session_id=session_id, items=items, created_by_id=user.id)
        db.add(row)

        try:
            db.flush()
        except IntegrityError:
            db.rollback()
            winner = _draft_for(db, session_id)

            if winner is None:
                raise

            return to_view(winner, db.get(ConsultationSession, session_id))
    elif regenerate:
        row.items = items
        row.updated_at = datetime.now(timezone.utc)
    else:
        # 기다리는 사이 다른 요청이 먼저 만들었다.
        return to_view(row, session)

    audit_service.record(
        db,
        action=AuditAction.CHILD_APP_SESSION_QUESTIONS_CREATED,
        entity_type="child_session_question_draft",
        entity_id=row.id,
        actor_id=user.id,
        case_id=case.id,
        detail={"questions": len(items), "regenerate": regenerate},
    )
    db.commit()
    db.refresh(row)

    return to_view(row, session)


SELF_HARM_MESSAGE = "자해 · 죽음에 관한 질문은 아이 앱으로 보내지 않아요. 다음 상담에서 직접 물어 주세요."


def ensure_no_self_harm(text: str, options: List[str]) -> None:
    """상담사가 아이 앱 질문을 고칠 때도 자해 · 자살 · 죽음 말은 받지 않는다(경진 11/24 — 아이가 밤에 혼자 답해도
    그 자리에서 도울 사람이 없다). AI 초안과 같은 기준(child_session_question_llm.has_self_harm). 맞춤 질문 · 아이 답 AI
    추가 질문 고치기가 함께 쓴다."""

    check = load_callable(MODULE, "has_self_harm")

    if any(check(value) for value in [text, *options]):
        raise bad_request(ErrorCode.VALIDATION_ERROR, SELF_HARM_MESSAGE)


def update_question(
    db: Session,
    case: Case,
    user: User,
    question_id: str,
    text: str,
    options: List[str],
    ip_address: Optional[str],
) -> Dict[str, Any]:
    """상담사가 맞춤 질문 문장 · 보기를 고친다(가장 최근 분석 회차 초안만).

    이미 보낸 질문은 질문 묶음에 복사돼 있어 바뀌지 않는다 — 고친 글은 다음에 보낼 때부터 간다.
    건너뛰기는 아이 앱에 따로 있다. 글은 감사 기록에 넣지 않는다.
    """

    child_app_service.ensure_assigned(case, user)
    child_app_service.ensure_active(case)
    session = latest_session(db, case.id)
    row = _draft_for(db, session.id, lock=True) if session is not None else None
    items = copy.deepcopy(row.items) if row is not None else []
    item = next((entry for entry in items if entry["id"] == question_id), None)

    if row is None or item is None:
        raise not_found(ErrorCode.NOT_FOUND, "맞춤 질문을 찾을 수 없습니다. 화면을 새로고침해 주세요.")

    text = text.strip()

    # 공백만 보내면 빈 질문이 아이 앱으로 나간다(민규 #195 머지 뒤 리뷰 1).
    if not text:
        raise bad_request(ErrorCode.VALIDATION_ERROR, "질문 문장을 적어 주세요.")

    cleaned: List[str] = []

    for option in options:
        option = option.strip()

        if option and option not in cleaned:
            cleaned.append(option)

    if item["type"] == "text":
        if cleaned:
            raise bad_request(ErrorCode.VALIDATION_ERROR, "짧은 글 질문에는 보기를 넣지 않습니다.")
    elif not 2 <= len(cleaned) <= 5:
        raise bad_request(ErrorCode.VALIDATION_ERROR, "보기는 2~5개로 적어 주세요.")

    ensure_no_self_harm(text, cleaned)

    item["text"] = text
    item["options"] = cleaned if item["type"] == "choice" else []
    item.pop("concern", None)
    item["edited"] = True
    row.items = items
    row.updated_at = datetime.now(timezone.utc)
    audit_service.record(
        db,
        action=AuditAction.CHILD_APP_SESSION_QUESTIONS_EDITED,
        entity_type="child_session_question_draft",
        entity_id=row.id,
        actor_id=user.id,
        case_id=case.id,
        detail={"what": "question"},
        ip_address=ip_address,
    )
    db.commit()
    db.refresh(row)

    return to_view(row, session)


def question_for_send(db: Session, case_id: uuid.UUID, question_id: str) -> Optional[Dict[str, Any]]:
    """질문 보내기로 보낼 맞춤 질문(질문 묶음에 넣을 모양). 이 사례의 가장 최근 분석 회차 초안에 있는 것만."""

    session = latest_session(db, case_id)
    row = _draft_for(db, session.id) if session is not None else None
    item = next((entry for entry in (row.items if row is not None else []) if entry["id"] == question_id), None)

    if item is None:
        return None

    copied: Dict[str, Any] = {
        "id": item["id"],
        "category": item["category"],
        "type": item["type"],
        # 상담사 화면 답 목록의 짧은 이름 칸. 문장이 길면 앞부분만.
        "short": _short(item["text"]),
        "text": item["text"],
        # 건너뛰지 않은 답은 무엇이든 살펴볼 답(AMBER) — AI 가 보기별 수준을 정하지 않는다(민규 #195 리뷰, 경진 11/24).
        # 판정 기준이라 아이 앱으로 보내지 않는다(get_home hidden).
        "amber_any": True,
    }

    if item["type"] == "text":
        copied["chips"] = list(child_app_service.FREE_TEXT_CHIPS)
    else:
        copied["options"] = list(item["options"])

    return copied


SHORT_CHARS = 18


def _short(text: str) -> str:
    flat = text.strip().rstrip("?").strip()

    return flat if len(flat) <= SHORT_CHARS else f"{flat[:SHORT_CHARS]}…"
