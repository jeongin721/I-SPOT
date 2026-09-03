from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class SessionStatus(str, enum.Enum):
    """Shared session lifecycle states (see docs/02_ARCHITECTURE.md §4)."""

    CREATED = "CREATED"
    AUDIO_UPLOADED = "AUDIO_UPLOADED"
    STT_PROCESSING = "STT_PROCESSING"
    STT_REVIEW_REQUIRED = "STT_REVIEW_REQUIRED"
    STT_CONFIRMED = "STT_CONFIRMED"
    AI_PROCESSING = "AI_PROCESSING"
    AI_REVIEW_REQUIRED = "AI_REVIEW_REQUIRED"
    APPROVED = "APPROVED"


class Case(Base):
    __tablename__ = "cases"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    sessions: Mapped[list["ConsultSession"]] = relationship(
        back_populates="case",
        cascade="all, delete-orphan",
        order_by="ConsultSession.created_at",
    )


class ConsultSession(Base):
    """A counseling session (회차) belonging to a Case."""

    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    case_id: Mapped[str] = mapped_column(
        ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[SessionStatus] = mapped_column(
        Enum(SessionStatus, name="session_status"),
        default=SessionStatus.CREATED,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    case: Mapped["Case"] = relationship(back_populates="sessions")
