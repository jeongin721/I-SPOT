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
from app.schemas.common import StorableQueryText
from app.schemas.session import SessionCreateRequest, SessionResponse
from app.schemas.signal_history import SignalHistoryResponse
from app.schemas.closure_review import ClosureSummaryResponse, ClosureSummarySaveRequest
from app.services import case_service, closure_review_service, session_service, signal_history_service
from app.services.access import get_case_or_404

router = APIRouter(prefix="/cases", tags=["cases"])

# /cases/{case_id}/sessions 는 주소만 Case 하위일 뿐 다루는 대상은 Session 이다.
# 이 저장소는 주소가 아니라 대상으로 tag 를 나누므로(/sessions/{id}/audio 가
# audio tag 인 것과 같다) 별도 router 로 분리한다.
#
# 같은 router 에 tags=["sessions"] 만 붙이면 FastAPI 가 router tag 와 합쳐
# ["cases", "sessions"] 가 되고, 문서에 같은 endpoint 가 두 번 나온다.
session_router = APIRouter(prefix="/cases", tags=["sessions"])

# page 상한. 없으면 건너뛸 행 수((page - 1) × page_size)가 DB 정수 범위를 넘어 500 이 난다.
# 넘는 값은 다른 입력값 오류처럼 422 VALIDATION_ERROR 다. 목록 창구(사례 · 회기 · 업무 · 감사 로그)가 함께 쓴다.
MAX_PAGE = 1_000_000

PageQuery = Annotated[
    int, Query(ge=1, le=MAX_PAGE, description="1부터 시작하는 page 번호(최대 1,000,000)")
]
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
    # NUL 이 든 검색어는 422 다(SQL 파라미터로 쓰이므로 PostgreSQL 이 거절해 500 이 된다).
    # StorableQueryText 는 Query(...) 뒤에 둔다(common.py).
    search: Annotated[Optional[str], Query(max_length=100), StorableQueryText] = None,
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


@router.get("/{case_id}/signal-history", response_model=DataResponse[SignalHistoryResponse])
def get_signal_history(
    case_id: uuid.UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> DataResponse[SignalHistoryResponse]:
    """
    사례의 회차별 AI 신호 · 심각도 제안 · 상담원 판단 이력(API_CONTRACT 4절, 2026-10-28).

    회차마다 analysis · risk-assessment(회차 전체 판단) · risk-assessments(유형별 판단)를 부르던 것을 한 번에 준다.
    AI 를 새로 돌리지 않는다.
    권한 · 오류는 GET /cases/{case_id} 와 같다.
    """

    case = get_case_or_404(db, case_id, current_user)

    return DataResponse(data=signal_history_service.build_signal_history(db, case))


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


@router.post("/{case_id}/closure-review", response_model=DataResponse[CaseResponse])
def register_closure_review(
    case_id: uuid.UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> DataResponse[CaseResponse]:
    """종결 검토에 등록한다(4절, 2026-10-30). 진행 중 사례만, 이미 등록됐으면 그대로."""

    case = get_case_or_404(db, case_id, current_user)
    updated = case_service.set_closure_review(db, case, current_user, register=True)

    return DataResponse(data=_case_response(updated))


@router.delete("/{case_id}/closure-review", response_model=DataResponse[CaseResponse])
def cancel_closure_review(
    case_id: uuid.UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> DataResponse[CaseResponse]:
    """종결 검토 등록을 취소한다. 등록 전이면 그대로."""

    case = get_case_or_404(db, case_id, current_user)
    updated = case_service.set_closure_review(db, case, current_user, register=False)

    return DataResponse(data=_case_response(updated))


@router.get("/{case_id}/closure-summary", response_model=DataResponse[ClosureSummaryResponse])
def get_closure_summary(case_id: uuid.UUID, db: DbSession, current_user: CurrentUser) -> DataResponse[ClosureSummaryResponse]:
    """종결 검토 요약 · 보고서(4절, 2026-10-30). 만들기 전이면 summary null."""

    case = get_case_or_404(db, case_id, current_user)
    return DataResponse(data=closure_review_service.to_response(case, closure_review_service.get_row(db, case.id)))


@router.post("/{case_id}/closure-summary", response_model=DataResponse[ClosureSummaryResponse])
def generate_closure_summary(case_id: uuid.UUID, db: DbSession, current_user: CurrentUser) -> DataResponse[ClosureSummaryResponse]:
    """승인 완료 회차 요약으로 종결 요약을 (다시) 만든다. 동기 응답, 넘으면 504."""

    case = get_case_or_404(db, case_id, current_user)
    row = closure_review_service.generate(db, case, current_user)
    return DataResponse(data=closure_review_service.to_response(case, row))


@router.put("/{case_id}/closure-summary", response_model=DataResponse[ClosureSummaryResponse])
def save_closure_summary(
    case_id: uuid.UUID, payload: ClosureSummarySaveRequest, db: DbSession, current_user: CurrentUser
) -> DataResponse[ClosureSummaryResponse]:
    """확인 체크 · 고친 문장 · 종결보고서 칸을 저장한다(보낸 칸만)."""

    case = get_case_or_404(db, case_id, current_user)
    row = closure_review_service.save(db, case, current_user, payload)
    return DataResponse(data=closure_review_service.to_response(case, row))


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
