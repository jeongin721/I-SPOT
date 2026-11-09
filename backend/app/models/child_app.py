# 아이 앱(콩콩) 연결 · 질문 · 받은 내용.
#
# 코드와 기기 토큰은 해시만 저장한다. 이름 · 사례번호는 앱으로 보내지 않는다.
# 보낸 질문은 문항 목록이 바뀌어도 그때 아이가 본 그대로 남도록 복사해 둔다.

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import (
    ChildAnswerLevel,
    ChildAppEventKind,
    ChildAppLinkStatus,
    ChildQuestionSetStatus,
)
from app.models.base import Base, JSONType, TimestampMixin, UUIDPrimaryKeyMixin


class ChildAppLink(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "child_app_links"

    # 사례마다 한 행.
    case_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )
    status: Mapped[ChildAppLinkStatus] = mapped_column(
        SAEnum(ChildAppLinkStatus, name="child_app_link_status", native_enum=False, length=20),
        default=ChildAppLinkStatus.INVITED,
        nullable=False,
    )
    code_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, unique=True, index=True)
    code_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    device_token_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, unique=True, index=True)
    linked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_response_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class ChildQuestionSet(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "child_question_sets"

    case_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sent_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[ChildQuestionSetStatus] = mapped_column(
        SAEnum(ChildQuestionSetStatus, name="child_question_set_status", native_enum=False, length=20),
        default=ChildQuestionSetStatus.PENDING,
        nullable=False,
        index=True,
    )
    # 보낸 순서대로 문항 전체를 복사한 목록.
    questions: Mapped[List[Dict[str, Any]]] = mapped_column(JSONType, default=list, nullable=False)
    answered_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class ChildAppEvent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """상담사 화면의 시간순 피드 한 줄."""

    __tablename__ = "child_app_events"

    case_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    kind: Mapped[ChildAppEventKind] = mapped_column(
        SAEnum(ChildAppEventKind, name="child_app_event_kind", native_enum=False, length=20),
        nullable=False,
    )
    level: Mapped[ChildAnswerLevel] = mapped_column(
        SAEnum(ChildAnswerLevel, name="child_answer_level", native_enum=False, length=10),
        default=ChildAnswerLevel.NONE,
        nullable=False,
    )
    payload: Mapped[Dict[str, Any]] = mapped_column(JSONType, default=dict, nullable=False)
    # 긴급 알림을 누가 언제 확인했는가. 다른 종류는 비어 있다.
    acknowledged_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    acknowledged_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
