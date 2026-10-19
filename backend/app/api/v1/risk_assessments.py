# /sessions/{session_id}/risk-assessments — 상담원 위험도 판단(유형별 상/중/하)

import uuid
from typing import List

from fastapi import APIRouter

from app.core.deps import CurrentUser, DbSession
from app.core.enums import AbuseType
from app.core.responses import DataResponse
from app.schemas.risk_assessment import RiskAssessmentResponse, RiskAssessmentSaveRequest
from app.services import risk_assessment_service
from app.services.access import get_session_or_404

router = APIRouter(prefix="/sessions", tags=["risk-assessments"])


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
