# 상담원 위험도 판단 조회 · 저장.
#
# 회차 · 학대 유형마다 상담원 판단(상/중/하) 하나를 둔다. 판단할 때 그 회차 AI 분석
# 결과의 같은 유형 심각도(1~5)를 ai_level 로 함께 남긴다.
# AI 단계와 상/중/하를 대응시키거나 사례 단위 위험도를 계산하지 않는다(팀 결정 전).

import uuid
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.enums import (
    AbuseType,
    AnalysisStatus,
    AuditAction,
    SessionStatus,
    abuse_type_from_label,
)
from app.core.errors import ErrorCode, conflict
from app.core.state_machine import assert_status_in
from app.models.risk_assessment import SessionRiskAssessment
from app.models.session import ConsultationSession
from app.models.user import User
from app.schemas.risk_assessment import RiskAssessmentSaveRequest
from app.services import analysis_service, audit_service

# 판단을 받는 회차 상태. 원문을 확정한 뒤부터 받는다.
# - AI 분석 중(AI_PROCESSING)은 받지 않는다. 판단 당시 AI 제안이 무엇이었는지 흐려진다.
# - AI 실패(AI_FAILED)에도 받는다. AI 제안은 참고일 뿐 판단은 상담원이 한다(ai_level 은 null).
# - 승인(APPROVED) 뒤에도 받는다. 이 기능 전에 승인한 회차에도 판단을 남길 수 있어야 한다.
ASSESSABLE_STATUSES = {
    SessionStatus.STT_CONFIRMED,
    SessionStatus.AI_REVIEW_REQUIRED,
    SessionStatus.AI_FAILED,
    SessionStatus.APPROVED,
}

_TYPE_ORDER = {abuse_type: index for index, abuse_type in enumerate(AbuseType)}


def list_assessments(db: Session, session_id: uuid.UUID) -> List[SessionRiskAssessment]:
    """판단한 유형만 준다. 순서는 AbuseType 정의 순서(신체 · 정서 · 성 · 방임)."""

    assessments = db.scalars(
        select(SessionRiskAssessment).where(SessionRiskAssessment.session_id == session_id)
    )

    return sorted(assessments, key=lambda item: _TYPE_ORDER[item.abuse_type])


def ai_level_for(db: Session, session_id: uuid.UUID, abuse_type: AbuseType) -> Optional[int]:
    """
    그 회차 최신 AI 분석 결과의 severity_ratings 에서 같은 유형의 level(1~5)을 읽는다.

    최신 분석이 완료되지 않았거나(처리 중 · 실패), 그 유형 항목이 없거나,
    level 이 1~5 정수가 아니면(정보 부족 null 포함) None 이다.
    같은 유형 항목이 여럿이면 처음 것을 쓴다.
    """

    analysis = analysis_service.get_latest_analysis(db, session_id)

    if analysis is None or analysis.status != AnalysisStatus.COMPLETED:
        return None

    result = analysis.result if isinstance(analysis.result, dict) else {}
    ratings = result.get("severity_ratings")

    if not isinstance(ratings, list):
        return None

    for rating in ratings:
        if not isinstance(rating, dict):
            continue

        if abuse_type_from_label(rating.get("major_type")) != abuse_type:
            continue

        level = rating.get("level")

        # bool 은 int 의 하위 형이라 따로 막는다(True 가 1 로 읽히지 않게).
        if isinstance(level, int) and not isinstance(level, bool) and 1 <= level <= 5:
            return level

        return None

    return None


def save_assessment(
    db: Session,
    session: ConsultationSession,
    abuse_type: AbuseType,
    current_user: User,
    payload: RiskAssessmentSaveRequest,
) -> SessionRiskAssessment:
    """판단이 없으면 만들고 있으면 고친다. 고칠 때도 ai_level 은 지금 AI 제안으로 다시 읽는다."""

    assert_status_in(session.status, ASSESSABLE_STATUSES)

    now = datetime.now(timezone.utc)
    ai_level = ai_level_for(db, session.id, abuse_type)

    assessment = db.scalar(
        select(SessionRiskAssessment).where(
            SessionRiskAssessment.session_id == session.id,
            SessionRiskAssessment.abuse_type == abuse_type,
        )
    )

    # 감사 기록에는 유형과 단계 값만 남긴다. 판단 이유(reason) 원문은 넣지 않는다.
    detail = {
        "abuse_type": abuse_type.value,
        "counselor_level": payload.counselor_level.value,
        "ai_level": ai_level,
    }

    if assessment is None:
        assessment = SessionRiskAssessment(
            session_id=session.id,
            abuse_type=abuse_type,
            counselor_level=payload.counselor_level,
            reason=payload.reason,
            ai_level=ai_level,
            assessed_by_id=current_user.id,
            assessed_at=now,
        )
        db.add(assessment)

        try:
            db.flush()
        except IntegrityError as error:
            # 같은 유형을 동시에 처음 저장한 다른 요청이 먼저 커밋했다.
            # (session_id, abuse_type) 유니크 제약에 걸린 것을 500 대신 409 로 알려준다.
            db.rollback()

            raise conflict(
                ErrorCode.DUPLICATE_RESOURCE,
                "다른 요청이 먼저 이 유형의 판단을 저장했습니다. 새로고침 후 다시 저장해 주세요.",
            ) from error

        action = AuditAction.RISK_ASSESSMENT_CREATED
    else:
        detail["previous_level"] = assessment.counselor_level.value

        assessment.counselor_level = payload.counselor_level
        assessment.reason = payload.reason
        assessment.ai_level = ai_level
        assessment.assessed_by_id = current_user.id
        assessment.assessed_at = now

        action = AuditAction.RISK_ASSESSMENT_UPDATED

    audit_service.record(
        db,
        action=action,
        entity_type="SessionRiskAssessment",
        entity_id=assessment.id,
        actor_id=current_user.id,
        case_id=session.case_id,
        session_id=session.id,
        detail=detail,
    )

    db.commit()
    db.refresh(assessment)

    return assessment
