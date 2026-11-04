# Session CRUD 및 상태 조회.

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Optional, Tuple

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core import storage
from app.core.config import settings
from app.core.enums import AnalysisStatus, AuditAction, DraftsStatus, ReviewStatus, SessionStatus
from app.core.errors import ErrorCode, conflict
from app.core.logging import get_logger
from app.core.state_machine import assert_transition
from app.models.analysis import AIAnalysis
from app.models.audio import AudioFile
from app.models.case import Case
from app.models.session import ConsultationSession
from app.models.summary import ConsultationSummary
from app.models.transcript import Transcript
from app.models.user import User
from app.schemas.common import SessionErrorInfo
from app.schemas.session import (
    SessionCreateRequest,
    SessionDetailResponse,
    SessionUpdateRequest,
)
from app.services import audit_service

logger = get_logger(__name__)

_SESSION_NUMBER_MAX_RETRY = 5


def create_session(
    db: Session,
    case: Case,
    current_user: User,
    payload: SessionCreateRequest,
) -> ConsultationSession:
    for attempt in range(_SESSION_NUMBER_MAX_RETRY):
        next_number = (
            db.scalar(
                select(func.coalesce(func.max(ConsultationSession.session_number), 0)).where(
                    ConsultationSession.case_id == case.id
                )
            )
            or 0
        ) + 1

        session = ConsultationSession(
            case_id=case.id,
            session_number=next_number,
            title=payload.title,
            status=SessionStatus.CREATED,
            counselor_id=case.counselor_id,
            consulted_at=payload.consulted_at,
            location=payload.location,
            memo=payload.memo,
            consultation_type=payload.consultation_type,
        )

        db.add(session)

        try:
            db.flush()
        except IntegrityError as error:
            # 같은 사례에 동시에 만든 다른 요청이 같은 번호를 먼저 가져갔다.
            # (case_id, session_number) 유니크 제약. 번호를 다시 계산해 재시도한다.
            db.rollback()

            if attempt == _SESSION_NUMBER_MAX_RETRY - 1:
                raise conflict(
                    ErrorCode.DUPLICATE_RESOURCE,
                    "회기 번호를 정하지 못했습니다. 다시 시도해 주세요.",
                ) from error

            continue

        audit_service.record(
            db,
            action=AuditAction.SESSION_CREATED,
            entity_type="ConsultationSession",
            entity_id=session.id,
            actor_id=current_user.id,
            case_id=case.id,
            session_id=session.id,
            detail={"session_number": session.session_number},
        )

        db.commit()
        db.refresh(session)

        return session

    raise conflict(ErrorCode.DUPLICATE_RESOURCE, "회기 번호를 정하지 못했습니다. 다시 시도해 주세요.")


def list_sessions(
    db: Session,
    case_id: uuid.UUID,
    *,
    offset: int,
    limit: int,
    status: Optional[SessionStatus] = None,
) -> Tuple[List[ConsultationSession], int]:
    # 작업이 사라져 멈춘 처리 중 회기를 먼저 실패로 마감한다. Session 상세 · 원문 · 분석 조회와
    # 업무 목록이 같은 함수를 쓴다. 안 하면 목록에서만 계속 "처리 중" 으로 보이고, 상태 필터와
    # 개수도 마감 전 상태로 센다. 제한 시간 안의 작업은 건드리지 않는다.
    processing = db.scalars(
        select(ConsultationSession).where(
            ConsultationSession.case_id == case_id,
            ConsultationSession.status.in_(list(_PROCESSING_RULES)),
        )
    ).all()

    for session in processing:
        expire_stale_processing(db, session)

    conditions = [ConsultationSession.case_id == case_id]

    if status is not None:
        conditions.append(ConsultationSession.status == status)

    total = db.scalar(
        select(func.count()).select_from(ConsultationSession).where(*conditions)
    ) or 0

    sessions = list(
        db.scalars(
            select(ConsultationSession)
            .where(*conditions)
            .order_by(ConsultationSession.session_number.desc())
            .offset(offset)
            .limit(limit)
        )
    )

    return sessions, total


