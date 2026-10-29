# 다음 상담 체크리스트(추가 확인 · 질문 화면) 저장.
#
# rag/(공식 근거 RAG)가 만든 '다음 상담 전 확인할 사항'과 '추가 질문' 초안을 회차마다 행으로 쌓는다.
# AI 분석이 끝난 뒤 같은 백그라운드 작업에서 만들고(followup_service), 상담사가 다시 만들기를 누르면 새 행을 더한다.
# 조회는 가장 최근 행이다. 행이 실패해도 회차 상태에는 영향을 주지 않는다.
#
# result 는 rag 가 돌려준 모양 그대로 담는다(API_CONTRACT.md 18절):
#   check_items · items(질문) · validation · speaker_check_items · notice
# AI 제안이며 상담사가 확인 · 승인한다. 학대 여부를 확정하는 값은 없다.

import uuid
from datetime import datetime
from typing import Any, Dict, Optional, TYPE_CHECKING

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import AnalysisStatus
from app.models.base import Base, JSONType, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.session import ConsultationSession


class FollowupSuggestion(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "followup_suggestions"

    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("consultation_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # 학대 유형을 읽은 AI 분석. 분석을 다시 돌리면 새 행이 생기므로 옛 행은 옛 분석을 가리킨다.
    analysis_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("ai_analyses.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    transcript_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("transcripts.id", ondelete="SET NULL"),
        nullable=True,
    )
    transcript_version: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # 분석과 같은 세 상태(PROCESSING · COMPLETED · FAILED)를 쓴다.
    status: Mapped[AnalysisStatus] = mapped_column(
        SAEnum(AnalysisStatus, name="followup_status", native_enum=False, length=20),
        default=AnalysisStatus.PROCESSING,
        nullable=False,
    )

    schema_version: Mapped[str] = mapped_column(String(10), default="1.0", nullable=False)
    provider: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    result: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONType, nullable=True)

    # 고정 문구만 담는다(상담 발화 · 예외 원문 금지).
    error_code: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    session: Mapped["ConsultationSession"] = relationship(
        back_populates="followup_suggestions"
    )

    def __repr__(self) -> str:
        return f"<FollowupSuggestion id={self.id} status={self.status.value}>"
