# /sessions/{session_id}

import uuid

from fastapi import APIRouter, status

from app.core.deps import CurrentUser, DbSession
from app.core.responses import DataResponse
from app.schemas.session import (
    SessionDetailResponse,
    SessionResponse,
    SessionUpdateRequest,
)
from app.services import session_service
from app.services.access import get_session_or_404

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.get("/{session_id}", response_model=DataResponse[SessionDetailResponse])
def get_session(
    session_id: uuid.UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> DataResponse[SessionDetailResponse]:
    """
    Session 상세 + 진행 상태 요약.

    Frontend 는 새로고침 후 이 endpoint 로 화면 상태를 복원한다.
    """

    session = get_session_or_404(db, session_id, current_user)

    return DataResponse(data=session_service.build_session_detail(db, session))


@router.patch("/{session_id}", response_model=DataResponse[SessionResponse])
def update_session(
    session_id: uuid.UUID,
    payload: SessionUpdateRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> DataResponse[SessionResponse]:
    session = get_session_or_404(db, session_id, current_user)
    updated = session_service.update_session(db, session, current_user, payload)

    return DataResponse(data=SessionResponse.model_validate(updated))


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_session(
    session_id: uuid.UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> None:
    session = get_session_or_404(db, session_id, current_user)
    session_service.delete_session(db, session, current_user)