def update_session(
    db: Session,
    session: ConsultationSession,
    current_user: User,
    payload: SessionUpdateRequest,
) -> ConsultationSession:
    if session.status == SessionStatus.APPROVED:
        raise conflict(
            ErrorCode.ALREADY_APPROVED,
            "승인이 완료된 Session 은 수정할 수 없습니다.",
        )

    data = payload.model_dump(exclude_unset=True)
    changed_fields = []

    for field in ("title", "consulted_at", "location", "memo", "consultation_type"):
        if field in data:
            setattr(session, field, data[field])
            changed_fields.append(field)

    if changed_fields:
        audit_service.record(
            db,
            action=AuditAction.SESSION_UPDATED,
            entity_type="ConsultationSession",
            entity_id=session.id,
            actor_id=current_user.id,
            case_id=session.case_id,
            session_id=session.id,
            detail={"changed_fields": changed_fields},
        )

    db.commit()
    db.refresh(session)

    return session


def delete_session(
    db: Session,
    session: ConsultationSession,
    current_user: User,
) -> None:
    # DB row 를 지우기 전에 Local Storage 의 음성 파일을 먼저 정리한다.
    audio_paths = list(
        db.scalars(select(AudioFile.path).where(AudioFile.session_id == session.id))
    )

    audit_service.record(
        db,
        action=AuditAction.SESSION_DELETED,
        entity_type="ConsultationSession",
        entity_id=session.id,
        actor_id=current_user.id,
        case_id=session.case_id,
        session_id=session.id,
        detail={"audio_file_count": len(audio_paths)},
    )

    db.delete(session)
    db.commit()

    for path in audio_paths:
        storage.delete_stored_audio(path)


def build_session_detail(
    db: Session,
    session: ConsultationSession,
) -> SessionDetailResponse:
    """새로고침 후 Frontend 가 상태를 복원할 수 있도록 진행 상황을 요약한다."""

    expire_stale_processing(db, session)

    latest_transcript = db.scalar(
        select(Transcript)
        .where(Transcript.session_id == session.id)
        .order_by(Transcript.version.desc())
        .limit(1)
    )

    has_audio = bool(
        db.scalar(
            select(func.count()).select_from(AudioFile).where(
                AudioFile.session_id == session.id
            )
        )
    )

    has_analysis = bool(
        db.scalar(
            select(func.count()).select_from(AIAnalysis).where(
                AIAnalysis.session_id == session.id
            )
        )
    )

    summary = db.scalar(
        select(ConsultationSummary).where(ConsultationSummary.session_id == session.id)
    )

    detail = SessionDetailResponse.model_validate(session)

    detail.has_audio = has_audio
    detail.has_transcript = latest_transcript is not None
    detail.transcript_version = latest_transcript.version if latest_transcript else None
    detail.transcript_confirmed = bool(latest_transcript and latest_transcript.is_confirmed)
    detail.has_analysis = has_analysis
    detail.has_summary = summary is not None
    detail.summary_approved = bool(summary and summary.status == ReviewStatus.APPROVED)
    detail.error = build_error_info(session)

    return detail


def build_error_info(session: ConsultationSession) -> Optional[SessionErrorInfo]:
    if not session.last_error_code:
        return None

    return SessionErrorInfo(
        code=session.last_error_code,
        message=session.last_error_message or "처리 중 오류가 발생했습니다.",
    )


def claim_status(
    db: Session,
    session: ConsultationSession,
    target: SessionStatus,
) -> None:
    """읽어 둔 상태가 DB 에서도 그대로일 때만 target 으로 바꾼다.

    두 요청이 같은 상태를 읽고 거의 동시에 들어오면 assert_transition 은 둘 다 통과한다.
    그러면 Background 작업이 두 번 예약되고, 늦게 도는 쪽은 상태 불일치로 조기 종료해
    분석이 PROCESSING 으로 남는다. UPDATE ... WHERE status = 읽은 상태 로 먼저 도착한
    요청만 성공시키고 나머지는 409 로 거절한다.

    행 잠금(SELECT ... FOR UPDATE)은 SQLite 에서 동작하지 않아 테스트로 확인할 수 없으므로
    SQLite · PostgreSQL 에서 똑같이 동작하는 조건부 UPDATE 를 쓴다.
    """

    expected = session.status
    assert_transition(expected, target)

    claimed = db.execute(
        update(ConsultationSession)
        .where(
            ConsultationSession.id == session.id,
            ConsultationSession.status == expected,
        )
        .values(status=target)
        .execution_options(synchronize_session=False)
    ).rowcount

    if claimed != 1:
        db.rollback()

        # rollback 으로 만료된 session 을 다시 읽어 지금 상태 기준으로 알려준다.
        assert_transition(session.status, target)

        raise conflict(
            ErrorCode.INVALID_SESSION_STATE,
            "다른 요청이 먼저 이 Session 의 상태를 바꿨습니다. 새로고침 후 다시 시도해 주세요.",
        )

    session.status = target


