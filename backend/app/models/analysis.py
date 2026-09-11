# AI 분석 결과 저장.
#
# - AI 담당의 Structured JSON Contract 를 result 컬럼에 그대로 보관한다.
# - 어떤 Transcript version 을 사용했는지 추적한다. (docs/02_ARCHITECTURE.md §3)

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import AnalysisStatus
from app.models.base import Base, JSONType, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.session import ConsultationSession
    from app.models.transcript import Transcript


class AIAnalysis(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "ai_analyses"

    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("consultation_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    transcript_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("transcripts.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    transcript_version: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    status: Mapped[AnalysisStatus] = mapped_column(
        SAEnum(AnalysisStatus, name="analysis_status", native_enum=False, length=20),
        default=AnalysisStatus.PROCESSING,
        nullable=False,
        index=True,
    )

    schema_version: Mapped[str] = mapped_column(String(10), default="1.0", nullable=False)

    # AI Output Contract 전체(summary/risk_utterances/abuse_signals/risk_factors/warnings)
    result: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONType, nullable=True)

    # AI 파이프라인 내부 결과인 근거 연결 정보. Contract 외 부가 정보이므로 분리 저장한다.
    summary_evidence: Mapped[Optional[List[Dict[str, Any]]]] = mapped_column(
        JSONType, nullable=True
    )

    provider: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    model: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    error_code: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    session: Mapped["ConsultationSession"] = relationship(back_populates="analyses")
    transcript: Mapped[Optional["Transcript"]] = relationship()

    def __repr__(self) -> str:
        return f"<AIAnalysis id={self.id} status={self.status.value}>"
