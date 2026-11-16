# 고령자 생활 · 정서 영역 변화(2026-11-16, API_CONTRACT 27절 '영역 변화').
#
# 회차마다 식사 · 수면 · 외출 · 사회활동 · 정서 다섯 영역의 이번 상태를 담당자가 확정하고(AI · 규칙 초안은 분석 결과
# senior.domain_drafts), 앞 회차에서 확정한 기록과 견준다. '견줄 앞 기록' 은 이 회차보다 회차 번호가 작은 회차 가운데
# 그 영역 이야기가 있던(NOT_MENTIONED 가 아닌) 가장 최근 확정 기록이다. 좋아짐 · 나빠짐 평가는 두지 않는다.

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.enums import AnalysisStatus, AuditAction, CareDomain, DomainChange, NextCheckOrigin
from app.core.errors import ErrorCode, bad_request, conflict
from app.models.case import Case
from app.models.senior import CareDomainNote
from app.models.session import ConsultationSession
from app.models.user import User
from app.schemas.senior import (
    DOMAIN_LABELS,
    CareDomainDraft,
    CareDomainNoteResponse,
    CareDomainRow,
    CareDomainsSaveRequest,
    CareDomainTimeline,
    CareDomainTimelineEntry,
    CareDomainTimelineResponse,
    PreviousDomainNote,
    RecentDomainChange,
    SessionCareDomainsResponse,
)
from app.services import analysis_service, audit_service, transcript_service
from app.services.senior_service import _local_date, ensure_senior

DOMAINS = list(CareDomain)


def _date(session: ConsultationSession) -> str:
    return _local_date(session.consulted_at) if session.consulted_at else ""


def _notes_with_sessions(db: Session, case_id: uuid.UUID) -> List[Tuple[CareDomainNote, ConsultationSession]]:
    return list(
        db.execute(
            select(CareDomainNote, ConsultationSession)
            .join(ConsultationSession, ConsultationSession.id == CareDomainNote.session_id)
            .where(CareDomainNote.case_id == case_id)
            .order_by(ConsultationSession.session_number.asc())
        ).tuples()
    )


def _previous(
    rows: List[Tuple[CareDomainNote, ConsultationSession]], session_number: int
) -> Dict[CareDomain, Tuple[CareDomainNote, ConsultationSession]]:
    """영역마다 이 회차보다 앞선, 이야기가 있던 가장 최근 확정 기록."""

    found: Dict[CareDomain, Tuple[CareDomainNote, ConsultationSession]] = {}
    for note, session in rows:  # 회차 순이라 뒤에 오는 것이 덮어쓴다
        if session.session_number < session_number and note.change != DomainChange.NOT_MENTIONED and note.text:
            found[note.domain] = (note, session)
    return found


def previous_domains_input(db: Session, session: ConsultationSession) -> List[Dict[str, Any]]:
    """회차 통합 요약(senior_session_llm)에 넘길 앞 기록 — care_domains 모듈의 previous_domains 모양."""

    previous = _previous(_notes_with_sessions(db, session.case_id), session.session_number)
    return [
        {
            "domain": domain.value,
            "text": note.text,
            "session_number": prev_session.session_number,
            "date": _date(prev_session),
        }
        for domain, (note, prev_session) in previous.items()
    ]


def _drafts(db: Session, session: ConsultationSession) -> Dict[str, Dict[str, Any]]:
    analysis = analysis_service.get_latest_analysis(db, session.id)
    if analysis is None or analysis.status != AnalysisStatus.COMPLETED or not isinstance(analysis.result, dict):
        return {}
    senior = analysis.result.get("senior")
    if not isinstance(senior, dict):
        return {}
    return {
        item["domain"]: item
        for item in senior.get("domain_drafts") or []
        if isinstance(item, dict) and item.get("domain") in CareDomain.__members__
    }


def get_session_domains(db: Session, session: ConsultationSession) -> SessionCareDomainsResponse:
    ensure_senior(session.case)
    rows = _notes_with_sessions(db, session.case_id)
    previous = _previous(rows, session.session_number)
    saved = {note.domain: note for note, item in rows if item.id == session.id}
    drafts = _drafts(db, session)

    result = []
    for domain in DOMAINS:
        prev = previous.get(domain)
        draft = drafts.get(domain.value)
        result.append(
            CareDomainRow(
                domain=domain,
                label=DOMAIN_LABELS[domain],
                previous=PreviousDomainNote(
                    session_id=prev[1].id,
                    session_number=prev[1].session_number,
                    date=_date(prev[1]),
                    text=prev[0].text or "",
                )
                if prev
                else None,
                draft=CareDomainDraft.model_validate(draft) if draft else None,
                saved=CareDomainNoteResponse.model_validate(saved[domain]) if domain in saved else None,
            )
        )
    return SessionCareDomainsResponse(
        session_id=session.id,
        session_number=session.session_number,
        domains=result,
        confirmed=len(saved) == len(DOMAINS),
    )


def _check_segments(db: Session, session: ConsultationSession, payload: CareDomainsSaveRequest) -> None:
    wanted = {seg for item in payload.items for seg in item.segment_ids}
    if not wanted:
        return
    transcript = transcript_service.get_latest_transcript(db, session.id)
    known = {segment.segment_id for segment in transcript.segments} if transcript is not None else set()
    if not wanted <= known:
        raise bad_request(ErrorCode.VALIDATION_ERROR, "근거로 단 발화 가운데 이 회차 녹취에 없는 것이 있습니다.")