# =========================================================
# 멈춘 처리 상태 복구
# =========================================================

# 제한 시간이 끝난 뒤 실패·결과를 기록하는 데 걸리는 시간을 감안한 여유.
STALE_GRACE_SECONDS = 60

# AI 분석 준비 단계(모듈 import · 모델 로드) 제한. analysis_service.PREPARE_TIMEOUT_SECONDS 가 이 값이다(까닭은 그 머리말).
# 3 · 4단계 초안 멈춤 판정(_expire_stale_drafts)도 같은 값을 쓴다 — 이 모듈은 analysis_service 를 import 하지 못한다.
AI_PREPARE_TIMEOUT_SECONDS = STALE_GRACE_SECONDS - 15


@dataclass(frozen=True)
class _ProcessingRule:
    started_field: str
    completed_field: str
    timeout_setting: str
    failed_status: SessionStatus
    error_code: ErrorCode
    audit_action: AuditAction


_PROCESSING_RULES = {
    SessionStatus.STT_PROCESSING: _ProcessingRule(
        "stt_started_at",
        "stt_completed_at",
        "STT_TIMEOUT_SECONDS",
        SessionStatus.STT_FAILED,
        ErrorCode.STT_FAILED,
        AuditAction.STT_FAILED,
    ),
    SessionStatus.AI_PROCESSING: _ProcessingRule(
        "ai_started_at",
        "ai_completed_at",
        "AI_TIMEOUT_SECONDS",
        SessionStatus.AI_FAILED,
        ErrorCode.AI_FAILED,
        AuditAction.ANALYSIS_FAILED,
    ),
}

_STALE_MESSAGE = (
    "처리 제한 시간이 지나도 결과가 없어 중단된 것으로 처리했습니다(서버 재시작 등). "
    "다시 시도해 주세요."
)


