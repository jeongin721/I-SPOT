# 일정(API_CONTRACT 19절, 2026-11-02, 일정 디자인).
#
# 보이는 일정: 상담사는 자기 일정 + 다른 상담사가 팀 공유한 개인 · 기관 일정, 관리자는 전체.
# 고치기 · 지우기는 만든 사람 · 관리자만(공유 일정은 보기만). 사례를 붙이려면 그 사례를 볼 수 있어야 한다.
# 종류별 필수 칸: 상담 일정 = 사례 · 상담 유형, 개인 · 기관 일정 = 분류(최초접수면 사례도). 상담 일정에는 분류 · 제목 · 공유를,
# 개인 · 기관 일정에는 상담 유형을 두지 않는다(종류를 바꾸면 맞지 않는 칸은 비운다).
# 최초접수의 법정 기한(3 · 7 · 30일)은 화면이 접수일로 계산한다. 목록은 기간 앞 30일 안의 최초접수도 함께 준다(기한이 기간 안에 올 수 있어서).
# 감사 기록에는 종류 · 분류 · 바뀐 칸 이름만 남긴다(제목 · 장소 글은 남기지 않는다).

import uuid
from datetime import date, timedelta
from typing import Dict, List, Optional

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session, selectinload

from app.core.enums import AuditAction, ScheduleCategory, ScheduleKind
from app.core.errors import APIError, ErrorCode, forbidden, not_found
from app.models.case import Case
from app.models.schedule import INTAKE_DEADLINE_DAYS, ScheduleEvent
from app.models.user import User
from app.schemas.schedule import (
    DEADLINE_KEYS,
    ScheduleCreateRequest,
    ScheduleEventResponse,
    ScheduleUpdateRequest,
)
from app.services import audit_service
from app.services.access import get_case_or_404

#: 한 번에 볼 수 있는 기간(일). 달력 한 달 + 앞뒤 주를 넉넉히 덮는다.
MAX_RANGE_DAYS = 400
INTAKE_LOOKBACK_DAYS = max(INTAKE_DEADLINE_DAYS)


def _invalid(message: str) -> APIError:
    return APIError(ErrorCode.VALIDATION_ERROR, message, status_code=422)


def _can_see_case(user: User, case: Optional[Case]) -> bool:
    return case is not None and (user.is_admin or case.counselor_id == user.id)


def _can_edit(user: User, row: ScheduleEvent) -> bool:
    return user.is_admin or row.owner_id == user.id


