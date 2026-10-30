# 다음 상담 전 확인할 사항 조회 · 저장(18.1절, 2026-10-30). 추가 질문(followup_question_service)과 같은 꼴.
#
# AI 확인 메모 초안(분석 결과 followup_check_points)은 그대로 두고, 상담사가 고친 · 직접 쓴 · 브리핑에 넣기로 고른 목록을
# 회차마다 한 행에 저장한다. 저장은 목록 통째 바꾸기다.

import uuid
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.enums import AuditAction, FollowupQuestionSource
from app.core.errors import ErrorCode, conflict
from app.core.state_machine import assert_status_in
from app.models.followup_check import SessionFollowupChecks
from app.models.session import ConsultationSession
from app.models.user import User
from app.schemas.followup_check import FollowupChecksResponse, FollowupChecksSaveRequest
from app.services import audit_service
from app.services.followup_question_service import EDITABLE_STATUSES, _check_segment_ids


def get_row(db: Session, session_id: uuid.UUID) -> Optional[SessionFollowupChecks]:
    return db.scalar(select(SessionFollowupChecks).where(SessionFollowupChecks.session_id == session_id))


def to_response(session_id: uuid.UUID, row: Optional[SessionFollowupChecks]) -> FollowupChecksResponse:
    if row is None:
        return FollowupChecksResponse(session_id=session_id, saved=False, items=[], updated_at=None, updated_by_id=None)

    return FollowupChecksResponse(
        session_id=session_id,
        saved=True,
        items=list(row.items or []),
        updated_at=row.updated_at,
        updated_by_id=row.updated_by_id,
    )


def save_checks(
    db: Session,
    session: ConsultationSession,
    current_user: User,
    payload: FollowupChecksSaveRequest,
) -> SessionFollowupChecks:
    # 받는 회차 상태 · 근거 번호 확인은 추가 질문과 같다(원문 확정 뒤, AI 분석 중 제외, 승인 뒤에도 받음).
    assert_status_in(session.status, EDITABLE_STATUSES)
    _check_segment_ids(db, session.id, payload.items)

    items: List[Dict[str, Any]] = [
        {
            "text": item.text,
            "source": item.source.value,
            "segment_ids": list(item.segment_ids),
            # 상담사가 직접 쓴 것은 '고침' 이 아니다.
            "edited": bool(item.edited) and item.source == FollowupQuestionSource.AI,
            "in_briefing": bool(item.in_briefing),
        }
        for item in payload.items
    ]
    row = get_row(db, session.id)

    # 감사 기록에는 수만 남긴다. 확인 사항 문장은 아동 진술을 이어받아 넣지 않는다.
    detail = {
        "count": len(items),
        "ai_count": sum(1 for item in items if item["source"] == FollowupQuestionSource.AI.value),
        "counselor_count": sum(1 for item in items if item["source"] == FollowupQuestionSource.COUNSELOR.value),
        "edited_count": sum(1 for item in items if item["edited"]),
        "briefing_count": sum(1 for item in items if item["in_briefing"]),
        "previous_count": len(row.items or []) if row else 0,
    }

    if row is None:
        row = SessionFollowupChecks(session_id=session.id, items=items, updated_by_id=current_user.id)
        db.add(row)

        try:
            db.flush()
        except IntegrityError as error:
            # 같은 회차를 동시에 처음 저장한 다른 요청이 먼저 커밋했다(session_id 유니크).
            db.rollback()

            raise conflict(
                ErrorCode.DUPLICATE_RESOURCE,
                "다른 요청이 먼저 확인 사항을 저장했습니다. 새로고침 후 다시 저장해 주세요.",
            ) from error
    else:
        row.items = items
        row.updated_by_id = current_user.id

    audit_service.record(
        db,
        action=AuditAction.FOLLOWUP_CHECKS_UPDATED,
        entity_type="SessionFollowupChecks",
        entity_id=row.id,
        actor_id=current_user.id,
        case_id=session.case_id,
        session_id=session.id,
        detail=detail,
    )

    db.commit()
    db.refresh(row)

    return row
