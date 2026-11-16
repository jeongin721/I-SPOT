"""add care domain notes

Revision ID: a1d2c3e4f5b6
Revises: d4e5f6a7b8c9
Create Date: 2026-11-16 10:00:00.000000

고령자 회차별 생활 · 정서 영역 기록(식사 · 수면 · 외출 · 사회활동 · 정서)과 이전 대비 변화(feature/senior, API_CONTRACT 27절).
담당자가 확정한 것만 저장한다. 회차 하나에 영역 하나는 한 줄.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'a1d2c3e4f5b6'
down_revision: Union[str, None] = 'd4e5f6a7b8c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('care_domain_notes',
    sa.Column('case_id', sa.Uuid(), nullable=False),
    sa.Column('session_id', sa.Uuid(), nullable=False),
    sa.Column('domain', sa.Enum('MEAL', 'SLEEP', 'OUTING', 'SOCIAL', 'MOOD', name='care_domain', native_enum=False, length=10), nullable=False),
    sa.Column('text', sa.Text(), nullable=True),
    sa.Column('change', sa.Enum('SIMILAR', 'CHANGED', 'NEW', 'NOT_MENTIONED', name='domain_change', native_enum=False, length=15), nullable=False),
    sa.Column('change_note', sa.Text(), nullable=True),
    sa.Column('segment_ids', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=False),
    sa.Column('origin', sa.Enum('AI', 'RULE', 'COUNSELOR', name='next_check_origin', native_enum=False, length=10), nullable=False),
    sa.Column('edited', sa.Boolean(), nullable=False),
    sa.Column('compared_session_id', sa.Uuid(), nullable=True),
    sa.Column('confirmed_by_id', sa.Uuid(), nullable=True),
    sa.Column('confirmed_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['case_id'], ['cases.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['session_id'], ['consultation_sessions.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['compared_session_id'], ['consultation_sessions.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['confirmed_by_id'], ['users.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('session_id', 'domain', name='uq_care_domain_note_session_domain')
    )
    op.create_index(op.f('ix_care_domain_notes_case_id'), 'care_domain_notes', ['case_id'], unique=False)
    op.create_index(op.f('ix_care_domain_notes_session_id'), 'care_domain_notes', ['session_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_care_domain_notes_session_id'), table_name='care_domain_notes')
    op.drop_index(op.f('ix_care_domain_notes_case_id'), table_name='care_domain_notes')
    op.drop_table('care_domain_notes')
