# 상담사 검수 대상 요약.
#
# Human-in-the-loop(docs/05_RULES.md §2):
#   AI 생성 → 상담사 확인 → 수정/제외 → 승인 → 저장
#
# AI 원본(AIAnalysis.result)은 보존하고, 상담사가 수정하는 사본을 여기에 둔다.

import uuid
from datetime import datetime
from typing import Any, Dict, Optional, TYPE_CHECKING

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
from app.models.encrypted_field import EncryptedColumn

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

    # overview · key_points · counselor_note 는 *_enc 에 암호문으로 둔다(encrypted_field). 평문 칸은 없다(11/27 지움).
    # key_points 는 JSON 글자로 바꿔 암호화한다.
    overview_enc: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    overview = EncryptedColumn("overview", empty="")
    key_points_enc: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    key_points = EncryptedColumn("key_points", empty=[], json_value=True)

    # 상담 요약 사정 관점 4칸(contracts.SummaryAssessment 모양, {칸 이름: {text, segment_ids}}).
    # 2026-10-27 이전에 만든 요약은 null 이고 응답에서 빈 칸으로 보인다.
    assessment: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONType, nullable=True)

    # 상담사 추가 의견. AI 결과와 구분해서 보관한다.
    counselor_note_enc: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    counselor_note = EncryptedColumn("counselor_note", empty=None)

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
