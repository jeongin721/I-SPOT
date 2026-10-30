# 다음 상담 체크리스트 만들기 · 저장 · 조회(API_CONTRACT 19절, specs followup-rag-checklist, 2026-10-30).
#
# 회차마다 한 행(session_followup_checklists). 분석이 저장된 직후 같은 백그라운드 작업에서 만들고
# (analysis_service.process_analysis → generate_after_analysis), 상담사가 '만들기 · 다시 만들기' 를 누르면 POST 가 행을
# 차지해 백그라운드로 돌린다(request_generation → process_checklist).
#
# 행 차지(_claim): 읽어 둔 attempt 와 같을 때만 status=PROCESSING · attempt+1 로 바꾸는 조건부 UPDATE 한 번이다.
# SQLite · PostgreSQL 모두 원자적이라 동시에 들어온 POST 둘 중 하나만 작업을 띄운다(#117 교차검증 R5).
# 작업은 차지한 attempt 를 들고 가서, 끝날 때 행이 아직 그 attempt · PROCESSING 일 때만 쓴다(_finish) — 다시 만들기 ·
# 재분석으로 새 작업이 시작됐거나 멈춤 판정으로 마감됐으면 늦은 결과를 버린다.
#
# 동시 실행: 서버 전체 FOLLOWUP_MAX_CONCURRENCY 자리. run_with_timeout 은 thread 를 멈추지 못해 시간을 넘긴 작업이 뒤에서
# 계속 도므로, 자리는 작업 thread 가 실제로 끝날 때 돌려준다(law_guide_service 와 같은 방식, #117 교차검증 R4).
#
# rag 에 넘기는 값(followup_checklist_adapter.FollowupChecklistInput — 닫힌 #117 의 입력과 같다):
#   - 이번 회차 확정 전사본(분석에 쓴 버전, rag 는 CHILD 발화만 쓴다)
#   - 학대 유형: 그 분석의 abuse_signals(detected) · severity_ratings(level 있음). 둘 이상이면 multiple, 없으면 None
#   - 같은 사례의 이전 회차(최근 3개): 승인된 요약 · 그 회차의 확인 사항 · 확정 전사본
#   - 그 분석의 추가 질문 AI 초안(followup_questions) — 공식 근거를 붙일 대상
#
# 여기서 하는 일이 실패해도 회차 · 분석 상태에는 영향을 주지 않는다. 로그에는 식별자와 예외 종류만 남긴다.

import threading
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.adapters.followup_checklist_adapter import (
    FOLLOWUP_MESSAGES,
    FollowupChecklistError,
    FollowupChecklistInput,
    get_followup_checklist_adapter,
    is_enabled,
    map_followup_error,
)
from app.core.concurrency import OperationTimeout, run_with_timeout
from app.core.config import settings
from app.core.database import SessionLocal
from app.core.enums import AbuseType, AnalysisStatus, AuditAction, ReviewStatus, abuse_type_from_label
from app.core.errors import APIError, ErrorCode
from app.core.logging import get_logger
from app.models.analysis import AIAnalysis
from app.models.followup_checklist import SessionFollowupChecklist
from app.models.session import ConsultationSession
from app.models.transcript import Transcript
from app.models.user import User
from app.schemas.common import SessionErrorInfo
from app.schemas.followup_checklist import FollowupChecklistEnvelope, FollowupChecklistOut
from app.services import audit_service, transcript_service

logger = get_logger(__name__)

PREVIOUS_SESSION_LIMIT = 3

# 처리 중 행이 시작 + 제한 시간 + 이 값보다 오래되면 작업이 사라진 것으로 보고 실패로 마감한다(서버 재시작 등).
STALE_GRACE_SECONDS = 60

# 차지할 때 attempt 가 그 사이 바뀌었으면 다시 읽어 몇 번까지 해 본다(분석 저장이 겹치는 드문 경우).
CLAIM_RETRIES = 3

DISABLED_MESSAGE = "다음 상담 체크리스트 만들기가 꺼져 있습니다(FOLLOWUP_PROVIDER=off)."
NOT_READY_MESSAGE = "AI 분석이 끝난 회차에서만 다음 상담 체크리스트를 만들 수 있습니다."

