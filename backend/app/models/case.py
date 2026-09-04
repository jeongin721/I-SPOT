# 사례(Case).
#
# 개인정보 최소 저장 원칙(docs/05_RULES.md)에 따라
# 아동 실명 대신 alias 를 사용하고, 생년월일 대신 출생연도만 보관한다.

import uuid
from typing import List, Optional, TYPE_CHECKING

from sqlalchemy import Enum as SAEnum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import CaseStatus
from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.session import ConsultationSession
    from app.models.user import User


class Case(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "cases"

    case_number: Mapped[str] = mapped_column(
        String(50), unique=True, index=True, nullable=False
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)

    # 개인정보 최소화: 실명 대신 식별용 alias 만 저장한다.
    child_alias: Mapped[str] = mapped_column(String(100), nullable=False)
    child_birth_year: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    child_gender: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)

    status: Mapped[CaseStatus] = mapped_column(
        SAEnum(CaseStatus, name="case_status", native_enum=False, length=20),
        default=CaseStatus.ACTIVE,
        nullable=False,
        index=True,
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    counselor_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    created_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    counselor: Mapped["User"] = relationship(
        back_populates="assigned_cases",
        foreign_keys=[counselor_id],
    )
    sessions: Mapped[List["ConsultationSession"]] = relationship(
        back_populates="case",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def __repr__(self) -> str:
        return f"<Case id={self.id} case_number={self.case_number}>"
