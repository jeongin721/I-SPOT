# 수정/승인 이력 기록.
#
# detail 에는 상담 원문을 저장하지 않는다. 변경 개수/필드명 등 metadata 만 남긴다.
#
# 사례 목록의 기본 순서는 최근 수정순이다(API_CONTRACT 4절). 사례에 걸린 변경을 여기에 기록하면(아래 _NO_CASE_TOUCH 를 뺀
# 모든 action, 성공한 것만) 그 사례의 수정 시각(cases.updated_at)을 커밋 직전에 지금으로 찍는다(2026-11-25).
# 그래서 사례 정보뿐 아니라 회차 · 상담 요약 · 문서 · 추가 질문 · 위험도 판단 · 메모 · 아이 앱 질문 … 을 저장한 사례가 목록 맨 위로 온다.
# 변경을 저장하는 서비스는 지금처럼 record(case_id=…) 만 부르면 된다 — 사례를 따로 건드리지 않는다.

import uuid
from typing import Any, Dict, Optional

from sqlalchemy import event, update
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.enums import AuditAction
from app.models.audit_log import AuditLog
from app.models.base import utcnow
from app.models.case import Case

# 사례를 목록 위로 올리지 않는 기록. 새 action 을 더할 때, 사례 내용이 바뀌지 않는 것(조회 · 내려받기 · 실패)만 여기에 넣는다.
_NO_CASE_TOUCH = frozenset(
    {
        # 조회 · 내려받기
        AuditAction.CASE_PERSONAL_INFO_VIEWED,
        AuditAction.CASE_LIST_PERSONAL_INFO_VIEWED,
        AuditAction.CHILD_APP_FEED_VIEWED,
        AuditAction.DOCBOX_FILE_DOWNLOADED,
        # 사례 내용이 아닌 것(법령 질문)
        AuditAction.LAW_QA_ASKED,
        # 실패한 작업 — 내용이 바뀌지 않았다
        AuditAction.STT_FAILED,
        AuditAction.ANALYSIS_FAILED,
        AuditAction.ANALYSIS_DRAFTS_FAILED,
        # 지운 사례 · 회차 번호 정리 스크립트
        AuditAction.CASE_DELETED,
        AuditAction.SESSION_RENUMBERED,
    }
)

# Session.info 에 '이번 거래에서 수정 시각을 찍을 사례 ID' 를 모아 두는 열쇠.
_TOUCH_KEY = "cases_to_touch"


def record(
    db: Session,
    *,
    action: AuditAction,
    entity_type: str,
    entity_id: Optional[uuid.UUID] = None,
    actor_id: Optional[uuid.UUID] = None,
    case_id: Optional[uuid.UUID] = None,
    session_id: Optional[uuid.UUID] = None,
    detail: Optional[Dict[str, Any]] = None,
    status: str = "SUCCESS",
    error_code: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> AuditLog:
    """
    Audit log 를 추가한다. commit 은 호출 측 transaction 에 맡긴다.

    사례에 걸린 변경이면(case_id 가 있고, 성공했고, _NO_CASE_TOUCH 가 아니면) 그 사례를 커밋 직전에 목록 맨 위로 올린다.
    """

    log = AuditLog(
        actor_id=actor_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        case_id=case_id,
        session_id=session_id,
        detail=detail,
        status=status,
        error_code=error_code,
        ip_address=ip_address,
        user_agent=user_agent,
    )

    db.add(log)

    if case_id is not None and status == "SUCCESS" and action not in _NO_CASE_TOUCH:
        db.info.setdefault(_TOUCH_KEY, set()).add(case_id)

    return log


def _touch_cases_before_commit(db: Session) -> None:
    """이번 거래에서 변경을 기록한 사례의 수정 시각을 찍는다. 기록과 한 거래라 되돌리면 같이 되돌아간다."""

    case_ids = db.info.pop(_TOUCH_KEY, None)

    if not case_ids:
        return

    # 다른 행(회차 · 요약 · 문서 …)을 먼저 다 쓰고 사례 행을 마지막에 잡는다. 요청마다 잠그는 순서가 같아야 같은 사례를
    # 동시에 고치는 두 요청이 서로를 기다리다 멈추지 않는다(PostgreSQL deadlock). 사례가 여럿이면 ID 순서로 잡는다.
    db.flush()
    now = utcnow()

    for case_id in sorted(case_ids, key=str):
        db.execute(
            update(Case)
            .where(Case.id == case_id)
            .values(updated_at=now)
            .execution_options(synchronize_session=False)
        )


def _forget_case_touches(db: Session, previous_transaction: Any) -> None:
    """되돌린 거래의 기록은 올리지 않는다(같은 Session 의 다음 커밋으로 넘어가지 않게)."""

    db.info.pop(_TOUCH_KEY, None)


# 앱 · 스크립트 · 시험이 모두 SessionLocal 로 Session 을 만든다. 모듈을 다시 읽어도 두 번 걸리지 않게 확인하고 건다.
if not event.contains(SessionLocal, "before_commit", _touch_cases_before_commit):
    event.listen(SessionLocal, "before_commit", _touch_cases_before_commit)
    event.listen(SessionLocal, "after_soft_rollback", _forget_case_touches)
