# 사례 개인 식별 정보(암호화 저장) 서비스. API_CONTRACT 4절 '개인 식별 정보', specs case-personal-info-encryption.
#
# - 저장: 칸마다 pii_crypto.encrypt_text(묶음 값 = 사례 ID + 칸 이름). 묶음 칸(사례관리대상자 · 면접대상자 ·
#   가족관계 · 건강정도)은 JSON 을 통째로 암호화한다. 저장할 때마다 모든 칸을 다시 쓰고(읽은 값과 같아도 UPDATE 에 넣는다),
#   읽는 행을 잠근다(PostgreSQL FOR UPDATE — 같은 사례의 저장은 차례로 돈다). 겹친 저장이 섞이지 않고 감사 칸 이름도 맞게.
# - 권한은 호출부가 먼저 본다(get_case_or_404 — 상담사는 담당 사례만, 관리자는 전체).
# - 복호화해서 내준 때마다 열람 기록을 남긴다: 한 사례 CASE_PERSONAL_INFO_VIEWED, 목록 CASE_LIST_PERSONAL_INFO_VIEWED 1줄.
# - 값은 로그 · 감사 detail · 오류 문구에 넣지 않는다. 칸 이름 · 사례 ID · 키 이름만 남긴다.

import json
import logging
import uuid
from typing import Any, Dict, List, Optional

from sqlalchemy import ColumnElement, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.core import pii_crypto
from app.core.enums import AuditAction
from app.core.errors import APIError, ErrorCode, conflict
from app.core.pii_crypto import PersonalInfoCryptoError
from app.models.case import Case
from app.models.case_personal_info import ENCRYPTED_FIELDS, CasePersonalInfo
from app.models.user import User
from app.schemas.case_personal_info import PersonalInfoRequest, PersonalInfoResponse
from app.services import audit_service

logger = logging.getLogger(__name__)

UNAVAILABLE_MESSAGE = "개인 식별 정보를 풀 수 없습니다. 관리자에게 문의해 주세요."

# 글자 그대로 담는 칸. 나머지는 JSON 이다.
_TEXT_FIELDS = ("child_name", "child_birth_date")

# 풀지 못한 저장 값. 새 값과 견주면 늘 '바뀜' 이 되어 덮어쓴다(고칠 길을 남긴다).
_UNREADABLE = object()

# 저장마다 UPDATE 에 늘 싣는 칸. SQLAlchemy 는 읽은 때와 같은 값(None → None, 같은 이름 색인)을 UPDATE 에서 빼므로
# 겹친 저장에서 앞 요청 값이 남는다 — flag_modified 로 넣는다(Codex #127 재검증 R2).
_REWRITTEN_COLUMNS = (*(f"{field}_enc" for field in ENCRYPTED_FIELDS), "child_name_index", "updated_by_id")


def _is_blank(value: Any) -> bool:
    if value is None or value == "" or value == [] or value == {}:
        return True

    if isinstance(value, dict):
        return all(_is_blank(item) for item in value.values())

    return False


def _plain_values(payload: PersonalInfoRequest) -> Dict[str, Optional[str]]:
    """요청 → 칸별 평문 글자(비었으면 None). 같은 값은 늘 같은 글자가 되게 JSON 키를 정렬한다."""

    data = payload.model_dump(mode="json")
    values: Dict[str, Optional[str]] = {}

    for field in ENCRYPTED_FIELDS:
        value = data.get(field)

        if _is_blank(value):
            values[field] = None
        elif field in _TEXT_FIELDS:
            values[field] = value
        else:
            values[field] = json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)

    return values


def _unavailable(row: CasePersonalInfo, field: str, error: Exception) -> APIError:
    logger.error(
        "개인 식별 정보를 풀지 못했습니다. case_id=%s field=%s key_id=%s reason=%s",
        row.case_id,
        field,
        pii_crypto.key_id_of(getattr(row, f"{field}_enc") or ""),
        type(error).__name__,
    )

    return APIError(ErrorCode.PERSONAL_INFO_UNAVAILABLE, UNAVAILABLE_MESSAGE, status_code=500)


