# 상담 기록 문서 회차(API_CONTRACT 20절, 2026-11-02).
#
# 녹취 · 자료 올리기의 '문서 파일'. 상담사가 이미 쓴 상담 기록 문서를 새 회차(CREATED, 음성 없음)에 올리면:
#  1) 글자를 뽑고(document_text) 원본 파일은 버린다.
#  2) AI_PROVIDER=modeling 이면 ai/modeling/abuse/document_note_llm.fill_note(마스킹 → LLM → 원문 복사 검사)가, 아니면
#     rule_based_note(머리줄 나누기, AI 아님)가 상담 요약 4칸 · 상담 일지 칸에 그 글을 나눠 옮긴다.
#  3) 상담 요약(ConsultationSummary, DRAFT)을 4칸으로 만들고, 일지 칸 초안은 note_draft 에 둔다(상담사가 저장해야 일지가 된다).
#  4) 회차는 source=DOCUMENT, 상태는 CREATED → AI_REVIEW_REQUIRED(3단계). 1 · 2단계(원문 검수 · AI 분석)는 없다.
# 동기 요청이다(종결 요약과 같다). 제한 시간 DOCUMENT_NOTE_TIMEOUT_SECONDS 를 넘으면 504, 회차는 그대로(다시 올릴 수 있다).
#
# 4단계 초안(draft_followups): 상담사가 3단계에서 저장한 요약 4칸 · 상담 일지(없으면 일지 초안)를 입력으로 확인 사항 · 추가 질문
# 초안을 만든다. 근거 위치는 없다(전사본이 없다). LLM 을 쓰지 않는 서버는 초안 없이(source NONE) 상담사가 직접 쓴다.
#
# AI 호출은 회차마다 한 번에 하나다(겹치면 429). 실패 문구에는 원문 · 예외 문구를 넣지 않는다.
# 감사 기록에는 형식 · 글자 수 · 채운 칸 이름 · 초안 수만 남긴다(문서 글은 남기지 않는다).

import logging
import threading
import time
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.adapters.module_loader import ModuleLoadError, load_callable
from app.core.concurrency import OperationTimeout, run_with_timeout
from app.core.config import settings
from app.core.enums import AuditAction, ReviewStatus, SessionSource, SessionStatus
from app.core.errors import APIError, ErrorCode, conflict, not_found
from app.core.state_machine import assert_status_in
from app.models.audio import AudioFile
from app.models.document import Document
from app.models.session import ConsultationSession
from app.models.source_document import SessionSourceDocument
from app.models.summary import ConsultationSummary
from app.models.user import User
from app.schemas.source_document import SourceDocumentResponse
from app.services import audit_service
from app.services.document_text import extract_text

logger = logging.getLogger(__name__)

MODULE = "ai.modeling.abuse.document_note_llm"
CONSULTATION_RECORD = "CONSULTATION_RECORD"
ASSESSMENT_KEYS = ("safety_changes", "strengths_resources", "safety_risks", "desired_changes")
NOTE_KEYS = ("statement", "attitude", "environment", "signals", "opinion")

_ERRORS = {
    ErrorCode.AI_TIMEOUT: (504, "문서를 읽는 데 제한 시간이 지났습니다. 잠시 후 다시 시도해 주세요."),
    ErrorCode.AI_INVALID_OUTPUT: (502, "AI 가 문서에서 옮길 칸을 찾지 못했습니다. 문서 내용을 확인해 주세요."),
    ErrorCode.AI_FAILED: (502, "문서를 처리하지 못했습니다. 잠시 후 다시 시도해 주세요."),
}

_running: set = set()
_running_lock = threading.Lock()


def _ai_error(code: ErrorCode) -> APIError:
    status, message = _ERRORS[code]
    return APIError(code, message, status_code=status)


def _run_ai(session: ConsultationSession, name: str, call: Callable[[Callable], Dict[str, Any]]) -> Dict[str, Any]:
    """회차마다 한 번에 하나. 자리는 실제 호출이 끝날 때 돌려준다(제한 시간이 지나도 thread 는 돈다)."""

    with _running_lock:
        if session.id in _running:
            raise APIError(ErrorCode.RATE_LIMITED, "이 회차 문서를 이미 처리하고 있습니다. 잠시 후 새로고침해 주세요.", status_code=429)
        _running.add(session.id)

    started = threading.Event()

    def release() -> None:
        with _running_lock:
            _running.discard(session.id)

    try:
        run = load_callable(MODULE, name)
        deadline = time.monotonic() + settings.DOCUMENT_NOTE_TIMEOUT_SECONDS
    except BaseException:
        release()
        raise

    def work() -> Dict[str, Any]:
        started.set()
        try:
            return call(lambda *args, **kwargs: run(*args, deadline=deadline, **kwargs))
        finally:
            release()

    try:
        return run_with_timeout(work, settings.DOCUMENT_NOTE_TIMEOUT_SECONDS)
    except (OperationTimeout, TimeoutError) as error:
        raise _ai_error(ErrorCode.AI_TIMEOUT) from error
    except ModuleLoadError as error:
        logger.warning("문서 모듈을 불러오지 못했습니다. session_id=%s", session.id)
        raise _ai_error(ErrorCode.AI_FAILED) from error
    except APIError:
        raise
    except Exception as error:  # noqa: BLE001 — 문구에 원문이 섞일 수 있어 종류 이름만 남긴다
        output_error = type(error).__name__ == "DocumentNoteOutputError"
        logger.warning("문서 처리 실패 session_id=%s error=%s", session.id, type(error).__name__)
        raise _ai_error(ErrorCode.AI_INVALID_OUTPUT if output_error else ErrorCode.AI_FAILED) from error
    finally:
        if not started.is_set():
            release()


