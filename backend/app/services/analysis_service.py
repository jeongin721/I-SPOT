# AI 연동 및 결과 저장.
#
# 상태 흐름:
#   STT_CONFIRMED → AI_PROCESSING → AI_REVIEW_REQUIRED → APPROVED
#
# AI 담당의 Structured JSON Contract 를 변형하지 않고 그대로 저장한다.
# Backend 는 학대 여부/위험도를 판단하지 않는다.

import math
import time
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.adapters.ai_adapter import AI_TIMEOUT_MESSAGE, AIError, accepts_keyword, get_ai_adapter
from app.core.concurrency import OperationTimeout, run_with_timeout
from app.core.config import settings
from app.core.database import SessionLocal
from app.core.enums import AnalysisStatus, AuditAction, ReviewStatus, SessionStatus
from app.core.errors import ErrorCode, not_found
from app.core.logging import get_logger
from app.models.analysis import AIAnalysis
from app.models.session import ConsultationSession
from app.models.summary import ConsultationSummary
from app.models.user import User
from app.schemas.analysis import AnalysisEnvelope, AnalysisResponse
from app.schemas.common import SessionErrorInfo
from app.schemas.contracts import SummaryEvidenceItem
from app.services import audit_service, session_service, transcript_service

logger = get_logger(__name__)

# 어댑터 준비 단계(prepare: 모듈 import · 모델 로드)에 주는 최대 시간. AI_TIMEOUT_SECONDS 와 따로 잰다.
#
# 시간은 작업 하나 전체로 맞춘다(_job_deadline). 처리 중 멈춤 판정(session_service.expire_stale_processing)은
# 요청 시각 + AI_TIMEOUT_SECONDS + STALE_GRACE_SECONDS 에 작업이 사라진 것으로 보고 실패로 마감한다.
# 작업은 요청 시각 + PREPARE_TIMEOUT_SECONDS + AI_TIMEOUT_SECONDS 안에 끝나도록 준비 · 분석 제한을 남은 시간만큼
# 줄인다. 작업 시작이 늦었거나(대기) 준비가 길었으면 그만큼 분석 제한이 짧아진다. 그래서 준비 제한을 여유
# 시간보다 짧게 두면 살아 있는 작업은 멈춤 판정보다 (여유 - 준비 제한) = 15초 먼저 끝난다.
# 그래도 늦게 끝난 결과(서버 시계 차이 등)는 저장하지 않는다(_claim_finish).
PREPARE_TIMEOUT_SECONDS = session_service.STALE_GRACE_SECONDS - 15

PREPARE_TIMEOUT_MESSAGE = "AI 모델을 아직 불러오는 중입니다. 잠시 뒤 다시 시도해 주세요."

# 새 분석 요청이 같은 회차에 PROCESSING 으로 남은 옛 분석을 마감할 때 적는 문구(_close_leftover_analyses).
# 고정 문구다. 발화 · 결과 · 원인 예외 문구는 넣지 않는다.
SUPERSEDED_MESSAGE = "같은 회기에 새 AI 분석을 요청해 이 분석은 중단된 것으로 처리했습니다."


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
    # Polling 중 작업이 사라져 멈춘 상태면 실패로 바꿔 재시도 버튼이 보이게 한다.
    session_service.expire_stale_processing(db, session)

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

    # 작업이 사라져 멈춘 처리 중 상태면 먼저 실패로 마감해 재시도를 허용한다.
    session_service.expire_stale_processing(db, session)

    transcript = transcript_service.require_confirmed_transcript(db, session.id)

    # 동시에 들어온 중복 요청은 여기서 한 건만 통과한다.
    session_service.claim_status(db, session, SessionStatus.AI_PROCESSING)

    # 회차가 옛 분석을 마감하지 않은 채 처리 중에서 벗어났다 돌아왔으면 그 분석을 먼저 마감한다.
    # 새 행보다 먼저 해야 처리 중 회차에 PROCESSING 분석이 둘이 되지 않는다(_claim_finish).
    _close_leftover_analyses(db, session, current_user)

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


