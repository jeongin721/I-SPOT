# 수정/승인 이력 추적(docs/05_RULES.md §4).
#
# detail 에는 상담 원문을 저장하지 않는다. 변경 개수/필드명 등 metadata 만 남긴다.

import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import AuditAction
from app.models.base import Base, JSONType, UUIDPrimaryKeyMixin, utcnow


class AuditLog(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "audit_logs"

    actor_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )

    action: Mapped[AuditAction] = mapped_column(
        SAEnum(AuditAction, name="audit_action", native_enum=False, length=40),
        nullable=False,
        index=True,
    )

    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), nullable=True
    )

    # 모든 이력은 case_id / session_id 로 추적 가능해야 한다.
    case_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), nullable=True, index=True
    )
    session_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), nullable=True, index=True
    )

    # 행동의 결과. 실패한 로그인 · 거부된 접근도 남기기 위해 둔다.
    # 실패를 별도 action 값으로 만들면 action 이 *_FAILED 로 두 배가 된다.
    status: Mapped[str] = mapped_column(
        String(20), default="SUCCESS", server_default="SUCCESS", nullable=False, index=True
    )
    error_code: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # 접속 기록 화면이 쓰는 값. IPv6 가 최대 45자라 String(45) 로 둔다.
    # PostgreSQL 전용 INET 은 SQLite 테스트에서 쓸 수 없다.(models/base.py)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    detail: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONType, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    def __repr__(self) -> str:
        return f"<AuditLog action={self.action.value} entity={self.entity_type}>"
