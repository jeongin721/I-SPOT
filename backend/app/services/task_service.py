# 처리 대기 업무 목록.
#
# 업무는 따로 저장하지 않는다. Session 상태가 곧 "지금 누구 차례인가"의 정답이므로
# 조회할 때마다 상태에서 계산한다. 따로 저장하면 상태 기계와 어긋날 수 있다.
#
# 정렬 기준은 "이 상태로 기다리기 시작한 시각"이다. 새 컬럼 없이 이미 저장되는
# 시각(STT·AI 완료, 원문 확정, 음성 업로드)에서 계산하고, 정렬·페이지는 DB 에서 한다.

import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

from sqlalchemy import and_, case, func, not_, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.enums import CaseStatus, SessionStatus, TaskType
from app.core.errors import forbidden
from app.models.audio import AudioFile
from app.models.case import Case
from app.models.session import ConsultationSession
from app.models.transcript import Transcript
from app.models.user import User
from app.schemas.task import TaskItem, TaskSummary
from app.services import session_service

TASK_BY_STATUS: Dict[SessionStatus, TaskType] = {
    SessionStatus.CREATED: TaskType.UPLOAD_AUDIO,
    SessionStatus.AUDIO_UPLOADED: TaskType.REQUEST_STT,
    SessionStatus.STT_REVIEW_REQUIRED: TaskType.REVIEW_TRANSCRIPT,
    SessionStatus.STT_CONFIRMED: TaskType.REQUEST_ANALYSIS,
    SessionStatus.AI_REVIEW_REQUIRED: TaskType.REVIEW_ANALYSIS,
    SessionStatus.STT_FAILED: TaskType.RETRY_STT,
    SessionStatus.AI_FAILED: TaskType.RETRY_ANALYSIS,
}

STATUS_BY_TASK: Dict[TaskType, SessionStatus] = {
    task: status for status, task in TASK_BY_STATUS.items()
}

_RETRY_TASKS = {TaskType.RETRY_STT, TaskType.RETRY_ANALYSIS}

# 시스템이 처리하는 중인 상태. 업무는 아니지만, 멈춘 것은 조회 때 실패로 마감한다.
_PROCESSING_STATUSES = (SessionStatus.STT_PROCESSING, SessionStatus.AI_PROCESSING)


# =========================================================
# 조회 조건
# =========================================================

def _scope(current_user: User, counselor_id: Optional[uuid.UUID]) -> list:
    """
    볼 수 있는 범위.

    Session.counselor_id 는 Session 을 만들 때 사례 담당자를 복사한 값이라, 사례 담당자를
    바꿔도 따라 바뀌지 않는다. 접근 권한(access.ensure_case_access)과 같이 사례 기준으로 거른다.
    """

    if not current_user.is_admin:
        if counselor_id is not None and counselor_id != current_user.id:
            raise forbidden("다른 상담사의 업무는 관리자만 볼 수 있습니다.")

        return [Case.counselor_id == current_user.id]

    if counselor_id is not None:
        return [Case.counselor_id == counselor_id]

    return []


def _task_conditions(now: datetime) -> list:
    return [
        Case.status == CaseStatus.ACTIVE,
        ConsultationSession.status.in_(list(TASK_BY_STATUS)),
        # 상담일이 아직 오지 않은 회기는 녹음할 차례가 아니다.
        # consulted_at 이 비어 있으면 비교 결과가 NULL 이 되어 행이 빠지므로 먼저 걸러 낸다.
        not_(
            and_(
                ConsultationSession.status == SessionStatus.CREATED,
                ConsultationSession.consulted_at.is_not(None),
                ConsultationSession.consulted_at > now,
            )
        ),
    ]


def _later(first, second):
    """
    두 시각 중 늦은 값. 한쪽이 비어 있으면 다른 쪽.

    GREATEST(PostgreSQL) · max(SQLite) 처럼 DB 마다 함수 이름이 달라 CASE 로 쓴다.
    """

    return case(
        (first.is_(None), second),
        (second.is_(None), first),
        (first > second, first),
        else_=second,
    )


def _waiting_since():
    """Session 이 지금 상태로 기다리기 시작한 시각."""

    session = ConsultationSession

    latest_audio_at = (
        select(func.max(AudioFile.created_at))
        .where(AudioFile.session_id == session.id)
        .correlate(session)
        .scalar_subquery()
    )
    latest_confirmed_at = (
        select(func.max(Transcript.confirmed_at))
        .where(Transcript.session_id == session.id)
        .correlate(session)
        .scalar_subquery()
    )

    started = case(
        (
            session.status == SessionStatus.CREATED,
            func.coalesce(session.consulted_at, session.created_at),
        ),
        (session.status == SessionStatus.AUDIO_UPLOADED, latest_audio_at),
        # 확정 후 다시 고치려고 되돌렸으면 확정 시각부터 기다린 것으로 본다.
        # 원래 STT 완료 시각을 쓰면 방금 되돌린 업무가 오래된 것처럼 보인다.
        (
            session.status == SessionStatus.STT_REVIEW_REQUIRED,
            _later(session.stt_completed_at, latest_confirmed_at),
        ),
        # AI 분석이 실패해 원문 확정 상태로 되돌렸으면 실패 시각부터.
        (
            session.status == SessionStatus.STT_CONFIRMED,
            _later(latest_confirmed_at, session.ai_completed_at),
        ),
        (session.status == SessionStatus.AI_REVIEW_REQUIRED, session.ai_completed_at),
        # 실패 시각도 같은 칸에 기록된다(_fail_stt · _fail_analysis · expire_stale_processing).
        (session.status == SessionStatus.STT_FAILED, session.stt_completed_at),
        (session.status == SessionStatus.AI_FAILED, session.ai_completed_at),
    )

    # 시각이 비어 있는 옛 데이터는 마지막 수정 시각으로 대신한다.
    return func.coalesce(started, session.updated_at)


