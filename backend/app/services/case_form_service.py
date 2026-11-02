# 기관 서식 작성 · 임시 저장 · 확정(API_CONTRACT 22절, 2026-11-02).
#
# 사례 · 서식 종류마다 임시 저장 차수는 하나뿐이다. 만들기(POST)는 다음 차수를 새로 열고, 임시 저장 차수가 이미 있으면 409.
# 확정한 차수는 고칠 수 없다(409) — 다시 쓰려면 다음 차수를 만든다. 사례 권한은 access.get_case_or_404 로 본다.

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.enums import AuditAction, CaseFormType, ReviewStatus
from app.core.errors import APIError, ErrorCode, conflict, not_found
from app.models.case import Case
from app.models.case_form import CaseForm
from app.models.user import User
from app.schemas.case_form import CaseFormCreateRequest, CaseFormResponse, form_totals, normalize_values
from app.services import audit_service


def _values(form_type: CaseFormType, raw: Dict[str, Any]) -> Dict[str, Any]:
    try:
        return normalize_values(form_type, raw)
    except ValidationError as error:
        # 사유에는 받은 값을 넣지 않는다(소견 글이 오류 응답 · 로그에 실리지 않게). 어느 칸인지만 알린다.
        fields = sorted({".".join(str(part) for part in item["loc"]) for item in error.errors()})
        raise APIError(
            ErrorCode.VALIDATION_ERROR,
            "서식 칸 값이 맞지 않습니다.",
            status_code=422,
            details={"fields": fields[:20]},
        ) from None


def to_response(row: CaseForm) -> CaseFormResponse:
    return CaseFormResponse(
        id=row.id,
        case_id=row.case_id,
        form_type=row.form_type,
        round=row.round,
        status=row.status,
        values=row.values or {},
        totals=form_totals(row.form_type, row.values or {}),
        created_by_id=row.created_by_id,
        updated_by_id=row.updated_by_id,
        confirmed_by_id=row.confirmed_by_id,
        confirmed_at=row.confirmed_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def list_forms(db: Session, case: Case, form_type: Optional[CaseFormType] = None) -> List[CaseForm]:
    """그 사례의 서식 기록. 종류 → 차수가 큰 것(최근)부터."""

    query = select(CaseForm).where(CaseForm.case_id == case.id)
    if form_type is not None:
        query = query.where(CaseForm.form_type == form_type)
    rows = list(db.scalars(query))
    rows.sort(key=lambda row: (row.form_type.value, -row.round))
    return rows


def get_form_or_404(db: Session, case: Case, form_id: uuid.UUID, *, edit: bool = False) -> CaseForm:
    """edit=True 면 행을 잠그고 읽는다(임시 저장 · 확정이 겹쳐도 확정 뒤 값이 바뀌지 않게). SQLite 시험에서는 잠금이 무시된다."""

    query = select(CaseForm).where(CaseForm.id == form_id, CaseForm.case_id == case.id)
    row = db.scalar(query.with_for_update() if edit else query)
    if row is None:
        raise not_found(ErrorCode.NOT_FOUND, "서식 기록을 찾을 수 없습니다.")
    return row


def _audit(db: Session, action: AuditAction, user: User, row: CaseForm) -> None:
    audit_service.record(
        db,
        action=action,
        entity_type="CaseForm",
        entity_id=row.id,
        actor_id=user.id,
        case_id=row.case_id,
        detail={"form_type": row.form_type.value, "round": row.round},
    )


def create_form(db: Session, user: User, case: Case, payload: CaseFormCreateRequest) -> CaseForm:
    values = _values(payload.form_type, payload.values)
    draft = db.scalar(
        select(CaseForm.id).where(
            CaseForm.case_id == case.id,
            CaseForm.form_type == payload.form_type,
            CaseForm.status == ReviewStatus.DRAFT,
        )
    )
    if draft is not None:
        raise conflict(
            ErrorCode.DUPLICATE_RESOURCE,
            "임시 저장한 서식이 이미 있습니다. 그 서식을 이어서 고쳐 주세요.",
        )

    last = db.scalar(
        select(func.max(CaseForm.round)).where(CaseForm.case_id == case.id, CaseForm.form_type == payload.form_type)
    )
    row = CaseForm(
        case_id=case.id,
        form_type=payload.form_type,
        round=(last or 0) + 1,
        status=ReviewStatus.DRAFT,
        values=values,
        created_by_id=user.id,
        updated_by_id=user.id,
    )
    db.add(row)
    try:
        db.flush()
    except IntegrityError:
        # 같은 순간 다른 창에서 같은 차수를 먼저 만들었다(사례 · 종류 · 차수 unique).
        db.rollback()
        raise conflict(
            ErrorCode.DUPLICATE_RESOURCE,
            "다른 창에서 같은 서식을 먼저 만들었습니다. 다시 열어 이어서 고쳐 주세요.",
        ) from None
    _audit(db, AuditAction.CASE_FORM_CREATED, user, row)
    db.commit()
    db.refresh(row)
    return row


def _ensure_draft(row: CaseForm) -> None:
    if row.status == ReviewStatus.APPROVED:
        raise conflict(
            ErrorCode.ALREADY_APPROVED,
            "확정한 서식은 고칠 수 없습니다. 다음 차수로 새로 작성해 주세요.",
        )


def update_form(db: Session, user: User, row: CaseForm, raw: Dict[str, Any]) -> CaseForm:
    _ensure_draft(row)
    row.values = _values(row.form_type, raw)
    row.updated_by_id = user.id
    _audit(db, AuditAction.CASE_FORM_UPDATED, user, row)
    db.commit()
    db.refresh(row)
    return row


def confirm_form(db: Session, user: User, row: CaseForm) -> CaseForm:
    _ensure_draft(row)
    row.status = ReviewStatus.APPROVED
    row.confirmed_by_id = user.id
    row.confirmed_at = datetime.now(timezone.utc)
    _audit(db, AuditAction.CASE_FORM_CONFIRMED, user, row)
    db.commit()
    db.refresh(row)
    return row
