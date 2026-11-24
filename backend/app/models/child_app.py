# 아이 앱(콩콩) 연결 · 질문 · 받은 내용.
#
# 코드와 기기 토큰은 해시만 저장한다. 이름 · 사례번호는 앱으로 보내지 않는다.
# 보낸 질문은 문항 목록이 바뀌어도 그때 아이가 본 그대로 남도록 복사해 둔다.

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import Boolean, DateTime, Enum as SAEnum, ForeignKey, Integer, String, Text, false
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import (
    ChildAnswerLevel,
    ChildAppEventKind,
    ChildAppLinkStatus,
    ChildQuestionSetStatus,
)
from app.models.base import Base, JSONType, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.encrypted_field import EncryptedColumn


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
    # 응답 상태 '기준'(5 · 7 · 10일). 마지막 응답 뒤 이만큼 지나면 '안부 확인 필요'. 연결을 해지하면 행과 함께 없어진다.
    silent_days: Mapped[int] = mapped_column(Integer, default=7, server_default="7", nullable=False)


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
    # 발송 예약: 이 시각부터 아이 앱에 보인다. 비어 있으면 만든 즉시 보인다(2026-11-11).
    deliver_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


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
    payload_plain: Mapped[Dict[str, Any]] = mapped_column("payload", JSONType, default=dict, nullable=False)
    payload_enc: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    payload = EncryptedColumn("payload", empty={}, json_value=True)  # 상담 본문 암호화 2단계(encrypted_field)
    # 상담사 확인이 필요한 줄(긴급 알림 · 바로 확인 답 · 연락 요청). 확인하면 누가 언제 했는지 남는다.
    needs_ack: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false(), nullable=False)
    acknowledged_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    acknowledged_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


class ChildAppAiDraft(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """답 묶음 하나의 AI 초안. items: [{question_id, note, note_edited, questions: [{id, text, options, edited, question_set_id}]}]."""

    __tablename__ = "child_app_ai_drafts"

    case_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    event_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("child_app_events.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )
    items_plain: Mapped[List[Dict[str, Any]]] = mapped_column("items", JSONType, default=list, nullable=False)
    items_enc: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    items = EncryptedColumn("items", empty=[], json_value=True)  # 상담 본문 암호화 2단계(encrypted_field)
    created_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


class ChildSessionQuestionDraft(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """회차 하나의 '이번 회차 맞춤 질문' AI 초안(2026-11-24). 상담사가 골라 질문 보내기로 함께 보낸다.

    items: [{id, category, type, text, options, reason}]. id 는 'sq_' 로 시작한다(질문 보내기가 고정 문항과 구별).
    다시 만들면 items 를 통째로 바꾼다 — 이미 보낸 질문은 질문 묶음에 복사돼 있어 영향이 없다.
    """

    __tablename__ = "child_session_question_drafts"

    case_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("consultation_sessions.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )
    items_plain: Mapped[List[Dict[str, Any]]] = mapped_column("items", JSONType, default=list, nullable=False)
    items_enc: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    items = EncryptedColumn("items", empty=[], json_value=True)  # 이유(reason)에 회차 내용이 들어가 처음부터 암호화
    created_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
