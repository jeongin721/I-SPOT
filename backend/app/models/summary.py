# 상담사 검수 대상 요약.
#
# Human-in-the-loop(docs/05_RULES.md §2):
#   AI 생성 → 상담사 확인 → 수정/제외 → 승인 → 저장
#
# AI 원본(AIAnalysis.result)은 보존하고, 상담사가 수정하는 사본을 여기에 둔다.

import uuid
from datetime import datetime
from typing import List, Optional, TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import ReviewStatus
from app.models.base import Base, JSONType, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.analysis import AIAnalysis
    from app.models.session import ConsultationSession
    from app.models.user import User


class ConsultationSummary(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "consultation_summaries"

    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("consultation_sessions.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    analysis_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("ai_analyses.id", ondelete="SET NULL"), nullable=True
    )

    overview: Mapped[str] = mapped_column(Text, default="", nullable=False)
    key_points: Mapped[List[str]] = mapped_column(JSONType, default=list, nullable=False)

    # 상담사 추가 의견. AI 결과와 구분해서 보관한다.
    counselor_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    status: Mapped[ReviewStatus] = mapped_column(
        SAEnum(ReviewStatus, name="review_status", native_enum=False, length=20),
        default=ReviewStatus.DRAFT,
        nullable=False,
        index=True,
    )
    is_edited: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    approved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    approved_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    session: Mapped["ConsultationSession"] = relationship(back_populates="summary")
    analysis: Mapped[Optional["AIAnalysis"]] = relationship()
    approved_by: Mapped[Optional["User"]] = relationship(foreign_keys=[approved_by_id])

    def __repr__(self) -> str:
        return f"<ConsultationSummary session_id={self.session_id} status={self.status.value}>"
