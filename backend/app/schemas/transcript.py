# Transcript Schema.
#
# transcript.segments 는 STT Contract 와 완전히 동일한 형태를 유지한다.
# 상담사 수정 여부 같은 Backend metadata 는 segment 안이 아니라
# transcript level(edited_segment_ids)에 둔다.

import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.core.enums import SessionStatus, Speaker, TranscriptSource
from app.schemas.common import SessionErrorInfo
from app.schemas.contracts import STTSegment


class TranscriptResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    session_id: uuid.UUID
    version: int
    schema_version: str
    source: TranscriptSource
    is_confirmed: bool
    confirmed_at: Optional[datetime]
    stt_provider: Optional[str]
    stt_model: Optional[str]
    created_at: datetime

    segments: List[STTSegment]
    edited_segment_ids: List[str] = Field(default_factory=list)


class TranscriptEnvelope(BaseModel):
    """
    Polling 대응 응답.

    STT 가 아직 끝나지 않았으면 transcript 는 null 이고
    session_status 로 진행 상황을 판단한다. (docs/02_ARCHITECTURE.md §5)
    """

    session_id: uuid.UUID
    session_status: SessionStatus
    transcript: Optional[TranscriptResponse] = None
    error: Optional[SessionErrorInfo] = None


class TranscriptSegmentUpdate(BaseModel):
    """상담사 수정 입력. 지정한 필드만 반영된다."""

    segment_id: str = Field(..., min_length=1, max_length=50)
    speaker: Optional[Speaker] = None
    text: Optional[str] = Field(default=None, max_length=10000)
    start_ms: Optional[int] = Field(default=None, ge=0)
    end_ms: Optional[int] = Field(default=None, ge=0)

    @model_validator(mode="after")
    def _at_least_one_field(self) -> "TranscriptSegmentUpdate":
        if (
            self.speaker is None
            and self.text is None
            and self.start_ms is None
            and self.end_ms is None
        ):
            raise ValueError("수정할 필드를 최소 1개 지정해야 합니다.")

        if (
            self.start_ms is not None
            and self.end_ms is not None
            and self.end_ms < self.start_ms
        ):
            raise ValueError("end_ms 는 start_ms 보다 작을 수 없습니다.")

        return self


class TranscriptUpdateRequest(BaseModel):
    """
    수정 요청은 새로운 Transcript version 을 생성한다.
    기존 version 은 이력으로 보존된다.
    """

    segments: List[TranscriptSegmentUpdate] = Field(default_factory=list)
    removed_segment_ids: List[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _require_change(self) -> "TranscriptUpdateRequest":
        if not self.segments and not self.removed_segment_ids:
            raise ValueError("수정 또는 삭제할 segment 를 지정해야 합니다.")

        duplicated = len({item.segment_id for item in self.segments}) != len(self.segments)

        if duplicated:
            raise ValueError("동일한 segment_id 를 중복 지정할 수 없습니다.")

        return self


class STTRequestResponse(BaseModel):
    """STT 실행 요청 결과. 실제 처리는 비동기로 진행된다."""

    session_id: uuid.UUID
    session_status: SessionStatus
    message: str
