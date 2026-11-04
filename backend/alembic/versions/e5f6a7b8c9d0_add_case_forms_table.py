"""add case_forms table

Revision ID: e5f6a7b8c9d0
Revises: 7a1c5e9b3d20
Create Date: 2026-11-02 18:00:00.000000

기관 서식 작성 기록(사정기록지 안전영역 · 사례관리 점검표 · 위험수준 척도 · 가족관계 척도). API_CONTRACT 22절.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'e5f6a7b8c9d0'
down_revision: Union[str, None] = '7a1c5e9b3d20'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_JSON = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql')


def upgrade() -> None:
    op.create_table('case_forms',
    sa.Column('case_id', sa.Uuid(), nullable=False),
    sa.Column('form_type', sa.Enum('SAFETY_ASSESSMENT', 'MANAGEMENT_CHECKLIST', 'RISK_SCALE', 'FAMILY_SCALE', name='case_form_type', native_enum=False, length=30), nullable=False),
    sa.Column('round', sa.Integer(), nullable=False),
    sa.Column('status', sa.Enum('DRAFT', 'APPROVED', name='case_form_status', native_enum=False, length=20), nullable=False),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('values', _JSON, nullable=False),
    sa.Column('created_by_id', sa.Uuid(), nullable=True),
    sa.Column('updated_by_id', sa.Uuid(), nullable=True),
    sa.Column('confirmed_by_id', sa.Uuid(), nullable=True),
    sa.Column('confirmed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['case_id'], ['cases.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['confirmed_by_id'], ['users.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['created_by_id'], ['users.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['updated_by_id'], ['users.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('case_id', 'form_type', 'round', name='uq_case_forms_case_type_round')
    )
    op.create_index(op.f('ix_case_forms_case_id'), 'case_forms', ['case_id'], unique=False)
    # 사례 · 서식 종류마다 임시 저장 차수는 하나(DRAFT 행에만 거는 유일 인덱스).
    op.create_index(
        'uq_case_forms_one_draft', 'case_forms', ['case_id', 'form_type'], unique=True,
        sqlite_where=sa.text("status = 'DRAFT'"), postgresql_where=sa.text("status = 'DRAFT'"),
    )


def downgrade() -> None:
    op.drop_index('uq_case_forms_one_draft', table_name='case_forms')
    op.drop_index(op.f('ix_case_forms_case_id'), table_name='case_forms')
    op.drop_table('case_forms')
