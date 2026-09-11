# /sessions/{session_id}/audio

import uuid
from typing import Annotated, Optional

from fastapi import APIRouter, File, Form, UploadFile, status

from app.core.deps import CurrentUser, DbSession
from app.core.responses import DataResponse
from app.schemas.audio import AudioResponse, AudioUploadResponse
from app.services import audio_service
from app.services.access import get_session_or_404

router = APIRouter(prefix="/sessions", tags=["audio"])


@router.post(
    "/{session_id}/audio",
    response_model=DataResponse[AudioUploadResponse],
    status_code=status.HTTP_201_CREATED,
    summary="상담 음성 업로드",
)
def upload_audio(
    session_id: uuid.UUID,
    db: DbSession,
    current_user: CurrentUser,
    file: Annotated[UploadFile, File(description="상담 녹음 파일")],
    duration_ms: Annotated[
        Optional[int],
        Form(ge=0, description="클라이언트가 측정한 녹음 길이(ms). WAV 는 서버가 계산한다."),
    ] = None,
) -> DataResponse[AudioUploadResponse]:
    session = get_session_or_404(db, session_id, current_user)

    audio = audio_service.upload_audio(
        db,
        session,
        current_user,
        filename=file.filename,
        content_type=file.content_type,
        file=file.file,
        duration_ms=duration_ms,
    )

    return DataResponse(
        data=AudioUploadResponse(
            audio=AudioResponse.model_validate(audio),
            session_status=session.status,
        )
    )


@router.get(
    "/{session_id}/audio",
    response_model=DataResponse[AudioResponse],
    summary="최신 음성 metadata 조회",
)
def get_audio(
    session_id: uuid.UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> DataResponse[AudioResponse]:
    session = get_session_or_404(db, session_id, current_user)
    audio = audio_service.get_latest_audio(db, session.id)

    return DataResponse(data=AudioResponse.model_validate(audio))
