# 기관 서식 작성 기록(2026-11-02, 탭 5 › 기관 서식 작성 디자인 · API_CONTRACT 22절). 한 행이 서식 하나의 한 차수다.
#
# 서식은 회차가 아니라 사례 단위다 — 점검표는 3개월마다 1차 · 2차 · 3차, 사정기록지 · 척도는 초기 사정 · 재사정 때 쓴다.
# 사례 · 서식 종류마다 임시 저장(DRAFT) 차수는 하나만 둔다. 확정(APPROVED)한 차수는 고치지 않고, 다시 쓰면 다음 차수를 만든다.
# 칸 값은 상담사가 고른 · 쓴 것만 담는다(AI 가 채우지 않는다). 점수 합계 같은 계산 값은 저장하지 않고 응답 때 계산한다.

import uuid
from datetime import datetime
from typing import Any, Dict, Optional, TYPE_CHECKING

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import CaseFormType, ReviewStatus
from app.models.base import Base, JSONType, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.case import Case


class CaseForm(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "case_forms"
    __table_args__ = (UniqueConstraint("case_id", "form_type", "round", name="uq_case_forms_case_type_round"),)

    case_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    form_type: Mapped[CaseFormType] = mapped_column(
        SAEnum(CaseFormType, name="case_form_type", native_enum=False, length=30), nullable=False
    )
    # 차수(1부터). 사례 · 서식 종류마다 따로 센다.
    round: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[ReviewStatus] = mapped_column(
        SAEnum(ReviewStatus, name="case_form_status", native_enum=False, length=20),
        default=ReviewStatus.DRAFT,
        nullable=False,
    )
    # 서식 종류별 칸 값(schemas/case_form.py 의 *Values 꼴).
    values: Mapped[Dict[str, Any]] = mapped_column(JSONType, default=dict, nullable=False)

    created_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    updated_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    confirmed_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    confirmed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    case: Mapped["Case"] = relationship(foreign_keys=[case_id])

    def __repr__(self) -> str:
        return f"<CaseForm id={self.id} type={self.form_type.value} round={self.round} status={self.status.value}>"
