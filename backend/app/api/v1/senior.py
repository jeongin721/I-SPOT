# /cases/{case_id}/senior-* · /cases/{case_id}/health-* — 고령자 건강상담(27절, 2026-11-13).
#
# 모두 담당 상담사 · 관리자만(get_case_or_404), 대상 종류가 SENIOR 인 사례만(아니면 409 INVALID_CASE_STATE).

import uuid
from typing import Annotated, List, Optional

from fastapi import APIRouter, Query, status

from app.core.enums import NextCheckStatus
from app.core.deps import CurrentUser, DbSession
from app.core.responses import DataResponse
from app.schemas.senior import (
    HealthMeasurementCreateRequest,
    HealthMeasurementResponse,
    HealthMeasurementUpdateRequest,
    HealthTrendResponse,
    NextCheckResponse,
    NextChecksSaveRequest,
    NextCheckUpdateRequest,
    SeniorBriefResponse,
    SeniorHistoryResponse,
    SeniorProfileResponse,
    SeniorProfileUpdateRequest,
)
from app.services import senior_service
from app.services.access import get_case_or_404

router = APIRouter(prefix="/cases", tags=["senior"])


@router.get("/{case_id}/senior-profile", response_model=DataResponse[SeniorProfileResponse])
def get_senior_profile(case_id: uuid.UUID, db: DbSession, current_user: CurrentUser) -> DataResponse[SeniorProfileResponse]:
    case = get_case_or_404(db, case_id, current_user)
    return DataResponse(data=senior_service.get_profile(db, case))


@router.patch("/{case_id}/senior-profile", response_model=DataResponse[SeniorProfileResponse])
def update_senior_profile(
    case_id: uuid.UUID,
    payload: SeniorProfileUpdateRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> DataResponse[SeniorProfileResponse]:
    case = get_case_or_404(db, case_id, current_user)
    return DataResponse(data=senior_service.update_profile(db, case, current_user, payload))


@router.get("/{case_id}/health-measurements", response_model=DataResponse[List[HealthMeasurementResponse]])
def list_health_measurements(
    case_id: uuid.UUID, db: DbSession, current_user: CurrentUser
) -> DataResponse[List[HealthMeasurementResponse]]:
    case = get_case_or_404(db, case_id, current_user)
    return DataResponse(data=senior_service.list_measurements(db, case))


@router.post(
    "/{case_id}/health-measurements",
    response_model=DataResponse[HealthMeasurementResponse],
    status_code=status.HTTP_201_CREATED,
)
def create_health_measurement(
    case_id: uuid.UUID,
    payload: HealthMeasurementCreateRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> DataResponse[HealthMeasurementResponse]:
    case = get_case_or_404(db, case_id, current_user)
    return DataResponse(data=senior_service.create_measurement(db, case, current_user, payload))


@router.patch(
    "/{case_id}/health-measurements/{measurement_id}",
    response_model=DataResponse[HealthMeasurementResponse],
)
def update_health_measurement(
    case_id: uuid.UUID,
    measurement_id: uuid.UUID,
    payload: HealthMeasurementUpdateRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> DataResponse[HealthMeasurementResponse]:
    case = get_case_or_404(db, case_id, current_user)
    return DataResponse(data=senior_service.update_measurement(db, case, measurement_id, current_user, payload))


@router.delete("/{case_id}/health-measurements/{measurement_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_health_measurement(
    case_id: uuid.UUID,
    measurement_id: uuid.UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> None:
    case = get_case_or_404(db, case_id, current_user)
    senior_service.delete_measurement(db, case, measurement_id, current_user)


@router.get("/{case_id}/health-trend", response_model=DataResponse[HealthTrendResponse])
def get_health_trend(case_id: uuid.UUID, db: DbSession, current_user: CurrentUser) -> DataResponse[HealthTrendResponse]:
    case = get_case_or_404(db, case_id, current_user)
    return DataResponse(data=senior_service.get_trend(db, case))


@router.post("/{case_id}/senior-brief", response_model=DataResponse[SeniorBriefResponse])
def generate_senior_brief(
    case_id: uuid.UUID, db: DbSession, current_user: CurrentUser
) -> DataResponse[SeniorBriefResponse]:
    """요약 · 다음 상담 확인사항을 만든다. 저장하지 않는다(부를 때마다 새로). 담당자가 읽고 고른다."""

    case = get_case_or_404(db, case_id, current_user)
    return DataResponse(data=senior_service.generate_brief(db, case, current_user))


@router.get("/{case_id}/next-checks", response_model=DataResponse[List[NextCheckResponse]])
def list_next_checks(
    case_id: uuid.UUID,
    db: DbSession,
    current_user: CurrentUser,
    status_filter: Annotated[Optional[NextCheckStatus], Query(alias="status")] = None,
) -> DataResponse[List[NextCheckResponse]]:
    case = get_case_or_404(db, case_id, current_user)
    return DataResponse(data=senior_service.list_next_checks(db, case, status_filter))


@router.post(
    "/{case_id}/next-checks",
    response_model=DataResponse[List[NextCheckResponse]],
    status_code=status.HTTP_201_CREATED,
)
def save_next_checks(
    case_id: uuid.UUID,
    payload: NextChecksSaveRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> DataResponse[List[NextCheckResponse]]:
    """담당자가 고른 확인사항을 저장한다(초안을 두기 · 고치기 · 지우기 한 결과)."""

    case = get_case_or_404(db, case_id, current_user)
    return DataResponse(data=senior_service.save_next_checks(db, case, current_user, payload))


@router.patch("/{case_id}/next-checks/{check_id}", response_model=DataResponse[NextCheckResponse])
def update_next_check(
    case_id: uuid.UUID,
    check_id: uuid.UUID,
    payload: NextCheckUpdateRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> DataResponse[NextCheckResponse]:
    case = get_case_or_404(db, case_id, current_user)
    return DataResponse(data=senior_service.update_next_check(db, case, check_id, current_user, payload))


@router.delete("/{case_id}/next-checks/{check_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_next_check(case_id: uuid.UUID, check_id: uuid.UUID, db: DbSession, current_user: CurrentUser) -> None:
    case = get_case_or_404(db, case_id, current_user)
    senior_service.delete_next_check(db, case, check_id, current_user)


@router.get("/{case_id}/senior-history", response_model=DataResponse[SeniorHistoryResponse])
def get_senior_history(case_id: uuid.UUID, db: DbSession, current_user: CurrentUser) -> DataResponse[SeniorHistoryResponse]:
    """상담 이력 조회 — 방문 · 측정 · 요약 · 확인사항을 시간순(최근 것부터)으로."""

    case = get_case_or_404(db, case_id, current_user)
    return DataResponse(data=senior_service.get_history(db, case))