RAG_ABUSE_TYPES: Dict[AbuseType, str] = {
    AbuseType.PHYSICAL: "physical",
    AbuseType.EMOTIONAL: "emotional",
    AbuseType.SEXUAL: "sexual",
    AbuseType.NEGLECT: "neglect",
}


class _Limits:
    """서버 전체 동시 실행 자리. 설정이 바뀌면 reset_limits 로 새로 만든다."""

    def __init__(self) -> None:
        self.slots = threading.BoundedSemaphore(settings.FOLLOWUP_MAX_CONCURRENCY)


_limits = _Limits()


def reset_limits() -> None:
    """시험용. 동시 실행 자리를 설정값으로 다시 만든다."""

    global _limits
    _limits = _Limits()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(value: Optional[datetime]) -> Optional[datetime]:
    # SQLite 는 시간대 없이 돌려준다. 저장은 UTC 로 한다.
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


# =========================================================
# 조회
# =========================================================

def get_row(db: Session, session_id: uuid.UUID) -> Optional[SessionFollowupChecklist]:
    # 이 모듈은 조건부 UPDATE(synchronize_session=False)로 행을 바꾸고, SessionLocal 은 expire_on_commit=False 라
    # 같은 DB 세션이 들고 있던 객체는 옛 값 그대로다. 읽을 때마다 DB 값으로 다시 채운다.
    return db.scalar(
        select(SessionFollowupChecklist)
        .where(SessionFollowupChecklist.session_id == session_id)
        .execution_options(populate_existing=True)
    )


def _stale_cutoff() -> datetime:
    return _now() - timedelta(seconds=settings.FOLLOWUP_TIMEOUT_SECONDS + STALE_GRACE_SECONDS)


def expire_stale(db: Session, row: Optional[SessionFollowupChecklist]) -> Optional[SessionFollowupChecklist]:
    """처리 중인 채 너무 오래된 행을 FAILED · AI_TIMEOUT 으로 마감한다(작업이 사라진 경우). 그 attempt 일 때만 바꾼다."""

    if row is None or row.status != AnalysisStatus.PROCESSING:
        return row

    started = _aware(row.started_at)

    if started is not None and started >= _stale_cutoff():
        return row

    changed = db.execute(
        update(SessionFollowupChecklist)
        .where(
            SessionFollowupChecklist.id == row.id,
            SessionFollowupChecklist.attempt == row.attempt,
            SessionFollowupChecklist.status == AnalysisStatus.PROCESSING,
        )
        .values(
            status=AnalysisStatus.FAILED,
            error_code=ErrorCode.AI_TIMEOUT.value,
            error_message=FOLLOWUP_MESSAGES[ErrorCode.AI_TIMEOUT],
            completed_at=_now(),
        )
        .execution_options(synchronize_session=False)
    ).rowcount
    db.commit()

    if changed:
        logger.warning("다음 상담 체크리스트 작업이 멈춘 것으로 보고 마감했습니다. session_id=%s", row.session_id)

    db.refresh(row)

    return row


def to_out(row: SessionFollowupChecklist) -> FollowupChecklistOut:
    error = (
        SessionErrorInfo(code=row.error_code, message=row.error_message or "")
        if row.status == AnalysisStatus.FAILED and row.error_code
        else None
    )

    return FollowupChecklistOut(
        status=row.status,
        attempt=row.attempt,
        analysis_id=row.analysis_id,
        transcript_version=row.transcript_version,
        provider=row.provider,
        # 결과는 COMPLETED 일 때만 보인다(처리 중 · 실패에는 없다).
        result=row.result if row.status == AnalysisStatus.COMPLETED else None,
        error=error,
        started_at=row.started_at,
        completed_at=row.completed_at,
    )


def get_envelope(db: Session, session: ConsultationSession) -> FollowupChecklistEnvelope:
    row = expire_stale(db, get_row(db, session.id))

    return FollowupChecklistEnvelope(enabled=is_enabled(), checklist=to_out(row) if row is not None else None)


# =========================================================
# rag 입력 만들기 (닫힌 #117 followup_service 와 같다)
# =========================================================

