"""add session_followup_checks table

Revision ID: e4b7c9a1f2d6
Revises: 1a685a4ac64a
Create Date: 2026-10-30 12:00:00.000000

다음 상담 전 확인할 사항 목록(18.1절). 회차마다 한 행에 JSON 목록 하나 — 추가 질문(c5e1f7a2d9b3)과 같은 꼴.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'e4b7c9a1f2d6'
down_revision: Union[str, None] = '1a685a4ac64a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('session_followup_checks',
    sa.Column('session_id', sa.Uuid(), nullable=False),
    sa.Column('items', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=False),
    sa.Column('updated_by_id', sa.Uuid(), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['session_id'], ['consultation_sessions.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['updated_by_id'], ['users.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_session_followup_checks_session_id'), 'session_followup_checks', ['session_id'], unique=True)


def downgrade() -> None:
    op.drop_index(op.f('ix_session_followup_checks_session_id'), table_name='session_followup_checks')
    op.drop_table('session_followup_checks')
