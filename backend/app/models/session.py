# 상담 Session.
#
# 공통 상태(docs/02_ARCHITECTURE.md)를 status 로 관리하고,
# 실패 시 재시도를 위해 last_error_code / last_error_message 를 유지한다.

import uuid
from datetime import datetime
from typing import List, Optional, TYPE_CHECKING

from sqlalchemy import (
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import SessionStatus
from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.analysis import AIAnalysis
    from app.models.audio import AudioFile
    from app.models.case import Case
    from app.models.document import Document
    from app.models.summary import ConsultationSummary
    from app.models.transcript import Transcript
    from app.models.user import User


class ConsultationSession(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "consultation_sessions"
    __table_args__ = (
        UniqueConstraint("case_id", "session_number", name="uq_session_case_number"),
    )

    case_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("cases.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    session_number: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

    status: Mapped[SessionStatus] = mapped_column(
        SAEnum(SessionStatus, name="session_status", native_enum=False, length=30),
        default=SessionStatus.CREATED,
        nullable=False,
        index=True,
    )

    counselor_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    consulted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    location: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    memo: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # 재시도 가능한 오류 정보
    last_error_code: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    last_error_message: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    stt_started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    stt_completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    ai_started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    ai_completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    approved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    approved_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    case: Mapped["Case"] = relationship(back_populates="sessions")
    counselor: Mapped["User"] = relationship(foreign_keys=[counselor_id])

    audio_files: Mapped[List["AudioFile"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="AudioFile.created_at",
    )
    transcripts: Mapped[List["Transcript"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="Transcript.version",
    )
    analyses: Mapped[List["AIAnalysis"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="AIAnalysis.created_at",
    )
    summary: Mapped[Optional["ConsultationSummary"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        passive_deletes=True,
        uselist=False,
    )
    documents: Mapped[List["Document"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="Document.created_at",
    )

    def clear_error(self) -> None:
        self.last_error_code = None
        self.last_error_message = None

    def set_error(self, code: str, message: str) -> None:
        self.last_error_code = code
        self.last_error_message = message[:500]

    def __repr__(self) -> str:
        return f"<ConsultationSession id={self.id} status={self.status.value}>"
