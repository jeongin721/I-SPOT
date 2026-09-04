# 상담사/관리자 계정.
# 자유 회원가입은 없으며 관리자 또는 seed script 로만 생성한다.

from typing import List, TYPE_CHECKING

from sqlalchemy import Boolean, Enum as SAEnum, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import UserRole
from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

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

    assigned_cases: Mapped[List["Case"]] = relationship(
        back_populates="counselor",
        foreign_keys="Case.counselor_id",
    )

    @property
    def is_admin(self) -> bool:
        return self.role == UserRole.ADMIN

    def __repr__(self) -> str:
        return f"<User id={self.id} role={self.role.value}>"
