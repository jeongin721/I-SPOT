# Transcript Schema.
#
# transcript.segments 는 STT Contract 와 완전히 동일한 형태를 유지한다.
# 상담사 수정 여부 같은 Backend metadata 는 segment 안이 아니라
# transcript level(edited_segment_ids)에 둔다.

import uuid
from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.core.enums import SessionStatus, Speaker, TranscriptSource
from app.schemas.common import RequestModel, SessionErrorInfo
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
    # Additive handoff view. The existing ``segments`` Contract is unchanged.
    child_handoff: Optional["ChildHandoffResponse"] = None
    # STT 검수 '1차 임시 핵심 발화'(7절). 저장한 값이고 없으면 null(이 기능 전 전사본).
    key_scan: Optional["KeyScanResponse"] = None


class KeyScanLegalReference(BaseModel):
    """발화 글이 그 유형의 행위 예시와 닮을 때만 붙는 '임시' 관련 조문(2026-11-09, PROPOSAL_stt_law_match.md).
    excerpt 는 닮은 예시(왜 붙었는지), score 는 유사도. 매칭 모델이 없을 때는 유형 조문만 근거 없이(excerpt 빈 값 · score null)."""

    abuse_type: Optional[str] = None
    law_name: str
    article: str
    item_label: str = ""
    text: str = ""
    portal_url: str = ""
    excerpt: str = ""
    score: Optional[float] = None


class KeyScanSegment(BaseModel):
    segment_id: str
    # PHYSICAL · EMOTIONAL · SEXUAL · NEGLECT. 유형 이름 자체는 화면에 그리지 않는다(판정처럼 읽힘, 제안서 §8 답 3).
    abuse_types: List[str] = Field(default_factory=list)
    # 비어 있으면 화면은 조문 없이 '먼저 들어볼 곳'만 보인다.
    legal_references: List[KeyScanLegalReference] = Field(default_factory=list)


class KeyScanResponse(BaseModel):
    """1차 모델 스캔으로 고른 '먼저 들어볼 곳'. 판정이 아니다.
    status: DONE · FAILED · SKIPPED, 그리고 원문 수정 뒤 저장한 원문으로 다시 스캔하는 중인 REFRESHING(끝나면 DONE · FAILED).
    scanned_version 은 segments 를 만든 원문 version(REFRESHING · 다시 스캔 실패면 직전 version), started_at 은 REFRESHING 시작 시각."""

    status: Literal["DONE", "FAILED", "SKIPPED", "REFRESHING"]
    model: Optional[str] = None
    segments: List[KeyScanSegment] = Field(default_factory=list)
    scanned_version: Optional[int] = None
    started_at: Optional[datetime] = None


class ChildHandoffSegment(BaseModel):
    segment_id: str = Field(min_length=1, max_length=50)
    text: str
    start_ms: int = Field(ge=0)
    end_ms: int = Field(ge=0)

    @model_validator(mode="after")
    def _valid_range(self) -> "ChildHandoffSegment":
        if self.end_ms < self.start_ms:
            raise ValueError("end_ms must not precede start_ms")
        return self


class ReviewNeededSegment(ChildHandoffSegment):
    reason: str


class ChildHandoffResponse(BaseModel):
    child_analysis_text: str = ""
    confirmed_child_segments: List[ChildHandoffSegment] = Field(default_factory=list)
    review_needed_segments: List[ReviewNeededSegment] = Field(default_factory=list)


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


class TranscriptSegmentUpdate(RequestModel):
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


class TranscriptUpdateRequest(RequestModel):
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
