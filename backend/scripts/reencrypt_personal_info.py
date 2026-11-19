# 개인 식별 정보 키 바꾸기 script. 서버에서만 실행한다(backend/README.md '개인 식별 정보 키').
#
# 순서:
#   1) 새 키를 PII_ENCRYPTION_KEYS 맨 앞에 넣고(옛 키는 뒤에 남김) 서버를 다시 띄운다 — 새로 저장하는 값은 새 키로 간다.
#   2) 이 script 로 옛 키로 만든 값을 모두 새 키(맨 앞 키)로 다시 암호화한다. 상담사 메모 본문(counselor_memos.text_enc,
#      API_CONTRACT 25절)도 같은 키라 함께 한다(민규 #170 1 — 전에는 메모를 건너뛰고도 0 으로 끝나 옛 키를 빼면 메모가 500 이 됐다).
#   3) 종료 코드가 0(풀지 못한 · 겹쳐 못 바꾼 사례 · 메모 · 작성 양식 모두 0)이면 옛 키를 설정에서 뺀다. 1 이면 다시 돌린다.
# 검색 색인 키(PII_INDEX_KEY)를 바꿨으면 --reindex 로 색인도 다시 계산한다.
#
# 같은 키 링을 쓰는 상담 본문 칸(상담일지 · 원문 발화 · 요약 · 회차 메모 · 분석 결과, encrypted_field.ENCRYPTED_COLUMNS)도
# 함께 다시 암호화한다. 원문 조각처럼 큰 표는 묶음(encrypt_content_columns.BATCH_SIZE)씩 읽고 묶음마다 commit 한다.
# 본문 칸은 감사 로그를 남기지 않는다(행이 많다). 출력의 칸별 수로 확인한다.
# 문서함 작성 양식 파일(.ispotform, API_CONTRACT 23절)의 본체도 같은 키 링이다. 본체는 DB 가 아니라 저장소 파일
# (storage/docbox/<uuid>)이라 파일을 다시 써서 바꾼다(민규 #185 — 전에는 건너뛰어 옛 키를 빼면 /download 가 깨졌다).
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
import os
import sys
import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core import pii_crypto
from app.core.database import SessionLocal
from app.core.enums import AuditAction
from app.core.errors import APIError
from app.core.pii_crypto import PersonalInfoCryptoError
from app.models.base import utcnow
from app.models.case_personal_info import ENCRYPTED_FIELDS, CasePersonalInfo
from app.models.counselor_memo import CounselorMemo
from app.models.docbox import DocboxFile
from app.services import audit_service, docbox_service
from scripts.encrypt_content_columns import iter_batches, targets

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
    # 상담사 메모(본문 한 칸).
    memo_rows: int = 0
    changed_memos: int = 0
    failed_memo_ids: List[uuid.UUID] = field(default_factory=list)
    busy_memo_ids: List[uuid.UUID] = field(default_factory=list)

    @property
    def clean(self) -> bool:
        """옛 키를 빼도 되는가(풀지 못한 · 겹쳐 못 바꾼 것이 하나도 없음)."""

        return not (self.failed_case_ids or self.busy_case_ids or self.failed_memo_ids or self.busy_memo_ids)


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


def _reencrypt_memo(db: Session, memo_id: uuid.UUID, result: ReencryptResult, *, active_key_id: str, dry_run: bool) -> None:
    """메모 하나를 다시 암호화하고 그 메모만 commit 한다. 읽은 값이 그대로일 때만 바꾼다(그사이 고친 본문을 덮지 않게)."""

    for _ in range(_MAX_ATTEMPTS):
        row = db.get(CounselorMemo, memo_id, populate_existing=True)

        if row is None:
            db.rollback()
            return

        token = row.text_enc

        if pii_crypto.key_id_of(token) == active_key_id:
            db.rollback()
            return

        try:
            plain = pii_crypto.decrypt_memo(token, memo_id=memo_id)
        except PersonalInfoCryptoError:
            db.rollback()
            result.failed_memo_ids.append(memo_id)
            return

        if dry_run:
            db.rollback()
            result.changed_memos += 1
            return

        updated = db.execute(
            update(CounselorMemo)
            .where(CounselorMemo.id == memo_id, CounselorMemo.text_enc == token)
            .values(text_enc=pii_crypto.encrypt_memo(plain, memo_id=memo_id), updated_at=utcnow())
            .execution_options(synchronize_session=False)
        ).rowcount

        if updated != 1:
            db.rollback()
            continue

        # 본문은 남기지 않는다(감사 기록에는 메모 ID · 키 이름만).
        audit_service.record(
            db,
            action=AuditAction.MEMO_UPDATED,
            entity_type="CounselorMemo",
            entity_id=memo_id,
            case_id=row.case_id,
            detail={"via": VIA, "fields": ["text"], "key_id": active_key_id},
        )
        db.commit()
        result.changed_memos += 1
        return

    result.busy_memo_ids.append(memo_id)


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

    memo_ids = list(db.scalars(select(CounselorMemo.id).order_by(CounselorMemo.id)))
    db.rollback()

    for memo_id in memo_ids:
        result.memo_rows += 1
        _reencrypt_memo(db, memo_id, result, active_key_id=active_key_id, dry_run=dry_run)

    return result


