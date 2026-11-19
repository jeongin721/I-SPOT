"""add session_briefing_checks table

Revision ID: e3f4a5b6c7d8
Revises: d2e3f4a5b6c7
Create Date: 2026-11-11 15:00:00.000000

상담 전 브리핑 '확인할 사항' 체크(API_CONTRACT 26절). 회차마다 확인함으로 표시한 문장 목록 한 행.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'e3f4a5b6c7d8'
down_revision: Union[str, None] = 'd2e3f4a5b6c7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_json = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql')


def upgrade() -> None:
    op.create_table('session_briefing_checks',
    sa.Column('session_id', sa.Uuid(), nullable=False),
    sa.Column('checked', _json, nullable=False),
    sa.Column('updated_by_id', sa.Uuid(), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['session_id'], ['consultation_sessions.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['updated_by_id'], ['users.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_session_briefing_checks_session_id'), 'session_briefing_checks', ['session_id'], unique=True)


def downgrade() -> None:
    op.drop_index(op.f('ix_session_briefing_checks_session_id'), table_name='session_briefing_checks')
    op.drop_table('session_briefing_checks')
