# STT 연동 및 Transcript 저장/조회/수정.
#
# 호출 경로: router → service → stt_adapter
#
# 상태 흐름:
#   AUDIO_UPLOADED → STT_PROCESSING → STT_REVIEW_REQUIRED → STT_CONFIRMED
#
# 장시간 작업은 BackgroundTasks 로 처리하고 Frontend 는 Polling 한다.

import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.adapters.stt_adapter import STTError, STTOutputError, get_stt_adapter
from app.core import storage
from app.core.concurrency import OperationTimeout, run_with_timeout
from app.core.config import settings
from app.core.database import SessionLocal
from app.core.enums import AuditAction, SessionStatus, TranscriptSource
from app.core.errors import ErrorCode, conflict, not_found
from app.core.logging import get_logger
from app.core.state_machine import assert_status_in, assert_transition
from app.models.session import ConsultationSession
from app.models.transcript import Transcript, TranscriptSegment
from app.models.user import User
from app.schemas.contracts import STTResult
from app.schemas.transcript import (
    TranscriptEnvelope,
    TranscriptResponse,
    TranscriptUpdateRequest,
)
from app.services import audit_service, audio_service, session_service

logger = get_logger(__name__)

_EDITABLE_STATUSES = {
    SessionStatus.STT_REVIEW_REQUIRED,
    SessionStatus.STT_CONFIRMED,
}


# =========================================================
# 조회
# =========================================================

def get_latest_transcript(
    db: Session,
    session_id: uuid.UUID,
) -> Optional[Transcript]:
    return db.scalar(
        select(Transcript)
        .options(selectinload(Transcript.segments))
        .where(Transcript.session_id == session_id)
        .order_by(Transcript.version.desc())
        .limit(1)
    )


def require_confirmed_transcript(db: Session, session_id: uuid.UUID) -> Transcript:
    transcript = get_latest_transcript(db, session_id)

    if transcript is None:
        raise not_found(ErrorCode.TRANSCRIPT_NOT_FOUND, "Transcript 가 없습니다.")

    if not transcript.is_confirmed:
        raise conflict(
            ErrorCode.TRANSCRIPT_NOT_CONFIRMED,
            "확정되지 않은 Transcript 로는 AI 분석을 실행할 수 없습니다.",
        )

    return transcript


def to_transcript_response(transcript: Transcript) -> TranscriptResponse:
    segments = sorted(transcript.segments, key=lambda item: item.order_index)

    return TranscriptResponse(
        id=transcript.id,
        session_id=transcript.session_id,
        version=transcript.version,
        schema_version=transcript.schema_version,
        source=transcript.source,
        is_confirmed=transcript.is_confirmed,
        confirmed_at=transcript.confirmed_at,
        stt_provider=transcript.stt_provider,
        stt_model=transcript.stt_model,
        created_at=transcript.created_at,
        segments=[
            {
                "segment_id": segment.segment_id,
                "speaker": segment.speaker,
                "start_ms": segment.start_ms,
                "end_ms": segment.end_ms,
                "text": segment.text,
                "confidence": segment.confidence,
            }
            for segment in segments
        ],
        edited_segment_ids=[
            segment.segment_id for segment in segments if segment.is_edited
        ],
    )


def build_envelope(db: Session, session: ConsultationSession) -> TranscriptEnvelope:
    transcript = get_latest_transcript(db, session.id)

    return TranscriptEnvelope(
        session_id=session.id,
        session_status=session.status,
        transcript=to_transcript_response(transcript) if transcript else None,
        error=session_service.build_error_info(session),
    )


def transcript_to_contract(transcript: Transcript) -> Dict[str, object]:
    """AI Service 로 전달할 STT Contract payload 를 만든다."""

    segments = sorted(transcript.segments, key=lambda item: item.order_index)

    return {
        "schema_version": transcript.schema_version,
        "segments": [
            {
                "segment_id": segment.segment_id,
                "speaker": segment.speaker.value,
                "start_ms": segment.start_ms,
                "end_ms": segment.end_ms,
                "text": segment.text,
                "confidence": segment.confidence,
            }
            for segment in segments
        ],
    }


# =========================================================
# STT 실행
# =========================================================

def request_stt(
    db: Session,
    session: ConsultationSession,
    current_user: User,
) -> ConsultationSession:
    """
    STT 실행을 예약한다.

    음성 파일이 없으면 시작하지 않고, 상태만 STT_PROCESSING 으로 전이한다.
    """

    audio_service.get_latest_audio(db, session.id)

    assert_transition(session.status, SessionStatus.STT_PROCESSING)

    session.status = SessionStatus.STT_PROCESSING
    session.stt_started_at = datetime.now(timezone.utc)
    session.stt_completed_at = None
    session.clear_error()

    audit_service.record(
        db,
        action=AuditAction.STT_REQUESTED,
        entity_type="ConsultationSession",
        entity_id=session.id,
        actor_id=current_user.id,
        case_id=session.case_id,
        session_id=session.id,
    )

    db.commit()
    db.refresh(session)

    return session


