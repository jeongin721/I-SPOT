# 다음 상담 전 확인할 사항 목록(18.1절, 2026-10-30). 회차마다 한 행에 목록(JSON) 하나 — 추가 질문(followup_question)과 같은 꼴.
#
# AI 확인 메모 초안은 분석 결과(followup_check_points)에 그대로 남고, 여기에는 상담사가 고친 · 직접 쓴 · 브리핑에 넣기로
# 고른 목록을 저장한다. 한 번 저장하면 이 목록이 그 회차의 확인 사항이다(화면은 AI 초안 대신 이 목록을 보인다).

import uuid
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, JSONType, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.session import ConsultationSession

# 한 회차에 저장할 수 있는 확인 사항 수 · 문장 길이 · 근거 번호 수 상한
FOLLOWUP_CHECKS_MAX = 20
FOLLOWUP_CHECK_TEXT_MAX_LENGTH = 300
FOLLOWUP_CHECK_SEGMENTS_MAX = 20


class SessionFollowupChecks(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "session_followup_checks"

    # 회차마다 한 행. 다시 저장하면 그 행의 목록을 바꾼다.
    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("consultation_sessions.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    # [{text, source, segment_ids, edited, in_briefing}]
    items: Mapped[List[Dict[str, Any]]] = mapped_column(JSONType, default=list, nullable=False)

    updated_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    session: Mapped["ConsultationSession"] = relationship(back_populates="followup_checks")

    def __repr__(self) -> str:
        return f"<SessionFollowupChecks id={self.id} count={len(self.items or [])}>"
