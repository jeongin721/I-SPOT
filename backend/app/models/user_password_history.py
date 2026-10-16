# 이전 비밀번호 이력.
#
# 팀 회의 결정(2026-09-18) "이전 비밀번호 재사용 금지" 를 위해 둔다.
# 비밀번호 원문은 저장하지 않는다. 해시만 남기고 개수도 설정값만큼만 유지한다.

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, utcnow


class UserPasswordHistory(Base):
    __tablename__ = "user_password_history"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # 계정을 지우면 이력도 같이 사라져야 한다. 상담 기록 쪽 FK 와 달리 CASCADE 다.
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    def __repr__(self) -> str:
        return f"<UserPasswordHistory user_id={self.user_id}>"
