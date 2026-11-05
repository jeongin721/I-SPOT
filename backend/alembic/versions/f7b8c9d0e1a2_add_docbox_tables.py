"""add docbox tables

Revision ID: f7b8c9d0e1a2
Revises: e9a4c1d7b2f6
Create Date: 2026-11-05 12:00:00.000000

문서함(기관 서식 · 참고 문서 공용 보관, API_CONTRACT 23절).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'f7b8c9d0e1a2'
down_revision: Union[str, None] = 'e9a4c1d7b2f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('docbox_folders',
    sa.Column('name', sa.String(length=40), nullable=False),
    sa.Column('created_by_id', sa.Uuid(), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['created_by_id'], ['users.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('name')
    )
    op.create_table('docbox_files',
    sa.Column('folder_id', sa.Uuid(), nullable=True),
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('content_type', sa.String(length=100), nullable=False),
    sa.Column('size_bytes', sa.Integer(), nullable=False),
    sa.Column('path', sa.String(length=255), nullable=False),
    sa.Column('preview_kind', sa.String(length=10), nullable=False),
    sa.Column('preview_text', sa.Text(), nullable=True),
    sa.Column('uploaded_by_id', sa.Uuid(), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['folder_id'], ['docbox_folders.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['uploaded_by_id'], ['users.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_docbox_files_folder_id'), 'docbox_files', ['folder_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_docbox_files_folder_id'), table_name='docbox_files')
    op.drop_table('docbox_files')
    op.drop_table('docbox_folders')
