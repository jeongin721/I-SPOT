# 다음 상담 체크리스트(추가 확인 · 질문 화면) 만들기 · 저장 · 조회. API_CONTRACT.md 19절.
#
# AI 분석이 저장된 직후 같은 백그라운드 작업에서 만든다(analysis_service.process_analysis → generate_after_analysis).
# 상담사가 '다시 만들기'를 누르면 새 행을 더한다(request_generation → process_followup). 조회는 가장 최근 행이다.
#
# rag 에 넘기는 값(followup_adapter.FollowupInput):
#   - 이번 회차 확정 전사본(rag 는 CHILD 발화만 쓴다)
#   - 학대 유형: 최신 AI 분석의 abuse_signals(detected) · severity_ratings(level 있음). 둘 이상이면 multiple, 없으면 None
#   - 같은 사례의 이전 회차(최근 3개): 승인된 요약 · 그 회차의 확인 사항 · 확정 전사본
#   - 아이 앱 응답: 아직 Backend 에 없어 빈 목록
#
# 여기서 하는 일이 실패해도 회차 상태에는 영향을 주지 않는다. 로그에는 식별자와 예외 종류만 남긴다.

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.adapters.followup_adapter import (
    FOLLOWUP_MESSAGES,
    SCHEMA_VERSION,
    FollowupError,
    FollowupInput,
    get_followup_adapter,
    is_enabled,
)
from app.core.concurrency import OperationTimeout, run_with_timeout
from app.core.config import settings
from app.core.database import SessionLocal
from app.core.enums import AbuseType, AnalysisStatus, ReviewStatus, abuse_type_from_label
from app.core.errors import APIError, ErrorCode, conflict
from app.core.logging import get_logger
from app.models.analysis import AIAnalysis
from app.models.followup_suggestion import FollowupSuggestion
from app.models.session import ConsultationSession
from app.models.transcript import Transcript
from app.schemas.common import SessionErrorInfo
from app.schemas.followup import FollowupSuggestionResponse
from app.services import transcript_service

logger = get_logger(__name__)

PREVIOUS_SESSION_LIMIT = 3

# 처리 중 행이 제한 시간 + 이 값보다 오래되면 작업이 사라진 것으로 보고 실패로 마감한다(서버 재시작 등).
STALE_GRACE_SECONDS = 60

DISABLED_MESSAGE = "다음 상담 체크리스트 만들기가 꺼져 있습니다(FOLLOWUP_PROVIDER=off)."

RAG_ABUSE_TYPES: Dict[AbuseType, str] = {
    AbuseType.PHYSICAL: "physical",
    AbuseType.EMOTIONAL: "emotional",
    AbuseType.SEXUAL: "sexual",
    AbuseType.NEGLECT: "neglect",
}


# =========================================================
# 조회
# =========================================================

def _latest_analysis(db: Session, session_id: uuid.UUID) -> Optional[AIAnalysis]:
    # analysis_service.get_latest_analysis 와 같다. analysis_service 가 이 모듈을 부르므로 순환 import 를 피해 따로 둔다.
    return db.scalar(
        select(AIAnalysis)
        .where(AIAnalysis.session_id == session_id)
        .order_by(AIAnalysis.created_at.desc(), AIAnalysis.id.desc())
        .limit(1)
    )


def latest_for_session(db: Session, session_id: uuid.UUID) -> Optional[FollowupSuggestion]:
    return db.scalar(
        select(FollowupSuggestion)
        .where(FollowupSuggestion.session_id == session_id)
        .order_by(FollowupSuggestion.created_at.desc(), FollowupSuggestion.id.desc())
        .limit(1)
    )


def _is_stale(row: FollowupSuggestion) -> bool:
    created = row.created_at

    if created.tzinfo is None:  # SQLite 는 시간대 없이 돌려준다.
        created = created.replace(tzinfo=timezone.utc)

    limit = timedelta(seconds=settings.FOLLOWUP_TIMEOUT_SECONDS + STALE_GRACE_SECONDS)

    return datetime.now(timezone.utc) - created > limit


