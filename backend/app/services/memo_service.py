# 상담사 메모 서비스(API_CONTRACT 25절, 2026-11-10, 민규 #169 조건).
#
#  - 메모는 쓴 상담사만 읽고 고치고 지운다. 관리자도 남의 메모는 보지 못한다(목록 · 한 건 모두 owner_id 로 거른다 — 남의 것은 404).
#  - 관련 사례는 지금 볼 수 있는 사례만 붙인다(get_case_or_404 — 없으면 404, 남의 사례면 403).
#    담당이 바뀌어 지금 볼 수 없게 된 사례의 메모는 목록에서 빠지고 한 건 읽기 · 고치기 · 지우기도 404 다.
#  - 본문은 pii_crypto.encrypt_memo 로 암호화해 저장한다(묶음 값 = 메모 ID). 풀지 못하면 500 MEMO_UNAVAILABLE(키 이름만 로그).
#  - 본문은 로그 · 감사 기록에 넣지 않는다. 감사 기록은 만들기 · 고치기 · 지우기만, 메모 ID · 사례 ID · 바뀐 칸 이름만 남긴다.

import logging
import uuid
from typing import List, Optional, Tuple

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.core import pii_crypto
from app.core.enums import AuditAction
from app.core.errors import APIError, ErrorCode, not_found
from app.models.case import Case
from app.models.counselor_memo import CounselorMemo
from app.models.user import User
from app.schemas.memo import MemoCreateRequest, MemoResponse, MemoUpdateRequest
from app.services import audit_service
from app.services.access import get_case_or_404

logger = logging.getLogger(__name__)

UNAVAILABLE_MESSAGE = "메모를 읽을 수 없습니다. 관리자에게 알려 주세요."


def _visible(user: User):
    """쓴 사람의 메모 중 사례가 없거나 지금 볼 수 있는 사례의 것."""

    conditions = [CounselorMemo.owner_id == user.id]

    if not user.is_admin:
        conditions.append(or_(CounselorMemo.case_id.is_(None), Case.counselor_id == user.id))

    return conditions


def _base_query():
    return select(CounselorMemo).outerjoin(Case, CounselorMemo.case_id == Case.id)


def _decrypt(row: CounselorMemo) -> str:
    try:
        return pii_crypto.decrypt_memo(row.text_enc, memo_id=row.id)
    except pii_crypto.PersonalInfoCryptoError as error:
        logger.error(
            "메모를 풀지 못했습니다. memo_id=%s key_id=%s reason=%s",
            row.id,
            pii_crypto.key_id_for_log(row.text_enc),
            type(error).__name__,
        )
        raise APIError(ErrorCode.MEMO_UNAVAILABLE, UNAVAILABLE_MESSAGE, status_code=500) from error


def to_response(row: CounselorMemo) -> MemoResponse:
    return MemoResponse(
        id=row.id,
        case_id=row.case_id,
        child_alias=row.case.child_alias if row.case else None,
        text=_decrypt(row),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def list_memos(
    db: Session, user: User, *, offset: int, limit: int, case_id: Optional[uuid.UUID] = None
) -> Tuple[List[CounselorMemo], int]:
    conditions = _visible(user)

    if case_id is not None:
        conditions.append(CounselorMemo.case_id == case_id)

    total = db.scalar(select(func.count()).select_from(CounselorMemo).outerjoin(Case, CounselorMemo.case_id == Case.id).where(*conditions)) or 0
    rows = db.scalars(
        _base_query()
        .options(selectinload(CounselorMemo.case))
        .where(*conditions)
        .order_by(CounselorMemo.created_at.desc(), CounselorMemo.id.desc())
        .offset(offset)
        .limit(limit)
    ).all()

    return list(rows), int(total)


def get_memo_or_404(db: Session, memo_id: uuid.UUID, user: User) -> CounselorMemo:
    row = db.scalar(_base_query().options(selectinload(CounselorMemo.case)).where(CounselorMemo.id == memo_id, *_visible(user)))

    if row is None:
        raise not_found(ErrorCode.NOT_FOUND, "메모를 찾을 수 없습니다.")

    return row


def create_memo(db: Session, user: User, payload: MemoCreateRequest) -> CounselorMemo:
    if payload.case_id is not None:
        get_case_or_404(db, payload.case_id, user)

    memo_id = uuid.uuid4()
    row = CounselorMemo(
        id=memo_id,
        owner_id=user.id,
        case_id=payload.case_id,
        text_enc=pii_crypto.encrypt_memo(payload.text, memo_id=memo_id),
    )

    db.add(row)
    db.flush()
    audit_service.record(
        db,
        action=AuditAction.MEMO_CREATED,
        entity_type="CounselorMemo",
        entity_id=row.id,
        actor_id=user.id,
        case_id=row.case_id,
    )
    db.commit()

    return get_memo_or_404(db, row.id, user)


def update_memo(db: Session, user: User, row: CounselorMemo, payload: MemoUpdateRequest) -> CounselorMemo:
    sent = payload.model_fields_set
    changed: List[str] = []

    if "case_id" in sent and payload.case_id != row.case_id:
        if payload.case_id is not None:
            get_case_or_404(db, payload.case_id, user)
        row.case_id = payload.case_id
        changed.append("case_id")

    if "text" in sent and payload.text is not None:
        row.text_enc = pii_crypto.encrypt_memo(payload.text, memo_id=row.id)
        changed.append("text")

    if changed:
        audit_service.record(
            db,
            action=AuditAction.MEMO_UPDATED,
            entity_type="CounselorMemo",
            entity_id=row.id,
            actor_id=user.id,
            case_id=row.case_id,
            detail={"fields": changed},
        )
    db.commit()
    db.expire(row)

    return get_memo_or_404(db, row.id, user)


def delete_memo(db: Session, user: User, row: CounselorMemo) -> None:
    audit_service.record(
        db,
        action=AuditAction.MEMO_DELETED,
        entity_type="CounselorMemo",
        entity_id=row.id,
        actor_id=user.id,
        case_id=row.case_id,
    )
    db.delete(row)
    db.commit()
