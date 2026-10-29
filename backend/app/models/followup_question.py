# 승인한 추가 질문 목록. 회차마다 한 행에 목록(JSON) 하나를 둔다(PROPOSAL_ai_suggestions_case_context.md §7 답 4).
#
# AI 가 만든 질문 초안은 분석 결과(followup_questions)에 그대로 남고, 여기에는 상담사가 승인 · 고친 · 직접 쓴 질문만
# 저장한다. 목록을 통째로 바꿔 저장하므로 질문마다 행을 두지 않는다.

import uuid
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, JSONType, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.session import ConsultationSession

# 한 회차에 저장할 수 있는 질문 수 · 질문 문장 길이 · 근거 번호 수 상한
FOLLOWUP_QUESTIONS_MAX = 20
FOLLOWUP_QUESTION_TEXT_MAX_LENGTH = 300
FOLLOWUP_QUESTION_SEGMENTS_MAX = 20


class SessionFollowupQuestions(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "session_followup_questions"

    # 회차마다 한 행. 다시 저장하면 그 행의 목록을 바꾼다.
    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("consultation_sessions.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    # [{text, kind, source, segment_ids, bank_code, approved_at}] — approved_at 은 서버가 찍은 ISO 8601 문자열.
    questions: Mapped[List[Dict[str, Any]]] = mapped_column(JSONType, default=list, nullable=False)

    updated_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    session: Mapped["ConsultationSession"] = relationship(back_populates="followup_questions")

    def __repr__(self) -> str:
        return f"<SessionFollowupQuestions id={self.id} count={len(self.questions or [])}>"
