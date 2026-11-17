"""add child app ai drafts

Revision ID: a9c1d2e3f4b5
Revises: f3a4b5c6d7e8
Create Date: 2026-11-09 18:00:00.000000

아이 앱 AI 초안 — 확인해 볼 점 · 추가 질문(API_CONTRACT 24절).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'a9c1d2e3f4b5'
down_revision: Union[str, None] = 'f3a4b5c6d7e8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_json = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql')


def upgrade() -> None:
    op.create_table(
        'child_app_ai_drafts',
        sa.Column('case_id', sa.Uuid(), sa.ForeignKey('cases.id', ondelete='CASCADE'), nullable=False),
        sa.Column('event_id', sa.Uuid(), sa.ForeignKey('child_app_events.id', ondelete='CASCADE'), nullable=False),
        sa.Column('items', _json, nullable=False),
        sa.Column('created_by_id', sa.Uuid(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_child_app_ai_drafts_case_id'), 'child_app_ai_drafts', ['case_id'], unique=False)
    op.create_index(op.f('ix_child_app_ai_drafts_event_id'), 'child_app_ai_drafts', ['event_id'], unique=True)


def downgrade() -> None:
    op.drop_index(op.f('ix_child_app_ai_drafts_event_id'), table_name='child_app_ai_drafts')
    op.drop_index(op.f('ix_child_app_ai_drafts_case_id'), table_name='child_app_ai_drafts')
    op.drop_table('child_app_ai_drafts')
