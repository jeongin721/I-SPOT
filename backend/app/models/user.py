# 상담사/관리자 계정.
# 자유 회원가입은 없으며 관리자 또는 seed script 로만 생성한다.

from datetime import datetime
from typing import List, Optional, TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum as SAEnum,
    Integer,
    String,
    false,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.config import settings
from app.core.enums import UserRole
from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, as_utc, utcnow

if TYPE_CHECKING:
    from app.models.case import Case


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        SAEnum(UserRole, name="user_role", native_enum=False, length=20),
        default=UserRole.COUNSELOR,
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # --- 계정 상태 ----------------------------------------------------
    # is_active(관리자 정지) · locked_until(실패 잠금) · dormant_at(미접속) ·
    # anonymized_at(퇴사) 은 뜻이 서로 다르다. 한 칸으로 합치면 관리자 화면에서
    # "왜 로그인이 안 되는지" 를 구분해 보여줄 수 없다.
    must_change_password: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=false(), nullable=False
    )
    password_changed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # 휴면 판정 기준. 비어 있으면 created_at 을 쓴다.
    last_login_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    dormant_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )

    failed_login_count: Mapped[int] = mapped_column(
        Integer, default=0, server_default=text("0"), nullable=False
    )
    locked_until: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # 퇴사 비식별 처리 시각. 처리 기능은 정책이 정해진 뒤에 붙인다.
    anonymized_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # 발급한 Token 을 한꺼번에 무효화하는 번호. 비밀번호를 바꾸거나 관리자가
    # 강제 로그아웃시키면 1 올린다. 요청마다 users 를 이미 읽으므로 조회가 늘지 않는다.
    token_version: Mapped[int] = mapped_column(
        Integer, default=0, server_default=text("0"), nullable=False
    )

    assigned_cases: Mapped[List["Case"]] = relationship(
        back_populates="counselor",
        foreign_keys="Case.counselor_id",
    )

    @property
    def is_admin(self) -> bool:
        return self.role == UserRole.ADMIN

    def is_locked_at(self, now: datetime) -> bool:
        """
        로그인 실패 잠금 여부. 잠금 판정은 여기 한 곳에만 둔다.

        `LOGIN_LOCK_MINUTES` 가 0 이면 시간으로 풀리지 않으므로 실패 횟수가 기준이다.
        0 보다 크면 locked_until 시각까지만 잠긴다.
        """

        locked_until = as_utc(self.locked_until)

        if locked_until is not None:
            return locked_until > now

        # DB 에 넣기 전 객체는 default 가 아직 적용되지 않아 None 일 수 있다.
        return (self.failed_login_count or 0) >= settings.LOGIN_MAX_FAILURES

    @property
    def is_locked(self) -> bool:
        """
        지금 잠겨 있는지. 계정 응답(UserResponse.is_locked)이 쓴다.

        기본 설정(LOGIN_LOCK_MINUTES=0)에서는 locked_until 이 비어 있어
        그 칸만으로는 잠김을 알 수 없다.
        """

        return self.is_locked_at(utcnow())

    def __repr__(self) -> str:
        return f"<User id={self.id} role={self.role.value}>"
