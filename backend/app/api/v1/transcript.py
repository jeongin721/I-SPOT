# /sessions/{session_id}/transcript
#
# STT 는 장시간 작업이므로 요청은 202 로 즉시 반환하고
# Frontend 는 GET 으로 Polling 한다.(docs/02_ARCHITECTURE.md §5)

import uuid

from fastapi import APIRouter, BackgroundTasks, status

from app.core.deps import CurrentUser, DbSession
from app.core.responses import DataResponse
from app.schemas.transcript import (
    STTRequestResponse,
    TranscriptEnvelope,
    TranscriptResponse,
    TranscriptUpdateRequest,
)
from app.services import transcript_service
from app.services.access import get_session_or_404

router = APIRouter(prefix="/sessions", tags=["transcript"])


@router.post(
    "/{session_id}/transcript",
    response_model=DataResponse[STTRequestResponse],
    status_code=status.HTTP_202_ACCEPTED,
    summary="STT 실행 요청",
)
def request_stt(
    session_id: uuid.UUID,
    db: DbSession,
    current_user: CurrentUser,
    background_tasks: BackgroundTasks,
) -> DataResponse[STTRequestResponse]:
    session = get_session_or_404(db, session_id, current_user)
    transcript_service.request_stt(db, session, current_user)

    background_tasks.add_task(transcript_service.process_stt, session.id)

    return DataResponse(
        data=STTRequestResponse(
            session_id=session.id,
            session_status=session.status,
            message="STT 처리를 시작했습니다. 상태를 Polling 해 주세요.",
        )
    )


@router.get(
    "/{session_id}/transcript",
    response_model=DataResponse[TranscriptEnvelope],
    summary="Transcript 조회 (Polling)",
)
def get_transcript(
    session_id: uuid.UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> DataResponse[TranscriptEnvelope]:
    session = get_session_or_404(db, session_id, current_user)

    return DataResponse(data=transcript_service.build_envelope(db, session))


@router.patch(
    "/{session_id}/transcript",
    response_model=DataResponse[TranscriptResponse],
    summary="Transcript 수정 (새 version 생성)",
)
def update_transcript(
    session_id: uuid.UUID,
    payload: TranscriptUpdateRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> DataResponse[TranscriptResponse]:
    session = get_session_or_404(db, session_id, current_user)
    transcript = transcript_service.update_transcript(db, session, current_user, payload)

    return DataResponse(data=transcript_service.to_transcript_response(transcript))


@router.post(
    "/{session_id}/transcript/confirm",
    response_model=DataResponse[TranscriptResponse],
    summary="Transcript 확정",
)
def confirm_transcript(
    session_id: uuid.UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> DataResponse[TranscriptResponse]:
    session = get_session_or_404(db, session_id, current_user)
    transcript = transcript_service.confirm_transcript(db, session, current_user)

    return DataResponse(data=transcript_service.to_transcript_response(transcript))
