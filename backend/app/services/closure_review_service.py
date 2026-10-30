# 종결 검토 요약 · 보고서(API_CONTRACT 4절 closure-summary, 2026-10-30).
#
# 만들기(POST): 종결 검토에 등록한 사례의 승인 완료 회차 요약(상담원 확정 4칸)과 회차별 AI 관련 신호를 모아
#  - AI_PROVIDER=modeling 이면 ai/modeling/abuse/closure_summary_llm.generate_closure_summary(마스킹 → LLM → 검사)로 AI 초안,
#  - 아니면 rule_based_summary(LLM 없이 4칸 묶음, AI 생성 아님)로 만든다.
# 동기 응답이고 CLOSURE_SUMMARY_TIMEOUT_SECONDS 를 넘으면 504. 실패 문구에는 원문 · 예외 문구를 넣지 않는다(종류로 코드만).
# 다시 만들면 요약 문장 key 가 바뀌므로 확인 체크 · 고친 문장은 비운다. 보고서 칸(상담원이 쓴 글 · 날짜)은 남긴다.
# 감사 기록에는 수 · 출처만 남긴다(요약 문장은 아동 진술을 이어받아 넣지 않는다).

import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.adapters.module_loader import ModuleLoadError, load_callable
from app.core.concurrency import OperationTimeout, run_with_timeout
from app.core.config import settings
from app.core.enums import AuditAction, ReviewStatus, SessionStatus
from app.core.errors import APIError, ErrorCode, conflict
from app.models.case import Case
from app.models.closure_review import CaseClosureReview
from app.models.session import ConsultationSession
from app.models.summary import ConsultationSummary
from app.models.user import User
from app.schemas.closure_review import ClosureReport, ClosureSummaryResponse, ClosureSummarySaveRequest
from app.services import audit_service
from app.services.signal_history_service import build_signal_history

logger = logging.getLogger(__name__)

MODULE = "ai.modeling.abuse.closure_summary_llm"
ASSESSMENT_KEYS = ("safety_risks", "strengths_resources", "safety_changes", "desired_changes")
TYPE_SHORT = {"PHYSICAL": "신체", "EMOTIONAL": "정서", "SEXUAL": "성", "NEGLECT": "방임"}

_ERRORS = {
    ErrorCode.AI_TIMEOUT: (504, "종결 요약이 제한 시간 안에 끝나지 않았습니다. 잠시 후 다시 시도해 주세요."),
    ErrorCode.AI_INVALID_OUTPUT: (502, "AI 가 종결 요약을 만들지 못했습니다. 다시 시도해 주세요."),
    ErrorCode.AI_FAILED: (502, "종결 요약을 만들지 못했습니다. 잠시 후 다시 시도해 주세요."),
}


def _ai_error(code: ErrorCode) -> APIError:
    status, message = _ERRORS[code]
    return APIError(code, message, status_code=status)


def get_row(db: Session, case_id) -> Optional[CaseClosureReview]:
    return db.scalar(select(CaseClosureReview).where(CaseClosureReview.case_id == case_id))


def to_response(case: Case, row: Optional[CaseClosureReview]) -> ClosureSummaryResponse:
    return ClosureSummaryResponse(
        case_id=case.id,
        summary=row.summary if row else None,
        checks=dict(row.checks or {}) if row else {},
        edits=dict(row.edits or {}) if row else {},
        report=ClosureReport(**(row.report or {})) if row else ClosureReport(),
        updated_at=row.updated_at if row else None,
    )


def _approved_sessions(db: Session, case: Case) -> List[Dict[str, Any]]:
    """승인 완료 회차(번호 순)의 확정 요약 4칸과 AI 관련 신호(유형 짧은 이름)."""

    sessions = list(
        db.scalars(
            select(ConsultationSession)
            .where(ConsultationSession.case_id == case.id, ConsultationSession.status == SessionStatus.APPROVED)
            .order_by(ConsultationSession.session_number.asc())
        )
    )
    if not sessions:
        return []

    summaries = {
        summary.session_id: summary
        for summary in db.scalars(
            select(ConsultationSummary).where(
                ConsultationSummary.session_id.in_([session.id for session in sessions]),
                ConsultationSummary.status == ReviewStatus.APPROVED,
            )
        )
    }
    signals = {
        row.session_id: [TYPE_SHORT[item.abuse_type.value] for item in row.types if item.detected is True]
        for row in build_signal_history(db, case).sessions
    }

    result = []
    for session in sessions:
        stored = summaries.get(session.id)
        assessment = stored.assessment if stored is not None and isinstance(stored.assessment, dict) else {}
        texts = {}
        for key in ASSESSMENT_KEYS:
            field = assessment.get(key)
            text = field.get("text") if isinstance(field, dict) else None
            if isinstance(text, str) and text.strip():
                texts[key] = text.strip()
        result.append(
            {
                "number": session.session_number,
                "date": session.consulted_at.date().isoformat() if session.consulted_at else "",
                "assessment": texts,
                "signals": signals.get(session.id, []),
            }
        )
    return result