def save_session_domains(
    db: Session, session: ConsultationSession, current_user: User, payload: CareDomainsSaveRequest
) -> SessionCareDomainsResponse:
    case: Case = session.case
    ensure_senior(case)
    _check_segments(db, session, payload)
    previous = _previous(_notes_with_sessions(db, case.id), session.session_number)

    for item in payload.items:
        has_previous = item.domain in previous
        label = DOMAIN_LABELS[item.domain]
        if item.change in (DomainChange.SIMILAR, DomainChange.CHANGED) and not has_previous:
            raise bad_request(ErrorCode.VALIDATION_ERROR, f"{label}: 견줄 앞 기록이 없어 '처음 기록' 으로만 저장할 수 있습니다.")
        if item.change == DomainChange.NEW and has_previous:
            raise bad_request(ErrorCode.VALIDATION_ERROR, f"{label}: 앞 기록이 있어 '비슷함' 이나 '달라짐' 으로 골라 주세요.")

    existing = {
        note.domain: note
        for note in db.scalars(
            select(CareDomainNote).where(CareDomainNote.session_id == session.id).with_for_update()
        )
    }
    now = datetime.now(timezone.utc)
    for item in payload.items:
        note = existing.get(item.domain)
        if note is None:
            note = CareDomainNote(case_id=case.id, session_id=session.id, domain=item.domain)
            db.add(note)
        note.text = item.text
        note.change = item.change
        note.change_note = item.change_note if item.change == DomainChange.CHANGED else None
        note.segment_ids = item.segment_ids
        note.origin = item.origin
        note.edited = item.edited and item.origin != NextCheckOrigin.COUNSELOR
        prev = previous.get(item.domain)
        note.compared_session_id = prev[1].id if prev and item.change != DomainChange.NEW else None
        note.confirmed_by_id = current_user.id
        note.confirmed_at = now

    changes: Dict[str, int] = {}
    for item in payload.items:
        changes[item.change.value] = changes.get(item.change.value, 0) + 1
    audit_service.record(
        db,
        action=AuditAction.CARE_DOMAINS_SAVED,
        entity_type="ConsultationSession",
        entity_id=session.id,
        actor_id=current_user.id,
        case_id=case.id,
        session_id=session.id,
        detail={
            "domains": [item.domain.value for item in payload.items],
            "changes": changes,
            "edited": sum(1 for item in payload.items if item.edited and item.origin != NextCheckOrigin.COUNSELOR),
        },
    )
    try:
        db.commit()
    except IntegrityError as error:  # 같은 회차를 두 곳에서 동시에 처음 저장
        db.rollback()
        raise conflict(ErrorCode.DUPLICATE_RESOURCE, "다른 곳에서 먼저 저장했습니다. 다시 불러와 주세요.") from error
    return get_session_domains(db, session)


def notes_by_session(db: Session, case_id: uuid.UUID) -> Dict[uuid.UUID, List[CareDomainNoteResponse]]:
    """상담 이력 조회용 — 회차별 확정 기록(영역 순서)."""

    order = {domain: index for index, domain in enumerate(DOMAINS)}
    grouped: Dict[uuid.UUID, List[CareDomainNote]] = {}
    for note, session in _notes_with_sessions(db, case_id):
        grouped.setdefault(session.id, []).append(note)
    return {
        session_id: [CareDomainNoteResponse.model_validate(n) for n in sorted(notes, key=lambda n: order[n.domain])]
        for session_id, notes in grouped.items()
    }


def recent_changes(db: Session, case_id: uuid.UUID) -> List[RecentDomainChange]:
    """영역을 확정한 가장 최근 회차에서 '달라짐' 인 것(방문 전 브리핑)."""

    rows = _notes_with_sessions(db, case_id)
    if not rows:
        return []
    latest = max(session.session_number for _, session in rows)
    order = {domain: index for index, domain in enumerate(DOMAINS)}
    picked = sorted(
        (
            (note, session)
            for note, session in rows
            if session.session_number == latest and note.change == DomainChange.CHANGED
        ),
        key=lambda pair: order[pair[0].domain],
    )
    return [
        RecentDomainChange(
            domain=note.domain,
            label=DOMAIN_LABELS[note.domain],
            session_id=session.id,
            session_number=session.session_number,
            date=_date(session),
            text=note.text,
            change_note=note.change_note,
        )
        for note, session in picked
    ]


def get_timeline(db: Session, case: Case) -> CareDomainTimelineResponse:
    """영역별로 회차 순(오래된 것부터) 확정 기록 — 이력 비교 화면."""

    ensure_senior(case)
    entries: Dict[CareDomain, List[CareDomainTimelineEntry]] = {domain: [] for domain in DOMAINS}
    for note, session in _notes_with_sessions(db, case.id):
        entries[note.domain].append(
            CareDomainTimelineEntry(
                session_id=session.id,
                session_number=session.session_number,
                date=_date(session),
                text=note.text,
                change=note.change,
                change_note=note.change_note,
                segment_ids=list(note.segment_ids or []),
            )
        )
    return CareDomainTimelineResponse(
        case_id=case.id,
        domains=[
            CareDomainTimeline(domain=domain, label=DOMAIN_LABELS[domain], entries=entries[domain]) for domain in DOMAINS
        ],
    )
