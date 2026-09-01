# 업로드된 상담 음성 metadata.
# 파일 자체는 Local Storage 에 있고, DB 에는 경로/타입/크기/길이만 저장한다.

import uuid
from typing import Optional, TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.session import ConsultationSession


class AudioFile(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "audio_files"

    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("consultation_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # storage/audio/{case_id}/{session_id}/ 기준 상대 경로
    path: Mapped[str] = mapped_column(String(500), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    checksum_sha256: Mapped[str] = mapped_column(String(64), nullable=False)

    uploaded_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    session: Mapped["ConsultationSession"] = relationship(back_populates="audio_files")

    def __repr__(self) -> str:
        return f"<AudioFile id={self.id} size={self.size_bytes}>"
