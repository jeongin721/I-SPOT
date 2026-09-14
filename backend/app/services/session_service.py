# Session CRUD 및 상태 조회.

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Optional, Tuple

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core import storage
from app.core.config import settings
from app.core.enums import AnalysisStatus, AuditAction, ReviewStatus, SessionStatus
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


def create_session(
    db: Session,
    case: Case,
    current_user: User,
    payload: SessionCreateRequest,
) -> ConsultationSession:
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
    )

    db.add(session)
    db.flush()

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


def list_sessions(
    db: Session,
    case_id: uuid.UUID,
    *,
    offset: int,
    limit: int,
    status: Optional[SessionStatus] = None,
) -> Tuple[List[ConsultationSession], int]:
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

    for field in ("title", "consulted_at", "location", "memo"):
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

    서버 시작 시 일괄 정리하지 않는 이유: 여러 프로세스로 띄우면 다른 프로세스가
    처리 중인 작업까지 실패로 만든다. 그래서 조회·재요청 시점에 Session 별로 판단한다.
    """

    rule = _PROCESSING_RULES.get(session.status)

    if rule is None:
        return False

    now = datetime.now(timezone.utc)
    limit_seconds = getattr(settings, rule.timeout_setting) + STALE_GRACE_SECONDS
    started_at = getattr(session, rule.started_field)

    if started_at is not None:
        if started_at.tzinfo is None:
            # SQLite 는 시간대 정보 없이 돌려준다. 저장 값은 UTC 다.
            started_at = started_at.replace(tzinfo=timezone.utc)

        if (now - started_at).total_seconds() <= limit_seconds:
            return False

    processing = session.status

    expired = db.execute(
        update(ConsultationSession)
        .where(
            ConsultationSession.id == session.id,
            ConsultationSession.status == processing,
        )
        .values(status=rule.failed_status)
        .execution_options(synchronize_session=False)
    ).rowcount

    if expired != 1:
        # 판단하는 사이에 작업이 끝나 상태가 바뀌었다.
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