def expire_stale_processing(db: Session, session: ConsultationSession) -> bool:
    """처리 제한 시간을 한참 넘긴 처리 중 상태를 실패로 마감한다. 마감했으면 True.

    STT · AI 처리는 같은 프로세스의 BackgroundTasks 에서만 돈다. 처리 도중 서버가
    재시작되면 작업이 사라지고, 처리 중 상태에서 벗어나는 API 경로가 없어 Session 이
    영원히 멈춘다(재요청·재업로드 모두 409).

    살아 있는 작업은 run_with_timeout 때문에 제한 시간 안에 결과나 실패를 기록한다.
    그래서 제한 시간 + 여유 시간이 지난 처리 중 상태만 작업이 사라진 것으로 본다.
    AI 분석은 모델 준비까지 포함해 요청 시각 + 준비 제한(45초) + 제한 시간 안에 끝나도록 제한을 줄이고
    (analysis_service._job_deadline), 여기서 마감한 뒤 늦게 끝난 작업의 결과 · 실패는 저장하지 않는다
    (analysis_service._claim_finish).

    서버 시작 시 일괄 정리하지 않는 이유: 여러 프로세스로 띄우면 다른 프로세스가
    처리 중인 작업까지 실패로 만든다. 그래서 조회·재요청 시점에 Session 별로 판단한다.

    읽어 둔 시작 시각이 DB 에서도 그대로일 때만 마감한다. 읽은 뒤 다른 요청이 같은 작업을 먼저
    마감하고 다시 요청했으면, 상태는 같은 처리 중이어도 시작 시각이 새 요청의 것이다. 상태만 보고
    마감하면 옛 판단으로 막 시작한 새 작업까지 실패로 만든다.

    처리 중이 아닌 회차는 2단계를 먼저 저장하고 3 · 4단계 초안을 기다리는(drafts PENDING) 분석이 멈췄는지 본다
    (_expire_stale_drafts, 2026-11-04). 회차 상태는 바꾸지 않고 초안만 FAILED 로 마감한다.
    """

    rule = _PROCESSING_RULES.get(session.status)

    if rule is None:
        pending = _pending_drafts_analysis_id(db, session.id)

        return pending is not None and _expire_stale_drafts(db, session, pending)

    now = datetime.now(timezone.utc)
    limit_seconds = getattr(settings, rule.timeout_setting) + STALE_GRACE_SECONDS

    # STT 작업은 전사 뒤 같은 작업에서 1차 핵심 발화 스캔을 돌린다(modeling 일 때만, key_scan_service).
    if session.status == SessionStatus.STT_PROCESSING and settings.AI_PROVIDER == "modeling":
        limit_seconds += settings.KEY_SCAN_TIMEOUT_SECONDS
    read_started_at = getattr(session, rule.started_field)
    started_at = read_started_at

    if started_at is not None:
        if started_at.tzinfo is None:
            # SQLite 는 시간대 정보 없이 돌려준다. 저장 값은 UTC 다.
            started_at = started_at.replace(tzinfo=timezone.utc)

        if (now - started_at).total_seconds() <= limit_seconds:
            return False

    processing = session.status
    started_column = getattr(ConsultationSession, rule.started_field)

    # 판단에 쓴 바로 그 작업인지 보려고 DB 에서 읽은 값 그대로 비교한다(위의 시간대 붙이기는 경과 시간 계산에만 쓴다).
    # 시작 시각이 없으면(옛 자료) 위에서 바로 멈춤으로 보고, SQLAlchemy 가 `== None` 을 IS NULL 로 바꿔 여전히 없을 때만 마감한다.
    same_job = started_column == read_started_at

    expired = db.execute(
        update(ConsultationSession)
        .where(
            ConsultationSession.id == session.id,
            ConsultationSession.status == processing,
            same_job,
        )
        .values(status=rule.failed_status)
        .execution_options(synchronize_session=False)
    ).rowcount

    if expired != 1:
        # 판단하는 사이에 작업이 끝나 상태가 바뀌었거나, 다른 요청이 마감하고 새 작업을 시작했다.
        db.rollback()
        return False

    session.status = rule.failed_status
    setattr(session, rule.completed_field, now)
    session.set_error(rule.error_code.value, _STALE_MESSAGE)

    if processing == SessionStatus.AI_PROCESSING:
        db.execute(
            update(AIAnalysis)
            .where(
                AIAnalysis.session_id == session.id,
                AIAnalysis.status == AnalysisStatus.PROCESSING,
            )
            .values(
                status=AnalysisStatus.FAILED,
                error_code=rule.error_code.value,
                error_message=_STALE_MESSAGE,
                completed_at=now,
            )
            .execution_options(synchronize_session=False)
        )

    audit_service.record(
        db,
        action=rule.audit_action,
        entity_type="ConsultationSession",
        entity_id=session.id,
        case_id=session.case_id,
        session_id=session.id,
        detail={
            "error_code": rule.error_code.value,
            "reason": "stale_processing",
            "limit_seconds": limit_seconds,
        },
    )

    db.commit()

    logger.warning(
        "처리 중 상태가 제한 시간을 넘겨 실패로 마감했습니다. session_id=%s status=%s",
        session.id,
        processing.value,
    )

    return True


# =========================================================
# 3 · 4단계 AI 초안(drafts_status, 2026-11-04 PROPOSAL_analysis_signals_first.md)
# =========================================================

DRAFTS_PENDING_MESSAGE = (
    "AI 초안(상담 요약 · 확인 메모 · 추가 질문 등)을 만드는 중입니다. 잠시 뒤 다시 시도해 주세요."
)


def _pending_drafts_analysis_id(db: Session, session_id: uuid.UUID) -> Optional[uuid.UUID]:
    """이 회차에서 3 · 4단계 초안을 기다리는 분석 id. 없으면 None.

    PENDING 동안은 재분석을 받지 않아(assert_drafts_not_pending) 보통 가장 최근 분석 하나뿐이다.
    """

    return db.scalar(
        select(AIAnalysis.id)
        .where(
            AIAnalysis.session_id == session_id,
            AIAnalysis.drafts_status == DraftsStatus.PENDING,
        )
        .limit(1)
    )


