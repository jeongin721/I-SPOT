# AI 연동 및 결과 저장.
#
# 상태 흐름:
#   STT_CONFIRMED → AI_PROCESSING → AI_REVIEW_REQUIRED → APPROVED
#
# AI 담당의 Structured JSON Contract 를 변형하지 않고 그대로 저장한다.
# Backend 는 학대 여부/위험도를 판단하지 않는다.
#
# 두 번 저장(2026-11-04, I-SPOT_DOCS/docs/PROPOSAL_analysis_signals_first.md §3):
#   모듈이 학대 신호 확인(2단계) 값을 먼저 넘기면(on_signals_ready) 그때 회차를 AI_REVIEW_REQUIRED 로 넘기고
#   drafts_status = PENDING 으로 저장한다(_SignalsSave). 모듈이 돌아오면 3 · 4단계 칸만 채워 DONE 으로 바꾼다(_save_drafts).
#   콜백이 불리지 않으면(예전 판 모듈 · mock · 콜백 전 실패 · 첫 저장 실패) 지금처럼 끝에서 한 번에 저장한다.

import math
import time
import uuid
from datetime import datetime, timezone
from typing import Callable, List, Optional

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.adapters.ai_adapter import (
    AI_TIMEOUT_MESSAGE,
    AIAnalysisBundle,
    AIError,
    accepts_keyword,
    get_ai_adapter,
)
from app.core.concurrency import OperationTimeout, run_with_timeout
from app.core.config import settings
from app.core.database import SessionLocal
from app.core.enums import AnalysisStatus, AuditAction, DraftsStatus, ReviewStatus, SessionStatus
from app.core.errors import ErrorCode, not_found
from app.core.logging import get_logger
from app.models.analysis import AIAnalysis
from app.models.session import ConsultationSession
from app.models.summary import ConsultationSummary
from app.models.user import User
from app.schemas.analysis import AnalysisEnvelope, AnalysisResponse
from app.schemas.common import SessionErrorInfo
from app.schemas.contracts import AIAnalysisResult, SummaryEvidenceItem
from app.services import (
    audit_service,
    case_context_service,
    followup_checklist_service,
    personal_info_service,
    session_service,
    transcript_service,
)

logger = get_logger(__name__)

# 어댑터 준비 단계(prepare: 모듈 import · 모델 로드)에 주는 최대 시간. AI_TIMEOUT_SECONDS 와 따로 잰다.
#
# 시간은 작업 하나 전체로 맞춘다(_job_deadline). 처리 중 멈춤 판정(session_service.expire_stale_processing)은
# 요청 시각 + AI_TIMEOUT_SECONDS + STALE_GRACE_SECONDS 에 작업이 사라진 것으로 보고 실패로 마감한다.
# 작업은 요청 시각 + PREPARE_TIMEOUT_SECONDS + AI_TIMEOUT_SECONDS 안에 끝나도록 준비 · 분석 제한을 남은 시간만큼
# 줄인다. 작업 시작이 늦었거나(대기) 준비가 길었으면 그만큼 분석 제한이 짧아진다. 그래서 준비 제한을 여유
# 시간보다 짧게 두면 살아 있는 작업은 멈춤 판정보다 (여유 - 준비 제한) = 15초 먼저 끝난다.
# 그래도 늦게 끝난 결과(서버 시계 차이 등)는 저장하지 않는다(_claim_finish).
# 값은 session_service 에 둔다 — 3 · 4단계 초안 멈춤 판정도 같은 값을 쓰는데 그쪽은 이 모듈을 import 하지 못한다.
PREPARE_TIMEOUT_SECONDS = session_service.AI_PREPARE_TIMEOUT_SECONDS

PREPARE_TIMEOUT_MESSAGE = "AI 모델을 아직 불러오는 중입니다. 잠시 뒤 다시 시도해 주세요."