def process_stt(session_id: uuid.UUID) -> None:
    """
    BackgroundTasks 에서 실행되는 STT 처리.

    별도 DB Session 을 사용하고, 어떤 예외가 발생해도
    Session 상태를 STT_REVIEW_REQUIRED 또는 STT_FAILED 로 마감한다.
    """

    db = SessionLocal()

    try:
        session = db.scalar(
            select(ConsultationSession).where(ConsultationSession.id == session_id)
        )

        if session is None:
            logger.warning("STT 대상 Session 을 찾을 수 없습니다. session_id=%s", session_id)
            return

        if session.status != SessionStatus.STT_PROCESSING:
            logger.warning(
                "STT 처리 조건이 아닙니다. session_id=%s status=%s",
                session_id,
                session.status.value,
            )
            return

        try:
            audio = audio_service.get_latest_audio(db, session.id)
            audio_path = storage.resolve_stored_path(audio.path)

            adapter = get_stt_adapter()

            result = run_with_timeout(
                lambda: adapter.transcribe(audio_path),
                settings.STT_TIMEOUT_SECONDS,
            )

            if not isinstance(result, STTResult):
                raise STTOutputError("STT Adapter 가 STTResult 를 반환하지 않았습니다.")

            _save_stt_result(
                db,
                session=session,
                result=result,
                provider=getattr(adapter, "name", "unknown"),
                model=getattr(adapter, "model", None),
            )

        except OperationTimeout as error:
            _fail_stt(db, session, ErrorCode.STT_TIMEOUT, str(error))
        except STTOutputError as error:
            _fail_stt(db, session, ErrorCode.STT_INVALID_OUTPUT, str(error))
        except STTError as error:
            _fail_stt(db, session, ErrorCode.STT_FAILED, str(error))
        except Exception as error:
            logger.exception("STT 처리 중 예상하지 못한 오류. session_id=%s", session_id)
            _fail_stt(
                db,
                session,
                ErrorCode.STT_FAILED,
                f"STT 처리 중 오류가 발생했습니다: {type(error).__name__}",
            )
    finally:
        db.close()


def _save_stt_result(
    db: Session,
    *,
    session: ConsultationSession,
    result: STTResult,
    provider: str,
    model: Optional[str],
) -> Transcript:
    next_version = (
        db.scalar(
            select(func.coalesce(func.max(Transcript.version), 0)).where(
                Transcript.session_id == session.id
            )
        )
        or 0
    ) + 1

    transcript = Transcript(
        session_id=session.id,
        version=next_version,
        schema_version=result.schema_version,
        source=TranscriptSource.STT,
        is_confirmed=False,
        stt_provider=provider,
        stt_model=model,
    )

    db.add(transcript)
    db.flush()

    for index, segment in enumerate(result.segments):
        db.add(
            TranscriptSegment(
                transcript_id=transcript.id,
                segment_id=segment.segment_id,
                order_index=index,
                speaker=segment.speaker,
                start_ms=segment.start_ms,
                end_ms=segment.end_ms,
                text=segment.text,
                confidence=segment.confidence,
            )
        )

    session.status = SessionStatus.STT_REVIEW_REQUIRED
    session.stt_completed_at = datetime.now(timezone.utc)
    session.clear_error()

    audit_service.record(
        db,
        action=AuditAction.STT_COMPLETED,
        entity_type="Transcript",
        entity_id=transcript.id,
        case_id=session.case_id,
        session_id=session.id,
        detail={
            "version": next_version,
            "segment_count": len(result.segments),
            "provider": provider,
        },
    )

    db.commit()

    # 상담 원문은 로그에 남기지 않고 개수만 기록한다.
    logger.info(
        "STT 완료 session_id=%s version=%s segment_count=%s",
        session.id,
        next_version,
        len(result.segments),
    )

    return transcript


def _fail_stt(
    db: Session,
    session: ConsultationSession,
    code: ErrorCode,
    message: str,
) -> None:
    db.rollback()

    session.status = SessionStatus.STT_FAILED
    session.stt_completed_at = datetime.now(timezone.utc)
    session.set_error(code.value, message)

    audit_service.record(
        db,
        action=AuditAction.STT_FAILED,
        entity_type="ConsultationSession",
        entity_id=session.id,
        case_id=session.case_id,
        session_id=session.id,
        detail={"error_code": code.value},
    )

    db.commit()

    logger.warning("STT 실패 session_id=%s code=%s", session.id, code.value)


# =========================================================
# 상담사 수정 / 확정
# =========================================================

