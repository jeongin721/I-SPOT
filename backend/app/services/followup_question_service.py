# 승인한 추가 질문 조회 · 저장(18절).
#
# AI 질문 초안(분석 결과 followup_questions)은 그대로 두고, 상담사가 승인 · 고친 · 직접 쓴 질문 목록만 회차마다 한 행에
# 저장한다. 저장은 목록 통째 바꾸기다. 질문마다 승인 일시(approved_at)는 서버가 찍고, 전과 똑같은 질문은 처음 승인한
# 일시를 그대로 둔다(목록 순서만 바꾸거나 다른 질문을 더해도 이미 승인한 질문의 일시가 바뀌지 않게).

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.enums import AuditAction, FollowupQuestionSource, SessionStatus
from app.core.errors import APIError, ErrorCode, conflict
from app.core.state_machine import assert_status_in
from app.models.followup_question import SessionFollowupQuestions
from app.models.session import ConsultationSession
from app.models.user import User
from app.schemas.followup_question import (
    FollowupQuestionIn,
    FollowupQuestionsResponse,
    FollowupQuestionsSaveRequest,
)
from app.services import audit_service, transcript_service

# 저장을 받는 회차 상태. 위험도 판단(11절)과 같다 — 원문을 확정한 뒤부터, AI 분석 중에는 받지 않는다.
# AI 실패에도 받는다(AI 초안 없이 상담사가 직접 쓸 수 있다). 승인 뒤에도 받는다(다음 상담 전 브리핑에서 고친다).
EDITABLE_STATUSES = {
    SessionStatus.STT_CONFIRMED,
    SessionStatus.AI_REVIEW_REQUIRED,
    SessionStatus.AI_FAILED,
    SessionStatus.APPROVED,
}

_Key = Tuple[str, str, str, Tuple[str, ...], Optional[str]]


def get_row(db: Session, session_id: uuid.UUID) -> Optional[SessionFollowupQuestions]:
    return db.scalar(
        select(SessionFollowupQuestions).where(SessionFollowupQuestions.session_id == session_id)
    )


def to_response(session_id: uuid.UUID, row: Optional[SessionFollowupQuestions]) -> FollowupQuestionsResponse:
    if row is None:
        return FollowupQuestionsResponse(
            session_id=session_id, questions=[], updated_at=None, updated_by_id=None
        )

    return FollowupQuestionsResponse(
        session_id=session_id,
        questions=list(row.questions or []),
        updated_at=row.updated_at,
        updated_by_id=row.updated_by_id,
    )


def _key(item: Dict[str, Any]) -> _Key:
    return (
        str(item.get("text", "")),
        str(item.get("kind", "")),
        str(item.get("source", "")),
        tuple(item.get("segment_ids") or []),
        item.get("bank_code"),
    )


def _check_segment_ids(db: Session, session_id: uuid.UUID, questions: List[FollowupQuestionIn]) -> None:
    """근거 번호는 그 회차 최신 전사본에 있는 것만 받는다(422, 다른 입력 검증과 같은 코드).

    문구에는 받은 번호를 넣지 않는다.
    """

    wanted = {segment_id for question in questions for segment_id in question.segment_ids}

    if not wanted:
        return

    transcript = transcript_service.get_latest_transcript(db, session_id)
    known = {segment.segment_id for segment in transcript.segments} if transcript else set()

    if not wanted <= known:
        raise APIError(
            ErrorCode.VALIDATION_ERROR,
            "근거 발화 번호 중 이 회차 전사본에 없는 것이 있습니다. 새로고침 후 다시 저장해 주세요.",
            status_code=422,
        )


def save_questions(
    db: Session,
    session: ConsultationSession,
    current_user: User,
    payload: FollowupQuestionsSaveRequest,
) -> SessionFollowupQuestions:
    assert_status_in(session.status, EDITABLE_STATUSES)
    _check_segment_ids(db, session.id, payload.questions)

    now = datetime.now(timezone.utc).isoformat()
    row = get_row(db, session.id)

    # 전과 똑같은 질문의 승인 일시(같은 질문이 여럿이면 앞에서부터 하나씩 짝짓는다).
    previous: Dict[_Key, List[str]] = {}

    for item in (row.questions if row else None) or []:
        previous.setdefault(_key(item), []).append(item.get("approved_at") or now)

    questions: List[Dict[str, Any]] = []

    for question in payload.questions:
        item: Dict[str, Any] = {
            "text": question.text,
            "kind": question.kind.value,
            "source": question.source.value,
            "segment_ids": list(question.segment_ids),
            "bank_code": question.bank_code,
        }
        kept = previous.get(_key(item))
        item["approved_at"] = kept.pop(0) if kept else now
        questions.append(item)

    # 감사 기록에는 수만 남긴다. 질문 문장은 아동 진술을 이어받아 넣지 않는다.
    detail = {
        "count": len(questions),
        "ai_count": sum(1 for item in questions if item["source"] == FollowupQuestionSource.AI.value),
        "counselor_count": sum(
            1 for item in questions if item["source"] == FollowupQuestionSource.COUNSELOR.value
        ),
        "previous_count": len(row.questions or []) if row else 0,
    }

    if row is None:
        row = SessionFollowupQuestions(
            session_id=session.id, questions=questions, updated_by_id=current_user.id
        )
        db.add(row)

        try:
            db.flush()
        except IntegrityError as error:
            # 같은 회차를 동시에 처음 저장한 다른 요청이 먼저 커밋했다(session_id 유니크).
            db.rollback()

            raise conflict(
                ErrorCode.DUPLICATE_RESOURCE,
                "다른 요청이 먼저 추가 질문을 저장했습니다. 새로고침 후 다시 저장해 주세요.",
            ) from error
    else:
        row.questions = questions
        row.updated_by_id = current_user.id

    audit_service.record(
        db,
        action=AuditAction.FOLLOWUP_QUESTIONS_UPDATED,
        entity_type="SessionFollowupQuestions",
        entity_id=row.id,
        actor_id=current_user.id,
        case_id=session.case_id,
        session_id=session.id,
        detail=detail,
    )

    db.commit()
    db.refresh(row)

    return row