def expire_stale(db: Session, row: FollowupSuggestion) -> FollowupSuggestion:
    """작업이 사라져 처리 중으로 남은 행을 AI_TIMEOUT 실패로 마감한다. 늦게 끝난 작업의 결과는 _finish 가 버린다."""

    if row.status != AnalysisStatus.PROCESSING or not _is_stale(row):
        return row

    _finish(db, row.id, AnalysisStatus.FAILED, error=ErrorCode.AI_TIMEOUT)
    db.refresh(row)

    return row


def to_response(row: FollowupSuggestion) -> FollowupSuggestionResponse:
    error = None

    if row.error_code:
        error = SessionErrorInfo(
            code=row.error_code,
            message=row.error_message or FOLLOWUP_MESSAGES[ErrorCode.AI_FAILED],
        )

    return FollowupSuggestionResponse(
        id=row.id,
        session_id=row.session_id,
        analysis_id=row.analysis_id,
        transcript_version=row.transcript_version,
        status=row.status,
        schema_version=row.schema_version,
        provider=row.provider,
        created_at=row.created_at,
        completed_at=row.completed_at,
        result=row.result,
        error=error,
    )


def get_latest_response(
    db: Session, session: ConsultationSession
) -> Optional[FollowupSuggestionResponse]:
    """가장 최근 행. 아직 만들기 전이면 None(화면은 '만들기 전')."""

    row = latest_for_session(db, session.id)

    if row is None:
        return None

    return to_response(expire_stale(db, row))


# =========================================================
# rag 입력 만들기
# =========================================================

def abuse_type_for_rag(result: Any) -> Optional[str]:
    """AI 분석 결과에서 rag 의 학대 유형 값을 정한다. 감지된 유형이 없으면 None(rag 는 질문을 만들지 않는다)."""

    if not isinstance(result, dict):
        return None

    found = set()

    for signal in result.get("abuse_signals") or []:
        if isinstance(signal, dict) and signal.get("detected") is True:
            abuse_type = abuse_type_from_label(signal.get("abuse_type") or signal.get("major_type"))
            if abuse_type is not None:
                found.add(abuse_type)

    for rating in result.get("severity_ratings") or []:
        if not isinstance(rating, dict):
            continue
        level = rating.get("level")
        # level 이 없으면(정보 부족) 그 유형이 보였다고 보지 않는다. bool 은 int 의 하위 형이라 따로 막는다.
        if isinstance(level, int) and not isinstance(level, bool) and level >= 1:
            abuse_type = abuse_type_from_label(rating.get("major_type"))
            if abuse_type is not None:
                found.add(abuse_type)

    if not found:
        return None

    if len(found) > 1:
        return "multiple"

    return RAG_ABUSE_TYPES[found.pop()]


def _summary_text(summary: Any) -> str:
    """승인된 회차 요약을 한 덩어리 글로. 사정 관점 4칸도 붙인다(빈 칸은 뺀다)."""

    if summary is None or summary.status != ReviewStatus.APPROVED:
        return ""

    parts = [summary.overview or ""]
    parts.extend(str(point) for point in summary.key_points or [])

    assessment = summary.assessment if isinstance(summary.assessment, dict) else {}
    names = {
        "safety_changes": "안전 관련 변화",
        "strengths_resources": "강점과 자원",
        "safety_risks": "위험요인",
        "desired_changes": "원하는 변화",
    }
    for key, name in names.items():
        value = assessment.get(key)
        text = value.get("text") if isinstance(value, dict) else None
        if isinstance(text, str) and text.strip():
            parts.append(f"{name}: {text.strip()}")

    return " ".join(part.strip() for part in parts if part and part.strip())


