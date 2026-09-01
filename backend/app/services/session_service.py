# Session CRUD 및 상태 조회.

import uuid
from typing import List, Optional, Tuple

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core import storage
from app.core.enums import AuditAction, ReviewStatus, SessionStatus
from app.core.errors import ErrorCode, conflict
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