@dataclass
class ContentReencryptResult:
    # 암호문이 있는 행(표 · 칸마다 한 번씩 센다)
    rows: int = 0
    changed_rows: int = 0
    # 풀지 못한 (표.칸, 행 ID). 그 행은 바꾸지 않는다.
    failed: List[Tuple[str, uuid.UUID]] = field(default_factory=list)


def reencrypt_content(db: Session, *, dry_run: bool = False) -> ContentReencryptResult:
    """상담 본문 칸에서 맨 앞 키가 아닌 키로 만든 값을 맨 앞 키로 다시 암호화한다. dry_run 이면 세기만 한다.

    읽은 암호문이 그대로일 때만 바꾼다(조건부 UPDATE). 그사이 API 가 저장했으면 이미 맨 앞 키라 건너뛴다.
    묶은 값(AAD)은 행 ID 그대로라 같은 행에 다시 넣는다.
    """

    active_key_id = pii_crypto.active_key_id()
    result = ContentReencryptResult()

    for table, column in targets():
        enc = table.c[column.enc_attr]

        for rows in iter_batches(db, table, (enc.name,), enc.is_not(None)):
            for row_id, token in rows:
                result.rows += 1

                if pii_crypto.key_id_of(token) == active_key_id:
                    continue

                try:
                    text = column.decrypt(token, row_id)
                except PersonalInfoCryptoError:
                    result.failed.append((f"{column.table}.{column.column}", row_id))
                    continue

                if dry_run:
                    result.changed_rows += 1
                    continue

                result.changed_rows += db.execute(
                    update(table)
                    .where(table.c.id == row_id, enc == token)
                    .values({enc.name: column.encrypt(text, row_id)})
                    .execution_options(synchronize_session=False)
                ).rowcount

            if not dry_run:
                db.commit()

    return result


@dataclass
class DocboxReencryptResult:
    # 작성 양식 파일(.ispotform) 행 수
    rows: int = 0
    changed_rows: int = 0
    # 봉인되지 않은 본체(앱 암호화 전 모양) — 키와 상관없어 그대로 둔다.
    plain_rows: int = 0
    # 본체 파일이 없는 행(그사이 지워졌거나 저장소에서 빠짐). 키와 상관없어 종료 코드에 넣지 않는다.
    missing_ids: List[uuid.UUID] = field(default_factory=list)
    # 풀지 못한 행 ID. 그 파일은 바꾸지 않는다.
    failed_ids: List[uuid.UUID] = field(default_factory=list)


def _read_token(path) -> Optional[str]:
    """본체 파일에서 봉인 값을 읽는다. 봉인 모양이 아니면(평문 JSON 등) None."""

    try:
        token = path.read_bytes().decode("ascii").strip()
    except UnicodeDecodeError:
        return None

    return token if pii_crypto.key_id_of(token) is not None else None


