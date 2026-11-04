# 회원가입(2026-11-02, API_CONTRACT 3절 '회원가입'). 이메일 인증번호 → 대기 신청 → 관리자 승인.
#
# 인증번호 단계(SignupEmailCode)와 대기 신청(SignupRequest)을 나눈다. 계정이나 대기 신청이 이미 있는 이메일에도
# 인증번호 행을 똑같이 만들어야(메일만 안 보낸다) 다시 보내기 · 하루 횟수 · 틀림 횟수가 같게 걸려 응답으로 계정 존재가
# 드러나지 않는다. 대기 신청 행 하나에 몰면 대기 중인 이메일의 다음 번호를 그 행에 겹쳐 적어야 해서 꼬인다.
#
# users 행은 관리자가 승인할 때만 생긴다. 인증번호 · 확인 토큰 · 비밀번호 원문은 저장하지 않는다(해시만).
# 지우는 때(보관 기한)는 signup_service.purge_expired 에 있다.

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, Index, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import SignupRequestStatus, UserRole
from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class SignupEmailCode(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """인증번호 단계. 이메일당 한 행이다. 번호를 새로 보내면 같은 행을 고친다."""

    __tablename__ = "signup_email_codes"

    # 소문자로 맞춘 이메일.
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)

    # 살아 있는 인증번호의 HMAC-SHA256 hex(signup_service._code_hash). 맞히거나 기준만큼 틀리면 비운다.
    code_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    code_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    # 지금 번호의 틀린 횟수. 대조하기 전에 먼저 센다(로그인 실패 횟수와 같은 방식).
    failed_attempts: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"), nullable=False)

    # 마지막으로 번호를 만든 시각(다시 보내기 간격). 보관 기한도 이 시각으로 본다.
    last_sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    # '하루 몇 번' 을 세기 시작한 시각과 그 안에서 만든 번호 수. 달력 날짜가 아니라 첫 보내기부터 24시간이다.
    window_started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    send_count: Mapped[int] = mapped_column(Integer, nullable=False)

    # 번호를 맞히면 주는 확인 토큰의 SHA-256 hex. 대기 신청에 한 번 쓰면 비운다.
    token_hash: Mapped[Optional[str]] = mapped_column(String(64), unique=True, nullable=True)
    token_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        return f"<SignupEmailCode id={self.id}>"


class SignupRequest(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """대기 신청. 승인 · 거절하면 비밀번호 해시를 지운다(승인이면 users 로 옮긴 뒤)."""

    __tablename__ = "signup_requests"
    __table_args__ = (
        # 이메일당 대기 신청 하나. 승인 · 거절된 옛 행이 있어도 새 신청은 들어간다.
        Index(
            "uq_signup_requests_pending_email",
            "email",
            unique=True,
            postgresql_where=text("status = 'PENDING'"),
            sqlite_where=text("status = 'PENDING'"),
        ),
    )

    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    hashed_password: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    status: Mapped[SignupRequestStatus] = mapped_column(
        SAEnum(SignupRequestStatus, name="signup_request_status", native_enum=False, length=20),
        default=SignupRequestStatus.PENDING,
        nullable=False,
        index=True,
    )

    # 승인 때 관리자가 고른 역할과 만든 계정.
    role: Mapped[Optional[UserRole]] = mapped_column(
        SAEnum(UserRole, name="signup_request_role", native_enum=False, length=20), nullable=True
    )
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    decided_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    decided_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        return f"<SignupRequest id={self.id} status={self.status.value}>"
