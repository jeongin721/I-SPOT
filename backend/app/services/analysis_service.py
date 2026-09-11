# AI 연동 및 결과 저장.
#
# 상태 흐름:
#   STT_CONFIRMED → AI_PROCESSING → AI_REVIEW_REQUIRED → APPROVED
#
# AI 담당의 Structured JSON Contract 를 변형하지 않고 그대로 저장한다.
# Backend 는 학대 여부/위험도를 판단하지 않는다.

import uuid
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.adapters.ai_adapter import AIError, get_ai_adapter
from app.core.concurrency import OperationTimeout, run_with_timeout
from app.core.config import settings
from app.core.database import SessionLocal
from app.core.enums import AnalysisStatus, AuditAction, ReviewStatus, SessionStatus
from app.core.errors import ErrorCode, not_found
from app.core.logging import get_logger
from app.core.state_machine import assert_transition
from app.models.analysis import AIAnalysis
from app.models.session import ConsultationSession
from app.models.summary import ConsultationSummary
from app.models.user import User
from app.schemas.analysis import AnalysisEnvelope, AnalysisResponse
from app.schemas.common import SessionErrorInfo
from app.schemas.contracts import SummaryEvidenceItem
from app.services import audit_service, session_service, transcript_service

logger = get_logger(__name__)


# =========================================================
# 조회
# =========================================================

def get_latest_analysis(db: Session, session_id: uuid.UUID) -> Optional[AIAnalysis]:
    return db.scalar(
        select(AIAnalysis)
        .where(AIAnalysis.session_id == session_id)
        .order_by(AIAnalysis.created_at.desc(), AIAnalysis.id.desc())
        .limit(1)
    )


def to_analysis_response(analysis: AIAnalysis) -> AnalysisResponse:
    error = None

    if analysis.error_code:
        error = SessionErrorInfo(
            code=analysis.error_code,
            message=analysis.error_message or "AI 분석에 실패했습니다.",
        )

    return AnalysisResponse(
        id=analysis.id,
        session_id=analysis.session_id,
        transcript_id=analysis.transcript_id,
        transcript_version=analysis.transcript_version,
        status=analysis.status,
        schema_version=analysis.schema_version,
        provider=analysis.provider,
        model=analysis.model,
        created_at=analysis.created_at,
        completed_at=analysis.completed_at,
        result=analysis.result,
        summary_evidence=analysis.summary_evidence or [],
        error=error,
    )


def build_envelope(db: Session, session: ConsultationSession) -> AnalysisEnvelope:
    analysis = get_latest_analysis(db, session.id)

    return AnalysisEnvelope(
        session_id=session.id,
        session_status=session.status,
        analysis=to_analysis_response(analysis) if analysis else None,
        error=session_service.build_error_info(session),
    )


# =========================================================
# AI 실행
# =========================================================

def request_analysis(
    db: Session,
    session: ConsultationSession,
    current_user: User,
) -> AIAnalysis:
    """
    AI 분석을 예약한다. 확정된 Transcript 가 없으면 시작하지 않는다.
    """

    transcript = transcript_service.require_confirmed_transcript(db, session.id)

    assert_transition(session.status, SessionStatus.AI_PROCESSING)

    analysis = AIAnalysis(
        session_id=session.id,
        transcript_id=transcript.id,
        transcript_version=transcript.version,
        status=AnalysisStatus.PROCESSING,
    )

    db.add(analysis)

    session.status = SessionStatus.AI_PROCESSING
    session.ai_started_at = datetime.now(timezone.utc)
    session.ai_completed_at = None
    session.clear_error()

    db.flush()

    audit_service.record(
        db,
        action=AuditAction.ANALYSIS_REQUESTED,
        entity_type="AIAnalysis",
        entity_id=analysis.id,
        actor_id=current_user.id,
        case_id=session.case_id,
        session_id=session.id,
        detail={"transcript_version": transcript.version},
    )

    db.commit()
    db.refresh(analysis)

    return analysis


def process_analysis(session_id: uuid.UUID, analysis_id: uuid.UUID) -> None:
    """
    BackgroundTasks 에서 실행되는 AI 분석.

    어떤 예외가 발생해도 Session 을 AI_REVIEW_REQUIRED 또는 AI_FAILED 로 마감한다.
    """

    db = SessionLocal()

    try:
        session = db.scalar(
            select(ConsultationSession).where(ConsultationSession.id == session_id)
        )
        analysis = db.scalar(select(AIAnalysis).where(AIAnalysis.id == analysis_id))

        if session is None or analysis is None:
            logger.warning(
                "AI 분석 대상을 찾을 수 없습니다. session_id=%s analysis_id=%s",
                session_id,
                analysis_id,
            )
            return

        if session.status != SessionStatus.AI_PROCESSING:
            logger.warning(
                "AI 처리 조건이 아닙니다. session_id=%s status=%s",
                session_id,
                session.status.value,
            )
            return

        try:
            transcript = transcript_service.get_latest_transcript(db, session.id)

            if transcript is None:
                raise AIError("Transcript 가 없습니다.", ErrorCode.AI_FAILED)

            payload = transcript_service.transcript_to_contract(transcript)
            adapter = get_ai_adapter()

            bundle = run_with_timeout(
                lambda: adapter.analyze(payload),
                settings.AI_TIMEOUT_SECONDS,
            )

            _save_analysis_result(db, session=session, analysis=analysis, bundle=bundle)

        except OperationTimeout as error:
            _fail_analysis(db, session, analysis, ErrorCode.AI_TIMEOUT, str(error))
        except AIError as error:
            _fail_analysis(db, session, analysis, error.error_code, str(error))
        except Exception as error:
            logger.exception("AI 분석 중 예상하지 못한 오류. session_id=%s", session_id)
            _fail_analysis(
                db,
                session,
                analysis,
                ErrorCode.AI_FAILED,
                f"AI 분석 중 오류가 발생했습니다: {type(error).__name__}",
            )
    finally:
        db.close()


