"""seal senior health values

Revision ID: c3d4e5f6a7b8
Revises: b2e3d4f5a6c7
Create Date: 2026-11-16 18:00:00.000000

고령자 건강 정보 암호화(민규 리뷰 11/16 — 건강 메모 · 복약 메모 · 측정값 평문). 내담자 실명과 같은 키(PII_ENCRYPTION_KEYS) ·
같은 저장 모양(pii_crypto.encrypt_text)으로, 칸들을 JSON 으로 묶어 sealed_values 한 칸에 둔다.
- senior_profiles: health_notes · care_notes · takes_medication · medication_notes · care_needs_note · care_status_note
  (묶음 값 = 사례 ID + "senior_profile")
- health_measurements: systolic · diastolic · pulse · blood_glucose · glucose_timing · weight_kg · body_temp_c · extra_results · note
  (묶음 값 = 사례 ID + "health_measurement:<줄 ID>")
있던 줄은 옮기며 암호화한다(되돌리면 풀어서 칸으로). 거주 형태 · 장기요양 등급 · 돌봄 필요 · 돌봄 상태(분류)와 잰 시각은 평문.
"""
import json
import uuid
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, None] = 'b2e3d4f5a6c7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

JSON = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql')

PROFILE = ('health_notes', 'care_notes', 'takes_medication', 'medication_notes', 'care_needs_note', 'care_status_note')
MEASURE = ('systolic', 'diastolic', 'pulse', 'blood_glucose', 'glucose_timing', 'weight_kg', 'body_temp_c', 'extra_results', 'note')


def _uuid(value):
    return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))


def _json(value):
    return json.loads(value) if isinstance(value, str) else value


def _seal(values, case_id, field):
    from app.core import pii_crypto

    values = {k: v for k, v in values.items() if v is not None and v != []}
    if not values:
        return None
    return pii_crypto.encrypt_text(json.dumps(values, ensure_ascii=False, sort_keys=True), case_id=_uuid(case_id), field=field)


def _open(token, case_id, field):
    from app.core import pii_crypto

    return json.loads(pii_crypto.decrypt_text(token, case_id=_uuid(case_id), field=field)) if token else {}


def upgrade() -> None:
    bind = op.get_bind()
    with op.batch_alter_table('senior_profiles') as batch:
        batch.add_column(sa.Column('sealed_values', sa.Text(), nullable=True))
    with op.batch_alter_table('health_measurements') as batch:
        batch.add_column(sa.Column('sealed_values', sa.Text(), nullable=True))

    profiles = sa.table('senior_profiles', sa.column('id', sa.Uuid()), sa.column('case_id', sa.Uuid()), sa.column('sealed_values', sa.Text()), *[sa.column(c) for c in PROFILE])
    for row in bind.execute(sa.select(profiles)).mappings().all():
        token = _seal({c: row[c] for c in PROFILE}, row['case_id'], 'senior_profile')
        bind.execute(profiles.update().where(profiles.c.id == row['id']).values(sealed_values=token))

    measures = sa.table('health_measurements', sa.column('id', sa.Uuid()), sa.column('case_id', sa.Uuid()), sa.column('sealed_values', sa.Text()), *[sa.column(c) for c in MEASURE[:-2]], sa.column('extra_results', JSON), sa.column('note'))
    for row in bind.execute(sa.select(measures)).mappings().all():
        values = {c: row[c] for c in MEASURE}
        values['extra_results'] = _json(values['extra_results'])
        token = _seal(values, row['case_id'], f"health_measurement:{_uuid(row['id'])}")
        bind.execute(measures.update().where(measures.c.id == row['id']).values(sealed_values=token))

    with op.batch_alter_table('senior_profiles') as batch:
        for column in PROFILE:
            batch.drop_column(column)
    with op.batch_alter_table('health_measurements') as batch:
        for column in MEASURE:
            batch.drop_column(column)


def downgrade() -> None:
    bind = op.get_bind()
    with op.batch_alter_table('senior_profiles') as batch:
        batch.add_column(sa.Column('health_notes', sa.Text(), nullable=True))
        batch.add_column(sa.Column('care_notes', sa.Text(), nullable=True))
        batch.add_column(sa.Column('takes_medication', sa.Boolean(), nullable=True))
        batch.add_column(sa.Column('medication_notes', sa.Text(), nullable=True))
        batch.add_column(sa.Column('care_needs_note', sa.Text(), nullable=True))
        batch.add_column(sa.Column('care_status_note', sa.Text(), nullable=True))
    with op.batch_alter_table('health_measurements') as batch:
        batch.add_column(sa.Column('systolic', sa.Integer(), nullable=True))
        batch.add_column(sa.Column('diastolic', sa.Integer(), nullable=True))
        batch.add_column(sa.Column('pulse', sa.Integer(), nullable=True))
        batch.add_column(sa.Column('blood_glucose', sa.Integer(), nullable=True))
        batch.add_column(sa.Column('glucose_timing', sa.Enum('FASTING', 'POST_MEAL', 'RANDOM', name='glucose_timing', native_enum=False, length=10), nullable=True))
        batch.add_column(sa.Column('weight_kg', sa.Float(), nullable=True))
        batch.add_column(sa.Column('body_temp_c', sa.Float(), nullable=True))
        batch.add_column(sa.Column('extra_results', JSON, nullable=False, server_default='[]'))
        batch.add_column(sa.Column('note', sa.Text(), nullable=True))

    profiles = sa.table('senior_profiles', sa.column('id', sa.Uuid()), sa.column('case_id', sa.Uuid()), sa.column('sealed_values', sa.Text()), *[sa.column(c) for c in PROFILE])
    for row in bind.execute(sa.select(profiles)).mappings().all():
        values = _open(row['sealed_values'], row['case_id'], 'senior_profile')
        bind.execute(profiles.update().where(profiles.c.id == row['id']).values(**{c: values.get(c) for c in PROFILE}))

    measures = sa.table('health_measurements', sa.column('id', sa.Uuid()), sa.column('case_id', sa.Uuid()), sa.column('sealed_values', sa.Text()), *[sa.column(c) for c in MEASURE[:-2]], sa.column('extra_results', JSON), sa.column('note'))
    for row in bind.execute(sa.select(measures)).mappings().all():
        values = _open(row['sealed_values'], row['case_id'], f"health_measurement:{_uuid(row['id'])}")
        update = {c: values.get(c) for c in MEASURE}
        update['extra_results'] = update['extra_results'] or []
        bind.execute(measures.update().where(measures.c.id == row['id']).values(**update))

    with op.batch_alter_table('senior_profiles') as batch:
        batch.drop_column('sealed_values')
    with op.batch_alter_table('health_measurements') as batch:
        batch.drop_column('sealed_values')
