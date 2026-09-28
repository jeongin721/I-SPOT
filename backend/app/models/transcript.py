# Transcript 와 Segment.
#
# STT Contract(docs/02_ARCHITECTURE.md §6)를 DB 로 그대로 옮긴 구조이며,
# 상담사 수정 시 기존 version 을 보존하고 새 version 을 만든다.

import uuid
from datetime import datetime
from typing import List, Optional, TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum as SAEnum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import Speaker, TranscriptSource
from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.session import ConsultationSession
    from app.models.user import User


class Transcript(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "transcripts"
    __table_args__ = (
        UniqueConstraint("session_id", "version", name="uq_transcript_session_version"),
    )

    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("consultation_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    schema_version: Mapped[str] = mapped_column(String(10), default="1.0", nullable=False)

    source: Mapped[TranscriptSource] = mapped_column(
        SAEnum(TranscriptSource, name="transcript_source", native_enum=False, length=20),
        default=TranscriptSource.STT,
        nullable=False,
    )

    is_confirmed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    confirmed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    confirmed_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    stt_provider: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    stt_model: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    created_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    session: Mapped["ConsultationSession"] = relationship(back_populates="transcripts")
    confirmed_by: Mapped[Optional["User"]] = relationship(foreign_keys=[confirmed_by_id])

    segments: Mapped[List["TranscriptSegment"]] = relationship(
        back_populates="transcript",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="TranscriptSegment.order_index",
    )

    def __repr__(self) -> str:
        return f"<Transcript id={self.id} version={self.version}>"


class TranscriptSegment(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "transcript_segments"
    __table_args__ = (
        UniqueConstraint(
            "transcript_id", "segment_id", name="uq_segment_transcript_segment_id"
        ),
    )

    transcript_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("transcripts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # STT Contract 의 segment_id (예: "seg_001"). AI 근거 연결 키로 사용된다.
    segment_id: Mapped[str] = mapped_column(String(50), nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)

    speaker: Mapped[Speaker] = mapped_column(
        SAEnum(Speaker, name="speaker", native_enum=False, length=20),
        default=Speaker.UNKNOWN,
        nullable=False,
    )
    start_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    end_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)

    # 상담사가 수정한 segment 를 검수 화면에서 구분할 수 있게 한다.
    is_edited: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    transcript: Mapped["Transcript"] = relationship(back_populates="segments")

    def __repr__(self) -> str:
        return f"<TranscriptSegment segment_id={self.segment_id}>"
