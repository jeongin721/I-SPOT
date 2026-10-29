# /sessions/{session_id}/audio

import uuid
from typing import Annotated, Optional

from fastapi import APIRouter, File, Form, UploadFile, status
from fastapi.responses import FileResponse

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


@router.get(
    "/{session_id}/audio/file",
    response_class=FileResponse,
    summary="최신 음성 파일 내려주기(다시 듣기용)",
)
def get_audio_file(
    session_id: uuid.UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> FileResponse:
    """최신 음성 파일의 본문을 그대로 돌려준다. `{"data": ...}` 로 감싸지 않는 유일한 음성 창구다.

    - Range 요청을 받는다(Starlette FileResponse: 206 · Content-Range · 416). 화면은 구간 재생 때
      앞에서부터 다 받지 않고 그 자리로 건너뛸 수 있다.
    - 인증은 다른 창구와 같이 Authorization 헤더뿐이다. 주소에 token 을 넣는 방식은 쓰지 않는다
      (접속 로그 · 브라우저 기록에 token 이 남는다). `<audio src>` 는 헤더를 못 붙이므로 화면은
      fetch 로 받아 Blob URL 로 재생한다(API_CONTRACT 6절).
    - 상담 음성은 브라우저 캐시에 남기지 않는다(Cache-Control: no-store).
    """

    session = get_session_or_404(db, session_id, current_user)
    audio, path = audio_service.get_latest_audio_file(db, session.id)

    return FileResponse(
        path,
        media_type=audio.mime_type,
        filename=audio.original_filename,
        content_disposition_type="inline",
        headers={"Cache-Control": "no-store"},
    )