def _expire_stale_processing(db: Session, scope: list) -> None:
    """
    멈춘 처리 중 Session 을 먼저 실패로 마감해 재시도 업무로 보이게 한다.

    Session 상세 · 원문 · 분석 조회와 같은 방식이다. 제한 시간 안의 작업은 건드리지 않는다.
    """

    processing = db.scalars(
        select(ConsultationSession)
        .join(Case, Case.id == ConsultationSession.case_id)
        .where(ConsultationSession.status.in_(_PROCESSING_STATUSES), *scope)
    ).all()

    for session in processing:
        session_service.expire_stale_processing(db, session)


def _overdue_cutoff(now: datetime) -> datetime:
    return now - timedelta(hours=settings.TASK_OVERDUE_HOURS)


def _as_utc(value: datetime) -> datetime:
    # SQLite 는 시간대 없이 돌려준다. 저장 값은 UTC 다.
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)

    return value.astimezone(timezone.utc)


# =========================================================
# 목록 · 요약
# =========================================================

def list_tasks(
    db: Session,
    current_user: User,
    *,
    offset: int,
    limit: int,
    task_type: Optional[TaskType] = None,
    overdue_only: bool = False,
    counselor_id: Optional[uuid.UUID] = None,
) -> Tuple[List[TaskItem], int]:
    scope = _scope(current_user, counselor_id)
    _expire_stale_processing(db, scope)

    now = datetime.now(timezone.utc)
    cutoff = _overdue_cutoff(now)

    conditions = [*_task_conditions(now), *scope]

    if task_type is not None:
        conditions.append(ConsultationSession.status == STATUS_BY_TASK[task_type])

    tasks = (
        select(
            ConsultationSession.id.label("session_id"),
            ConsultationSession.case_id,
            Case.case_number,
            Case.child_alias,
            ConsultationSession.session_number,
            ConsultationSession.title.label("session_title"),
            ConsultationSession.status.label("session_status"),
            _waiting_since().label("waiting_since"),
            Case.counselor_id,
            User.name.label("counselor_name"),
            ConsultationSession.last_error_code,
        )
        .join(Case, Case.id == ConsultationSession.case_id)
        # 상담사 계정이 지워져도 업무는 보여야 하므로 outer join 한다(사례 목록과 같음).
        .outerjoin(User, User.id == Case.counselor_id)
        .where(*conditions)
        .subquery()
    )

    query = select(tasks)

    if overdue_only:
        query = query.where(tasks.c.waiting_since < cutoff)

    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0

    rows = db.execute(
        query.order_by(
            tasks.c.waiting_since,
            tasks.c.case_number,
            tasks.c.session_number,
        )
        .offset(offset)
        .limit(limit)
    ).all()

    return [_to_item(row, cutoff) for row in rows], total


def _to_item(row, cutoff: datetime) -> TaskItem:
    status = SessionStatus(row.session_status)
    task_type = TASK_BY_STATUS[status]
    waiting_since = _as_utc(row.waiting_since)

    return TaskItem(
        session_id=row.session_id,
        case_id=row.case_id,
        case_number=row.case_number,
        child_alias=row.child_alias,
        session_number=row.session_number,
        session_title=row.session_title,
        session_status=status,
        task_type=task_type,
        waiting_since=waiting_since,
        is_overdue=waiting_since < cutoff,
        counselor_id=row.counselor_id,
        counselor_name=row.counselor_name,
        last_error_code=row.last_error_code if task_type in _RETRY_TASKS else None,
    )


def summarize_tasks(
    db: Session,
    current_user: User,
    *,
    counselor_id: Optional[uuid.UUID] = None,
) -> TaskSummary:
    scope = _scope(current_user, counselor_id)
    _expire_stale_processing(db, scope)

    now = datetime.now(timezone.utc)
    cutoff = _overdue_cutoff(now)

    overdue = case((_waiting_since() < cutoff, 1), else_=0)

    rows = db.execute(
        select(
            ConsultationSession.status,
            func.count(),
            func.sum(overdue),
        )
        .join(Case, Case.id == ConsultationSession.case_id)
        .where(*_task_conditions(now), *scope)
        .group_by(ConsultationSession.status)
    ).all()

    by_type = {task_type: 0 for task_type in TaskType}
    total = 0
    overdue_total = 0

    for status, count, overdue_count in rows:
        by_type[TASK_BY_STATUS[SessionStatus(status)]] = count
        total += count
        overdue_total += int(overdue_count or 0)

    return TaskSummary(total=total, overdue=overdue_total, by_type=by_type)
