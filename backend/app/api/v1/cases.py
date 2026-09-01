# /cases 및 /cases/{case_id}/sessions

import uuid
from typing import Annotated, Optional

from fastapi import APIRouter, Query, status

from app.core.enums import CaseStatus, SessionStatus
from app.core.deps import CurrentUser, DbSession
from app.core.responses import DataResponse, PagedItems, paged
from app.schemas.case import (
    CaseCreateRequest,
    CaseDetailResponse,
    CaseResponse,
    CaseUpdateRequest,
)
from app.schemas.auth import UserResponse
from app.schemas.session import SessionCreateRequest, SessionResponse
from app.services import case_service, session_service
from app.services.access import get_case_or_404

router = APIRouter(prefix="/cases", tags=["cases"])

PageQuery = Annotated[int, Query(ge=1, description="1부터 시작하는 page 번호")]
PageSizeQuery = Annotated[int, Query(ge=1, le=100)]


@router.get("", response_model=DataResponse[PagedItems[CaseResponse]])
def list_cases(
    db: DbSession,
    current_user: CurrentUser,
    page: PageQuery = 1,
    page_size: PageSizeQuery = 20,
    status_filter: Annotated[Optional[CaseStatus], Query(alias="status")] = None,
    search: Annotated[Optional[str], Query(max_length=100)] = None,
) -> DataResponse[PagedItems[CaseResponse]]:
    cases, total = case_service.list_cases(
        db,
        current_user,
        offset=(page - 1) * page_size,
        limit=page_size,
        status=status_filter,
        search=search,
    )

    items = [CaseResponse.model_validate(case) for case in cases]

    return DataResponse(data=paged(items, total, page, page_size))


@router.post(
    "",
    response_model=DataResponse[CaseResponse],
    status_code=status.HTTP_201_CREATED,
)
def create_case(
    payload: CaseCreateRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> DataResponse[CaseResponse]:
    case = case_service.create_case(db, current_user, payload)

    return DataResponse(data=CaseResponse.model_validate(case))


@router.get("/{case_id}", response_model=DataResponse[CaseDetailResponse])
def get_case(
    case_id: uuid.UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> DataResponse[CaseDetailResponse]:
    case, session_count = case_service.get_case_detail(db, case_id, current_user)

    detail = CaseDetailResponse.model_validate(case)
    detail.session_count = session_count
    detail.counselor = (
        UserResponse.model_validate(case.counselor) if case.counselor else None
    )

    return DataResponse(data=detail)


@router.patch("/{case_id}", response_model=DataResponse[CaseResponse])
def update_case(
    case_id: uuid.UUID,
    payload: CaseUpdateRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> DataResponse[CaseResponse]:
    case = get_case_or_404(db, case_id, current_user)
    updated = case_service.update_case(db, case, current_user, payload)

    return DataResponse(data=CaseResponse.model_validate(updated))


@router.delete("/{case_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_case(
    case_id: uuid.UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> None:
    case = get_case_or_404(db, case_id, current_user)
    case_service.delete_case(db, case, current_user)


# =========================================================
# /cases/{case_id}/sessions
# =========================================================

@router.get(
    "/{case_id}/sessions",
    response_model=DataResponse[PagedItems[SessionResponse]],
    tags=["sessions"],
)
def list_sessions(
    case_id: uuid.UUID,
    db: DbSession,
    current_user: CurrentUser,
    page: PageQuery = 1,
    page_size: PageSizeQuery = 20,
    status_filter: Annotated[Optional[SessionStatus], Query(alias="status")] = None,
) -> DataResponse[PagedItems[SessionResponse]]:
    get_case_or_404(db, case_id, current_user)

    sessions, total = session_service.list_sessions(
        db,
        case_id,
        offset=(page - 1) * page_size,
        limit=page_size,
        status=status_filter,
    )

    items = [SessionResponse.model_validate(session) for session in sessions]

    return DataResponse(data=paged(items, total, page, page_size))


@router.post(
    "/{case_id}/sessions",
    response_model=DataResponse[SessionResponse],
    status_code=status.HTTP_201_CREATED,
    tags=["sessions"],
)
def create_session(
    case_id: uuid.UUID,
    payload: SessionCreateRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> DataResponse[SessionResponse]:
    case = get_case_or_404(db, case_id, current_user)
    session = session_service.create_session(db, case, current_user, payload)

    return DataResponse(data=SessionResponse.model_validate(session))
