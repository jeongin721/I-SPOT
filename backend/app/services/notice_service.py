# 사내 공지사항(API_CONTRACT 28절, 2026-11-20). 읽기는 로그인한 누구나, 쓰고 고치고 지우기는 관리자만(라우터에서 막는다).
# 감사 기록에는 공지 ID · 중요 여부 · 바뀐 칸 이름만 남긴다(제목 · 본문은 넣지 않는다).

import uuid
from typing import List

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.enums import AuditAction
from app.core.errors import ErrorCode, not_found
from app.models.notice import Notice
from app.models.user import User
from app.schemas.notice import NoticeCreateRequest, NoticeResponse, NoticeUpdateRequest
from app.services import audit_service

#: 한 번에 주는 공지 수(최신부터).
NOTICE_LIST_MAX = 50


def to_response(row: Notice) -> NoticeResponse:
    return NoticeResponse(
        id=row.id,
        title=row.title,
        body=row.body,
        important=row.important,
        team=row.team,
        author_name=row.author.name if row.author else None,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def list_notices(db: Session, limit: int) -> List[Notice]:
    return list(
        db.scalars(
            select(Notice)
            .options(selectinload(Notice.author))
            .order_by(Notice.created_at.desc(), Notice.id.desc())
            .limit(min(max(limit, 1), NOTICE_LIST_MAX))
        )
    )


def get_notice_or_404(db: Session, notice_id: uuid.UUID) -> Notice:
    row = db.scalar(select(Notice).options(selectinload(Notice.author)).where(Notice.id == notice_id))

    if row is None:
        raise not_found(ErrorCode.NOT_FOUND, "공지를 찾을 수 없습니다.")

    return row


def create_notice(db: Session, user: User, payload: NoticeCreateRequest) -> Notice:
    row = Notice(title=payload.title, body=payload.body, important=payload.important, team=payload.team, author_id=user.id)
    db.add(row)
    db.flush()
    audit_service.record(
        db,
        action=AuditAction.NOTICE_CREATED,
        entity_type="Notice",
        entity_id=row.id,
        actor_id=user.id,
        detail={"important": row.important},
    )
    db.commit()

    return get_notice_or_404(db, row.id)


def update_notice(db: Session, user: User, row: Notice, payload: NoticeUpdateRequest) -> Notice:
    changes = payload.model_dump(exclude_unset=True)

    for key, value in changes.items():
        setattr(row, key, value)

    if changes:
        audit_service.record(
            db,
            action=AuditAction.NOTICE_UPDATED,
            entity_type="Notice",
            entity_id=row.id,
            actor_id=user.id,
            detail={"fields": sorted(changes)},
        )
        db.commit()

    return get_notice_or_404(db, row.id)


def delete_notice(db: Session, user: User, row: Notice) -> None:
    audit_service.record(
        db,
        action=AuditAction.NOTICE_DELETED,
        entity_type="Notice",
        entity_id=row.id,
        actor_id=user.id,
    )
    db.delete(row)
    db.commit()
