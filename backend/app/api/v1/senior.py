# /cases/{case_id}/senior-* · /cases/{case_id}/health-* — 고령자 건강상담(27절, 2026-11-13).
#
# 모두 담당 상담사 · 관리자만(get_case_or_404), 대상 종류가 SENIOR 인 사례만(아니면 409 INVALID_CASE_STATE).

import uuid
from typing import List

from fastapi import APIRouter, status

from app.core.deps import CurrentUser, DbSession
from app.core.responses import DataResponse
from app.schemas.senior import (
    HealthMeasurementCreateRequest,
    HealthMeasurementResponse,
    HealthMeasurementUpdateRequest,
    HealthTrendResponse,
    SeniorBriefResponse,
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