# 새 분석 요청이 같은 회차에 PROCESSING 으로 남은 옛 분석을 마감할 때 적는 문구(_close_leftover_analyses).
# 고정 문구다. 발화 · 결과 · 원인 예외 문구는 넣지 않는다.
SUPERSEDED_MESSAGE = "같은 회기에 새 AI 분석을 요청해 이 분석은 중단된 것으로 처리했습니다."

# 3 · 4단계 초안 실패 문구(drafts_error.message). 저장은 코드만 하고(session_service.fail_pending_drafts) 문구는 여기서 고른다.
DRAFTS_ERROR_MESSAGES = {
    ErrorCode.AI_TIMEOUT.value: (
        "AI 초안(상담 요약 · 확인 메모 · 추가 질문 등)을 제한 시간 안에 만들지 못했습니다. "
        "다시 분석하면 학대 신호 확인부터 다시 만듭니다."
    ),
    ErrorCode.AI_FAILED.value: (
        "AI 초안(상담 요약 · 확인 메모 · 추가 질문 등)을 만들지 못했습니다. "
        "다시 분석하면 학대 신호 확인부터 다시 만듭니다."
    ),
}

# 둘째 저장이 마지막 값으로 바꾸는 칸(제안서 §3-3). 나머지(2단계 칸 · summary.key_points · summary_evidence)는 첫 저장 값 그대로다.
# summary.overview · summary.assessment 도 바꾼다(_merge_drafts).
_DRAFT_FIELDS = ("session_change_notes", "followup_check_points", "followup_questions", "topic_tags", "warnings")


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

    drafts_error = None

    if analysis.drafts_status == DraftsStatus.FAILED:
        code = analysis.drafts_error_code or ErrorCode.AI_FAILED.value
        drafts_error = SessionErrorInfo(
            code=code,
            message=DRAFTS_ERROR_MESSAGES.get(code, DRAFTS_ERROR_MESSAGES[ErrorCode.AI_FAILED.value]),
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
        drafts_status=analysis.drafts_status,
        drafts_error=drafts_error,
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

    # 2단계를 먼저 저장하고 3 · 4단계 초안을 기다리는 동안은 받지 않는다(409 ANALYSIS_DRAFTS_PENDING).
    # 받으면 새 작업이 회차를 처리 중으로 되돌려 2단계를 보던 상담사 화면이 사라지고, 옛 작업의 둘째 저장이 버려진다.
    session_service.assert_drafts_not_pending(db, session)

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

    결과를 저장했으면 끝에서(DB 세션을 닫은 뒤) 같은 작업 안에서 다음 상담 체크리스트를 만든다(19절,
    followup_checklist_service.generate_after_analysis — 꺼져 있으면 아무것도 하지 않고, 예외를 내지 않는다).

    모듈이 2단계 값을 먼저 넘기면(on_signals_ready) 그때 첫 저장을 하고(_SignalsSave), 모듈이 돌아오면 둘째 저장을
    한다(_save_drafts). 첫 저장 뒤의 예외 · 시간 초과는 회차를 그대로 두고 초안만 FAILED 로 마감한다(_fail_analysis).
    다음 상담 체크리스트는 둘째 저장 뒤에 만든다(3 · 4단계 칸이 다 찬 결과로).
    """

    saved = False
    signals = _SignalsSave(session_id, analysis_id)
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
            case_context = _build_case_context(db, session)
            adapter = get_ai_adapter()
            known_identifiers = _known_identifiers(db, session, adapter)

            _prepare_adapter(adapter, job_deadline)

            time_limit = _time_limit(job_deadline, settings.AI_TIMEOUT_SECONDS)
            bundle = run_with_timeout(
                lambda: _analyze(adapter, payload, time_limit, case_context, known_identifiers, signals),
                time_limit,
            )

            # 첫 저장을 했으면 둘째 저장, 아니면(콜백이 안 불림 · 첫 저장 실패 · 버림) 지금처럼 한 번에 저장한다.
            if signals.saved:
                saved = _save_drafts(db, session_id=session_id, analysis_id=analysis_id, bundle=bundle)
            else:
                saved = _save_analysis_result(db, session=session, analysis=analysis, bundle=bundle)

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

    if saved:
        followup_checklist_service.generate_after_analysis(session_id, analysis_id)


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


def _build_case_context(db: Session, session: ConsultationSession) -> Optional[dict]:
    """분석에 넘길 사례 정보(case_context_service). 만들다 실패해도 분석은 사례 정보 없이 계속한다(보조 입력이라서)."""

    try:
        return case_context_service.build_case_context(db, session)
    except Exception:  # noqa: BLE001 — 사례 정보는 보조 입력이라 분석을 멈추지 않는다
        logger.exception("분석에 넘길 사례 정보를 만들지 못했습니다. session_id=%s", session.id)
        # PostgreSQL 은 SQL 오류 뒤 거래가 깨져(InFailedSqlTransaction) 뒤 결과 저장까지 실패한다. 이 앞은 읽기만 해서
        # 되돌려도 잃는 변경이 없다(민규 #122 교차검증 — SQLite 는 재현되지 않음).
        db.rollback()
        return None


def _known_identifiers(db: Session, session: ConsultationSession, adapter) -> Optional[List[str]]:
    """외부 AI 로 보내기 전 가리기에 넘길 그 사례의 등록 이름(personal_info_service.known_identifiers, 메모리에서만).

    받는 어댑터(ModelingAIAdapter)일 때만 복호화한다 — 다른 어댑터에는 넘기지 않는다. 못 읽으면 빈 목록(실명 없이 지금처럼 가림).
    """

    if not accepts_keyword(adapter.analyze, "known_identifiers"):
        return None

    return personal_info_service.known_identifiers(db, session.case_id)


def _analyze(
    adapter,
    payload,
    time_limit: float,
    case_context: Optional[dict] = None,
    known_identifiers: Optional[List[str]] = None,
    on_signals_ready: Optional[Callable[[AIAnalysisBundle], None]] = None,
):
    """받는 어댑터(ModelingAIAdapter)에만 줄어든 제한 시간 · 사례 정보 · 등록 이름 · 2단계 먼저 받기 콜백을 키워드로 넘긴다.
    다른 어댑터는 그대로 부른다."""

    options = {}

    if accepts_keyword(adapter.analyze, "time_limit_seconds"):
        options["time_limit_seconds"] = time_limit

    if case_context is not None and accepts_keyword(adapter.analyze, "case_context"):
        options["case_context"] = case_context

    if known_identifiers is not None and accepts_keyword(adapter.analyze, "known_identifiers"):
        options["known_identifiers"] = known_identifiers

    if on_signals_ready is not None and accepts_keyword(adapter.analyze, "on_signals_ready"):
        options["on_signals_ready"] = on_signals_ready

    return adapter.analyze(payload, **options)


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


class _SignalsSave:
    """모듈에 넘기는 on_signals_ready(어댑터가 검증한 AIAnalysisBundle 을 받는다). 2단계 값으로 첫 저장을 한다.

    run_with_timeout 이 띄운 작업 스레드에서 불리므로 바깥 process_analysis 의 DB 세션을 쓰지 않고 SessionLocal 을 따로 연다.
    어떤 예외도 내보내지 않는다 — 모듈은 콜백 예외를 잡지 않아 새면 분석 전체가 실패한다. 첫 저장이 실패하면 예외 종류만
    남기고, 바깥 스레드가 끝에서 지금처럼 한 번에 저장한다.

    saved 는 첫 저장을 커밋했는지다. 콜백은 모듈이 돌아오기 전에 같은 작업 스레드에서 끝나므로 바깥 스레드가 결과를
    받은 뒤 읽으면 맞는 값이다(시간 초과로 결과를 받지 못한 경로는 saved 를 보지 않고 DB 조건으로 마감한다).
    두 번 불리면 두 번째는 회차가 처리 중이 아니라 버려지고 saved 는 그대로다.
    """

    def __init__(self, session_id: uuid.UUID, analysis_id: uuid.UUID) -> None:
        self.session_id = session_id
        self.analysis_id = analysis_id
        self.saved = False

    def __call__(self, bundle: AIAnalysisBundle) -> None:
        try:
            db = SessionLocal()

            try:
                session = db.get(ConsultationSession, self.session_id)
                analysis = db.get(AIAnalysis, self.analysis_id)

                if session is None or analysis is None:
                    logger.warning(
                        "2단계 먼저 저장할 AI 분석을 찾을 수 없습니다. session_id=%s analysis_id=%s",
                        self.session_id,
                        self.analysis_id,
                    )
                    return

                if _save_analysis_result(db, session=session, analysis=analysis, bundle=bundle, drafts_pending=True):
                    self.saved = True
            finally:
                db.close()
        except Exception as error:  # noqa: BLE001 — 첫 저장이 실패해도 분석은 계속한다(끝에서 한 번에 저장)
            logger.warning(
                "학대 신호 확인 값을 먼저 저장하지 못했습니다. 끝에서 한 번에 저장합니다. analysis_id=%s type=%s",
                self.analysis_id,
                type(error).__name__,
            )


def _save_analysis_result(
    db: Session,
    *,
    session: ConsultationSession,
    analysis: AIAnalysis,
    bundle,
    drafts_pending: bool = False,
) -> bool:
    """결과를 저장했으면 True, 늦은 결과라 버렸으면 False(다음 상담 체크리스트를 만들지 않는다).

    drafts_pending: 2단계를 먼저 저장하는 첫 저장(_SignalsSave). 조건(_claim_finish) · 회차 상태 · 감사 기록은 한 번에 저장할
    때와 같고, 초안을 PENDING 으로 두며 Summary 초안은 만들지 않는다 — 빈 Summary 를 상담사가 먼저 고치면(is_edited) 둘째
    저장이 AI 초안을 넣지 못한다(_sync_summary_draft).
    """

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
        return False

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
    analysis.drafts_status = DraftsStatus.PENDING if drafts_pending else DraftsStatus.DONE
    analysis.drafts_error_code = None

    if not drafts_pending:
        _sync_summary_draft(db, session=session, analysis=analysis, result=bundle.result)

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
        "AI 분석 완료 session_id=%s provider=%s key_points=%s drafts_pending=%s",
        session.id,
        bundle.provider,
        len(bundle.result.summary.key_points),
        drafts_pending,
    )

    return True


def _merge_drafts(first: AIAnalysisResult, last: AIAnalysisResult) -> AIAnalysisResult:
    """첫 저장 결과에 3 · 4단계 칸 · summary.overview · summary.assessment · warnings 만 마지막 값으로 바꾼다(제안서 §3-3).

    2단계 칸(위험 3필드 · 심각도 · 보호요인)과 summary.key_points 는 첫 저장 값 그대로다. 상담사가 첫 저장 뒤 2단계를 보고
    판단을 적기 시작했을 수 있어, 모듈이 다른 값을 돌려줘도 바꾸지 않는다. warnings 는 콜백 때 붙은 경고를 지우려고 마지막 값으로 바꾼다.
    """

    summary = first.summary.model_copy(
        update={"overview": last.summary.overview, "assessment": last.summary.assessment}
    )

    return first.model_copy(
        update={"summary": summary, **{name: getattr(last, name) for name in _DRAFT_FIELDS}}
    )


def _save_drafts(
    db: Session,
    *,
    session_id: uuid.UUID,
    analysis_id: uuid.UUID,
    bundle,
) -> bool:
    """2단계를 먼저 저장한 분석에 3 · 4단계 초안을 채운다(둘째 저장). 채웠으면 True, 버렸으면 되돌리고 False.

    조건은 그 분석 id · drafts PENDING 이다(조건부 UPDATE 의 행 수). 그 사이 멈춤 판정이 초안을 마감했거나 회차가
    지워졌으면 버린다(재분석은 PENDING 동안 받지 않고, 마감된 뒤의 새 분석은 id 가 달라 건드리지 않는다).

    첫 저장은 작업 스레드의 다른 DB 세션이 커밋했으므로 먼저 되돌려(이 세션은 읽기만 했다) 회차 · 분석을 다시 읽는다.
    되돌리면 읽어 둔 객체가 만료돼 지워진 행이면 읽다가 오류가 나므로, id 로 조건을 먼저 확인하고 맞을 때만 읽는다.
    result 는 PENDING 동안 이 작업만 바꾸므로 UPDATE 뒤 읽은 값이 첫 저장 값이다. summary_evidence · provider · model ·
    completed_at · 회차의 ai_completed_at 은 첫 저장 값 그대로 둔다.
    """

    db.rollback()

    claimed = db.execute(
        update(AIAnalysis)
        .where(
            AIAnalysis.id == analysis_id,
            AIAnalysis.drafts_status == DraftsStatus.PENDING,
        )
        .values(drafts_status=DraftsStatus.DONE)
        .execution_options(synchronize_session=False)
    ).rowcount

    if claimed != 1:
        db.rollback()
        logger.warning(
            "AI 초안을 채울 분석이 PENDING 이 아니라 둘째 저장을 하지 않습니다. analysis_id=%s",
            analysis_id,
        )
        return False

    analysis = db.get(AIAnalysis, analysis_id, populate_existing=True)
    session = db.get(ConsultationSession, session_id, populate_existing=True)

    merged = _merge_drafts(AIAnalysisResult.model_validate(analysis.result or {}), bundle.result)

    analysis.result = merged.model_dump()

    _sync_summary_draft(db, session=session, analysis=analysis, result=merged)

    audit_service.record(
        db,
        action=AuditAction.ANALYSIS_DRAFTS_COMPLETED,
        entity_type="AIAnalysis",
        entity_id=analysis_id,
        case_id=session.case_id,
        session_id=session.id,
        detail={
            "warning_count": len(merged.warnings),
            "followup_question_count": len(merged.followup_questions),
            "followup_check_point_count": len(merged.followup_check_points),
        },
    )

    db.commit()

    logger.info("AI 초안 채움 session_id=%s analysis_id=%s", session.id, analysis_id)

    return True


def _sync_summary_draft(
    db: Session,
    *,
    session: ConsultationSession,
    analysis: AIAnalysis,
    result: AIAnalysisResult,
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
                overview=result.summary.overview,
                key_points=list(result.summary.key_points),
                assessment=result.summary.assessment.model_dump(),
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

    summary.overview = result.summary.overview
    summary.key_points = list(result.summary.key_points)
    summary.assessment = result.summary.assessment.model_dump()
    summary.status = ReviewStatus.DRAFT


def _fail_analysis(
    db: Session,
    session: ConsultationSession,
    analysis: AIAnalysis,
    code: ErrorCode,
    message: str,
    error: BaseException,
) -> None:
    """분석 실패 마감. 회차가 이 작업을 기다리면 AI_FAILED, 2단계를 먼저 저장했으면(초안 PENDING) 초안만 FAILED.

    첫 저장 뒤의 실패 · 시간 초과는 회차가 이미 AI_REVIEW_REQUIRED 라 _claim_finish 가 맞지 않는다. 그때 회차와
    2단계 결과는 그대로 두고 초안만 마감한다(session_service.fail_pending_drafts — 오류 코드만 저장, 원인 문구는 버림).
    시간 초과가 작업 스레드의 첫 저장과 겹쳐도 조건부 UPDATE 로 한 쪽만 통과한다 — 이쪽이 먼저면 AI_FAILED 로 끝나고 첫
    저장은 버려지며, 첫 저장이 먼저면 초안 FAILED 다.
    """

    # rollback 하면 ORM 객체가 만료되므로 로그에 쓸 id 는 미리 읽어 둔다.
    analysis_id = analysis.id

    db.rollback()

    if not _claim_finish(db, session, analysis, SessionStatus.AI_FAILED, AnalysisStatus.FAILED):
        if session_service.fail_pending_drafts(db, session, analysis_id, code):
            return

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
