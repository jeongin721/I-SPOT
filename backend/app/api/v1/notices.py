# /notices — 사내 공지사항(28절, 2026-11-20). 읽기는 로그인한 누구나, 쓰고 고치고 지우기는 관리자만.

import uuid
from typing import Annotated

from fastapi import APIRouter, Query, Response, status

from app.core.deps import AdminUser, CurrentUser, DbSession
from app.core.responses import DataResponse
from app.schemas.notice import NoticeCreateRequest, NoticeResponse, NoticeUpdateRequest
from app.services import notice_service

router = APIRouter(prefix="/notices", tags=["notices"])


@router.get("", response_model=DataResponse[list[NoticeResponse]])
def list_notices(
    db: DbSession,
    current_user: CurrentUser,
    limit: Annotated[int, Query(ge=1, le=notice_service.NOTICE_LIST_MAX)] = 20,
) -> DataResponse[list[NoticeResponse]]:
    return DataResponse(data=[notice_service.to_response(row) for row in notice_service.list_notices(db, limit)])


@router.post("", response_model=DataResponse[NoticeResponse], status_code=status.HTTP_201_CREATED)
def create_notice(payload: NoticeCreateRequest, db: DbSession, admin: AdminUser) -> DataResponse[NoticeResponse]:
    return DataResponse(data=notice_service.to_response(notice_service.create_notice(db, admin, payload)))


@router.patch("/{notice_id}", response_model=DataResponse[NoticeResponse])
def update_notice(
    notice_id: uuid.UUID, payload: NoticeUpdateRequest, db: DbSession, admin: AdminUser
) -> DataResponse[NoticeResponse]:
    row = notice_service.get_notice_or_404(db, notice_id)

    return DataResponse(data=notice_service.to_response(notice_service.update_notice(db, admin, row, payload)))


@router.delete("/{notice_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_notice(notice_id: uuid.UUID, db: DbSession, admin: AdminUser) -> Response:
    notice_service.delete_notice(db, admin, notice_service.get_notice_or_404(db, notice_id))

    return Response(status_code=status.HTTP_204_NO_CONTENT)