def _close_leftover_analyses(
    db: Session,
    session: ConsultationSession,
    current_user: User,
) -> None:
    """이 회차에 아직 PROCESSING 으로 남은 분석을 고정 문구 AI_FAILED 로 마감한다. commit 은 호출 측이 한다.

    보통은 하나도 없다. 처리 중에서 나가는 길(저장 · 실패 · 멈춤 판정)은 모두 그 분석을 마감하고, 이미 처리 중인
    회차에 들어온 요청은 claim_status 가 409 로 거절해 여기까지 오지 않는다. 다만 읽어 둔 회차 상태로 전이하는
    요청이 그 사이 커밋된 AI_PROCESSING 을 덮으면(예: 전사 수정 transcript_service.update_transcript 의 기존 경합)
    분석이 PROCESSING 인 채 회차만 처리 중에서 벗어난다. 그 회차를 다시 확정해 분석을 요청하면 옛 작업과 새 작업이
    함께 PROCESSING 이 되고, 옛 작업이 먼저 끝나면 옛 전사 판 결과로 회차를 마감해 새 작업이 영구 PROCESSING 으로
    남는다. 여기서 옛 분석을 마감해 두면 옛 작업의 늦은 결과 · 실패는 _claim_finish 가 버린다.

    claim_status 가 회차 행을 먼저 바꾼 뒤에 부른다. _claim_finish · 멈춤 판정과 같은 순서(회차 → 분석)라
    PostgreSQL 에서 서로 행 잠금을 기다리며 막히지 않고, 옛 작업의 마감은 이 요청이 끝날 때까지 기다린다.
    """

    leftover = db.scalars(
        select(AIAnalysis.id).where(
            AIAnalysis.session_id == session.id,
            AIAnalysis.status == AnalysisStatus.PROCESSING,
        )
    ).all()

    now = datetime.now(timezone.utc)

    for analysis_id in leftover:
        closed = db.execute(
            update(AIAnalysis)
            .where(
                AIAnalysis.id == analysis_id,
                AIAnalysis.status == AnalysisStatus.PROCESSING,
            )
            .values(
                status=AnalysisStatus.FAILED,
                error_code=ErrorCode.AI_FAILED.value,
                error_message=SUPERSEDED_MESSAGE,
                completed_at=now,
            )
            .execution_options(synchronize_session=False)
        ).rowcount

        if closed != 1:
            continue

        audit_service.record(
            db,
            action=AuditAction.ANALYSIS_FAILED,
            entity_type="AIAnalysis",
            entity_id=analysis_id,
            actor_id=current_user.id,
            case_id=session.case_id,
            session_id=session.id,
            detail={"error_code": ErrorCode.AI_FAILED.value, "reason": "superseded"},
        )

        logger.warning(
            "새 분석 요청 전에 PROCESSING 으로 남은 AI 분석을 마감했습니다. session_id=%s analysis_id=%s",
            session.id,
            analysis_id,
        )


