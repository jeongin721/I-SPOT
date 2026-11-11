# /schedule/events — 일정(20절, 2026-11-02)

import uuid
from datetime import date

from fastapi import APIRouter, Query, Response, status

from app.core.deps import CurrentUser, DbSession
from app.core.responses import DataResponse
from app.schemas.schedule import (
    ScheduleCreateRequest,
    ScheduleEventResponse,
    ScheduleListResponse,
    ScheduleUpdateRequest,
)
from app.services import schedule_service

router = APIRouter(prefix="/schedule", tags=["schedule"])


@router.get("/events", response_model=DataResponse[ScheduleListResponse])
def list_schedule_events(
    db: DbSession,
    current_user: CurrentUser,
    start: date = Query(alias="from"),
    end: date = Query(alias="to"),
) -> DataResponse[ScheduleListResponse]:
    rows = schedule_service.list_events(db, current_user, start, end)

    return DataResponse(data=ScheduleListResponse(items=[schedule_service.to_response(row, current_user) for row in rows]))


@router.post("/events", response_model=DataResponse[ScheduleEventResponse], status_code=status.HTTP_201_CREATED)
def create_schedule_event(
    payload: ScheduleCreateRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> DataResponse[ScheduleEventResponse]:
    row = schedule_service.create_event(db, current_user, payload)

    return DataResponse(data=schedule_service.to_response(row, current_user))


@router.patch("/events/{event_id}", response_model=DataResponse[ScheduleEventResponse])
def update_schedule_event(
    event_id: uuid.UUID,
    payload: ScheduleUpdateRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> DataResponse[ScheduleEventResponse]:
    # 중요 표시만 보냈으면 볼 수 있는 일정은 누구나 고친다(get_event_or_404 mark_only).
    mark_only = set(payload.model_dump(exclude_unset=True)) == {"important"}
    row = schedule_service.get_event_or_404(db, event_id, current_user, edit=True, mark_only=mark_only)
    row = schedule_service.update_event(db, current_user, row, payload)

    return DataResponse(data=schedule_service.to_response(row, current_user))


@router.delete("/events/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_schedule_event(event_id: uuid.UUID, db: DbSession, current_user: CurrentUser) -> Response:
    row = schedule_service.get_event_or_404(db, event_id, current_user, edit=True)
    schedule_service.delete_event(db, current_user, row)

    return Response(status_code=status.HTTP_204_NO_CONTENT)
