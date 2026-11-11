# 상담 전 브리핑 '확인할 사항' 체크(상담 중 확인한 것 표시, 2026-11-11, API_CONTRACT 26절). 회차마다 한 행.
#
# 브리핑의 확인할 사항은 저장한 목록(session_followup_checks)일 때도, 저장 전 AI 초안 + 다음 상담 체크리스트일 때도 있다.
# 저장 전 목록에는 행이 없으므로 '확인함' 을 목록 행에 붙이지 않고 따로 둔다 — 확인한 문장(text) 목록. 웹 · 폰이 같은 값을 본다
# (전에는 기기마다 브라우저에만 기억했다).
import uuid
from typing import List, Optional

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, JSONType, TimestampMixin, UUIDPrimaryKeyMixin

#: 한 회차에 확인함으로 둘 수 있는 문장 수 · 문장 길이 상한(확인 사항 20개 + 체크리스트 여유).
BRIEFING_CHECKS_MAX = 60
BRIEFING_CHECK_TEXT_MAX_LENGTH = 300


class SessionBriefingChecks(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "session_briefing_checks"

    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("consultation_sessions.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )
    # 확인함으로 표시한 확인 사항 문장들(화면에 보인 그대로).
    checked: Mapped[List[str]] = mapped_column(JSONType, default=list, nullable=False)
    updated_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    def __repr__(self) -> str:
        # 문장은 찍지 않는다(아동 진술을 이어받을 수 있다).
        return f"<SessionBriefingChecks session_id={self.session_id} count={len(self.checked or [])}>"