def _save_analysis_result(
    db: Session,
    *,
    session: ConsultationSession,
    analysis: AIAnalysis,
    bundle,
) -> None:
    evidence: List[SummaryEvidenceItem] = list(bundle.summary_evidence or [])

    analysis.status = AnalysisStatus.COMPLETED
    analysis.schema_version = bundle.result.schema_version
    analysis.result = bundle.result.model_dump()
    analysis.summary_evidence = [item.model_dump() for item in evidence]
    analysis.provider = bundle.provider
    analysis.model = bundle.model
    analysis.error_code = None
    analysis.error_message = None
    analysis.completed_at = datetime.now(timezone.utc)

    _sync_summary_draft(db, session=session, analysis=analysis, bundle=bundle)

    session.status = SessionStatus.AI_REVIEW_REQUIRED
    session.ai_completed_at = datetime.now(timezone.utc)
    session.clear_error()

    audit_service.record(
        db,
        action=AuditAction.ANALYSIS_COMPLETED,
        entity_type="AIAnalysis",
        entity_id=analysis.id,
        case_id=session.case_id,
        session_id=session.id,
        detail={
            "provider": bundle.provider,
            "key_point_count": len(bundle.result.summary.key_points),
            "warning_count": len(bundle.result.warnings),
            "evidence_count": len(evidence),
        },
    )

    db.commit()

    logger.info(
        "AI 분석 완료 session_id=%s provider=%s key_points=%s",
        session.id,
        bundle.provider,
        len(bundle.result.summary.key_points),
    )


def _sync_summary_draft(
    db: Session,
    *,
    session: ConsultationSession,
    analysis: AIAnalysis,
    bundle,
) -> None:
    """
    상담사 검수용 Summary 초안을 준비한다.

    상담사가 이미 수정한 내용이 있으면 덮어쓰지 않는다.
    (docs/05_RULES.md §2 Human-in-the-loop / §4 수정 이력 추적)
    """

    summary = db.scalar(
        select(ConsultationSummary).where(ConsultationSummary.session_id == session.id)
    )

    if summary is None:
        db.add(
            ConsultationSummary(
                session_id=session.id,
                analysis_id=analysis.id,
                overview=bundle.result.summary.overview,
                key_points=list(bundle.result.summary.key_points),
                status=ReviewStatus.DRAFT,
                is_edited=False,
            )
        )

        return

    summary.analysis_id = analysis.id

    if summary.is_edited:
        # 상담사 수정 내용을 보존한다. 새 AI 결과는 analysis endpoint 로 확인할 수 있다.
        logger.info(
            "상담사 수정 Summary 를 보존합니다. session_id=%s",
            session.id,
        )

        return

    summary.overview = bundle.result.summary.overview
    summary.key_points = list(bundle.result.summary.key_points)
    summary.status = ReviewStatus.DRAFT


def _fail_analysis(
    db: Session,
    session: ConsultationSession,
    analysis: AIAnalysis,
    code: ErrorCode,
    message: str,
) -> None:
    db.rollback()

    analysis.status = AnalysisStatus.FAILED
    analysis.error_code = code.value
    analysis.error_message = message[:500]
    analysis.completed_at = datetime.now(timezone.utc)

    session.status = SessionStatus.AI_FAILED
    session.ai_completed_at = datetime.now(timezone.utc)
    session.set_error(code.value, message)

    audit_service.record(
        db,
        action=AuditAction.ANALYSIS_FAILED,
        entity_type="AIAnalysis",
        entity_id=analysis.id,
        case_id=session.case_id,
        session_id=session.id,
        detail={"error_code": code.value},
    )

    db.commit()

    logger.warning("AI 분석 실패 session_id=%s code=%s", session.id, code.value)


def require_analysis(db: Session, session_id: uuid.UUID) -> AIAnalysis:
    analysis = get_latest_analysis(db, session_id)

    if analysis is None:
        raise not_found(ErrorCode.ANALYSIS_NOT_FOUND, "AI 분석 결과가 없습니다.")

    return analysis