def abuse_type_for_rag(result: Any) -> Optional[str]:
    """AI 분석 결과에서 rag 의 학대 유형 값을 정한다. 감지된 유형이 없으면 None(rag 를 부르지 않는다)."""

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


def drafts_of(result: Any) -> List[Dict[str, Any]]:
    """분석의 추가 질문 AI 초안. draft_index 는 result.followup_questions 안의 위치다(화면이 같은 순서로 그린다)."""

    if not isinstance(result, dict) or not isinstance(result.get("followup_questions"), list):
        return []

    drafts = []

    for index, item in enumerate(result["followup_questions"]):
        if not isinstance(item, dict) or not isinstance(item.get("text"), str) or not item["text"].strip():
            continue
        reason = item.get("reason")
        drafts.append({"draft_index": index, "text": item["text"], "reason": reason if isinstance(reason, str) else ""})

    return drafts


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


def _latest_analysis(db: Session, session_id: uuid.UUID) -> Optional[AIAnalysis]:
    return db.scalar(
        select(AIAnalysis)
        .where(AIAnalysis.session_id == session_id)
        .order_by(AIAnalysis.created_at.desc(), AIAnalysis.id.desc())
        .limit(1)
    )


def _check_items_of(db: Session, session_id: uuid.UUID) -> List[Dict[str, Any]]:
    """그 회차의 '다음 상담 전 확인할 사항'. 체크리스트가 있으면 그것을, 없으면 AI 분석의 확인 메모를 쓴다.

    확인했는지(체크) 저장은 아직 없어 모두 open 으로 넘긴다 — rag 가 이행 여부를 다시 확인할 거리로 본다.
    """

    row = get_row(db, session_id)
    texts: List[str] = []

    if row is not None and row.status == AnalysisStatus.COMPLETED and isinstance(row.result, dict):
        texts = [
            str(item.get("text")) for item in row.result.get("check_items") or []
            if isinstance(item, dict) and item.get("text")
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
    analysis: AIAnalysis,
    transcript: Transcript,
) -> FollowupChecklistInput:
    return FollowupChecklistInput(
        transcript=transcript_service.transcript_to_contract(transcript),
        abuse_type=abuse_type_for_rag(analysis.result),
        session_no=session.session_number,
        session_id=str(session.id),
        previous_sessions=previous_sessions_input(db, session),
        drafts=drafts_of(analysis.result),
    )


# =========================================================
# 행 차지 · 마감
# =========================================================

def _claim(
    db: Session,
    session: ConsultationSession,
    analysis: AIAnalysis,
    provider: str,
    *,
    supersede: bool,
) -> Optional[int]:
    """행을 PROCESSING 으로 차지하고 그 attempt 를 돌려준다. 차지하지 못했으면 None.

    supersede=False(POST): 다른 작업이 처리 중(멈춤 아님)이면 차지하지 않는다.
    supersede=True(분석 저장 직후): 분석이 새로 저장됐으므로 처리 중인 앞 작업이 있어도 차지한다(앞 결과는 버려진다).
    """

    values = {
        "status": AnalysisStatus.PROCESSING,
        "analysis_id": analysis.id,
        "transcript_version": analysis.transcript_version,
        "provider": provider,
        "result": None,
        "error_code": None,
        "error_message": None,
        "started_at": _now(),
        "completed_at": None,
    }

    for _ in range(CLAIM_RETRIES):
        row = get_row(db, session.id)

        if row is None:
            try:
                db.add(SessionFollowupChecklist(session_id=session.id, attempt=1, **values))
                db.commit()
                return 1
            except IntegrityError:
                # 같은 회차에 동시에 처음 만들었다. 다시 읽어 UPDATE 로 차지해 본다.
                db.rollback()
                continue

        expected = row.attempt

        if not supersede and row.status == AnalysisStatus.PROCESSING:
            started = _aware(row.started_at)
            if started is None or started >= _stale_cutoff():
                return None

        claimed = db.execute(
            update(SessionFollowupChecklist)
            .where(
                SessionFollowupChecklist.id == row.id,
                SessionFollowupChecklist.attempt == expected,
            )
            .values(attempt=expected + 1, **values)
            .execution_options(synchronize_session=False)
        ).rowcount

        if claimed == 1:
            db.commit()
            return expected + 1

        db.rollback()

        if not supersede:
            # 그 사이 다른 요청이 차지했다. 그 작업을 쓴다.
            return None

    return None