def _decrypt(row: CasePersonalInfo, field: str) -> Optional[str]:
    token = getattr(row, f"{field}_enc")

    if token is None:
        return None

    return pii_crypto.decrypt_text(token, case_id=row.case_id, field=field)


def _decrypt_all(row: Optional[CasePersonalInfo]) -> Dict[str, Optional[str]]:
    """칸별 평문. 하나라도 풀지 못하면 500 PERSONAL_INFO_UNAVAILABLE(일부만 보여 주지 않는다)."""

    plain: Dict[str, Optional[str]] = {field: None for field in ENCRYPTED_FIELDS}

    if row is None:
        return plain

    for field in ENCRYPTED_FIELDS:
        try:
            plain[field] = _decrypt(row, field)
        except PersonalInfoCryptoError as error:
            raise _unavailable(row, field, error) from error

    return plain


def _to_response(row: Optional[CasePersonalInfo], plain: Dict[str, Optional[str]]) -> PersonalInfoResponse:
    data: Dict[str, Any] = {}

    for field, text in plain.items():
        if text is not None:
            data[field] = text if field in _TEXT_FIELDS else json.loads(text)

    return PersonalInfoResponse(
        registered=bool(data),
        updated_at=row.updated_at if row is not None and data else None,
        **data,
    )


def get_personal_info(db: Session, case: Case, current_user: User) -> PersonalInfoResponse:
    """복호화한 값. 부를 때마다 열람 기록 1줄(값 없이 채워진 칸 이름만)."""

    row = db.get(CasePersonalInfo, case.id)
    plain = _decrypt_all(row)
    response = _to_response(row, plain)

    audit_service.record(
        db,
        action=AuditAction.CASE_PERSONAL_INFO_VIEWED,
        entity_type="CasePersonalInfo",
        entity_id=case.id,
        actor_id=current_user.id,
        case_id=case.id,
        detail={"fields": [field for field, text in plain.items() if text is not None]},
    )
    db.commit()

    return response


def apply_personal_info(
    db: Session,
    case: Case,
    current_user: User,
    payload: PersonalInfoRequest,
) -> List[str]:
    """보낸 값으로 통째로 바꾼다(commit 은 호출부). 바뀐 칸 이름을 돌려준다.

    POST /cases(사례와 한 거래)와 PUT /cases/{id}/personal-info 가 함께 쓴다. case.id 가 있어야 한다(flush 뒤).

    행이 있으면 바뀐 칸만이 아니라 **모든 칸(빈 칸 · 이름 색인 · 생년월일의 출생연도 포함)을 다시 쓴다.** 두 요청이 같은 옛 값을
    읽고 저장이 겹쳐도 나중에 커밋한 요청의 본문이 통째로 남는다(Codex #127 R2 · 재검증 R2). 바뀐 칸은 감사 기록에만 쓴다.
    읽는 행은 잠근다(PostgreSQL FOR UPDATE): 같은 사례의 다음 저장은 앞 저장이 커밋된 뒤의 값을 읽어, 감사의 바뀐 칸이
    실제 바뀜과 맞는다(재검증 N1). SQLite(개발 · 시험)는 행 잠금이 없어 겹친 저장의 감사 칸 이름이 빠질 수 있다 — 값은 위대로 맞다.
    같은 사례에 처음 저장이 겹쳐 다른 요청이 먼저 행을 만들었으면 409 DUPLICATE_RESOURCE(회차 전체 판단 저장과 같은 방식).
    """

    case_id = case.id
    new = _plain_values(payload)
    row = db.get(CasePersonalInfo, case_id, populate_existing=True, with_for_update=True)
    old: Dict[str, Any] = {field: None for field in ENCRYPTED_FIELDS}

    if row is not None:
        for field in ENCRYPTED_FIELDS:
            try:
                old[field] = _decrypt(row, field)
            except PersonalInfoCryptoError:
                old[field] = _UNREADABLE

    changed = [field for field in ENCRYPTED_FIELDS if old[field] != new[field]]
    creating = row is None

    if creating and not changed:
        # 저장 전 사례에 빈 값을 보냄 — 행을 만들지 않는다.
        return []

    if creating:
        row = CasePersonalInfo(case_id=case_id)
        db.add(row)

    for field in ENCRYPTED_FIELDS:
        value = new[field]
        setattr(
            row,
            f"{field}_enc",
            None if value is None else pii_crypto.encrypt_text(value, case_id=case_id, field=field),
        )

    row.child_name_index = pii_crypto.name_index(new["child_name"]) if new["child_name"] else None
    row.updated_by_id = current_user.id

    if not creating:
        for column in _REWRITTEN_COLUMNS:
            flag_modified(row, column)

    if creating:
        try:
            db.flush()
        except IntegrityError as error:
            db.rollback()

            # 그사이 다른 요청이 이 사례의 행을 먼저 만들었으면 500 대신 409 로 알린다. 그 밖의 무결성 오류는 그대로 올린다.
            if db.get(CasePersonalInfo, case_id) is None:
                raise

            raise conflict(
                ErrorCode.DUPLICATE_RESOURCE,
                "다른 요청이 먼저 이 사례의 개인 식별 정보를 저장했습니다. 새로고침 후 다시 저장해 주세요.",
            ) from error

    # 생년월일이 있으면 사례의 출생연도(평문, 나이대 · 통계용)를 늘 그 해로 맞춘다. 날짜가 바뀌지 않았어도 맞춘다 —
    # 그사이 출생연도만 따로 고쳤으면 같은 날짜를 다시 저장해 되돌릴 수 있게(Codex #127 R3). 생년월일이 우선이다.
    # 읽은 해와 같아도 UPDATE 에 넣는다 — 겹친 저장에서 앞 요청의 해가 남지 않게(재검증 R2).
    if payload.child_birth_date is not None:
        year = payload.child_birth_date.year

        if case.child_birth_year != year:
            changed.append("child_birth_year")

        case.child_birth_year = year
        flag_modified(case, "child_birth_year")

    if not changed:
        return []

    audit_service.record(
        db,
        action=AuditAction.CASE_PERSONAL_INFO_UPDATED,
        entity_type="CasePersonalInfo",
        entity_id=case.id,
        actor_id=current_user.id,
        case_id=case.id,
        detail={"changed_fields": changed},
    )

    return changed


