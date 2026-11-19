# 상담사 앱(폰) 알림 — 웹 푸시 구독 · 보낸 기록(2026-11-19, API_CONTRACT 27절).
#
# 구독(push_subscriptions): 폰(브라우저) 하나가 한 행. endpoint 는 푸시 서비스가 정한 주소라 기기마다 다르고 겹치지 않는다.
#   같은 폰에서 다른 계정으로 다시 켜면 그 행의 user_id 를 바꾼다(한 폰은 마지막에 켠 계정 것).
#   알림 종류는 행마다 켜고 끈다: before_session(상담 30분 전) · upload_failed(업로드 실패 — 실제 알림은 폰이 스스로 띄우고
#   여기는 설정만 기억한다).
# 보낸 기록(push_deliveries): 같은 일정을 두 번 알리지 않게 (사용자, 종류, 대상 키)를 한 번만 넣는다. 대상 키에 일정 날짜 · 시간이
#   들어 있어 시간을 바꾸면 새 시간에 다시 알린다. 알림 문구는 저장하지 않는다.
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

#: 푸시 서비스 주소 길이 상한(구글 · 애플 · 모질라 모두 수백 자).
PUSH_ENDPOINT_MAX_LENGTH = 1000
#: 한 상담사가 켤 수 있는 기기 수. 넘으면 가장 오래 전에 쓴 것을 지운다.
PUSH_SUBSCRIPTIONS_PER_USER_MAX = 10


class PushSubscription(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "push_subscriptions"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    endpoint: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    p256dh: Mapped[str] = mapped_column(String(200), nullable=False)
    auth: Mapped[str] = mapped_column(String(100), nullable=False)
    before_session: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    upload_failed: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # 연달아 실패한 횟수(연결 오류 · 5xx). 많이 실패하면 지운다(push_service).
    fail_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        # endpoint · 키는 찍지 않는다.
        return f"<PushSubscription id={self.id} user_id={self.user_id}>"


class PushDelivery(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "push_deliveries"
    __table_args__ = (UniqueConstraint("user_id", "kind", "ref_key", name="uq_push_deliveries_user_kind_ref"),)

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    kind: Mapped[str] = mapped_column(String(40), nullable=False)
    ref_key: Mapped[str] = mapped_column(String(120), nullable=False)
    sent: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
