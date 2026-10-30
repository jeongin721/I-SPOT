# 다음 상담 체크리스트. 회차마다 한 행(API_CONTRACT 19절, specs followup-rag-checklist).
#
# rag 로 만든 '다음 상담 전 확인할 사항'(check_items)과, 추가 질문 AI 초안(분석 followup_questions)에 붙인 공식 근거
# (question_evidence)를 둔다. 공식 근거는 rag 의 검토를 통과한 것만 들어온다. 다시 만들면 같은 행을 고쳐 쓴다.
#
# attempt: 만들기를 시작할 때마다 1 씩 올린다. 작업은 시작할 때의 attempt 를 들고 가서, 끝날 때 행이 아직
# 그 attempt · PROCESSING 일 때만 결과를 쓴다(늦게 끝난 앞 작업이 새 결과를 덮지 않게).

import uuid
from datetime import datetime
from typing import Any, Dict, Optional, TYPE_CHECKING

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import AnalysisStatus
from app.models.base import Base, JSONType, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.session import ConsultationSession


class SessionFollowupChecklist(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "session_followup_checklists"

    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("consultation_sessions.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    # 만들 때 쓴 분석 · 확정 전사본. 분석이 지워지면 null(화면은 '분석이 바뀌었습니다' 로 본다).
    analysis_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("ai_analyses.id", ondelete="SET NULL"), nullable=True
    )
    transcript_version: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    status: Mapped[AnalysisStatus] = mapped_column(
        SAEnum(AnalysisStatus, name="followup_checklist_status", native_enum=False, length=20),
        nullable=False,
    )
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    provider: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # {schema_version, check_items, question_evidence, notice, dropped} — schemas/followup_checklist.ChecklistResult
    result: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONType, nullable=True)

    # 코드별 고정 문구만 둔다(발화 · 예외 원문을 넣지 않는다).
    error_code: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    session: Mapped["ConsultationSession"] = relationship(back_populates="followup_checklist")

    def __repr__(self) -> str:
        return f"<SessionFollowupChecklist id={self.id} status={self.status.value} attempt={self.attempt}>"
