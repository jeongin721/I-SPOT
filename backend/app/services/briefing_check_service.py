# 상담 전 브리핑 '확인할 사항' 체크 서비스(API_CONTRACT 26절, 2026-11-11, 민규 다음 작업 1번).
#
#  - 회차마다 한 행(session_briefing_checks)에 확인함으로 표시한 문장 목록을 둔다. 확인 사항 목록이 저장 전(AI 초안)이어도 된다.
#  - 한 번에 문장 하나를 켜고 끈다. 행을 잠그고(PostgreSQL FOR UPDATE) 바꿔서 웹 · 폰이 동시에 눌러도 다른 쪽 표시를 지우지 않는다.
#  - 화면이 지금 보이는 문장 목록(visible)을 같이 보내면, 거기 없는 옛 문장(목록을 고쳐 사라진 줄)의 체크를 지운다. 그래도 상한(60)에
#    닿으면 가장 오래 전에 켠 것을 밀어낸다 — 지금 보이는 줄을 켤 때 422 가 나지 않게(민규 #176 1).
#  - 볼 수 있는 회차만(get_session_or_404 — 담당 상담사 · 관리자). 회차 상태는 따지지 않는다(브리핑은 승인 뒤에도 본다).
#  - 감사 기록에는 켬 · 끔과 개수만 남기고 문장은 넣지 않는다(확인 사항은 아동 진술을 이어받을 수 있다).

import uuid
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.enums import AuditAction
from app.models.briefing_check import BRIEFING_CHECKS_MAX, SessionBriefingChecks
from app.models.session import ConsultationSession
from app.models.user import User
from app.schemas.briefing_check import BriefingCheckToggleRequest, BriefingChecksResponse
from app.services import audit_service


def get_row(db: Session, session_id: uuid.UUID, *, lock: bool = False) -> Optional[SessionBriefingChecks]:
    query = select(SessionBriefingChecks).where(SessionBriefingChecks.session_id == session_id)

    if lock:
        query = query.with_for_update()

    return db.scalar(query)


def to_response(session_id: uuid.UUID, row: Optional[SessionBriefingChecks]) -> BriefingChecksResponse:
    return BriefingChecksResponse(
        session_id=session_id,
        checked=list(row.checked or []) if row else [],
        updated_at=row.updated_at if row else None,
        updated_by_id=row.updated_by_id if row else None,
    )


def toggle(db: Session, session: ConsultationSession, user: User, payload: BriefingCheckToggleRequest) -> Optional[SessionBriefingChecks]:
    for attempt in range(2):
        row = get_row(db, session.id, lock=True)
        before: List[str] = list(row.checked or []) if row else []
        current = before

        if payload.visible is not None:
            shown = set(payload.visible) | {payload.text}
            current = [text for text in current if text in shown]

        if payload.checked and payload.text not in current:
            # 상한에 닿으면 가장 오래 전에 켠 것을 밀어낸다.
            while len(current) >= BRIEFING_CHECKS_MAX:
                current = current[1:]
            current = current + [payload.text]
        elif not payload.checked and payload.text in current:
            current = [text for text in current if text != payload.text]

        if current == before:
            db.rollback()
            return row

        if row is None:
            row = SessionBriefingChecks(session_id=session.id, checked=current, updated_by_id=user.id)
            db.add(row)
            try:
                db.flush()
            except IntegrityError:
                # 같은 회차에 다른 요청이 먼저 첫 행을 만들었다. 다시 읽어 그 행에 더한다.
                db.rollback()
                if attempt == 0:
                    continue
                raise
        else:
            row.checked = current
            row.updated_by_id = user.id

        audit_service.record(
            db,
            action=AuditAction.BRIEFING_CHECK_UPDATED,
            entity_type="SessionBriefingChecks",
            entity_id=row.id,
            actor_id=user.id,
            case_id=session.case_id,
            session_id=session.id,
            detail={"checked": payload.checked, "count": len(current)},
        )
        db.commit()
        db.refresh(row)

        return row

    return get_row(db, session.id)
