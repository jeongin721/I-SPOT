# 개인 식별 정보 키 바꾸기 script. 서버에서만 실행한다(backend/README.md '개인 식별 정보 키').
#
# 순서:
#   1) 새 키를 PII_ENCRYPTION_KEYS 맨 앞에 넣고(옛 키는 뒤에 남김) 서버를 다시 띄운다 — 새로 저장하는 값은 새 키로 간다.
#   2) 이 script 로 옛 키로 만든 값을 모두 새 키(맨 앞 키)로 다시 암호화한다.
#   3) 종료 코드가 0(풀지 못한 사례 · 겹쳐 못 바꾼 사례 모두 0)이면 옛 키를 설정에서 뺀다. 1 이면 다시 돌린다.
# 검색 색인 키(PII_INDEX_KEY)를 바꿨으면 --reindex 로 색인도 다시 계산한다.
#
# 값은 출력하지 않는다. 바꾼 행 · 칸 수와 풀지 못한(또는 저장이 겹쳐 손대지 못한) 사례 ID 만 출력한다.
# 바꾼 사례마다 감사 로그에 행동한 사람(actor) 없이 detail.via 로 남는다.
# 서비스 중에 돌려도 된다: 사례마다 읽은 값이 그대로일 때만 바꾸고, 그사이 저장된 값은 덮지 않는다.
#
# 사용 예:
#   python -m scripts.reencrypt_personal_info --dry-run
#   python -m scripts.reencrypt_personal_info
#   python -m scripts.reencrypt_personal_info --reindex

import argparse
import sys
import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core import pii_crypto
from app.core.database import SessionLocal
from app.core.enums import AuditAction
from app.core.pii_crypto import PersonalInfoCryptoError
from app.models.base import utcnow
from app.models.case_personal_info import ENCRYPTED_FIELDS, CasePersonalInfo
from app.services import audit_service

VIA = "reencrypt_personal_info script"


@dataclass
class ReencryptResult:
    rows: int = 0
    changed_rows: int = 0
    changed_fields: int = 0
    reindexed_rows: int = 0
    # 풀지 못한 사례 ID. 그 행은 하나도 바꾸지 않는다.
    failed_case_ids: List[uuid.UUID] = field(default_factory=list)
    # 다시 읽어도 그사이 계속 바뀌어 손대지 못한 사례 ID(서비스 중 저장이 몰림). 다시 돌리면 된다.
    busy_case_ids: List[uuid.UUID] = field(default_factory=list)


# 행을 읽은 뒤 바꾸기 전에 그사이 다른 저장(API PUT)이 끼면 다시 읽는 횟수.
_MAX_ATTEMPTS = 3

# 바꾸기 직전 '읽은 그대로인지' 견주는 칸.
_GUARD_COLUMNS = tuple(f"{name}_enc" for name in ENCRYPTED_FIELDS) + ("child_name_index",)


def _decrypt_row(row: CasePersonalInfo) -> Dict[str, str]:
    """행의 저장 값을 칸별 평문으로. 하나라도 못 풀면 PersonalInfoCryptoError."""

    return {
        name: pii_crypto.decrypt_text(token, case_id=row.case_id, field=name)
        for name in ENCRYPTED_FIELDS
        if (token := getattr(row, f"{name}_enc")) is not None
    }


