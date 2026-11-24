"""add child session question drafts

Revision ID: a1b2c3d4e5f7
Revises: e9f1a2b3c4d6
Create Date: 2026-11-24 12:00:00.000000

아이 앱 '이번 회차 맞춤 질문' AI 초안(API_CONTRACT 24절). items 는 처음부터 items_enc 에 암호문으로 둔다(평문 칸은 빈 목록).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'a1b2c3d4e5f7'
down_revision: Union[str, None] = 'e9f1a2b3c4d6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_json = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql')


def upgrade() -> None:
    op.create_table(
        'child_session_question_drafts',
        sa.Column('case_id', sa.Uuid(), sa.ForeignKey('cases.id', ondelete='CASCADE'), nullable=False),
        sa.Column('session_id', sa.Uuid(), sa.ForeignKey('consultation_sessions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('items', _json, nullable=False),
        sa.Column('items_enc', sa.Text(), nullable=True),
        sa.Column('created_by_id', sa.Uuid(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_child_session_question_drafts_case_id'), 'child_session_question_drafts', ['case_id'], unique=False
    )
    op.create_index(
        op.f('ix_child_session_question_drafts_session_id'), 'child_session_question_drafts', ['session_id'], unique=True
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_child_session_question_drafts_session_id'), table_name='child_session_question_drafts')
    op.drop_index(op.f('ix_child_session_question_drafts_case_id'), table_name='child_session_question_drafts')
    op.drop_table('child_session_question_drafts')
