# /sessions/{session_id}/analysis
#
# AI 분석도 Polling 방식이다. Frontend 는 LLM Provider 를 직접 호출하지 않는다.

import uuid

from fastapi import APIRouter, BackgroundTasks, status

from app.core.deps import CurrentUser, DbSession
from app.core.responses import DataResponse
from app.schemas.analysis import AnalysisEnvelope, AnalysisRequestResponse
from app.services import analysis_service
from app.services.access import get_session_or_404

router = APIRouter(prefix="/sessions", tags=["analysis"])


@router.post(
    "/{session_id}/analysis",
    response_model=DataResponse[AnalysisRequestResponse],
    status_code=status.HTTP_202_ACCEPTED,
    summary="AI 분석 실행 요청",
)
def request_analysis(
    session_id: uuid.UUID,
    db: DbSession,
    current_user: CurrentUser,
    background_tasks: BackgroundTasks,
) -> DataResponse[AnalysisRequestResponse]:
    session = get_session_or_404(db, session_id, current_user)
    analysis = analysis_service.request_analysis(db, session, current_user)

    background_tasks.add_task(analysis_service.process_analysis, session.id, analysis.id)

    return DataResponse(
        data=AnalysisRequestResponse(
            session_id=session.id,
            session_status=session.status,
            analysis_id=analysis.id,
            message="AI 분석을 시작했습니다. 상태를 Polling 해 주세요.",
        )
    )


@router.get(
    "/{session_id}/analysis",
    response_model=DataResponse[AnalysisEnvelope],
    summary="AI 분석 결과 조회 (Polling)",
)
def get_analysis(
    session_id: uuid.UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> DataResponse[AnalysisEnvelope]:
    session = get_session_or_404(db, session_id, current_user)

    return DataResponse(data=analysis_service.build_envelope(db, session))
