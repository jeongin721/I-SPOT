# Audio metadata Schema. 파일 자체는 응답에 포함하지 않는다.

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict

from app.core.enums import SessionStatus


class AudioResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    session_id: uuid.UUID
    path: str
    original_filename: str
    mime_type: str
    size_bytes: int
    duration_ms: Optional[int]
    checksum_sha256: str
    # 녹음 동의를 확인한 시각(폰 앱 녹음만). 없으면 null.
    consent_at: Optional[datetime] = None
    created_at: datetime


class AudioUploadResponse(BaseModel):
    audio: AudioResponse
    session_status: SessionStatus