def fail_pending_drafts(
    db: Session,
    session: ConsultationSession,
    analysis_id: uuid.UUID,
    error_code: ErrorCode,
    detail: Optional[dict] = None,
) -> bool:
    """그 분석의 3 · 4단계 초안이 아직 PENDING 일 때만 FAILED 로 마감한다. 마감했으면 commit 하고 True, 아니면 되돌리고 False.

    회차 상태와 먼저 저장한 2단계 결과(analysis.status · result)는 그대로 둔다. 분석 작업의 실패 · 시간 초과
    (analysis_service._fail_analysis)와 멈춤 판정(_expire_stale_drafts)이 쓴다. 둘째 저장 · 다른 마감과 겹쳐도 조건부
    UPDATE(그 분석 id · PENDING)의 행 수로 한 쪽만 통과한다.

    오류 코드는 AI_TIMEOUT · AI_FAILED 둘로 줄여 저장한다(응답 문구는 코드로 고르는 고정 문구, 원인 예외 문구는 싣지 않는다).
    """

    code = ErrorCode.AI_TIMEOUT if error_code == ErrorCode.AI_TIMEOUT else ErrorCode.AI_FAILED

    failed = db.execute(
        update(AIAnalysis)
        .where(
            AIAnalysis.id == analysis_id,
            AIAnalysis.drafts_status == DraftsStatus.PENDING,
        )
        .values(drafts_status=DraftsStatus.FAILED, drafts_error_code=code.value)
        .execution_options(synchronize_session=False)
    ).rowcount

    if failed != 1:
        db.rollback()
        return False

    audit_service.record(
        db,
        action=AuditAction.ANALYSIS_DRAFTS_FAILED,
        entity_type="AIAnalysis",
        entity_id=analysis_id,
        case_id=session.case_id,
        session_id=session.id,
        detail={"error_code": code.value, **(detail or {})},
    )

    db.commit()

    logger.warning(
        "AI 초안을 만들지 못했습니다. session_id=%s analysis_id=%s code=%s",
        session.id,
        analysis_id,
        code.value,
    )

    return True


def _expire_stale_drafts(db: Session, session: ConsultationSession, analysis_id: uuid.UUID) -> bool:
    """PENDING 초안이 요청 시각 + 준비 제한 + AI_TIMEOUT_SECONDS + 여유를 넘겼으면 FAILED(AI_FAILED)로 마감한다.

    살아 있는 작업은 요청 시각 + 준비 제한 + AI_TIMEOUT_SECONDS 안에 둘째 저장 · 초안 실패를 남긴다
    (analysis_service._job_deadline). 그 뒤 여유까지 지나도 PENDING 이면 작업이 사라진 것(배포 · 재시작)으로 본다.
    PENDING 동안은 새 분석 요청이 없어 요청 시각(ai_started_at)이 그 분석의 것이다.
    """

    limit_seconds = settings.AI_TIMEOUT_SECONDS + AI_PREPARE_TIMEOUT_SECONDS + STALE_GRACE_SECONDS
    started_at = session.ai_started_at

    if started_at is not None:
        if started_at.tzinfo is None:
            # SQLite 는 시간대 정보 없이 돌려준다. 저장 값은 UTC 다.
            started_at = started_at.replace(tzinfo=timezone.utc)

        if (datetime.now(timezone.utc) - started_at).total_seconds() <= limit_seconds:
            return False

    return fail_pending_drafts(
        db,
        session,
        analysis_id,
        ErrorCode.AI_FAILED,
        {"reason": "stale_processing", "limit_seconds": limit_seconds},
    )


def assert_drafts_not_pending(db: Session, session: ConsultationSession) -> None:
    """3 · 4단계 AI 초안을 만드는 중이면 409 ANALYSIS_DRAFTS_PENDING.

    재분석 · 요약 수정 · 승인 · 추가 질문 · 확인 사항 저장이 쓴다(위험도 판단 저장은 받는다). 바꾸기 전에 부른다
    (초안 마감이 되돌리기를 할 수 있다). 초안이 멈췄으면(작업이 사라짐) 먼저 FAILED 로 마감하고 받는다 — 화면이
    분석을 다시 조회하지 않아도 계속 막히지 않게. 마감하다 둘째 저장과 겹쳤으면 다시 읽어 지금 상태로 판단한다.
    PENDING 은 DONE · FAILED 로만 바뀌고 회차가 처리 중이 아니면 다시 PENDING 이 되지 않아, 확인한 뒤 요청을 처리하는
    사이에 막아야 할 상태로 돌아가지 않는다.
    """

    pending = _pending_drafts_analysis_id(db, session.id)

    if pending is not None and not _expire_stale_drafts(db, session, pending):
        pending = _pending_drafts_analysis_id(db, session.id)

        if pending is not None:
            raise conflict(ErrorCode.ANALYSIS_DRAFTS_PENDING, DRAFTS_PENDING_MESSAGE)