def _check_items_of(db: Session, session_id: uuid.UUID) -> List[Dict[str, Any]]:
    """그 회차의 '다음 상담 전 확인할 사항'. 체크리스트가 있으면 그것을, 없으면 AI 분석의 확인 메모를 쓴다.

    확인했는지(체크) 저장은 아직 없어 모두 open 으로 넘긴다 — rag 가 이행 여부를 다시 확인할 거리로 본다.
    """

    row = db.scalar(
        select(FollowupSuggestion)
        .where(
            FollowupSuggestion.session_id == session_id,
            FollowupSuggestion.status == AnalysisStatus.COMPLETED,
        )
        .order_by(FollowupSuggestion.created_at.desc(), FollowupSuggestion.id.desc())
        .limit(1)
    )
    texts: List[str] = []

    if row is not None and isinstance(row.result, dict):
        texts = [
            str(item.get("item")) for item in row.result.get("check_items") or []
            if isinstance(item, dict) and item.get("item")
        ]

    if not texts:
        analysis = _latest_analysis(db, session_id)
        result = analysis.result if analysis is not None and isinstance(analysis.result, dict) else {}
        texts = [
            str(point.get("text")) for point in result.get("followup_check_points") or []
            if isinstance(point, dict) and point.get("text")
        ]

    return [{"item": text, "status": "open"} for text in texts]


def previous_sessions_input(db: Session, session: ConsultationSession) -> List[Dict[str, Any]]:
    """같은 사례에서 이 회차보다 앞선 최근 회차들. 넘길 내용이 하나도 없는 회차는 뺀다."""

    previous = db.scalars(
        select(ConsultationSession)
        .where(
            ConsultationSession.case_id == session.case_id,
            ConsultationSession.session_number < session.session_number,
        )
        .order_by(ConsultationSession.session_number.desc())
        .limit(PREVIOUS_SESSION_LIMIT)
    ).all()

    entries: List[Dict[str, Any]] = []

    for item in previous:
        transcript = transcript_service.get_latest_transcript(db, item.id)
        entry = {
            "session_no": item.session_number,
            "session_id": str(item.id),
            "summary": _summary_text(item.summary),
            "safety_plan": "",
            "check_items": _check_items_of(db, item.id),
            "transcript": (
                transcript_service.transcript_to_contract(transcript)
                if transcript is not None and transcript.is_confirmed
                else None
            ),
        }

        if entry["summary"] or entry["check_items"] or entry["transcript"]:
            entries.append(entry)

    return entries


def build_input(
    db: Session,
    session: ConsultationSession,
    analysis: Optional[AIAnalysis],
    transcript: Transcript,
) -> FollowupInput:
    return FollowupInput(
        transcript=transcript_service.transcript_to_contract(transcript),
        abuse_type=abuse_type_for_rag(analysis.result if analysis is not None else None),
        session_no=session.session_number,
        session_id=str(session.id),
        previous_sessions=previous_sessions_input(db, session),
        child_app_responses=[],
    )


# =========================================================
# 만들기
# =========================================================

def _new_row(session: ConsultationSession, analysis: AIAnalysis) -> FollowupSuggestion:
    return FollowupSuggestion(
        session_id=session.id,
        analysis_id=analysis.id,
        transcript_id=analysis.transcript_id,
        transcript_version=analysis.transcript_version,
        status=AnalysisStatus.PROCESSING,
        schema_version=SCHEMA_VERSION,
        provider=get_followup_adapter().name,
    )


def request_generation(
    db: Session, session: ConsultationSession
) -> Tuple[FollowupSuggestion, bool]:
    """상담사가 누른 '다시 만들기'. (행, 새로 만들었는가).

    이미 만드는 중이면 그 행과 False 를 돌려준다 — 라우터는 새 작업을 띄우지 않는다.
    """

    if not is_enabled():
        raise APIError(ErrorCode.FOLLOWUP_DISABLED, DISABLED_MESSAGE, status_code=503)

    analysis = _latest_analysis(db, session.id)

    if analysis is None or analysis.status != AnalysisStatus.COMPLETED:
        raise conflict(
            ErrorCode.INVALID_SESSION_STATE,
            "AI 분석이 끝난 회차에서만 다음 상담 체크리스트를 만들 수 있습니다.",
        )

    latest = latest_for_session(db, session.id)

    if latest is not None and expire_stale(db, latest).status == AnalysisStatus.PROCESSING:
        return latest, False

    row = _new_row(session, analysis)
    db.add(row)
    db.commit()
    db.refresh(row)

    return row, True