def _finish(
    db: Session,
    checklist_id: uuid.UUID,
    attempt: int,
    *,
    status: AnalysisStatus,
    result: Optional[Dict[str, Any]] = None,
    error: Optional[FollowupChecklistError] = None,
) -> bool:
    """행이 아직 이 attempt · PROCESSING 일 때만 마감한다. 마감했으면 True."""

    changed = db.execute(
        update(SessionFollowupChecklist)
        .where(
            SessionFollowupChecklist.id == checklist_id,
            SessionFollowupChecklist.attempt == attempt,
            SessionFollowupChecklist.status == AnalysisStatus.PROCESSING,
        )
        .values(
            status=status,
            result=result,
            error_code=error.code.value if error is not None else None,
            error_message=error.message if error is not None else None,
            completed_at=_now(),
        )
        .execution_options(synchronize_session=False)
    ).rowcount
    db.commit()

    return changed == 1


# =========================================================
# 만들기
# =========================================================

def request_generation(
    db: Session,
    session: ConsultationSession,
    user: User,
) -> Tuple[SessionFollowupChecklist, Optional[int]]:
    """POST(만들기 · 다시 만들기). (행, 차지한 attempt) — attempt 가 None 이면 이미 만드는 중이라 새 작업을 띄우지 않는다."""

    if not is_enabled():
        raise APIError(ErrorCode.FOLLOWUP_DISABLED, DISABLED_MESSAGE, status_code=503)

    analysis = _latest_analysis(db, session.id)

    if analysis is None or analysis.status != AnalysisStatus.COMPLETED:
        raise APIError(ErrorCode.INVALID_SESSION_STATE, NOT_READY_MESSAGE, status_code=409)

    expire_stale(db, get_row(db, session.id))

    adapter = get_followup_checklist_adapter()
    attempt = _claim(db, session, analysis, adapter.name, supersede=False)
    row = get_row(db, session.id)

    if attempt is not None:
        audit_service.record(
            db,
            action=AuditAction.FOLLOWUP_CHECKLIST_REQUESTED,
            entity_type="SessionFollowupChecklist",
            entity_id=row.id,
            actor_id=user.id,
            case_id=session.case_id,
            session_id=session.id,
            detail={"provider": adapter.name, "attempt": attempt},
        )
        db.commit()

    db.refresh(row)

    return row, attempt


def generate_after_analysis(session_id: uuid.UUID, analysis_id: uuid.UUID) -> None:
    """분석이 저장된 직후 같은 백그라운드 작업에서 부른다. 꺼져 있으면 아무것도 하지 않는다.

    어떤 예외도 밖으로 내지 않는다(분석 작업 · 회차 상태에 영향을 주지 않게 — DB 세션 만들기 · close 포함, #117 C3).
    """

    try:
        if not is_enabled():
            return

        db = SessionLocal()

        try:
            session = db.get(ConsultationSession, session_id)
            analysis = db.get(AIAnalysis, analysis_id)

            if session is None or analysis is None or analysis.status != AnalysisStatus.COMPLETED:
                return

            adapter = get_followup_checklist_adapter()
            attempt = _claim(db, session, analysis, adapter.name, supersede=True)
            row = get_row(db, session.id)
            checklist_id = row.id if row is not None else None
        finally:
            db.close()

        if attempt is not None and checklist_id is not None:
            process_checklist(checklist_id, attempt)

    except Exception as error:  # noqa: BLE001 — 분석 작업으로 예외를 내보내지 않는다
        logger.warning(
            "분석 뒤 다음 상담 체크리스트를 시작하지 못했습니다. session_id=%s type=%s",
            session_id,
            type(error).__name__,
        )


