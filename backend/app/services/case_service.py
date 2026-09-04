# Case CRUD.

import uuid
from datetime import datetime, timezone
from typing import List, Optional, Tuple

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.core.enums import AuditAction, CaseStatus, UserRole
from app.core.errors import ErrorCode, bad_request, conflict, forbidden, not_found
from app.models.case import Case
from app.models.session import ConsultationSession
from app.models.user import User
from app.schemas.case import CaseCreateRequest, CaseUpdateRequest
from app.services import audit_service
from app.services.access import ensure_case_access

_CASE_NUMBER_MAX_RETRY = 5


def _generate_case_number(db: Session) -> str:
    year = datetime.now(timezone.utc).year
    prefix = f"C-{year}-"

    count = db.scalar(
        select(func.count())
        .select_from(Case)
        .where(Case.case_number.like(f"{prefix}%"))
    )

    return f"{prefix}{(count or 0) + 1:04d}"


def _resolve_counselor(
    db: Session,
    current_user: User,
    counselor_id: Optional[uuid.UUID],
) -> uuid.UUID:
    """담당 상담사 지정은 관리자만 가능하다."""

    if counselor_id is None or counselor_id == current_user.id:
        return current_user.id

    if not current_user.is_admin:
        raise forbidden("담당 상담사 지정은 관리자만 할 수 있습니다.")

    counselor = db.scalar(select(User).where(User.id == counselor_id))

    if counselor is None:
        raise not_found(ErrorCode.USER_NOT_FOUND, "담당 상담사를 찾을 수 없습니다.")

    if not counselor.is_active:
        raise bad_request(
            ErrorCode.VALIDATION_ERROR,
            "비활성화된 사용자를 담당 상담사로 지정할 수 없습니다.",
        )

    if counselor.role not in (UserRole.COUNSELOR, UserRole.ADMIN):
        raise bad_request(
            ErrorCode.VALIDATION_ERROR,
            "상담사 또는 관리자만 담당자로 지정할 수 있습니다.",
        )

    return counselor.id


def create_case(db: Session, current_user: User, payload: CaseCreateRequest) -> Case:
    counselor_id = _resolve_counselor(db, current_user, payload.counselor_id)

    for attempt in range(_CASE_NUMBER_MAX_RETRY):
        case_number = payload.case_number or _generate_case_number(db)

        case = Case(
            case_number=case_number,
            title=payload.title,
            child_alias=payload.child_alias,
            child_birth_year=payload.child_birth_year,
            child_gender=payload.child_gender,
            notes=payload.notes,
            status=CaseStatus.ACTIVE,
            counselor_id=counselor_id,
            created_by_id=current_user.id,
        )

        db.add(case)

        try:
            db.flush()
        except IntegrityError as error:
            db.rollback()

            # 직접 지정한 case_number 가 중복이면 재시도해도 의미가 없다.
            if payload.case_number or attempt == _CASE_NUMBER_MAX_RETRY - 1:
                raise conflict(
                    ErrorCode.DUPLICATE_RESOURCE,
                    "이미 존재하는 사례 번호입니다.",
                ) from error

            continue

        audit_service.record(
            db,
            action=AuditAction.CASE_CREATED,
            entity_type="Case",
            entity_id=case.id,
            actor_id=current_user.id,
            case_id=case.id,
            detail={"case_number": case.case_number},
        )

        db.commit()
        db.refresh(case)

        return case

    raise conflict(ErrorCode.DUPLICATE_RESOURCE, "사례 번호 생성에 실패했습니다.")


def list_cases(
    db: Session,
    current_user: User,
    *,
    offset: int,
    limit: int,
    status: Optional[CaseStatus] = None,
    search: Optional[str] = None,
) -> Tuple[List[Tuple[Case, Optional[datetime]]], int]:
    conditions = []

    # counselor 는 담당 Case 만 조회한다.
    if not current_user.is_admin:
        conditions.append(Case.counselor_id == current_user.id)

    if status is not None:
        conditions.append(Case.status == status)

    if search:
        pattern = f"%{search.strip()}%"
        conditions.append(
            Case.title.ilike(pattern)
            | Case.case_number.ilike(pattern)
            | Case.child_alias.ilike(pattern)
        )

    total = db.scalar(
        select(func.count()).select_from(Case).where(*conditions)
    ) or 0

    # Case List 화면(S03_UI_UX.md S02)이 "최근 상담일"을 표시하므로
    # 목록 조회에서 함께 계산한다. Frontend 가 Case 별로 Session 을
    # 다시 조회하는 N+1 을 막기 위한 것이다.
    rows = db.execute(
        select(Case, _last_session_at_subquery())
        .where(*conditions)
        .order_by(Case.created_at.desc())
        .offset(offset)
        .limit(limit)
    ).all()

    cases = [(row[0], row[1]) for row in rows]

    return cases, total


def _last_session_at_subquery():
    """
    Case 의 가장 최근 상담 일시.

    consulted_at 이 기록되지 않은 Session 은 생성 시각으로 대체한다.
    """

    return (
        select(
            func.max(
                func.coalesce(
                    ConsultationSession.consulted_at,
                    ConsultationSession.created_at,
                )
            )
        )
        .where(ConsultationSession.case_id == Case.id)
        .correlate(Case)
        .scalar_subquery()
    )


def get_case_detail(
    db: Session,
    case_id: uuid.UUID,
    current_user: User,
) -> Tuple[Case, int, Optional[datetime]]:
    row = db.execute(
        select(Case, _last_session_at_subquery())
        .options(selectinload(Case.counselor))
        .where(Case.id == case_id)
    ).first()

    if row is None:
        raise not_found(ErrorCode.CASE_NOT_FOUND, "사례를 찾을 수 없습니다.")

    case, last_session_at = row[0], row[1]

    ensure_case_access(current_user, case)

    session_count = db.scalar(
        select(func.count())
        .select_from(ConsultationSession)
        .where(ConsultationSession.case_id == case.id)
    ) or 0

    return case, session_count, last_session_at


def update_case(
    db: Session,
    case: Case,
    current_user: User,
    payload: CaseUpdateRequest,
) -> Case:
    changed_fields = []

    data = payload.model_dump(exclude_unset=True)

    if "counselor_id" in data and data["counselor_id"] is not None:
        new_counselor_id = _resolve_counselor(db, current_user, data["counselor_id"])

        if new_counselor_id != case.counselor_id:
            case.counselor_id = new_counselor_id
            changed_fields.append("counselor_id")

        data.pop("counselor_id")

    for field in ("title", "child_alias", "child_birth_year", "child_gender", "notes", "status"):
        if field in data:
            setattr(case, field, data[field])
            changed_fields.append(field)

    if changed_fields:
        audit_service.record(
            db,
            action=AuditAction.CASE_UPDATED,
            entity_type="Case",
            entity_id=case.id,
            actor_id=current_user.id,
            case_id=case.id,
            detail={"changed_fields": changed_fields},
        )

    db.commit()
    db.refresh(case)

    return case


def delete_case(db: Session, case: Case, current_user: User) -> None:
    """사례 삭제는 관리자만 가능하다."""

    if not current_user.is_admin:
        raise forbidden("사례 삭제는 관리자만 할 수 있습니다.")

    audit_service.record(
        db,
        action=AuditAction.CASE_DELETED,
        entity_type="Case",
        entity_id=case.id,
        actor_id=current_user.id,
        case_id=case.id,
        detail={"case_number": case.case_number},
    )

    db.delete(case)
    db.commit()
