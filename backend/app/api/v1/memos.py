# /memos — 상담사 메모(25절, 2026-11-10). 쓴 상담사만 읽고 고치고 지운다(관리자도 남의 메모는 못 본다).

import uuid
from typing import Annotated, Optional

from fastapi import APIRouter, Query, Response, status

from app.api.v1.cases import PageQuery, PageSizeQuery
from app.core.deps import CurrentUser, DbSession
from app.core.responses import DataResponse, PagedItems, paged
from app.schemas.memo import MemoCreateRequest, MemoResponse, MemoUpdateRequest
from app.services import memo_service

router = APIRouter(prefix="/memos", tags=["memos"])


@router.get("", response_model=DataResponse[PagedItems[MemoResponse]])
def list_memos(
    db: DbSession,
    current_user: CurrentUser,
    page: PageQuery = 1,
    page_size: PageSizeQuery = 20,
    case_id: Annotated[Optional[uuid.UUID], Query()] = None,
) -> DataResponse[PagedItems[MemoResponse]]:
    rows, total = memo_service.list_memos(db, current_user, offset=(page - 1) * page_size, limit=page_size, case_id=case_id)

    return DataResponse(data=paged([memo_service.to_response(row) for row in rows], total, page, page_size))


@router.post("", response_model=DataResponse[MemoResponse], status_code=status.HTTP_201_CREATED)
def create_memo(payload: MemoCreateRequest, db: DbSession, current_user: CurrentUser) -> DataResponse[MemoResponse]:
    row = memo_service.create_memo(db, current_user, payload)

    return DataResponse(data=memo_service.to_response(row))


@router.get("/{memo_id}", response_model=DataResponse[MemoResponse])
def get_memo(memo_id: uuid.UUID, db: DbSession, current_user: CurrentUser) -> DataResponse[MemoResponse]:
    return DataResponse(data=memo_service.to_response(memo_service.get_memo_or_404(db, memo_id, current_user)))


@router.patch("/{memo_id}", response_model=DataResponse[MemoResponse])
def update_memo(
    memo_id: uuid.UUID, payload: MemoUpdateRequest, db: DbSession, current_user: CurrentUser
) -> DataResponse[MemoResponse]:
    row = memo_service.get_memo_or_404(db, memo_id, current_user)
    row = memo_service.update_memo(db, current_user, row, payload)

    return DataResponse(data=memo_service.to_response(row))


@router.delete("/{memo_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_memo(memo_id: uuid.UUID, db: DbSession, current_user: CurrentUser) -> Response:
    row = memo_service.get_memo_or_404(db, memo_id, current_user)
    memo_service.delete_memo(db, current_user, row)

    return Response(status_code=status.HTTP_204_NO_CONTENT)