def _reencrypt_one(
    db: Session,
    case_id: uuid.UUID,
    result: ReencryptResult,
    *,
    active_key_id: str,
    reindex: bool,
    dry_run: bool,
) -> None:
    """사례 하나를 다시 암호화하고 그 사례만 commit 한다.

    서비스 중에 돌려도 API 저장을 덮지 않게, 읽은 값이 그대로일 때만 바꾼다(조건부 UPDATE). 그사이 저장이 끼면
    다시 읽어 그 최신 값으로 다시 한다(Codex #127 R1 — 예전에는 읽어 둔 옛 값으로 덮어 사용자 저장이 사라졌다).
    API 저장은 늘 맨 앞 키로 모든 칸을 다시 쓰므로, 다시 읽은 값은 보통 바꿀 것이 없다.
    """

    for _ in range(_MAX_ATTEMPTS):
        row = db.get(CasePersonalInfo, case_id, populate_existing=True)

        if row is None:
            # 그사이 사례가 지워졌다.
            db.rollback()
            return

        guard = {column: getattr(row, column) for column in _GUARD_COLUMNS}

        try:
            plain = _decrypt_row(row)
        except PersonalInfoCryptoError:
            db.rollback()
            result.failed_case_ids.append(case_id)
            return

        stale = [name for name in plain if pii_crypto.key_id_of(guard[f"{name}_enc"]) != active_key_id]
        new_index = pii_crypto.name_index(plain["child_name"]) if "child_name" in plain else None
        needs_index = reindex and guard["child_name_index"] != new_index

        if not stale and not needs_index:
            db.rollback()
            return

        if dry_run:
            db.rollback()
            result.changed_rows += 1
            result.changed_fields += len(stale)
            result.reindexed_rows += int(needs_index)
            return

        values: Dict[str, Optional[str]] = {
            f"{name}_enc": pii_crypto.encrypt_text(plain[name], case_id=case_id, field=name) for name in stale
        }

        if needs_index:
            values["child_name_index"] = new_index

        same_as_read = [
            getattr(CasePersonalInfo, column).is_(None) if value is None else getattr(CasePersonalInfo, column) == value
            for column, value in guard.items()
        ]
        updated = db.execute(
            update(CasePersonalInfo)
            .where(CasePersonalInfo.case_id == case_id, *same_as_read)
            .values(**values, updated_at=utcnow())
            .execution_options(synchronize_session=False)
        ).rowcount

        if updated != 1:
            # 그사이 API 가 저장했다. 버리고 다시 읽는다.
            db.rollback()
            continue

        audit_service.record(
            db,
            action=AuditAction.CASE_PERSONAL_INFO_UPDATED,
            entity_type="CasePersonalInfo",
            entity_id=case_id,
            case_id=case_id,
            detail={"via": VIA, "reencrypted_fields": stale, "reindexed": needs_index, "key_id": active_key_id},
        )
        db.commit()

        result.changed_rows += 1
        result.changed_fields += len(stale)
        result.reindexed_rows += int(needs_index)
        return

    result.busy_case_ids.append(case_id)


def reencrypt_all(db: Session, *, reindex: bool = False, dry_run: bool = False) -> ReencryptResult:
    """맨 앞 키가 아닌 키로 만든 값을 맨 앞 키로 다시 암호화한다. dry_run 이면 세기만 한다.

    사례마다 따로 commit 한다(중간에 멈춰도 바꾼 사례는 남고, 다시 돌리면 남은 것만 한다).
    """

    active_key_id = pii_crypto.active_key_id()
    result = ReencryptResult()
    case_ids = list(db.scalars(select(CasePersonalInfo.case_id).order_by(CasePersonalInfo.case_id)))
    db.rollback()

    for case_id in case_ids:
        result.rows += 1
        _reencrypt_one(db, case_id, result, active_key_id=active_key_id, reindex=reindex, dry_run=dry_run)

    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="개인 식별 정보를 맨 앞 키로 다시 암호화한다.")
    parser.add_argument("--reindex", action="store_true", help="이름 검색 색인도 지금 PII_INDEX_KEY 로 다시 계산한다.")
    parser.add_argument("--dry-run", action="store_true", help="바꾸지 않고 바꿀 수만 센다.")
    args = parser.parse_args()

    with SessionLocal() as db:
        result = reencrypt_all(db, reindex=args.reindex, dry_run=args.dry_run)

    verb = "바꿀" if args.dry_run else "바꾼"
    print(f"전체 {result.rows}행 · {verb} 행 {result.changed_rows} · 칸 {result.changed_fields} · 색인 {result.reindexed_rows}")

    if result.failed_case_ids:
        # 사례 ID 만 출력한다. 옛 키를 이미 뺐거나 값이 바뀐 것 — 키 사본으로 되살린 뒤 다시 돌린다.
        print(f"풀지 못한 사례 {len(result.failed_case_ids)}건(그대로 둠):", file=sys.stderr)
        for case_id in result.failed_case_ids:
            print(f"  {case_id}", file=sys.stderr)

    if result.busy_case_ids:
        # 그사이 저장이 계속 겹친 사례. 값은 그대로이고 다시 돌리면 된다.
        print(f"저장이 겹쳐 손대지 못한 사례 {len(result.busy_case_ids)}건(다시 돌려 주세요):", file=sys.stderr)
        for case_id in result.busy_case_ids:
            print(f"  {case_id}", file=sys.stderr)

    return 1 if result.failed_case_ids or result.busy_case_ids else 0


if __name__ == "__main__":
    sys.exit(main())
