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

# /cases/{case_id}/sessions 는 주소만 Case 하위일 뿐 다루는 대상은 Session 이다.
# 이 저장소는 주소가 아니라 대상으로 tag 를 나누므로(/sessions/{id}/audio 가
# audio tag 인 것과 같다) 별도 router 로 분리한다.
#
# 같은 router 에 tags=["sessions"] 만 붙이면 FastAPI 가 router tag 와 합쳐
# ["cases", "sessions"] 가 되고, 문서에 같은 endpoint 가 두 번 나온다.
session_router = APIRouter(prefix="/cases", tags=["sessions"])

PageQuery = Annotated[int, Query(ge=1, description="1부터 시작하는 page 번호")]
PageSizeQuery = Annotated[int, Query(ge=1, le=100)]


def _case_response(case) -> CaseResponse:
    """
    단건 응답을 만든다.

    counselor_name 은 relationship 에서 채운다. 목록은 N+1 을 피하려고
    join 으로 미리 가져오므로 여기를 거치지 않는다.
    """

    item = CaseResponse.model_validate(case)
    item.counselor_name = case.counselor.name if case.counselor else None

    return item


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

    items = []

    for case, last_session_at, counselor_name in cases:
        item = CaseResponse.model_validate(case)
        item.last_session_at = last_session_at
        item.counselor_name = counselor_name
        items.append(item)

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

    return DataResponse(data=_case_response(case))


@router.get("/{case_id}", response_model=DataResponse[CaseDetailResponse])
def get_case(
    case_id: uuid.UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> DataResponse[CaseDetailResponse]:
    case, session_count, last_session_at = case_service.get_case_detail(
        db, case_id, current_user
    )

    detail = CaseDetailResponse.model_validate(case)
    detail.session_count = session_count
    detail.last_session_at = last_session_at
    detail.counselor = (
        UserResponse.model_validate(case.counselor) if case.counselor else None
    )
    # 목록 응답과 같은 필드로도 읽을 수 있게 채운다.
    detail.counselor_name = case.counselor.name if case.counselor else None

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

    return DataResponse(data=_case_response(updated))


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

@session_router.get(
    "/{case_id}/sessions",
    response_model=DataResponse[PagedItems[SessionResponse]],
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


@session_router.post(
    "/{case_id}/sessions",
    response_model=DataResponse[SessionResponse],
    status_code=status.HTTP_201_CREATED,
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
