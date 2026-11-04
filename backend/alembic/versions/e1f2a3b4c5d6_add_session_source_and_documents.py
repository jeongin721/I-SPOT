"""add session source and session_source_documents table

Revision ID: e1f2a3b4c5d6
Revises: e9a4c1d7b2f6
Create Date: 2026-11-02 15:00:00.000000

회차 자료(녹음 · 상담 기록 문서)와 문서 회차의 문서 글 · 상담 일지 초안 · 4단계 초안. API_CONTRACT 21절.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'e1f2a3b4c5d6'
down_revision: Union[str, None] = 'e9a4c1d7b2f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_JSON = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql')


def upgrade() -> None:
    with op.batch_alter_table('consultation_sessions', schema=None) as batch_op:
        batch_op.add_column(sa.Column('source', sa.Enum('AUDIO', 'DOCUMENT', name='session_source', native_enum=False, length=20), server_default='AUDIO', nullable=False))

    op.create_table('session_source_documents',
    sa.Column('session_id', sa.Uuid(), nullable=False),
    sa.Column('filename', sa.String(length=255), nullable=False),
    sa.Column('file_format', sa.String(length=10), nullable=False),
    sa.Column('text', sa.Text(), nullable=False),
    sa.Column('char_count', sa.Integer(), nullable=False),
    sa.Column('fill_source', sa.String(length=20), nullable=False),
    sa.Column('fill_model', sa.String(length=100), nullable=True),
    sa.Column('note_draft', _JSON, nullable=False),
    sa.Column('followup_draft', _JSON, nullable=True),
    sa.Column('uploaded_by_id', sa.Uuid(), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['session_id'], ['consultation_sessions.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['uploaded_by_id'], ['users.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_session_source_documents_session_id'), 'session_source_documents', ['session_id'], unique=True)


def downgrade() -> None:
    op.drop_index(op.f('ix_session_source_documents_session_id'), table_name='session_source_documents')
    op.drop_table('session_source_documents')
    with op.batch_alter_table('consultation_sessions', schema=None) as batch_op:
        batch_op.drop_column('source')
