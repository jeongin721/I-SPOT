# 고령자 생활 · 정서 영역 변화(27절, 2026-11-16) — 회차별 확정 · 사례별 영역 이력.
#
# 담당 상담사 · 관리자만(get_session_or_404 · get_case_or_404), 대상 종류가 SENIOR 인 사례만(아니면 409 INVALID_CASE_STATE).

import uuid

from fastapi import APIRouter

from app.core.deps import CurrentUser, DbSession
from app.core.responses import DataResponse
from app.schemas.senior import CareDomainsSaveRequest, CareDomainTimelineResponse, SessionCareDomainsResponse
from app.services import care_domain_service
from app.services.access import get_case_or_404, get_session_or_404

session_router = APIRouter(prefix="/sessions", tags=["senior"])
case_router = APIRouter(prefix="/cases", tags=["senior"])


@session_router.get("/{session_id}/care-domains", response_model=DataResponse[SessionCareDomainsResponse])
def get_session_care_domains(
    session_id: uuid.UUID, db: DbSession, current_user: CurrentUser
) -> DataResponse[SessionCareDomainsResponse]:
    """다섯 영역마다 견줄 앞 기록 · 이번 초안 · 확정한 것."""

    session = get_session_or_404(db, session_id, current_user)
    return DataResponse(data=care_domain_service.get_session_domains(db, session))


@session_router.put("/{session_id}/care-domains", response_model=DataResponse[SessionCareDomainsResponse])
def save_session_care_domains(
    session_id: uuid.UUID,
    payload: CareDomainsSaveRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> DataResponse[SessionCareDomainsResponse]:
    """담당자가 검토한 영역을 확정한다. 보낸 영역만 바꾼다."""

    session = get_session_or_404(db, session_id, current_user)
    return DataResponse(data=care_domain_service.save_session_domains(db, session, current_user, payload))


@case_router.get("/{case_id}/care-domains", response_model=DataResponse[CareDomainTimelineResponse])
def get_case_care_domains(
    case_id: uuid.UUID, db: DbSession, current_user: CurrentUser
) -> DataResponse[CareDomainTimelineResponse]:
    """이력 비교 화면 — 영역별로 회차 순 확정 기록."""

    case = get_case_or_404(db, case_id, current_user)
    return DataResponse(data=care_domain_service.get_timeline(db, case))
