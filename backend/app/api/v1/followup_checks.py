# /sessions/{session_id}/followup-checks — 다음 상담 전 확인할 사항 목록(18.1절, 2026-10-30)

import uuid

from fastapi import APIRouter

from app.core.deps import CurrentUser, DbSession
from app.core.responses import DataResponse
from app.schemas.followup_check import FollowupChecksResponse, FollowupChecksSaveRequest
from app.services import followup_check_service
from app.services.access import get_session_or_404

router = APIRouter(prefix="/sessions", tags=["followup-checks"])


@router.get("/{session_id}/followup-checks", response_model=DataResponse[FollowupChecksResponse])
def get_followup_checks(
    session_id: uuid.UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> DataResponse[FollowupChecksResponse]:
    session = get_session_or_404(db, session_id, current_user)
    row = followup_check_service.get_row(db, session.id)

    return DataResponse(data=followup_check_service.to_response(session.id, row))


@router.put("/{session_id}/followup-checks", response_model=DataResponse[FollowupChecksResponse])
def save_followup_checks(
    session_id: uuid.UUID,
    payload: FollowupChecksSaveRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> DataResponse[FollowupChecksResponse]:
    session = get_session_or_404(db, session_id, current_user)
    row = followup_check_service.save_checks(db, session, current_user, payload)

    return DataResponse(data=followup_check_service.to_response(session.id, row))
