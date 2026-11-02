# 일정(2026-11-02, 일정 디자인 · API_CONTRACT 19절). 한 행이 일정 하나.
#
# 상담 일정(CONSULT)은 사례 · 상담 유형이 있고, 개인 · 기관 일정(OTHER)은 분류 · 제목이 있다(사례는 골라서).
# 최초접수(OTHER · INTAKE)는 사례가 필수이고, 학대 판정 뒤 법정 기한 3 · 7 · 30일 일정은 행으로 만들지 않고 화면이
# 접수일에서 계산한다. 기한마다 '완료' 표시만 deadline_done 에 남긴다.
# 일정은 만든 사람(owner) 것이다. 팀 공유(shared)한 개인 · 기관 일정은 다른 상담사도 본다(고치기 · 지우기는 만든 사람 · 관리자만).

import uuid
from datetime import date
from typing import Any, Dict, Optional, TYPE_CHECKING

from sqlalchemy import Boolean, Date, Enum as SAEnum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import ScheduleCategory, ScheduleConsultType, ScheduleKind
from app.models.base import Base, JSONType, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.case import Case
    from app.models.user import User

SCHEDULE_TITLE_MAX_LENGTH = 100
SCHEDULE_PLACE_MAX_LENGTH = 100
#: 최초접수 뒤 법정 기한(일). 학대 판정 후 3일 유선 상담 · 7일 주변 인물 만남 · 30일 계획서 제출.
INTAKE_DEADLINE_DAYS = (3, 7, 30)


class ScheduleEvent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "schedule_events"

    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    kind: Mapped[ScheduleKind] = mapped_column(
        SAEnum(ScheduleKind, name="schedule_kind", native_enum=False, length=20), nullable=False
    )
    consult_type: Mapped[Optional[ScheduleConsultType]] = mapped_column(
        SAEnum(ScheduleConsultType, name="schedule_consult_type", native_enum=False, length=20), nullable=True
    )
    category: Mapped[Optional[ScheduleCategory]] = mapped_column(
        SAEnum(ScheduleCategory, name="schedule_category", native_enum=False, length=30), nullable=True
    )
    case_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("cases.id", ondelete="CASCADE"), nullable=True, index=True
    )
    title: Mapped[Optional[str]] = mapped_column(String(SCHEDULE_TITLE_MAX_LENGTH), nullable=True)
    event_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    # 'HH:MM'(사용자 시간대 그대로). null 이면 종일.
    event_time: Mapped[Optional[str]] = mapped_column(String(5), nullable=True)
    place: Mapped[Optional[str]] = mapped_column(String(SCHEDULE_PLACE_MAX_LENGTH), nullable=True)
    important: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    shared: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # 최초접수 법정 기한 완료 표시 {"3": true, "7": false, "30": true}. 그 밖 일정은 {}.
    deadline_done: Mapped[Dict[str, Any]] = mapped_column(JSONType, default=dict, nullable=False)

    owner: Mapped["User"] = relationship(foreign_keys=[owner_id])
    case: Mapped[Optional["Case"]] = relationship(foreign_keys=[case_id])

    def __repr__(self) -> str:
        return f"<ScheduleEvent id={self.id} kind={self.kind.value} date={self.event_date}>"
