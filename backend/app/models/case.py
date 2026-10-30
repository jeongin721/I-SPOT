# 사례(Case).
#
# 개인정보 최소 저장 원칙(docs/05_RULES.md)에 따라
# 아동 실명 대신 alias 를 사용하고, 생년월일 대신 출생연도만 보관한다.

import uuid
from datetime import date
from typing import List, Optional, TYPE_CHECKING

from sqlalchemy import Date, Enum as SAEnum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import CaseStatus, GuardianType
from app.models.base import Base, JSONType, TimestampMixin, UUIDPrimaryKeyMixin

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

    # 보호자 유형. 목록에 없는 관계는 OTHER 로 두고 guardian_note 에 적는다.
    # 아동 실명과 마찬가지로 보호자 실명은 저장하지 않는다.
    guardian_type: Mapped[Optional[GuardianType]] = mapped_column(
        SAEnum(GuardianType, name="guardian_type", native_enum=False, length=20),
        nullable=True,
    )
    guardian_note: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # 초기면접(서식 4 ②)에서 고른 아동 특성 · 가정상황. app/core/intake.py 의 항목만 담는다(자유 글 없음).
    # 이 칸이 생기기 전에 만든 사례는 null 이고, 응답은 빈 목록으로 준다.
    intake_child_traits: Mapped[Optional[List[str]]] = mapped_column(JSONType, nullable=True)
    intake_family_situations: Mapped[Optional[List[str]]] = mapped_column(
        JSONType, nullable=True
    )

    # 서식 4 ① 의 날짜 셋(2026-10-30, 팀장님 '준비 중 이어서'). 사람을 가리키는 정보가 아니라 사례 진행 날짜다.
    report_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)  # 신고접수일
    linked_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)  # 사례연계일
    first_interview_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)  # 최초면접일

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
