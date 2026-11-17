# /sessions/{session_id}/briefing-checks — 상담 전 브리핑 '확인할 사항' 체크(26절, 2026-11-11)
import uuid

from fastapi import APIRouter

from app.core.deps import CurrentUser, DbSession
from app.core.responses import DataResponse
from app.schemas.briefing_check import BriefingCheckToggleRequest, BriefingChecksResponse
from app.services import briefing_check_service
from app.services.access import get_session_or_404

router = APIRouter(prefix="/sessions", tags=["briefing-checks"])


@router.get("/{session_id}/briefing-checks", response_model=DataResponse[BriefingChecksResponse])
def get_briefing_checks(session_id: uuid.UUID, db: DbSession, current_user: CurrentUser) -> DataResponse[BriefingChecksResponse]:
    session = get_session_or_404(db, session_id, current_user)

    return DataResponse(data=briefing_check_service.to_response(session.id, briefing_check_service.get_row(db, session.id)))


@router.patch("/{session_id}/briefing-checks", response_model=DataResponse[BriefingChecksResponse])
def toggle_briefing_check(
    session_id: uuid.UUID, payload: BriefingCheckToggleRequest, db: DbSession, current_user: CurrentUser
) -> DataResponse[BriefingChecksResponse]:
    session = get_session_or_404(db, session_id, current_user)
    row = briefing_check_service.toggle(db, session, current_user, payload)

    return DataResponse(data=briefing_check_service.to_response(session.id, row))