def reencrypt_docbox_forms(db: Session, *, dry_run: bool = False) -> DocboxReencryptResult:
    """문서함 작성 양식 본체 중 맨 앞 키가 아닌 키로 봉인한 것을 맨 앞 키로 다시 봉인한다. dry_run 이면 세기만 한다.

    본체는 올린 뒤 바뀌지 않는다(고치기 없음, 다시 저장하면 새 문서). 같은 폴더의 임시 파일에 쓴 뒤 바꿔 끼워(os.replace)
    중간에 멈춰도 본체가 반쯤 쓰인 채 남지 않는다. 바꿔 끼우기 직전 파일이 읽은 그대로인지 다시 보고, 그사이 행이 지워졌으면
    다시 만든 파일을 지운다. AAD 는 행 ID 그대로라 같은 행에 다시 넣는다. 두 번 돌려도 이미 맨 앞 키인 것은 건너뛴다.
    """

    active_key_id = pii_crypto.active_key_id()
    result = DocboxReencryptResult()
    rows = [(row_id, name) for row_id, name in db.execute(select(DocboxFile.id, DocboxFile.name).order_by(DocboxFile.id))]
    db.rollback()

    for row_id, name in rows:
        if docbox_service._extension(name) != docbox_service.FORM_EXT:
            continue

        result.rows += 1
        row = db.get(DocboxFile, row_id)
        db.rollback()

        if row is None:
            continue

        try:
            path = docbox_service.file_path(row)
        except APIError:  # 404 — 본체가 없다
            result.missing_ids.append(row_id)
            continue

        token = _read_token(path)

        if token is None:
            result.plain_rows += 1
            continue

        if pii_crypto.key_id_of(token) == active_key_id:
            continue

        try:
            plain = pii_crypto.decrypt_field(token, table="docbox_files", column="body", row_id=row_id)
        except PersonalInfoCryptoError:
            result.failed_ids.append(row_id)
            continue

        if dry_run:
            result.changed_rows += 1
            continue

        sealed = pii_crypto.encrypt_field(plain, table="docbox_files", column="body", row_id=row_id).encode("ascii")
        temp = path.with_name(f".{path.name}.reenc-{uuid.uuid4().hex}")
        try:
            temp.write_bytes(sealed)

            if _read_token(path) != token:
                # 그사이 다른 실행이 바꿨다(이미 맨 앞 키) — 건너뛴다.
                continue

            os.replace(temp, path)
        finally:
            temp.unlink(missing_ok=True)

        if db.get(DocboxFile, row_id) is None:
            # 그사이 행이 지워졌다(지우기는 행 먼저 · 파일 나중) — 다시 만든 본체를 남기지 않는다.
            path.unlink(missing_ok=True)
        else:
            result.changed_rows += 1
        db.rollback()

    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="개인 식별 정보를 맨 앞 키로 다시 암호화한다.")
    parser.add_argument("--reindex", action="store_true", help="이름 검색 색인도 지금 PII_INDEX_KEY 로 다시 계산한다.")
    parser.add_argument("--dry-run", action="store_true", help="바꾸지 않고 바꿀 수만 센다.")
    args = parser.parse_args()

    with SessionLocal() as db:
        result = reencrypt_all(db, reindex=args.reindex, dry_run=args.dry_run)
        content = reencrypt_content(db, dry_run=args.dry_run)
        forms = reencrypt_docbox_forms(db, dry_run=args.dry_run)

    verb = "바꿀" if args.dry_run else "바꾼"
    print(f"전체 {result.rows}행 · {verb} 행 {result.changed_rows} · 칸 {result.changed_fields} · 색인 {result.reindexed_rows}")
    print(f"메모 전체 {result.memo_rows}건 · {verb} 메모 {result.changed_memos}")

    print(f"상담 본문 암호문 {content.rows}행 · {verb} 행 {content.changed_rows}")
    print(f"문서함 작성 양식 {forms.rows}건 · {verb} 양식 {forms.changed_rows} · 봉인 전(그대로 둠) {forms.plain_rows}")

    if forms.missing_ids:
        # 행 ID 만 출력한다. 키와 상관없어 종료 코드에 넣지 않는다.
        print(f"본체 파일이 없는 작성 양식 {len(forms.missing_ids)}건(그대로 둠):", file=sys.stderr)
        for row_id in forms.missing_ids:
            print(f"  {row_id}", file=sys.stderr)

    if forms.failed_ids:
        # 행 ID 만 출력한다(파일 이름 · 내용은 출력하지 않는다).
        print(f"풀지 못한 작성 양식 {len(forms.failed_ids)}건(그대로 둠):", file=sys.stderr)
        for row_id in forms.failed_ids:
            print(f"  {row_id}", file=sys.stderr)

    if content.failed:
        # 표.칸 과 행 ID 만 출력한다.
        print(f"풀지 못한 상담 본문 {len(content.failed)}행(그대로 둠):", file=sys.stderr)
        for name, row_id in content.failed:
            print(f"  {name} {row_id}", file=sys.stderr)

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

    if result.failed_memo_ids:
        # 메모 ID 만 출력한다(본문 · 쓴 사람은 출력하지 않는다).
        print(f"풀지 못한 메모 {len(result.failed_memo_ids)}건(그대로 둠):", file=sys.stderr)
        for memo_id in result.failed_memo_ids:
            print(f"  {memo_id}", file=sys.stderr)

    if result.busy_memo_ids:
        print(f"고치기가 겹쳐 손대지 못한 메모 {len(result.busy_memo_ids)}건(다시 돌려 주세요):", file=sys.stderr)
        for memo_id in result.busy_memo_ids:
            print(f"  {memo_id}", file=sys.stderr)

    return 0 if result.clean and not content.failed and not forms.failed_ids else 1


if __name__ == "__main__":
    sys.exit(main())
