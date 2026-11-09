"""add child app tables

Revision ID: f3a4b5c6d7e8
Revises: f7b8c9d0e1a2
Create Date: 2026-11-09 12:00:00.000000

아이 앱(콩콩) 연결 · 보낸 질문 · 상담사 피드(API_CONTRACT 24절).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'f3a4b5c6d7e8'
down_revision: Union[str, None] = '7a1c5e9b3d20'  # 데모 브랜치의 끝. main 은 f7b8c9d0e1a2
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_json = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql')


def _common() -> list:
    return [
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    ]


def upgrade() -> None:
    op.create_table('child_app_links',
    sa.Column('case_id', sa.Uuid(), nullable=False),
    sa.Column('status', sa.Enum('INVITED', 'LINKED', name='child_app_link_status', native_enum=False, length=20), nullable=False),
    sa.Column('code_hash', sa.String(length=64), nullable=True),
    sa.Column('code_expires_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('device_token_hash', sa.String(length=64), nullable=True),
    sa.Column('linked_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('last_response_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['case_id'], ['cases.id'], ondelete='CASCADE'),
    *_common(),
    )
    op.create_index(op.f('ix_child_app_links_case_id'), 'child_app_links', ['case_id'], unique=True)
    op.create_index(op.f('ix_child_app_links_code_hash'), 'child_app_links', ['code_hash'], unique=True)
    op.create_index(op.f('ix_child_app_links_device_token_hash'), 'child_app_links', ['device_token_hash'], unique=True)

    op.create_table('child_question_sets',
    sa.Column('case_id', sa.Uuid(), nullable=False),
    sa.Column('sent_by_id', sa.Uuid(), nullable=True),
    sa.Column('status', sa.Enum('PENDING', 'ANSWERED', 'REPLACED', name='child_question_set_status', native_enum=False, length=20), nullable=False),
    sa.Column('questions', _json, nullable=False),
    sa.Column('answered_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['case_id'], ['cases.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['sent_by_id'], ['users.id'], ondelete='SET NULL'),
    *_common(),
    )
    op.create_index(op.f('ix_child_question_sets_case_id'), 'child_question_sets', ['case_id'], unique=False)
    op.create_index(op.f('ix_child_question_sets_status'), 'child_question_sets', ['status'], unique=False)

    op.create_table('child_app_events',
    sa.Column('case_id', sa.Uuid(), nullable=False),
    sa.Column('kind', sa.Enum('LINKED', 'QUESTIONS_SENT', 'ANSWERS', 'ALERT', name='child_app_event_kind', native_enum=False, length=20), nullable=False),
    sa.Column('level', sa.Enum('NONE', 'SKIP', 'AMBER', 'RED', name='child_answer_level', native_enum=False, length=10), nullable=False),
    sa.Column('payload', _json, nullable=False),
    sa.Column('needs_ack', sa.Boolean(), server_default=sa.false(), nullable=False),
    sa.Column('acknowledged_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('acknowledged_by_id', sa.Uuid(), nullable=True),
    sa.ForeignKeyConstraint(['case_id'], ['cases.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['acknowledged_by_id'], ['users.id'], ondelete='SET NULL'),
    *_common(),
    )
    op.create_index(op.f('ix_child_app_events_case_id'), 'child_app_events', ['case_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_child_app_events_case_id'), table_name='child_app_events')
    op.drop_table('child_app_events')
    op.drop_index(op.f('ix_child_question_sets_status'), table_name='child_question_sets')
    op.drop_index(op.f('ix_child_question_sets_case_id'), table_name='child_question_sets')
    op.drop_table('child_question_sets')
    op.drop_index(op.f('ix_child_app_links_device_token_hash'), table_name='child_app_links')
    op.drop_index(op.f('ix_child_app_links_code_hash'), table_name='child_app_links')
    op.drop_index(op.f('ix_child_app_links_case_id'), table_name='child_app_links')
    op.drop_table('child_app_links')
