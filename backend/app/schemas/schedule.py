# 일정 Schema(API_CONTRACT 19절, 2026-11-02).

import re
import uuid
from datetime import date, datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, Field, field_validator

from app.core.enums import ScheduleCategory, ScheduleConsultType, ScheduleKind
from app.models.schedule import INTAKE_DEADLINE_DAYS, SCHEDULE_PLACE_MAX_LENGTH, SCHEDULE_TITLE_MAX_LENGTH
from app.schemas.common import IsoDate, RequestModel

_TIME = re.compile(r"([01][0-9]|2[0-3]):[0-5][0-9]")
DEADLINE_KEYS = tuple(str(days) for days in INTAKE_DEADLINE_DAYS)


def _blank_to_none(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    value = " ".join(value.split())
    return value or None


class _ScheduleFields(RequestModel):
    """만들기 · 고치기 공통 칸. 종류별 필수 칸은 서비스가 합친 뒤 본다(schedule_service._check)."""

    consult_type: Optional[ScheduleConsultType] = None
    category: Optional[ScheduleCategory] = None
    case_id: Optional[uuid.UUID] = None
    title: Optional[str] = Field(default=None, max_length=SCHEDULE_TITLE_MAX_LENGTH)
    time: Optional[str] = None
    place: Optional[str] = Field(default=None, max_length=SCHEDULE_PLACE_MAX_LENGTH)
    important: Optional[bool] = None
    shared: Optional[bool] = None

    @field_validator("title", "place")
    @classmethod
    def _squash(cls, value: Optional[str]) -> Optional[str]:
        return _blank_to_none(value)

    @field_validator("time")
    @classmethod
    def _check_time(cls, value: Optional[str]) -> Optional[str]:
        if value is not None and not _TIME.fullmatch(value):
            raise ValueError("시간은 'HH:MM'(00:00~23:59) 으로 보내거나 종일이면 null 로 보냅니다.")
        return value


def _check_date(value: Optional[date]) -> Optional[date]:
    if value is not None and not (date(1900, 1, 1) <= value <= date(2100, 12, 31)):
        raise ValueError("날짜는 1900-01-01 부터 2100-12-31 까지만 쓸 수 있습니다.")
    return value


class ScheduleCreateRequest(_ScheduleFields):
    kind: ScheduleKind
    date: IsoDate

    @field_validator("date")
    @classmethod
    def _date_range(cls, value: date) -> date:
        return _check_date(value)


class ScheduleUpdateRequest(_ScheduleFields):
    """보낸 칸만 바뀐다. kind 는 바꿀 수 있다(상담 ↔ 개인 · 기관). deadline_done 은 최초접수만, 보낸 기한만 바뀐다."""

    kind: Optional[ScheduleKind] = None
    date: Optional[IsoDate] = None
    deadline_done: Optional[Dict[str, bool]] = None

    @field_validator("date")
    @classmethod
    def _date_range(cls, value: Optional[date]) -> Optional[date]:
        return _check_date(value)

    @field_validator("kind", "date", mode="before")
    @classmethod
    def _not_null(cls, value):
        # 빼면 그대로 두지만 null 은 받지 않는다(둘 다 DB 에서 비울 수 없는 칸 — 민규 #131 리뷰: null 이면 500 이었다).
        if value is None:
            raise ValueError("kind · date 는 null 로 보낼 수 없습니다(바꾸지 않으려면 빼고 보냅니다).")
        return value

    @field_validator("deadline_done")
    @classmethod
    def _deadline_keys(cls, value: Optional[Dict[str, bool]]) -> Optional[Dict[str, bool]]:
        if value is not None and not set(value) <= set(DEADLINE_KEYS):
            raise ValueError(f"처리 기한은 {' · '.join(DEADLINE_KEYS)}일만 있습니다.")
        return value


class ScheduleEventResponse(BaseModel):
    id: uuid.UUID
    kind: ScheduleKind
    consult_type: Optional[ScheduleConsultType]
    category: Optional[ScheduleCategory]
    #: 볼 수 있는 사례일 때만(팀 공유 일정의 남의 사례는 null).
    case_id: Optional[uuid.UUID]
    child_alias: Optional[str]
    title: Optional[str]
    date: date
    time: Optional[str]
    place: Optional[str]
    important: bool
    shared: bool
    deadline_done: Dict[str, bool]
    owner_id: uuid.UUID
    owner_name: Optional[str]
    #: 지금 사용자가 고치고 지울 수 있는가(만든 사람 · 관리자).
    editable: bool
    created_at: datetime
    updated_at: datetime


class ScheduleListResponse(BaseModel):
    items: List[ScheduleEventResponse]
