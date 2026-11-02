# 사례 개인 식별 정보(암호화 저장) 서비스. API_CONTRACT 4절 '개인 식별 정보', specs case-personal-info-encryption.
#
# - 저장: 칸마다 pii_crypto.encrypt_text(묶음 값 = 사례 ID + 칸 이름). 묶음 칸(사례관리대상자 · 면접대상자 ·
#   가족관계 · 건강정도)은 JSON 을 통째로 암호화한다. 저장할 때마다 모든 칸을 다시 쓰고(읽은 값과 같아도 UPDATE 에 넣는다),
#   읽는 행을 잠근다(PostgreSQL FOR UPDATE — 같은 사례의 저장은 차례로 돈다). 겹친 저장이 섞이지 않고 감사 칸 이름도 맞게.
# - 권한은 호출부가 먼저 본다(get_case_or_404 — 상담사는 담당 사례만, 관리자는 전체).
# - 복호화해서 내준 때마다 열람 기록을 남긴다: 한 사례 CASE_PERSONAL_INFO_VIEWED, 목록 CASE_LIST_PERSONAL_INFO_VIEWED 1줄.
# - 값은 로그 · 감사 detail · 오류 문구에 넣지 않는다. 칸 이름 · 사례 ID · 키 이름만 남긴다.
# - 외부 AI 로 보내기 전 이름 가리기(known_identifiers)에 넘길 등록 이름도 여기서 만든다(known_identifiers, specs 7절).
#   메모리에서만 쓰고 저장하지 않는다. 사람에게 내주는 값이 아니라(가린 토큰만 밖으로 나간다) 열람 기록은 남기지 않는다.

import json
import logging
import unicodedata
import uuid
from typing import Any, Dict, Iterable, List, Optional

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
        pii_crypto.key_id_for_log(getattr(row, f"{field}_enc") or ""),
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


# =========================================================
# 외부 AI 가리기에 넘길 등록 이름(known_identifiers)
# =========================================================

# 이름이 적히는 칸. 생년월일은 이름이 아니라 넘기지 않는다.
_NAME_FIELDS = ("child_name", "target_person", "interviewee", "family_members", "health")

# 흔한 두 글자 성. '선우진' 처럼 성이 한 글자인지 두 글자인지 모르면 두 경우의 이름을 모두 가린다.
_COMPOUND_SURNAMES = ("남궁", "황보", "제갈", "사공", "선우", "서문", "독고", "동방")

# 이름 칸에 사람 이름 대신 적기 쉬운 낱말. 가리기 목록에 넣으면 상담 원문의 같은 낱말(엄마 · 아빠 …)이 모두 가려져
# 외부 AI 가 내용을 알 수 없게 된다. privacy_gateway 의 _SWEEP_TARGET_BLOCKLIST(아동 · 상담사 · 보호자)를 포함한다.
_NOT_NAMES = frozenset(
    {"아동", "상담사", "보호자", "엄마", "아빠", "어머니", "아버지", "할머니", "할아버지", "누나", "언니", "오빠", "동생", "미상", "모름", "없음"}
)