def put_personal_info(
    db: Session,
    case: Case,
    current_user: User,
    payload: PersonalInfoRequest,
) -> PersonalInfoResponse:
    case_id = case.id
    apply_personal_info(db, case, current_user, payload)
    db.commit()

    row = db.get(CasePersonalInfo, case_id)

    # 보낸 값이 곧 이 요청이 저장한 값이다(모든 칸을 다시 씀). 다시 풀지 않는다.
    return _to_response(row, _plain_values(payload))


def child_names(db: Session, current_user: User, case_ids: List[uuid.UUID]) -> Dict[uuid.UUID, str]:
    """목록용 아동 실명(GET /cases?with_child_name=true). 실명이 있는 사례가 있으면 열람 기록 1줄.

    풀지 못한 값은 그 줄만 이름 없이 둔다(목록 전체를 막지 않는다). 권한은 목록 조회가 이미 걸렀다.
    """

    if not case_ids:
        return {}

    rows = db.scalars(
        select(CasePersonalInfo).where(
            CasePersonalInfo.case_id.in_(case_ids),
            CasePersonalInfo.child_name_enc.is_not(None),
        )
    ).all()

    names: Dict[uuid.UUID, str] = {}

    for row in rows:
        try:
            names[row.case_id] = _decrypt(row, "child_name")
        except PersonalInfoCryptoError as error:
            _unavailable(row, "child_name", error)

    if names:
        shown = [case_id for case_id in case_ids if case_id in names]
        audit_service.record(
            db,
            action=AuditAction.CASE_LIST_PERSONAL_INFO_VIEWED,
            entity_type="Case",
            actor_id=current_user.id,
            detail={"case_ids": [str(case_id) for case_id in shown], "count": len(shown)},
        )
        db.commit()

    return names


def name_search_condition(term: str) -> Optional[ColumnElement[bool]]:
    """검색어가 아동 실명과 정확히 같은(공백 무시) 사례. 검색어가 공백뿐이면 None."""

    index = pii_crypto.name_index(term)

    if index is None:
        return None

    return Case.id.in_(
        select(CasePersonalInfo.case_id).where(CasePersonalInfo.child_name_index == index)
    )
