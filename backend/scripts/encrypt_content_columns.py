# 상담 본문 평문 → 암호문 옮기기 script(상담 본문 앱 암호화 1단계). 서버에서만 실행한다.
#
# 대상 칸(app.models.encrypted_field.ENCRYPTED_COLUMNS):
#   documents.content · transcript_segments.text · consultation_summaries.overview · key_points · counselor_note ·
#   consultation_sessions.memo · ai_analyses.result
#
# 순서(PR 설명과 같다):
#   1) 1단계 코드 배포(alembic upgrade 로 *_enc 칸이 생긴다). 이때부터 새로 쓰는 값은 암호문으로만 들어간다.
#   2) RDS 스냅샷.
#   3) python -m scripts.encrypt_content_columns            ← 기본은 dry-run: 옮길 행 수만 세고, 행마다
#                                                               암호화 → 복호화 값 = 평문인지 확인한다. 아무것도 안 바꾼다.
#   4) python -m scripts.encrypt_content_columns --apply    ← 옮긴다. 행마다 확인한 뒤 `<칸>_enc` 에 넣고 평문 칸을
#                                                               빈 값("" · [] · NULL)으로 바꾼다. 묶음마다 commit.
#   5) python -m scripts.encrypt_content_columns --check    ← 남은 평문 0 · 모든 암호문이 풀리는지. 종료 코드 0 이면 끝.
#   6) 평문 칸 지우기는 다음 PR.
#
# 되돌리기(1단계 코드를 내리기 전): --decrypt-back --apply 로 암호문을 평문 칸으로 되돌린다(옛 코드는 평문 칸만 읽는다).
#
# 서비스 중에 돌려도 된다: 읽은 값이 그대로일 때만 바꾼다(조건부 UPDATE). 그사이 API 가 쓴 행은 이미 암호문이라 건너뛴다.
# 값은 출력하지 않는다. 표 · 칸별 행 수와, 문제가 있는 행의 표 · 칸 · 행 ID 만 출력한다.
#
# 사용 예:
#   python -m scripts.encrypt_content_columns
#   python -m scripts.encrypt_content_columns --apply
#   python -m scripts.encrypt_content_columns --check

import argparse
import sys
import uuid
from dataclasses import dataclass, field
from typing import Any, Iterator, List, Optional, Sequence, Tuple

from sqlalchemy import Table, select, update
from sqlalchemy.orm import Session

import app.models  # noqa: F401 — 모든 모델을 올려 ENCRYPTED_COLUMNS 를 채운다.
from app.core import pii_crypto
from app.core.database import SessionLocal
from app.core.pii_crypto import PersonalInfoCryptoError
from app.models.encrypted_field import ENCRYPTED_COLUMNS, EncryptedColumn

BATCH_SIZE = 500


@dataclass
class ColumnReport:
    table: str
    column: str
    # 옮길(옮긴) 행 · 되돌릴(되돌린) 행
    changed: int = 0
    # 남은 평문(--check) · 풀리지 않는 암호문(--check · 되돌리기)
    plain_left: int = 0
    # 암호화 → 복호화 값이 평문과 다르거나, 풀리지 않는 행. 손대지 않는다.
    failed_ids: List[uuid.UUID] = field(default_factory=list)
    # 읽은 뒤 그사이 API 가 써서 건너뛴 행(이미 암호문이다).
    skipped: int = 0

    @property
    def name(self) -> str:
        return f"{self.table}.{self.column}"


def targets() -> List[Tuple[Table, EncryptedColumn]]:
    """(표, 암호화 칸) 목록. 표 이름 · 칸 순으로 고정한다."""

    found = [(model.__table__, column) for model, columns in ENCRYPTED_COLUMNS.items() for column in columns]

    return sorted(found, key=lambda item: (item[1].table, item[1].column))


def has_value(value: Any) -> bool:
    """평문 칸에 옮길 값이 있는가(빈 글자 · 빈 목록 · NULL 은 없음 — 읽으면 같은 빈 값이 나온다)."""

    return value not in (None, "", [])


def iter_batches(db: Session, table: Table, columns: Sequence[str], *where: Any) -> Iterator[List[Any]]:
    """행 ID 순으로 BATCH_SIZE 씩 읽는다(원문 조각처럼 큰 표도 한 번에 올리지 않는다)."""

    last_id: Optional[uuid.UUID] = None

    while True:
        query = select(table.c.id, *(table.c[name] for name in columns)).where(*where)

        if last_id is not None:
            query = query.where(table.c.id > last_id)

        rows = db.execute(query.order_by(table.c.id).limit(BATCH_SIZE)).all()
        db.rollback()

        if not rows:
            return

        yield rows
        last_id = rows[-1][0]


def _round_trip_ok(column: EncryptedColumn, row_id: uuid.UUID, value: Any) -> Optional[str]:
    """암호화하고 바로 풀어 평문과 같으면 암호문을, 다르면 None."""

    token = column.encrypt(column.dumps(value), row_id)

    try:
        same = column.loads(column.decrypt(token, row_id)) == value
    except (PersonalInfoCryptoError, ValueError):
        same = False

    return token if same else None


