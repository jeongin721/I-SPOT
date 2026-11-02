# 상담 기록 문서(2026-11-02, API_CONTRACT 20절). 문서 회차(SessionSource.DOCUMENT)마다 한 행.
#
# 상담사가 쓴 문서에서 뽑은 글(text)만 저장한다(원본 파일은 저장하지 않는다). 올릴 때 AI(또는 머리줄 나누기)가 채운
# 상담 일지 칸 초안(note_draft — 상담 요약 4칸은 ConsultationSummary 에 바로 들어간다)과, 4단계 확인 사항 · 추가 질문 초안
# (followup_draft)을 함께 둔다. 초안은 상담사가 고치고 저장 · 승인해야 쓰인다.

import uuid
from typing import Any, Dict, Optional, TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, JSONType, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.session import ConsultationSession


class SessionSourceDocument(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "session_source_documents"

    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("consultation_sessions.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    # 'txt' · 'docx' · 'hwpx' · 'pdf'
    file_format: Mapped[str] = mapped_column(String(10), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    char_count: Mapped[int] = mapped_column(Integer, nullable=False)
    # 'AI'(document_note_llm) · 'HEADINGS'(머리줄 나누기, AI 아님)
    fill_source: Mapped[str] = mapped_column(String(20), nullable=False)
    fill_model: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    # 상담 일지 칸 초안 {statement, attitude, environment, signals, opinion}
    note_draft: Mapped[Dict[str, Any]] = mapped_column(JSONType, default=dict, nullable=False)
    # 4단계 초안 {checks: [{text}], questions: [{text, reason}], source, model, generated_at}. 만들기 전이면 null.
    followup_draft: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONType, nullable=True)

    uploaded_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    session: Mapped["ConsultationSession"] = relationship(back_populates="source_document")