def to_response(row: ScheduleEvent, user: User) -> ScheduleEventResponse:
    show_case = _can_see_case(user, row.case)
    return ScheduleEventResponse(
        id=row.id,
        kind=row.kind,
        consult_type=row.consult_type,
        category=row.category,
        case_id=row.case_id if show_case else None,
        child_alias=row.case.child_alias if show_case and row.case else None,
        title=row.title,
        date=row.event_date,
        time=row.event_time,
        place=row.place,
        important=row.important,
        shared=row.shared,
        deadline_done={key: bool((row.deadline_done or {}).get(key)) for key in DEADLINE_KEYS}
        if row.category == ScheduleCategory.INTAKE
        else {},
        owner_id=row.owner_id,
        owner_name=row.owner.name if row.owner else None,
        editable=_can_edit(user, row),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def list_events(db: Session, user: User, start: date, end: date) -> List[ScheduleEvent]:
    if end < start:
        raise _invalid("끝 날짜가 시작 날짜보다 앞입니다.")
    if (end - start).days > MAX_RANGE_DAYS:
        raise _invalid(f"한 번에 {MAX_RANGE_DAYS}일까지 볼 수 있습니다.")

    in_range = and_(ScheduleEvent.event_date >= start, ScheduleEvent.event_date <= end)
    intake_before = and_(
        ScheduleEvent.category == ScheduleCategory.INTAKE,
        ScheduleEvent.event_date >= start - timedelta(days=INTAKE_LOOKBACK_DAYS),
        ScheduleEvent.event_date < start,
    )
    query = (
        select(ScheduleEvent)
        .options(selectinload(ScheduleEvent.case), selectinload(ScheduleEvent.owner))
        .where(or_(in_range, intake_before))
    )
    if not user.is_admin:
        query = query.where(
            or_(
                ScheduleEvent.owner_id == user.id,
                and_(ScheduleEvent.shared.is_(True), ScheduleEvent.kind == ScheduleKind.OTHER),
            )
        )
    rows = list(db.scalars(query))
    # 종일(null)이 먼저, 그다음 시각 순.
    rows.sort(key=lambda row: (row.event_date, row.event_time is not None, row.event_time or "", row.created_at))
    return rows


def get_event_or_404(db: Session, event_id: uuid.UUID, user: User, *, edit: bool = False) -> ScheduleEvent:
    row = db.scalar(
        select(ScheduleEvent)
        .options(selectinload(ScheduleEvent.case), selectinload(ScheduleEvent.owner))
        .where(ScheduleEvent.id == event_id)
    )
    visible = row is not None and (
        user.is_admin or row.owner_id == user.id or (row.shared and row.kind == ScheduleKind.OTHER)
    )
    if not visible:
        raise not_found(ErrorCode.NOT_FOUND, "일정을 찾을 수 없습니다.")
    if edit and not _can_edit(user, row):
        raise forbidden("일정을 만든 상담사만 고치거나 지울 수 있습니다.")
    return row


def _check(db: Session, user: User, row: ScheduleEvent, case_changed: bool) -> None:
    """합친 값으로 종류별 필수 칸을 보고, 맞지 않는 칸은 비운다."""

    if row.kind == ScheduleKind.CONSULT:
        if row.case_id is None or row.consult_type is None:
            raise _invalid("상담 일정에는 사례와 상담 유형이 필요합니다.")
        row.category = None
        row.title = None
        row.shared = False
    else:
        if row.category is None:
            raise _invalid("개인 · 기관 일정에는 분류가 필요합니다.")
        if row.category == ScheduleCategory.INTAKE and row.case_id is None:
            raise _invalid("최초접수 일정에는 사례가 필요합니다.")
        row.consult_type = None

    if row.category != ScheduleCategory.INTAKE:
        row.deadline_done = {}

    if case_changed and row.case_id is not None:
        # 볼 수 없는 사례는 붙일 수 없다(없으면 404, 남의 사례면 403).
        row.case = get_case_or_404(db, row.case_id, user)


def create_event(db: Session, user: User, payload: ScheduleCreateRequest) -> ScheduleEvent:
    row = ScheduleEvent(
        owner_id=user.id,
        kind=payload.kind,
        consult_type=payload.consult_type,
        category=payload.category,
        case_id=payload.case_id,
        title=payload.title,
        event_date=payload.date,
        event_time=payload.time,
        place=payload.place,
        important=bool(payload.important),
        shared=bool(payload.shared),
        deadline_done={},
    )
    _check(db, user, row, case_changed=True)
    db.add(row)
    db.flush()
    audit_service.record(
        db,
        action=AuditAction.SCHEDULE_CREATED,
        entity_type="ScheduleEvent",
        entity_id=row.id,
        actor_id=user.id,
        case_id=row.case_id,
        detail={"kind": row.kind.value, "category": row.category.value if row.category else None},
    )
    db.commit()
    return get_event_or_404(db, row.id, user)


def update_event(db: Session, user: User, row: ScheduleEvent, payload: ScheduleUpdateRequest) -> ScheduleEvent:
    sent = payload.model_dump(exclude_unset=True)
    columns = {"date": "event_date", "time": "event_time"}
    old_case = row.case_id

    for field, value in sent.items():
        if field == "deadline_done":
            continue
        if field in ("important", "shared"):
            value = bool(value)
        setattr(row, columns.get(field, field), value)

    if "deadline_done" in sent:
        if row.category != ScheduleCategory.INTAKE:
            raise _invalid("법정 기한 완료 표시는 최초접수 일정에만 있습니다.")
        merged: Dict[str, bool] = {**(row.deadline_done or {}), **{k: bool(v) for k, v in sent["deadline_done"].items()}}
        row.deadline_done = merged

    _check(db, user, row, case_changed=row.case_id != old_case)
    audit_service.record(
        db,
        action=AuditAction.SCHEDULE_UPDATED,
        entity_type="ScheduleEvent",
        entity_id=row.id,
        actor_id=user.id,
        case_id=row.case_id,
        detail={"fields": sorted(sent)},
    )
    db.commit()
    return get_event_or_404(db, row.id, user)


def delete_event(db: Session, user: User, row: ScheduleEvent) -> None:
    audit_service.record(
        db,
        action=AuditAction.SCHEDULE_DELETED,
        entity_type="ScheduleEvent",
        entity_id=row.id,
        actor_id=user.id,
        case_id=row.case_id,
        detail={"kind": row.kind.value, "category": row.category.value if row.category else None},
    )
    db.delete(row)
    db.commit()