def move_column(db: Session, table: Table, column: EncryptedColumn, *, apply: bool) -> ColumnReport:
    report = ColumnReport(column.table, column.column)
    plain = table.c[column.column]
    enc = table.c[f"{column.column}_enc"]

    for rows in iter_batches(db, table, (column.column,), enc.is_(None), plain.is_not(None)):
        for row_id, value in rows:
            if not has_value(value):
                continue

            token = _round_trip_ok(column, row_id, value)

            if token is None:
                report.failed_ids.append(row_id)
                continue

            if not apply:
                report.changed += 1
                continue

            updated = db.execute(
                update(table)
                .where(table.c.id == row_id, enc.is_(None), plain == value)
                .values({enc.name: token, plain.name: column.empty()})
                .execution_options(synchronize_session=False)
            ).rowcount

            if updated == 1:
                report.changed += 1
            else:
                report.skipped += 1

        if apply:
            db.commit()

    return report


def check_column(db: Session, table: Table, column: EncryptedColumn) -> ColumnReport:
    """남은 평문 수와 풀리지 않는 암호문 행."""

    report = ColumnReport(column.table, column.column)
    enc_name = f"{column.column}_enc"

    for rows in iter_batches(db, table, (column.column, enc_name)):
        for row_id, value, token in rows:
            if has_value(value):
                report.plain_left += 1

            if token is None:
                continue

            try:
                column.loads(column.decrypt(token, row_id))
            except (PersonalInfoCryptoError, ValueError):
                report.failed_ids.append(row_id)

    return report


def decrypt_back_column(db: Session, table: Table, column: EncryptedColumn, *, apply: bool) -> ColumnReport:
    """되돌리기: 암호문을 풀어 평문 칸에 넣고 *_enc 를 비운다(1단계 코드를 내리기 전에)."""

    report = ColumnReport(column.table, column.column)
    plain = table.c[column.column]
    enc = table.c[f"{column.column}_enc"]

    for rows in iter_batches(db, table, (enc.name,), enc.is_not(None)):
        for row_id, token in rows:
            try:
                value = column.loads(column.decrypt(token, row_id))
            except (PersonalInfoCryptoError, ValueError):
                report.failed_ids.append(row_id)
                continue

            if not apply:
                report.changed += 1
                continue

            updated = db.execute(
                update(table)
                .where(table.c.id == row_id, enc == token)
                .values({enc.name: None, plain.name: value})
                .execution_options(synchronize_session=False)
            ).rowcount

            if updated == 1:
                report.changed += 1
            else:
                report.skipped += 1

        if apply:
            db.commit()

    return report


def run(db: Session, *, mode: str, apply: bool = False) -> List[ColumnReport]:
    reports = []

    for table, column in targets():
        if mode == "check":
            reports.append(check_column(db, table, column))
        elif mode == "decrypt-back":
            reports.append(decrypt_back_column(db, table, column, apply=apply))
        else:
            reports.append(move_column(db, table, column, apply=apply))

    return reports


def main() -> int:
    parser = argparse.ArgumentParser(description="상담 본문 평문을 *_enc 암호문 칸으로 옮긴다(기본은 dry-run).")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--check", action="store_true", help="남은 평문 수와 풀리지 않는 암호문을 센다.")
    group.add_argument("--decrypt-back", action="store_true", help="되돌리기: 암호문을 평문 칸으로 되돌린다.")
    parser.add_argument("--apply", action="store_true", help="실제로 바꾼다(없으면 세기만 한다).")
    args = parser.parse_args()

    mode = "check" if args.check else "decrypt-back" if args.decrypt_back else "move"
    pii_crypto.active_key_id()  # 키 설정이 없으면 여기서 멈춘다.

    with SessionLocal() as db:
        reports = run(db, mode=mode, apply=args.apply)

    failed = False

    for report in reports:
        if mode == "check":
            line = f"{report.name}: 남은 평문 {report.plain_left} · 풀리지 않는 행 {len(report.failed_ids)}"
            failed = failed or report.plain_left > 0
        else:
            verb = ("되돌린" if args.apply else "되돌릴") if mode == "decrypt-back" else ("옮긴" if args.apply else "옮길")
            line = f"{report.name}: {verb} 행 {report.changed} · 건너뜀 {report.skipped} · 문제 행 {len(report.failed_ids)}"
            failed = failed or report.skipped > 0

        print(line)

        if report.failed_ids:
            failed = True
            # 행 ID 만 출력한다(값은 출력하지 않는다).
            for row_id in report.failed_ids:
                print(f"  {report.name} {row_id}", file=sys.stderr)

    if not args.apply and mode != "check":
        print("dry-run 입니다. 바꾸려면 --apply 를 붙여 다시 돌리세요.")

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
