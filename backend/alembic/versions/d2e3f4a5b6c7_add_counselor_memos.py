"""add counselor_memos table

Revision ID: d2e3f4a5b6c7
Revises: c7d8e9f0a1b2
Create Date: 2026-11-10 22:00:00.000000

상담사 메모(앱 · 메모, API_CONTRACT 25절). 쓴 상담사만 보는 메모 한 행. 본문은 암호화한 글자(text_enc)만 둔다.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd2e3f4a5b6c7'
down_revision: Union[str, None] = 'c7d8e9f0a1b2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('counselor_memos',
    sa.Column('owner_id', sa.Uuid(), nullable=False),
    sa.Column('case_id', sa.Uuid(), nullable=True),
    sa.Column('text_enc', sa.Text(), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['case_id'], ['cases.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['owner_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_counselor_memos_case_id'), 'counselor_memos', ['case_id'], unique=False)
    op.create_index('ix_counselor_memos_owner_created', 'counselor_memos', ['owner_id', 'created_at'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_counselor_memos_owner_created', table_name='counselor_memos')
    op.drop_index(op.f('ix_counselor_memos_case_id'), table_name='counselor_memos')
    op.drop_table('counselor_memos')