def get_row(db: Session, session_id) -> Optional[SessionSourceDocument]:
    return db.scalar(select(SessionSourceDocument).where(SessionSourceDocument.session_id == session_id))


def require_row(db: Session, session: ConsultationSession) -> SessionSourceDocument:
    row = get_row(db, session.id)
    if row is None:
        raise not_found(ErrorCode.NOT_FOUND, "이 회차에는 올린 상담 기록 문서가 없습니다.")
    return row


def to_response(row: SessionSourceDocument) -> SourceDocumentResponse:
    return SourceDocumentResponse(
        session_id=row.session_id,
        filename=row.filename,
        file_format=row.file_format,
        char_count=row.char_count,
        text=row.text,
        fill_source=row.fill_source,
        fill_model=row.fill_model,
        note_draft={key: (row.note_draft or {}).get(key, "") for key in NOTE_KEYS},
        followup_draft=row.followup_draft,
        created_at=row.created_at,
    )


def claim_document_session(db: Session, session: ConsultationSession) -> None:
    """CREATED · AUDIO 회차를 문서 회차(AI_REVIEW_REQUIRED · DOCUMENT)로 옮긴다. 상태 전이 표 밖의 이동이라 여기서만 한다.

    조건부 UPDATE(status=CREATED · source=AUDIO 일 때만)라 두 문서가 겹치거나 그사이 음성이 올라오면 늦은 쪽은 409.
    ai_completed_at 을 올린 시각으로 채운다 — 홈 처리 대기 업무가 검수 대기 시간을 이 값으로 센다(task_service).
    """

    now = datetime.now(timezone.utc)
    claimed = db.execute(
        update(ConsultationSession)
        .where(
            ConsultationSession.id == session.id,
            ConsultationSession.status == SessionStatus.CREATED,
            ConsultationSession.source == SessionSource.AUDIO,
        )
        .values(status=SessionStatus.AI_REVIEW_REQUIRED, source=SessionSource.DOCUMENT, ai_completed_at=now)
        .execution_options(synchronize_session=False)
    ).rowcount
    if claimed != 1:
        db.rollback()
        raise conflict(ErrorCode.INVALID_SESSION_STATE, "다른 요청이 먼저 이 회차에 자료를 올렸습니다. 새로고침해 주세요.")
    session.status = SessionStatus.AI_REVIEW_REQUIRED
    session.source = SessionSource.DOCUMENT
    session.ai_completed_at = now
    session.clear_error()


