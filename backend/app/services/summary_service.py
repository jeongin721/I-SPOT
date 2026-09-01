# 상담사 수정 / 승인 Flow.
#
# docs/05_RULES.md §2:
#   AI 생성 → 상담사 확인 → 수정/제외 → 승인 → 저장
#
# 승인 주체는 항상 상담사이며, Backend 는 AI 결과를 자동 승인하지 않는다.

import uuid
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.enums import AuditAction, ReviewStatus, SessionStatus
from app.core.errors import ErrorCode, conflict, not_found
from app.core.state_machine import assert_status_in, assert_transition
from app.models.session import ConsultationSession
from app.models.summary import ConsultationSummary
from app.models.user import User
from app.schemas.contracts import SummaryEvidenceItem
from app.schemas.summary import SummaryEnvelope, SummaryResponse, SummaryUpdateRequest
from app.services import analysis_service, audit_service, session_service


def get_summary(db: Session, session_id: uuid.UUID) -> Optional[ConsultationSummary]:
    return db.scalar(
        select(ConsultationSummary).where(ConsultationSummary.session_id == session_id)
    )


def require_summary(db: Session, session_id: uuid.UUID) -> ConsultationSummary:
    summary = get_summary(db, session_id)

    if summary is None:
        raise not_found(
            ErrorCode.SUMMARY_NOT_FOUND,
            "상담 요약이 아직 생성되지 않았습니다.",
        )

    return summary


def build_envelope(db: Session, session: ConsultationSession) -> SummaryEnvelope:
    summary = get_summary(db, session.id)
    evidence: List[SummaryEvidenceItem] = []

    analysis = analysis_service.get_latest_analysis(db, session.id)

    if analysis and analysis.summary_evidence:
        evidence = [
            SummaryEvidenceItem.model_validate(item) for item in analysis.summary_evidence
        ]

    return SummaryEnvelope(
        session_id=session.id,
        session_status=session.status,
        summary=SummaryResponse.model_validate(summary) if summary else None,
        summary_evidence=evidence,
        error=session_service.build_error_info(session),
    )


def update_summary(
    db: Session,
    session: ConsultationSession,
    current_user: User,
    payload: SummaryUpdateRequest,
) -> ConsultationSummary:
    summary = require_summary(db, session.id)

    if summary.status == ReviewStatus.APPROVED:
        raise conflict(
            ErrorCode.ALREADY_APPROVED,
            "승인이 완료된 요약은 수정할 수 없습니다.",
        )

    assert_status_in(session.status, {SessionStatus.AI_REVIEW_REQUIRED})

    data = payload.model_dump(exclude_unset=True)
    changed_fields = []

    if "overview" in data and data["overview"] is not None:
        summary.overview = data["overview"]
        changed_fields.append("overview")

    if "key_points" in data and data["key_points"] is not None:
        summary.key_points = list(data["key_points"])
        changed_fields.append("key_points")

    if "counselor_note" in data and data["counselor_note"] is not None:
        summary.counselor_note = data["counselor_note"]
        changed_fields.append("counselor_note")

    if changed_fields:
        summary.is_edited = True

        audit_service.record(
            db,
            action=AuditAction.SUMMARY_UPDATED,
            entity_type="ConsultationSummary",
            entity_id=summary.id,
            actor_id=current_user.id,
            case_id=session.case_id,
            session_id=session.id,
            # 상담 원문은 저장하지 않고 변경 필드/개수만 남긴다.
            detail={
                "changed_fields": changed_fields,
                "key_point_count": len(summary.key_points or []),
            },
        )

    db.commit()
    db.refresh(summary)

    return summary


def approve_summary(
    db: Session,
    session: ConsultationSession,
    current_user: User,
) -> ConsultationSummary:
    summary = require_summary(db, session.id)

    if summary.status == ReviewStatus.APPROVED:
        raise conflict(ErrorCode.ALREADY_APPROVED, "이미 승인된 요약입니다.")

    assert_transition(session.status, SessionStatus.APPROVED)

    approved_at = datetime.now(timezone.utc)

    summary.status = ReviewStatus.APPROVED
    summary.approved_at = approved_at
    summary.approved_by_id = current_user.id

    session.status = SessionStatus.APPROVED
    session.approved_at = approved_at
    session.approved_by_id = current_user.id
    session.clear_error()

    audit_service.record(
        db,
        action=AuditAction.SUMMARY_APPROVED,
        entity_type="ConsultationSummary",
        entity_id=summary.id,
        actor_id=current_user.id,
        case_id=session.case_id,
        session_id=session.id,
        detail={"is_edited": summary.is_edited},
    )

    db.commit()
    db.refresh(summary)

    return summary