def _names_in(field: str, text: str) -> List[Any]:
    """칸 평문(아동 이름은 글자, 나머지는 JSON) → 그 칸에 적힌 이름. 모양이 틀린 JSON 은 ValueError."""

    if field == "child_name":
        return [text]

    value = json.loads(text)

    if field in ("target_person", "interviewee"):
        return [value.get("name")] if isinstance(value, dict) else []

    if field == "health":
        return [value.get("subject_name")] if isinstance(value, dict) else []

    return [item.get("name") for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _is_hangul(text: str) -> bool:
    return all("가" <= char <= "힣" for char in text)


def _variants(name: str) -> List[str]:
    """이름 하나 → 가릴 글자: 전체 이름 + 성 뺀 이름(남는 이름이 두 글자 이상일 때만, specs 7절).

    한 글자는 뺀다 — 다른 낱말 속 같은 글자까지 가린다(privacy_gateway 의 정확 매칭도 두 글자부터 본다).
    이름 칸에 적은 관계말(_NOT_NAMES)도 뺀다. 한글 이름을 '한 가람' 처럼 띄어 적었으면 붙여 쓴 '한가람' 도 가린다.
    가리기는 글자를 그대로 견주므로 적은 그대로의 표기(두 칸 공백 등)와 한글을 자모로 풀어 쓴 표기(NFD)도 함께 넣는다
    (Codex #138 H1 — 원문이 등록과 같은 표기인데 정리한 표기만 넣어 통과했다).
    """

    raw = name.strip()
    name = " ".join(unicodedata.normalize("NFC", raw).split())

    if len(name) < 2 or name in _NOT_NAMES:
        return []

    variants = [raw, name]
    compact = name.replace(" ", "")

    if _is_hangul(compact):
        if compact != name:
            variants.append(compact)

        if len(compact) >= 3:
            given = [compact[1:]] + ([compact[2:]] if compact[:2] in _COMPOUND_SURNAMES else [])
            variants += [part for part in given if len(part) >= 2 and part not in _NOT_NAMES]

    variants += [unicodedata.normalize("NFD", variant) for variant in variants]

    return list(dict.fromkeys(variants))


def known_identifiers(db: Session, case_id: uuid.UUID, *, extra: Iterable[Optional[str]] = ()) -> List[str]:
    """외부 AI 로 보내기 전 가리기(privacy_gateway 의 known_identifiers)에 넘길 그 사례의 등록 이름.

    아동 · 사례관리대상자 · 면접대상자 · 가족관계 표 · 건강정도 대상자 이름과 그 성 뺀 이름이다. extra(예: 사례 별칭)는 앞뒤 공백만
    떼고 더한다. 긴 것부터 늘어놓는다 — 가리기가 목록 순서대로 바꾸므로 '서윤' 을 '김서윤' 보다 먼저 바꾸면 '김' 이 남는다.

    메모리에서만 쓴다: 돌려준 값을 로그 · 감사 detail · DB · 오류 문구에 넣지 않는다. 열람 기록도 남기지 않는다(모듈 머리 주석).
    어떤 실패도 올리지 않는다. 풀지 못한 칸 · 모양이 틀린 칸은 빼고 경고만(칸 이름 · 키 이름 · 예외 종류, 값 없이) 남기고,
    DB 오류 같은 나머지 실패는 등록 이름 없이(extra 만) 돌려준다 — 실명 없이 지금처럼 가린다. DB 오류 뒤에는 거래를 되돌리므로
    (PostgreSQL 은 SQL 오류 뒤 거래가 깨진다) 부르기 전에 쓴 변경이 없어야 한다. 지금 부르는 곳(분석 · 다음 상담 체크리스트 ·
    종결 요약)은 모두 읽기만 한 뒤 부른다.
    """

    names: List[str] = []

    try:
        row = db.get(CasePersonalInfo, case_id)

        for field in _NAME_FIELDS if row is not None else ():
            try:
                text = _decrypt(row, field)
                found = _names_in(field, text) if text is not None else []
            except (PersonalInfoCryptoError, ValueError) as error:
                logger.warning(
                    "가리기에 넘길 등록 이름을 풀지 못해 그 칸은 빼고 보냅니다. case_id=%s field=%s key_id=%s reason=%s",
                    case_id,
                    field,
                    pii_crypto.key_id_for_log(getattr(row, f"{field}_enc") or ""),
                    type(error).__name__,
                )
                continue

            for name in found:
                if isinstance(name, str):
                    names += _variants(name)
    except Exception as error:  # noqa: BLE001 — 등록 이름은 가리기를 돕는 보조 입력이라 AI 작업을 멈추지 않는다
        logger.warning(
            "가리기에 넘길 등록 이름을 읽지 못해 등록 이름 없이 보냅니다. case_id=%s reason=%s",
            case_id,
            type(error).__name__,
        )
        names = []

        try:
            db.rollback()
        except Exception as rollback_error:  # noqa: BLE001
            logger.warning("등록 이름을 읽다 깨진 거래를 되돌리지 못했습니다. reason=%s", type(rollback_error).__name__)

    names += [value.strip() for value in extra if isinstance(value, str) and value.strip()]

    return sorted(dict.fromkeys(names), key=len, reverse=True)
