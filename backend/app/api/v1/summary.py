# /sessions/{session_id}/summary
#
# 상담사 수정 → 승인 Flow. 승인은 항상 상담사의 명시적 행위다.

import uuid

from fastapi import APIRouter

from app.core.deps import CurrentUser, DbSession
from app.core.responses import DataResponse
from app.schemas.summary import SummaryEnvelope, SummaryResponse, SummaryUpdateRequest
from app.services import summary_service
from app.services.access import get_session_or_404

router = APIRouter(prefix="/sessions", tags=["summary"])


@router.get(
    "/{session_id}/summary",
    response_model=DataResponse[SummaryEnvelope],
    summary="상담 요약 조회 (근거 발화 포함)",
)
def get_summary(
    session_id: uuid.UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> DataResponse[SummaryEnvelope]:
    session = get_session_or_404(db, session_id, current_user)

    return DataResponse(data=summary_service.build_envelope(db, session))


@router.patch(
    "/{session_id}/summary",
    response_model=DataResponse[SummaryResponse],
    summary="상담 요약 수정",
)
def update_summary(
    session_id: uuid.UUID,
    payload: SummaryUpdateRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> DataResponse[SummaryResponse]:
    session = get_session_or_404(db, session_id, current_user)
    summary = summary_service.update_summary(db, session, current_user, payload)

    return DataResponse(data=SummaryResponse.model_validate(summary))


@router.post(
    "/{session_id}/summary/approve",
    response_model=DataResponse[SummaryResponse],
    summary="상담 요약 승인",
)
def approve_summary(
    session_id: uuid.UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> DataResponse[SummaryResponse]:
    session = get_session_or_404(db, session_id, current_user)
    summary = summary_service.approve_summary(db, session, current_user)

    return DataResponse(data=SummaryResponse.model_validate(summary))
