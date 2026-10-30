# 개인 식별 정보 키 바꾸기 script. 서버에서만 실행한다(backend/README.md '개인 식별 정보 키').
#
# 순서:
#   1) 새 키를 PII_ENCRYPTION_KEYS 맨 앞에 넣고(옛 키는 뒤에 남김) 서버를 다시 띄운다 — 새로 저장하는 값은 새 키로 간다.
#   2) 이 script 로 옛 키로 만든 값을 모두 새 키(맨 앞 키)로 다시 암호화한다.
#   3) 남은 값이 0 이면 옛 키를 설정에서 뺀다.
# 검색 색인 키(PII_INDEX_KEY)를 바꿨으면 --reindex 로 색인도 다시 계산한다.
#
# 값은 출력하지 않는다. 바꾼 행 · 칸 수와 풀지 못한 사례 ID 만 출력한다.
# 바꾼 사례마다 감사 로그에 행동한 사람(actor) 없이 detail.via 로 남는다.
#
# 사용 예:
#   python -m scripts.reencrypt_personal_info --dry-run
#   python -m scripts.reencrypt_personal_info
#   python -m scripts.reencrypt_personal_info --reindex

import argparse
import sys
import uuid
from dataclasses import dataclass, field
from typing import List

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import pii_crypto
from app.core.database import SessionLocal
from app.core.enums import AuditAction
from app.core.pii_crypto import PersonalInfoCryptoError
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


def reencrypt_all(db: Session, *, reindex: bool = False, dry_run: bool = False) -> ReencryptResult:
    """맨 앞 키가 아닌 키로 만든 값을 맨 앞 키로 다시 암호화한다. dry_run 이면 세기만 한다. commit 까지 한다."""

    active_key_id = pii_crypto.active_key_id()
    result = ReencryptResult()

    for row in db.scalars(select(CasePersonalInfo).order_by(CasePersonalInfo.case_id)):
        result.rows += 1

        try:
            plain = {
                name: pii_crypto.decrypt_text(token, case_id=row.case_id, field=name)
                for name in ENCRYPTED_FIELDS
                if (token := getattr(row, f"{name}_enc")) is not None
            }
        except PersonalInfoCryptoError:
            result.failed_case_ids.append(row.case_id)
            continue

        stale = [
            name
            for name in plain
            if pii_crypto.key_id_of(getattr(row, f"{name}_enc")) != active_key_id
        ]
        new_index = pii_crypto.name_index(plain["child_name"]) if "child_name" in plain else None
        needs_index = reindex and row.child_name_index != new_index

        if not stale and not needs_index:
            continue

        result.changed_rows += 1
        result.changed_fields += len(stale)
        result.reindexed_rows += int(needs_index)

        if dry_run:
            continue

        for name in stale:
            setattr(row, f"{name}_enc", pii_crypto.encrypt_text(plain[name], case_id=row.case_id, field=name))

        if needs_index:
            row.child_name_index = new_index

        audit_service.record(
            db,
            action=AuditAction.CASE_PERSONAL_INFO_UPDATED,
            entity_type="CasePersonalInfo",
            entity_id=row.case_id,
            case_id=row.case_id,
            detail={"via": VIA, "reencrypted_fields": stale, "reindexed": needs_index, "key_id": active_key_id},
        )

    if not dry_run:
        db.commit()

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
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
