"""add child_app_links.silent_days

Revision ID: c7d8e9f1a2b3
Revises: b6c7d8e9f1a2
Create Date: 2026-11-19 18:00:00.000000

아이 연계 응답 상태의 '기준' 일수(5 · 7 · 10, 기본 7). 마지막 응답 뒤 이만큼 지나면 '안부 확인 필요'(11/19 콩콩 디자인).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c7d8e9f1a2b3'
down_revision: Union[str, None] = 'b6c7d8e9f1a2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('child_app_links') as batch:
        batch.add_column(sa.Column('silent_days', sa.Integer(), nullable=False, server_default='7'))


def downgrade() -> None:
    with op.batch_alter_table('child_app_links') as batch:
        batch.drop_column('silent_days')
