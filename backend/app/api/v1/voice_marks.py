# /sessions/{session_id}/voice-marks — 구간별 음성 참고 표시(떨림 · 웅얼거림 · 작은 소리) 조회.
#
# 상담사가 다시 들어 볼 구간을 알려 주는 참고 정보다. 학대 · 위험을 판정하지 않는다.
# 계산과 저장은 STT 저장 직후(와 확정 때)에 Backend 가 하고(voice_marks_service), 여기서는 읽기만 한다.

import uuid
from typing import Optional

from fastapi import APIRouter

from app.core.deps import CurrentUser, DbSession
from app.core.responses import DataResponse
from app.schemas.voice_marks import VoiceMarksResponse
from app.services import voice_marks_service
from app.services.access import get_session_or_404

router = APIRouter(prefix="/sessions", tags=["voice-marks"])


@router.get(
    "/{session_id}/voice-marks",
    response_model=DataResponse[Optional[VoiceMarksResponse]],
    summary="구간별 음성 참고 표시 조회(가장 최근 행)",
)
def get_voice_marks(
    session_id: uuid.UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> DataResponse[Optional[VoiceMarksResponse]]:
    """가장 최근 행 하나를 준다. 아직 계산 전이면 `data: null`(정상 상태라 404 가 아니다).

    분석 실패 · 시간 초과는 행이 없는 것이 아니라 `status: UNDETERMINED` · `reason: ANALYSIS_ERROR` 행으로 온다.
    """

    session = get_session_or_404(db, session_id, current_user)
    row = voice_marks_service.latest_for_session(db, session.id)

    if row is None:
        return DataResponse(data=None)

    return DataResponse(
        data=VoiceMarksResponse(
            id=row.id,
            audio_file_id=row.audio_file_id,
            transcript_id=row.transcript_id,
            transcript_version=row.transcript_version,
            extractor=row.extractor,
            schema_version=row.schema_version,
            created_at=row.created_at,
            result=row.features or {},
        )
    )
