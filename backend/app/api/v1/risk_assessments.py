# /sessions/{session_id}/risk-assessment — 상담원 위험도 판단(회차 전체 상/중/하 하나, 11.1절)
# /sessions/{session_id}/risk-assessments — 상담원 위험도 판단(유형별 상/중/하, 11.2절)

import uuid
from typing import List, Optional

from fastapi import APIRouter

from app.core.deps import CurrentUser, DbSession
from app.core.enums import AbuseType
from app.core.responses import DataResponse
from app.schemas.risk_assessment import (
    OverallRiskAssessmentResponse,
    RiskAssessmentResponse,
    RiskAssessmentSaveRequest,
)
from app.services import risk_assessment_service
from app.services.access import get_session_or_404

router = APIRouter(prefix="/sessions", tags=["risk-assessments"])


# =========================================================
# 회차 전체 판단 (11.1절)
# =========================================================

@router.get(
    "/{session_id}/risk-assessment",
    response_model=DataResponse[Optional[OverallRiskAssessmentResponse]],
    summary="회차 전체 상담원 위험도 판단 조회",
)
def get_overall_risk_assessment(
    session_id: uuid.UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> DataResponse[Optional[OverallRiskAssessmentResponse]]:
    """그 회차의 판단 하나를 준다. 아직 판단 전이면 `data: null`(정상 상태라 404 가 아니다). 회차 상태와 상관없이 조회된다."""

    session = get_session_or_404(db, session_id, current_user)
    assessment = risk_assessment_service.get_overall_assessment(db, session.id)

    if assessment is None:
        return DataResponse(data=None)

    return DataResponse(data=OverallRiskAssessmentResponse.model_validate(assessment))


@router.put(
    "/{session_id}/risk-assessment",
    response_model=DataResponse[OverallRiskAssessmentResponse],
    summary="회차 전체 상담원 위험도 판단 저장 · 수정",
)
def save_overall_risk_assessment(
    session_id: uuid.UUID,
    payload: RiskAssessmentSaveRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> DataResponse[OverallRiskAssessmentResponse]:
    session = get_session_or_404(db, session_id, current_user)
    assessment = risk_assessment_service.save_overall_assessment(
        db, session, current_user, payload
    )

    return DataResponse(data=OverallRiskAssessmentResponse.model_validate(assessment))


# =========================================================
# 유형별 판단 (11.2절)
# =========================================================

@router.get(
    "/{session_id}/risk-assessments",
    response_model=DataResponse[List[RiskAssessmentResponse]],
)
def list_risk_assessments(
    session_id: uuid.UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> DataResponse[List[RiskAssessmentResponse]]:
    session = get_session_or_404(db, session_id, current_user)
    assessments = risk_assessment_service.list_assessments(db, session.id)

    return DataResponse(
        data=[RiskAssessmentResponse.model_validate(item) for item in assessments]
    )


@router.put(
    "/{session_id}/risk-assessments/{abuse_type}",
    response_model=DataResponse[RiskAssessmentResponse],
)
def save_risk_assessment(
    session_id: uuid.UUID,
    abuse_type: AbuseType,
    payload: RiskAssessmentSaveRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> DataResponse[RiskAssessmentResponse]:
    session = get_session_or_404(db, session_id, current_user)
    assessment = risk_assessment_service.save_assessment(
        db, session, abuse_type, current_user, payload
    )

    return DataResponse(data=RiskAssessmentResponse.model_validate(assessment))