def process_analysis(session_id: uuid.UUID, analysis_id: uuid.UUID) -> None:
    """
    BackgroundTasks 에서 실행되는 AI 분석.

    어떤 예외가 발생해도 Session 을 AI_REVIEW_REQUIRED 또는 AI_FAILED 로 마감한다.
    다만 그 사이 멈춤 판정이나 새 분석 요청이 이 작업을 실패로 마감했거나 회차가 더는 처리 중이
    아니면 결과 · 실패를 저장하지 않고 버린다(_claim_finish).
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

        if analysis.status != AnalysisStatus.PROCESSING:
            # 작업이 늦게 시작하는 사이 멈춤 판정이나 새 분석 요청(_close_leftover_analyses)이 이 분석을
            # 마감했다. 회차가 처리 중이면 새로 요청한 작업이다.
            logger.warning(
                "이미 마감된 AI 분석이라 시작하지 않습니다. analysis_id=%s status=%s",
                analysis_id,
                analysis.status.value,
            )
            return

        try:
            job_deadline = _job_deadline(session)
            transcript = transcript_service.get_latest_transcript(db, session.id)

            if transcript is None:
                raise AIError("Transcript 가 없습니다.", ErrorCode.AI_FAILED)

            payload = transcript_service.transcript_to_contract(transcript)
            adapter = get_ai_adapter()

            _prepare_adapter(adapter, job_deadline)

            time_limit = _time_limit(job_deadline, settings.AI_TIMEOUT_SECONDS)
            bundle = run_with_timeout(
                lambda: _analyze(adapter, payload, time_limit),
                time_limit,
            )

            _save_analysis_result(db, session=session, analysis=analysis, bundle=bundle)

        except OperationTimeout as error:
            _fail_analysis(db, session, analysis, ErrorCode.AI_TIMEOUT, str(error), error)
        except AIError as error:
            # 어댑터가 알 수 없는 예외를 AI_FAILED 로 감쌀 때는 문구를 버리고
            # 예외 종류 이름만 싣는다(ai_adapter.map_ai_error). 원인은 여기서
            # session_id 와 함께 남긴다 — trace 에는 원인까지 예외 종류 · 호출 위치만
            # 남고 문구는 빠진다(core/logging.install_safe_exception_text). 다른 오류
            # 코드는 문구에 원인이 드러나 있어 trace 를 남기지 않는다.
            if error.error_code == ErrorCode.AI_FAILED and error.__cause__ is not None:
                logger.exception("AI 분석 중 어댑터 오류. session_id=%s", session_id)
            _fail_analysis(db, session, analysis, error.error_code, str(error), error)
        except Exception as error:
            logger.exception("AI 분석 중 예상하지 못한 오류. session_id=%s", session_id)
            _fail_analysis(
                db,
                session,
                analysis,
                ErrorCode.AI_FAILED,
                f"AI 분석 중 오류가 발생했습니다: {type(error).__name__}",
                error,
            )
    finally:
        db.close()


def _job_deadline(session: ConsultationSession) -> float:
    """이 작업이 끝나야 하는 시각(time.monotonic() 기준). 요청 시각 + 준비 제한 + 분석 제한이다.

    요청 시각(ai_started_at)은 요청을 받은 서버가 UTC 로 적은 값이고, 멈춤 판정도 같은 값을 같은 방식으로
    잰다. 작업 안에서는 벽시계가 바뀌어도 흔들리지 않게 시작할 때 한 번만 time.monotonic() 으로 바꾼다.
    요청 시각이 지금보다 뒤면(서버 시계 차이 · 시계를 되돌림) 흐른 시간을 0 으로 본다. 기본 제한보다
    늘리지는 않는다. 서버 시계가 서로 크게 어긋나 이 마감보다 멈춤 판정이 먼저 오면, 늦은 결과는
    _claim_finish 가 버린다.
    """

    elapsed = 0.0
    requested_at = session.ai_started_at

    if requested_at is not None:
        if requested_at.tzinfo is None:
            # SQLite 는 시간대 정보 없이 돌려준다. 저장 값은 UTC 다.
            requested_at = requested_at.replace(tzinfo=timezone.utc)

        elapsed = max(0.0, (datetime.now(timezone.utc) - requested_at).total_seconds())

    budget = PREPARE_TIMEOUT_SECONDS + settings.AI_TIMEOUT_SECONDS

    return time.monotonic() + budget - elapsed


def _time_limit(job_deadline: float, limit: float) -> float:
    """limit 과 작업 마감까지 남은 시간 가운데 짧은 쪽. 남은 시간이 없으면 시작하지 않고 AI_TIMEOUT.

    남은 시간은 0.1초 단위로 내린다(시간 초과 문구에 "134.7초" 처럼 나온다).
    """

    left = math.floor((job_deadline - time.monotonic()) * 10) / 10

    if left <= 0:
        raise AIError(AI_TIMEOUT_MESSAGE, ErrorCode.AI_TIMEOUT)

    return min(limit, left)


def _analyze(adapter, payload, time_limit: float):
    """분석 제한 시간을 받는 어댑터(ModelingAIAdapter)에는 줄어든 제한 시간을 넘긴다. 다른 어댑터는 그대로 부른다."""

    if accepts_keyword(adapter.analyze, "time_limit_seconds"):
        return adapter.analyze(payload, time_limit_seconds=time_limit)

    return adapter.analyze(payload)


def _prepare_adapter(adapter, job_deadline: float) -> None:
    """어댑터에 준비 단계가 있으면 분석 제한 시간 밖에서 먼저 부른다(ModelingAIAdapter.prepare).

    모델 로드가 분석 제한 시간을 쓰지 않게 하려는 것이다. 서버 시작 때 미리 불러 두었으면
    바로 끝난다. 아직 불러오는 중이면 그 import 가 끝나기를 기다린다(파이썬 import 잠금).
    PREPARE_TIMEOUT_SECONDS 와 작업 마감까지 남은 시간 가운데 짧은 쪽을 넘기면 이 분석만
    AI_TIMEOUT 으로 끝낸다. 불러오기는 thread 에서 계속되므로 다음 요청은 빨라진다.
    """

    prepare = getattr(adapter, "prepare", None)

    if prepare is None:
        return

    time_limit = _time_limit(job_deadline, PREPARE_TIMEOUT_SECONDS)

    try:
        run_with_timeout(prepare, time_limit)
    except OperationTimeout as error:
        raise AIError(PREPARE_TIMEOUT_MESSAGE, ErrorCode.AI_TIMEOUT) from error


def _claim_finish(
    db: Session,
    session: ConsultationSession,
    analysis: AIAnalysis,
    session_status: SessionStatus,
    analysis_status: AnalysisStatus,
) -> bool:
    """회차가 아직 이 작업을 기다릴 때만 마감 상태로 바꾼다. 바꿨으면 True, 아니면 되돌리고 False.

    회차가 처리 중(AI_PROCESSING)이고 이 분석이 아직 PROCESSING 일 때만이다. 처리 중 회차에서 PROCESSING
    분석은 회차가 기다리는 마지막 요청의 분석 하나뿐이다. 요청은 claim_status 로 한 건만 통과하고, 새 행을
    넣기 전에 같은 회차에 PROCESSING 으로 남은 옛 분석을 모두 마감한다(_close_leftover_analyses). 처리 중에서
    나가는 길(저장 · 실패 · 멈춤 판정)도 그 분석을 마감한다. 그래서 두 조건이 맞으면 회차가 기다리는 작업이
    이 분석이다.

    처리 중이 아닌 회차에는 PROCESSING 분석이 남아 있을 수 있다. 읽어 둔 회차 상태로 전이하는 요청이 그 사이
    커밋된 AI_PROCESSING 을 덮으면(예: 전사 수정 transcript_service.update_transcript 의 기존 경합) 분석을
    마감하지 않은 채 회차만 처리 중에서 벗어난다. 그 작업이 끝나도 회차가 처리 중이 아니라 저장하지 않고,
    분석은 다음 분석 요청이 마감할 때까지 PROCESSING 으로 남는다.

    멈춤 판정이 먼저 실패로 마감했거나 새 요청으로 새 작업이 시작됐으면 저장하지 않는다. 읽어 둔 값으로
    판단하면 그 사이 바뀐 것을 놓치므로 조건부 UPDATE(WHERE 상태 = 처리 중)의 행 수로 판단한다.
    SQLite · PostgreSQL 모두 원자적이다. 멈춤 판정(expire_stale_processing)과 같은 순서(회차 → 분석)로
    바꿔 PostgreSQL 에서 서로 행 잠금을 기다리며 막히지 않게 한다.
    """

    claimed = db.execute(
        update(ConsultationSession)
        .where(
            ConsultationSession.id == session.id,
            ConsultationSession.status == SessionStatus.AI_PROCESSING,
        )
        .values(status=session_status)
        .execution_options(synchronize_session=False)
    ).rowcount

    if claimed == 1:
        claimed = db.execute(
            update(AIAnalysis)
            .where(
                AIAnalysis.id == analysis.id,
                AIAnalysis.session_id == session.id,
                AIAnalysis.status == AnalysisStatus.PROCESSING,
            )
            .values(status=analysis_status)
            .execution_options(synchronize_session=False)
        ).rowcount

    if claimed != 1:
        db.rollback()
        return False

    session.status = session_status
    analysis.status = analysis_status

    return True


def _save_analysis_result(
    db: Session,
    *,
    session: ConsultationSession,
    analysis: AIAnalysis,
    bundle,
) -> None:
    # 버린 경우 rollback 으로 ORM 객체가 만료되므로 id 는 미리 읽어 둔다.
    analysis_id = analysis.id

    if not _claim_finish(
        db, session, analysis, SessionStatus.AI_REVIEW_REQUIRED, AnalysisStatus.COMPLETED
    ):
        # 결과 내용은 남기지 않는다(발화가 섞여 있다).
        logger.warning(
            "이미 마감된 AI 분석의 늦은 결과를 버렸습니다. analysis_id=%s",
            analysis_id,
        )
        return

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
    error: BaseException,
) -> None:
    # rollback 하면 ORM 객체가 만료되므로 로그에 쓸 id 는 미리 읽어 둔다.
    analysis_id = analysis.id

    db.rollback()

    if not _claim_finish(db, session, analysis, SessionStatus.AI_FAILED, AnalysisStatus.FAILED):
        # 실패 문구는 남기지 않는다(원인 예외의 문구가 섞일 수 있다). 예외 종류 이름만 남긴다.
        logger.warning(
            "이미 마감된 AI 분석의 늦은 실패를 버렸습니다. analysis_id=%s type=%s",
            analysis_id,
            type(error).__name__,
        )
        return

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