def update_transcript(
    db: Session,
    session: ConsultationSession,
    current_user: User,
    payload: TranscriptUpdateRequest,
) -> Transcript:
    """
    상담사 수정은 새 version 을 생성하고 기존 version 을 이력으로 보존한다.
    """

    assert_status_in(session.status, _EDITABLE_STATUSES)

    latest = get_latest_transcript(db, session.id)

    if latest is None:
        raise not_found(ErrorCode.TRANSCRIPT_NOT_FOUND, "수정할 Transcript 가 없습니다.")

    existing = sorted(latest.segments, key=lambda item: item.order_index)
    existing_ids = {segment.segment_id for segment in existing}

    updates = {item.segment_id: item for item in payload.segments}
    removed = set(payload.removed_segment_ids)

    unknown = (set(updates) | removed) - existing_ids

    if unknown:
        raise not_found(
            ErrorCode.TRANSCRIPT_NOT_FOUND,
            f"존재하지 않는 segment_id 입니다: {', '.join(sorted(unknown))}",
        )

    if removed and len(removed) >= len(existing_ids):
        raise conflict(
            ErrorCode.VALIDATION_ERROR,
            "모든 segment 를 삭제할 수는 없습니다.",
        )

    new_transcript = Transcript(
        session_id=session.id,
        version=latest.version + 1,
        schema_version=latest.schema_version,
        source=TranscriptSource.COUNSELOR_EDIT,
        is_confirmed=False,
        stt_provider=latest.stt_provider,
        stt_model=latest.stt_model,
        created_by_id=current_user.id,
    )

    db.add(new_transcript)
    db.flush()

    order_index = 0
    edited_ids: List[str] = []

    for segment in existing:
        if segment.segment_id in removed:
            continue

        update = updates.get(segment.segment_id)

        start_ms = segment.start_ms
        end_ms = segment.end_ms
        speaker = segment.speaker
        text = segment.text
        is_edited = segment.is_edited

        if update is not None:
            if update.speaker is not None:
                speaker = update.speaker

            if update.text is not None:
                text = update.text

            if update.start_ms is not None:
                start_ms = update.start_ms

            if update.end_ms is not None:
                end_ms = update.end_ms

            if end_ms < start_ms:
                raise conflict(
                    ErrorCode.VALIDATION_ERROR,
                    f"segment {segment.segment_id}: end_ms 는 start_ms 보다 작을 수 없습니다.",
                )

            is_edited = True
            edited_ids.append(segment.segment_id)

        db.add(
            TranscriptSegment(
                transcript_id=new_transcript.id,
                segment_id=segment.segment_id,
                order_index=order_index,
                speaker=speaker,
                start_ms=start_ms,
                end_ms=end_ms,
                text=text,
                # confidence 는 STT 값이므로 상담사 수정으로 변경하지 않는다.
                confidence=segment.confidence,
                is_edited=is_edited,
            )
        )

        order_index += 1

    # 확정 이후 수정하면 다시 검수 상태로 돌아간다.
    if session.status != SessionStatus.STT_REVIEW_REQUIRED:
        assert_transition(session.status, SessionStatus.STT_REVIEW_REQUIRED)
        session.status = SessionStatus.STT_REVIEW_REQUIRED

    session.clear_error()

    audit_service.record(
        db,
        action=AuditAction.TRANSCRIPT_UPDATED,
        entity_type="Transcript",
        entity_id=new_transcript.id,
        actor_id=current_user.id,
        case_id=session.case_id,
        session_id=session.id,
        detail={
            "from_version": latest.version,
            "to_version": new_transcript.version,
            "edited_segment_ids": edited_ids,
            "removed_segment_ids": sorted(removed),
        },
    )

    db.commit()
    db.refresh(new_transcript)

    return new_transcript


def confirm_transcript(
    db: Session,
    session: ConsultationSession,
    current_user: User,
) -> Transcript:
    transcript = get_latest_transcript(db, session.id)

    if transcript is None:
        raise not_found(ErrorCode.TRANSCRIPT_NOT_FOUND, "확정할 Transcript 가 없습니다.")

    if transcript.is_confirmed:
        raise conflict(
            ErrorCode.TRANSCRIPT_ALREADY_CONFIRMED,
            "이미 확정된 Transcript 입니다.",
        )

    assert_transition(session.status, SessionStatus.STT_CONFIRMED)

    transcript.is_confirmed = True
    transcript.confirmed_at = datetime.now(timezone.utc)
    transcript.confirmed_by_id = current_user.id

    session.status = SessionStatus.STT_CONFIRMED
    session.clear_error()

    audit_service.record(
        db,
        action=AuditAction.TRANSCRIPT_CONFIRMED,
        entity_type="Transcript",
        entity_id=transcript.id,
        actor_id=current_user.id,
        case_id=session.case_id,
        session_id=session.id,
        detail={"version": transcript.version},
    )

    db.commit()
    db.refresh(transcript)

    return transcript
