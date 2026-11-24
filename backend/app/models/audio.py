# 업로드된 상담 음성 metadata.
# 파일 자체는 Local Storage 에 있고, DB 에는 경로/타입/크기/길이만 저장한다.

import uuid
from datetime import datetime
from typing import List, Optional, TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.audio_feature import AudioFeature
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
    # 녹음 동의를 받았다고 상담사가 확인한 시각(폰 앱 녹음의 '녹음 동의 완료', 11/20 경진님). 확인한 사람은 uploaded_by.
    # 다른 녹음 앱 파일 · 웹에서 올린 파일은 앱이 동의를 묻지 않아 null 이다.
    consent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    session: Mapped["ConsultationSession"] = relationship(back_populates="audio_files")
    features: Mapped[List["AudioFeature"]] = relationship(
        back_populates="audio_file",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="AudioFeature.created_at",
    )

    def __repr__(self) -> str:
        return f"<AudioFile id={self.id} size={self.size_bytes}>"
