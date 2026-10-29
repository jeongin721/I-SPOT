"""add session_followup_questions table

Revision ID: c5e1f7a2d9b3
Revises: b7e4c2d91f05
Create Date: 2026-10-28 15:00:00.000000

승인한 추가 질문 목록(18절, PROPOSAL_ai_suggestions_case_context.md §7 답 4). 회차마다 한 행에 JSON 목록 하나.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'c5e1f7a2d9b3'
down_revision: Union[str, None] = 'b7e4c2d91f05'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('session_followup_questions',
    sa.Column('session_id', sa.Uuid(), nullable=False),
    sa.Column('questions', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=False),
    sa.Column('updated_by_id', sa.Uuid(), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['session_id'], ['consultation_sessions.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['updated_by_id'], ['users.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_session_followup_questions_session_id'), 'session_followup_questions', ['session_id'], unique=True)


def downgrade() -> None:
    op.drop_index(op.f('ix_session_followup_questions_session_id'), table_name='session_followup_questions')
    op.drop_table('session_followup_questions')
