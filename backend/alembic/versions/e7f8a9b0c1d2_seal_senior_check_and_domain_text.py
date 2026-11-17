"""seal senior check and domain text

Revision ID: e7f8a9b0c1d2
Revises: c3d4e5f6a7b8
Create Date: 2026-11-17 15:00:00.000000

고령자 확인사항 · 영역 기록 글 암호화(민규 72fc991 리뷰 11/17 — next_checks 의 text · result_note,
care_domain_notes 의 text · change_note 가 평문). c3d4e5f6a7b8(건강 정보)과 같은 방식으로 칸들을 JSON 으로 묶어
sealed_values 한 칸에 둔다(키 PII_ENCRYPTION_KEYS, 저장 모양 pii_crypto.encrypt_text).
- next_checks: text · result_note (묶음 값 = 사례 ID + "next_check:<줄 ID>")
- care_domain_notes: text · change_note (묶음 값 = 사례 ID + "care_domain_note:<줄 ID>")
있던 줄은 옮기며 암호화한다(되돌리면 풀어서 칸으로). 종류 · 기한 · 상태 · 영역 · 변화 구분(분류)과 근거 발화 번호는 평문.
"""
import json
import uuid
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'e7f8a9b0c1d2'
down_revision: Union[str, None] = 'c3d4e5f6a7b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLES = (
    ('next_checks', 'next_check', ('text', 'result_note')),
    ('care_domain_notes', 'care_domain_note', ('text', 'change_note')),
)


def _uuid(value):
    return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))


def _seal(values, case_id, field):
    from app.core import pii_crypto

    values = {k: v for k, v in values.items() if v is not None}
    if not values:
        return None
    return pii_crypto.encrypt_text(json.dumps(values, ensure_ascii=False, sort_keys=True), case_id=_uuid(case_id), field=field)


def _open(token, case_id, field):
    from app.core import pii_crypto

    return json.loads(pii_crypto.decrypt_text(token, case_id=_uuid(case_id), field=field)) if token else {}


def _table(name, columns):
    return sa.table(name, sa.column('id', sa.Uuid()), sa.column('case_id', sa.Uuid()), sa.column('sealed_values', sa.Text()), *[sa.column(c, sa.Text()) for c in columns])


def upgrade() -> None:
    bind = op.get_bind()
    for name, prefix, columns in TABLES:
        with op.batch_alter_table(name) as batch:
            batch.add_column(sa.Column('sealed_values', sa.Text(), nullable=True))
        table = _table(name, columns)
        for row in bind.execute(sa.select(table)).mappings().all():
            token = _seal({c: row[c] for c in columns}, row['case_id'], f"{prefix}:{_uuid(row['id'])}")
            bind.execute(table.update().where(table.c.id == row['id']).values(sealed_values=token))
        with op.batch_alter_table(name) as batch:
            for column in columns:
                batch.drop_column(column)


def downgrade() -> None:
    bind = op.get_bind()
    for name, prefix, columns in TABLES:
        with op.batch_alter_table(name) as batch:
            for column in columns:
                batch.add_column(sa.Column(column, sa.Text(), nullable=True))
        table = _table(name, columns)
        for row in bind.execute(sa.select(table)).mappings().all():
            values = _open(row['sealed_values'], row['case_id'], f"{prefix}:{_uuid(row['id'])}")
            update = {c: values.get(c) for c in columns}
            if name == 'next_checks':
                update['text'] = update['text'] or ''
            bind.execute(table.update().where(table.c.id == row['id']).values(**update))
        with op.batch_alter_table(name) as batch:
            if name == 'next_checks':
                batch.alter_column('text', existing_type=sa.Text(), nullable=False)
            batch.drop_column('sealed_values')
