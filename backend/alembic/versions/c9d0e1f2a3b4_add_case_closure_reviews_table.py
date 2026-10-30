"""add case_closure_reviews table

Revision ID: c9d0e1f2a3b4
Revises: b8c9d0e1f2a3
Create Date: 2026-10-30 18:00:00.000000

종결 검토 기록 — 사례마다 한 행(핵심 요약 · 확인 체크 · 고친 문장 · 종결보고서 칸).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'c9d0e1f2a3b4'
down_revision: Union[str, None] = 'b8c9d0e1f2a3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_JSON = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql')


def upgrade() -> None:
    op.create_table('case_closure_reviews',
    sa.Column('case_id', sa.Uuid(), nullable=False),
    sa.Column('summary', _JSON, nullable=True),
    sa.Column('checks', _JSON, nullable=False),
    sa.Column('edits', _JSON, nullable=False),
    sa.Column('report', _JSON, nullable=False),
    sa.Column('updated_by_id', sa.Uuid(), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['case_id'], ['cases.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['updated_by_id'], ['users.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_case_closure_reviews_case_id'), 'case_closure_reviews', ['case_id'], unique=True)


def downgrade() -> None:
    op.drop_index(op.f('ix_case_closure_reviews_case_id'), table_name='case_closure_reviews')
    op.drop_table('case_closure_reviews')