def upload(db: Session, session: ConsultationSession, current_user: User, *, filename: str, data: bytes) -> SessionSourceDocument:
    # 새 회차(음성 · 문서 없음)에만 올린다. 녹음 회차를 문서 회차로 바꾸지 않는다.
    assert_status_in(session.status, {SessionStatus.CREATED})
    has_audio = db.scalar(select(AudioFile.id).where(AudioFile.session_id == session.id).limit(1)) is not None
    if has_audio or get_row(db, session.id) is not None:
        raise conflict(ErrorCode.INVALID_SESSION_STATE, "이미 자료를 올린 회차입니다. 새 회차에 올려 주세요.")

    # 글자 뽑기만 따로 제한 시간을 둔다. 넘으면 422(파일 문제로 본다). thread 는 강제로 멈추지 못하지만 쪽 수 ·
    # 글자 수 상한(document_text)으로 오래 도는 일을 줄인다.
    try:
        text = run_with_timeout(lambda: extract_text(filename, data), settings.DOCUMENT_TEXT_TIMEOUT_SECONDS)
    except (OperationTimeout, TimeoutError) as error:
        logger.warning("문서 글자 뽑기 제한 시간 초과 session_id=%s", session.id)
        raise APIError(
            ErrorCode.VALIDATION_ERROR,
            "문서를 읽는 데 너무 오래 걸립니다. 파일이 손상됐을 수 있습니다. 다른 형식(.docx · .hwpx · .txt)으로 저장해 올려 주세요.",
            status_code=422,
        ) from error
    file_format = filename.rsplit(".", 1)[-1].lower()

    if settings.AI_PROVIDER == "modeling":
        known = [session.case.child_alias] if session.case and session.case.child_alias else []
        result = _run_ai(session, "fill_note", lambda run: run(text, known_identifiers=known))
        fill_source, fill_model = "AI", result.get("model")
    else:
        try:
            result = load_callable(MODULE, "rule_based_note")(text)
        except ModuleLoadError as error:
            raise _ai_error(ErrorCode.AI_FAILED) from error
        fill_source, fill_model = "HEADINGS", None

    assessment_in = result.get("assessment") or {}
    note_in = result.get("note") or {}

    claim_document_session(db, session)

    row = SessionSourceDocument(
        session_id=session.id,
        filename=(filename or "문서")[:255],
        file_format=file_format,
        text=text,
        char_count=len(text),
        fill_source=fill_source,
        fill_model=fill_model,
        note_draft={key: str(note_in.get(key) or "") for key in NOTE_KEYS},
        followup_draft=None,
        uploaded_by_id=current_user.id,
    )
    db.add(row)
    db.add(
        ConsultationSummary(
            session_id=session.id,
            analysis_id=None,
            overview=str(result.get("overview") or ""),
            key_points=[],
            assessment={key: {"text": str(assessment_in.get(key) or ""), "segment_ids": []} for key in ASSESSMENT_KEYS},
            status=ReviewStatus.DRAFT,
        )
    )
    try:
        db.flush()
    except IntegrityError as error:
        db.rollback()
        raise conflict(ErrorCode.DUPLICATE_RESOURCE, "다른 요청이 먼저 이 회차에 자료를 올렸습니다. 새로고침해 주세요.") from error

    audit_service.record(
        db,
        action=AuditAction.SOURCE_DOCUMENT_UPLOADED,
        entity_type="SessionSourceDocument",
        entity_id=row.id,
        actor_id=current_user.id,
        case_id=session.case_id,
        session_id=session.id,
        detail={
            "format": file_format,
            "char_count": len(text),
            "fill_source": fill_source,
            "filled": sorted([k for k in ASSESSMENT_KEYS if assessment_in.get(k)] + [k for k in NOTE_KEYS if note_in.get(k)]),
        },
    )
    db.commit()
    db.refresh(row)
    return row


def _followup_input(db: Session, session: ConsultationSession, row: SessionSourceDocument) -> Dict[str, Any]:
    """3단계에서 상담사가 저장한 요약 4칸 · 상담 일지(저장 전이면 일지 초안)."""

    summary = db.scalar(select(ConsultationSummary).where(ConsultationSummary.session_id == session.id))
    stored = summary.assessment if summary is not None and isinstance(summary.assessment, dict) else {}
    assessment = {}
    for key in ASSESSMENT_KEYS:
        field = stored.get(key)
        assessment[key] = field.get("text", "") if isinstance(field, dict) else ""
    record = db.scalar(
        select(Document)
        .where(Document.session_id == session.id, Document.doc_type == CONSULTATION_RECORD)
        .order_by(Document.created_at.desc())
        .limit(1)
    )
    return {"assessment": assessment, "note": dict(row.note_draft or {}), "record": record.content if record else ""}


def draft_followups(db: Session, session: ConsultationSession, current_user: User) -> SessionSourceDocument:
    if session.source != SessionSource.DOCUMENT:
        raise conflict(ErrorCode.INVALID_SESSION_STATE, "상담 기록 문서로 만든 회차에서만 쓸 수 있습니다.")
    assert_status_in(session.status, {SessionStatus.AI_REVIEW_REQUIRED, SessionStatus.APPROVED})
    row = require_row(db, session)
    inputs = _followup_input(db, session, row)

    try:
        note_input_text = load_callable(MODULE, "note_input_text")
    except ModuleLoadError as error:
        raise _ai_error(ErrorCode.AI_FAILED) from error
    # 저장한 상담 일지가 있으면 그것을, 없으면 일지 초안 칸을 쓴다.
    text = note_input_text(inputs["assessment"], {} if inputs["record"] else inputs["note"])
    if inputs["record"]:
        text = "\n".join(part for part in (text, f"- 상담 일지:\n{inputs['record']}") if part)
    if not text.strip():
        raise conflict(ErrorCode.INVALID_SESSION_STATE, "3단계 상담 요약 · 상담 일지에 쓴 내용이 없습니다. 먼저 채워 주세요.")

    if settings.AI_PROVIDER == "modeling":
        known = [session.case.child_alias] if session.case and session.case.child_alias else []
        result = _run_ai(session, "draft_followups", lambda run: run(text, known_identifiers=known))
        draft = {"checks": result.get("checks") or [], "questions": result.get("questions") or [], "source": "AI", "model": result.get("model")}
    else:
        draft = {"checks": [], "questions": [], "source": "NONE", "model": None}

    row.followup_draft = {**draft, "generated_at": datetime.now(timezone.utc).isoformat()}
    audit_service.record(
        db,
        action=AuditAction.DOCUMENT_FOLLOWUPS_DRAFTED,
        entity_type="SessionSourceDocument",
        entity_id=row.id,
        actor_id=current_user.id,
        case_id=session.case_id,
        session_id=session.id,
        detail={"source": draft["source"], "checks": len(draft["checks"]), "questions": len(draft["questions"])},
    )
    db.commit()
    db.refresh(row)
    return row
