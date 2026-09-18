# 수정/승인 이력 기록.
#
# detail 에는 상담 원문을 저장하지 않는다. 변경 개수/필드명 등 metadata 만 남긴다.

import uuid
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.core.enums import AuditAction
from app.models.audit_log import AuditLog


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

    return log
