# /sessions/{session_id}/followup-checklist — 다음 상담 체크리스트(19절)

import uuid

from fastapi import APIRouter, BackgroundTasks, status

from app.core.deps import CurrentUser, DbSession
from app.core.responses import DataResponse
from app.schemas.followup_checklist import FollowupChecklistEnvelope, FollowupChecklistOut
from app.services import followup_checklist_service
from app.services.access import get_session_or_404

router = APIRouter(prefix="/sessions", tags=["followup-checklist"])


@router.get(
    "/{session_id}/followup-checklist",
    response_model=DataResponse[FollowupChecklistEnvelope],
)
def get_followup_checklist(
    session_id: uuid.UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> DataResponse[FollowupChecklistEnvelope]:
    session = get_session_or_404(db, session_id, current_user)

    return DataResponse(data=followup_checklist_service.get_envelope(db, session))


@router.post(
    "/{session_id}/followup-checklist",
    response_model=DataResponse[FollowupChecklistOut],
    status_code=status.HTTP_202_ACCEPTED,
)
def request_followup_checklist(
    session_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    db: DbSession,
    current_user: CurrentUser,
) -> DataResponse[FollowupChecklistOut]:
    session = get_session_or_404(db, session_id, current_user)
    row, attempt = followup_checklist_service.request_generation(db, session, current_user)

    # 이미 만드는 중이면(attempt 없음) 새 작업을 띄우지 않고 그 행을 돌려준다.
    if attempt is not None:
        background_tasks.add_task(followup_checklist_service.process_checklist, row.id, attempt)

    return DataResponse(data=followup_checklist_service.to_out(row))