def _with_keys(groups: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [
        {
            "title": group["title"],
            "items": [{"key": f"{gi}-{ii}", **item} for ii, item in enumerate(group["items"])],
        }
        for gi, group in enumerate(groups)
    ]


def generate(db: Session, case: Case, current_user: User) -> CaseClosureReview:
    if case.closure_review_at is None:
        raise conflict(ErrorCode.INVALID_CASE_STATE, "종결 검토에 등록한 사례만 요약을 만들 수 있습니다.")

    sessions = _approved_sessions(db, case)
    if not any(session["assessment"] for session in sessions):
        raise conflict(ErrorCode.INVALID_CASE_STATE, "승인 완료한 회차 요약이 없습니다. 회차를 승인한 뒤 다시 시도해 주세요.")

    use_ai = settings.AI_PROVIDER == "modeling"
    started = time.monotonic()
    try:
        if use_ai:
            deadline = time.monotonic() + settings.CLOSURE_SUMMARY_TIMEOUT_SECONDS
            run = load_callable(MODULE, "generate_closure_summary")
            result = run_with_timeout(
                lambda: run(sessions, known_identifiers=[case.child_alias], deadline=deadline),
                settings.CLOSURE_SUMMARY_TIMEOUT_SECONDS,
            )
        else:
            result = load_callable(MODULE, "rule_based_summary")(sessions)
    except (OperationTimeout, TimeoutError) as error:
        raise _ai_error(ErrorCode.AI_TIMEOUT) from error
    except ModuleLoadError as error:
        logger.warning("종결 요약 모듈을 불러오지 못했습니다. case_id=%s", case.id)
        raise _ai_error(ErrorCode.AI_FAILED) from error
    except Exception as error:  # noqa: BLE001 — 문구에 원문이 섞일 수 있어 종류 이름만 남긴다
        code = ErrorCode.AI_INVALID_OUTPUT if type(error).__name__ == "ClosureSummaryOutputError" else ErrorCode.AI_FAILED
        logger.warning("종결 요약 실패 case_id=%s error=%s", case.id, type(error).__name__)
        raise _ai_error(code) from error

    summary = {
        "source": "AI" if use_ai else "APPROVED_SUMMARIES",
        "model": result.get("model") if use_ai else None,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sessions": [session["number"] for session in sessions],
        "groups": _with_keys(result.get("groups") or []),
        "report": result.get("report") or {},
    }
    row = get_row(db, case.id)
    if row is None:
        row = CaseClosureReview(case_id=case.id, summary=summary, checks={}, edits={}, report={}, updated_by_id=current_user.id)
        db.add(row)
        try:
            db.flush()
        except IntegrityError as error:
            db.rollback()
            raise conflict(ErrorCode.DUPLICATE_RESOURCE, "다른 요청이 먼저 종결 요약을 만들었습니다. 새로고침해 주세요.") from error
    else:
        row.summary = summary
        row.checks = {}
        row.edits = {}
        row.updated_by_id = current_user.id

    audit_service.record(
        db,
        action=AuditAction.CLOSURE_SUMMARY_GENERATED,
        entity_type="CaseClosureReview",
        entity_id=row.id,
        actor_id=current_user.id,
        case_id=case.id,
        detail={
            "source": summary["source"],
            "session_count": len(sessions),
            "item_count": sum(len(group["items"]) for group in summary["groups"]),
            "seconds": round(time.monotonic() - started, 1),
        },
    )
    db.commit()
    db.refresh(row)
    return row


def save(db: Session, case: Case, current_user: User, payload: ClosureSummarySaveRequest) -> CaseClosureReview:
    row = get_row(db, case.id)
    keys = {item["key"] for group in ((row.summary or {}).get("groups") or []) for item in group["items"]} if row else set()

    for field in (payload.checks, payload.edits):
        if field is not None and not set(field) <= keys:
            raise APIError(ErrorCode.VALIDATION_ERROR, "요약에 없는 문장입니다. 새로고침 후 다시 저장해 주세요.", status_code=422)

    if row is None:
        row = CaseClosureReview(case_id=case.id, summary=None, checks={}, edits={}, report={}, updated_by_id=current_user.id)
        db.add(row)

    if payload.checks is not None:
        row.checks = {**(row.checks or {}), **payload.checks}
    if payload.edits is not None:
        merged = {**(row.edits or {})}
        for key, text in payload.edits.items():
            text = " ".join(text.split()) if text.strip() else ""
            if text:
                merged[key] = text
            else:
                merged.pop(key, None)
        row.edits = merged
    if payload.report is not None:
        sent = payload.report.model_dump(mode="json", exclude_unset=True)
        row.report = {**(row.report or {}), **sent}
    row.updated_by_id = current_user.id

    audit_service.record(
        db,
        action=AuditAction.CLOSURE_SUMMARY_UPDATED,
        entity_type="CaseClosureReview",
        entity_id=row.id,
        actor_id=current_user.id,
        case_id=case.id,
        detail={
            "checks": len(payload.checks or {}),
            "edits": len(payload.edits or {}),
            "report_fields": sorted((payload.report.model_dump(exclude_unset=True) if payload.report else {}).keys()),
        },
    )
    db.commit()
    db.refresh(row)
    return row