def _run_adapter(adapter, payload: FollowupChecklistInput) -> Dict[str, Any]:
    """동시 실행 자리를 얻어 제한 시간 안에 adapter.build 를 돌린다. 실패는 FollowupChecklistError.

    자리는 작업 thread 가 실제로 끝날 때 돌려준다(시간을 넘긴 작업이 뒤에서 도는 동안 자리를 쥔다).
    작업이 시작조차 못 한 경우(시간 초과로 취소됨)만 여기서 돌려준다. 두 번 돌려주지 않는다.
    """

    timeout = settings.FOLLOWUP_TIMEOUT_SECONDS
    slots = _limits.slots

    if not slots.acquire(timeout=timeout):
        raise FollowupChecklistError(ErrorCode.AI_TIMEOUT, "NoSlot")

    work_started = threading.Event()
    release_lock = threading.Lock()
    released = False

    def release_slot() -> None:
        nonlocal released

        with release_lock:
            if released:
                return

            released = True
            slots.release()

    def work() -> Dict[str, Any]:
        work_started.set()

        try:
            return adapter.build(payload)
        finally:
            release_slot()

    try:
        return run_with_timeout(work, timeout)
    except OperationTimeout as error:
        raise FollowupChecklistError(ErrorCode.AI_TIMEOUT, "OperationTimeout") from error
    except Exception as error:
        raise map_followup_error(error) from error
    finally:
        if not work_started.is_set():
            release_slot()


def process_checklist(checklist_id: uuid.UUID, attempt: int) -> None:
    """체크리스트 하나를 만든다(백그라운드). 행이 이 attempt · PROCESSING 이 아니면 시작하지 않고, 끝나도 쓰지 않는다."""

    try:
        db = SessionLocal()
    except Exception as error:  # noqa: BLE001
        logger.warning("다음 상담 체크리스트 DB 세션을 열지 못했습니다. type=%s", type(error).__name__)
        return

    try:
        row = db.get(SessionFollowupChecklist, checklist_id)

        if row is None or row.attempt != attempt or row.status != AnalysisStatus.PROCESSING:
            return

        session = db.get(ConsultationSession, row.session_id)
        analysis = db.get(AIAnalysis, row.analysis_id) if row.analysis_id is not None else None
        transcript = (
            db.get(Transcript, analysis.transcript_id)
            if analysis is not None and analysis.transcript_id is not None
            else None
        )

        if session is None or analysis is None or transcript is None:
            _finish(db, checklist_id, attempt, status=AnalysisStatus.FAILED,
                    error=FollowupChecklistError(ErrorCode.AI_FAILED, "MissingInput"))
            return

        payload = build_input(db, session, analysis, transcript)
        # 외부 호출 동안 DB 연결을 쥐지 않는다.
        db.commit()

        try:
            result = _run_adapter(get_followup_checklist_adapter(), payload)
        except FollowupChecklistError as error:
            logger.warning(
                "다음 상담 체크리스트를 만들지 못했습니다. session_id=%s code=%s cause=%s",
                session.id,
                error.code.value,
                error.cause_name,
            )
            _finish(db, checklist_id, attempt, status=AnalysisStatus.FAILED, error=error)
            return

        if not _finish(db, checklist_id, attempt, status=AnalysisStatus.COMPLETED, result=result):
            logger.warning("다음 상담 체크리스트의 늦은 결과를 버렸습니다. session_id=%s", session.id)

    except Exception as error:  # noqa: BLE001 — 행을 실패로 마감해 '만드는 중' 에 멈추지 않게 한다
        logger.warning("다음 상담 체크리스트 처리 중 오류. checklist_id=%s type=%s", checklist_id, type(error).__name__)
        try:
            db.rollback()
            _finish(db, checklist_id, attempt, status=AnalysisStatus.FAILED,
                    error=FollowupChecklistError(ErrorCode.AI_FAILED, type(error).__name__))
        except Exception as finish_error:  # noqa: BLE001
            logger.warning("다음 상담 체크리스트 실패 마감도 하지 못했습니다. type=%s", type(finish_error).__name__)
    finally:
        try:
            db.close()
        except Exception as error:  # noqa: BLE001
            logger.warning("다음 상담 체크리스트 DB 세션을 닫지 못했습니다. type=%s", type(error).__name__)