def generate_after_analysis(session_id: uuid.UUID, analysis_id: uuid.UUID) -> None:
    """AI 분석 결과를 저장한 직후(process_analysis 안) 부른다. 어떤 예외도 밖으로 내지 않는다."""

    if not is_enabled():
        return

    db = SessionLocal()

    try:
        session = db.get(ConsultationSession, session_id)
        analysis = db.get(AIAnalysis, analysis_id)

        if session is None or analysis is None or analysis.status != AnalysisStatus.COMPLETED:
            return

        row = _new_row(session, analysis)
        db.add(row)
        db.commit()
        row_id = row.id
    except Exception as error:
        db.rollback()
        logger.warning(
            "다음 상담 체크리스트 행을 만들지 못했습니다. session_id=%s type=%s",
            session_id,
            type(error).__name__,
        )
        return
    finally:
        db.close()

    process_followup(row_id)


def process_followup(followup_id: uuid.UUID) -> None:
    """BackgroundTasks 에서 실행한다. 별도 DB Session 을 쓰고 어떤 예외도 밖으로 내지 않는다."""

    db = SessionLocal()

    try:
        row = db.get(FollowupSuggestion, followup_id)

        if row is None or row.status != AnalysisStatus.PROCESSING:
            return

        session_id = row.session_id

        try:
            session = db.get(ConsultationSession, row.session_id)
            analysis = db.get(AIAnalysis, row.analysis_id) if row.analysis_id else None
            transcript = (
                db.get(Transcript, row.transcript_id)
                if row.transcript_id
                else transcript_service.get_latest_transcript(db, row.session_id)
            )

            if session is None or transcript is None:
                raise FollowupError(ErrorCode.AI_FAILED, "MissingInput")

            payload = build_input(db, session, analysis, transcript)
            adapter = get_followup_adapter()
            result = run_with_timeout(
                lambda: adapter.build(payload),
                settings.FOLLOWUP_TIMEOUT_SECONDS,
            )

            if not isinstance(result, dict):
                raise FollowupError(ErrorCode.AI_INVALID_OUTPUT, type(result).__name__)

            result = {**result, "abuse_type": payload.abuse_type}
            _finish(db, followup_id, AnalysisStatus.COMPLETED, result=result)

            logger.info(
                "다음 상담 체크리스트 저장 session_id=%s check_items=%s questions=%s",
                session_id,
                len(result.get("check_items") or []),
                len(result.get("items") or []),
            )
        except OperationTimeout:
            logger.warning("다음 상담 체크리스트가 제한 시간을 넘겼습니다. session_id=%s", session_id)
            _finish(db, followup_id, AnalysisStatus.FAILED, error=ErrorCode.AI_TIMEOUT)
        except FollowupError as error:
            logger.warning(
                "다음 상담 체크리스트 실패 session_id=%s code=%s cause=%s",
                session_id,
                error.code.value,
                error.cause_name,
            )
            _finish(db, followup_id, AnalysisStatus.FAILED, error=error.code)
        except Exception as error:
            logger.warning(
                "다음 상담 체크리스트 중 예상하지 못한 오류 session_id=%s type=%s",
                session_id,
                type(error).__name__,
            )
            db.rollback()
            _finish(db, followup_id, AnalysisStatus.FAILED, error=ErrorCode.AI_FAILED)
    except Exception as error:
        db.rollback()
        logger.warning(
            "다음 상담 체크리스트를 저장하지 못했습니다. followup_id=%s type=%s",
            followup_id,
            type(error).__name__,
        )
    finally:
        db.close()


def _finish(
    db: Session,
    followup_id: uuid.UUID,
    status: AnalysisStatus,
    *,
    result: Optional[Dict[str, Any]] = None,
    error: Optional[ErrorCode] = None,
) -> bool:
    """처리 중인 행만 마감한다. 그 사이 멈춤 판정이 실패로 마감했으면 늦은 결과를 버리고 False."""

    values: Dict[str, Any] = {
        "status": status,
        "completed_at": datetime.now(timezone.utc),
        "result": result,
        "error_code": error.value if error else None,
        "error_message": FOLLOWUP_MESSAGES[error] if error else None,
    }

    finished = db.execute(
        update(FollowupSuggestion)
        .where(
            FollowupSuggestion.id == followup_id,
            FollowupSuggestion.status == AnalysisStatus.PROCESSING,
        )
        .values(**values)
        .execution_options(synchronize_session=False)
    ).rowcount

    db.commit()

    return finished == 1
