"""add closure_review_at to cases

Revision ID: b8c9d0e1f2a3
Revises: a7d8e9f0b1c2
Create Date: 2026-10-30 17:00:00.000000

종결 검토에 등록한 시각(내담자 정보 '종결 검토 등록'). 등록 전 · 취소하면 null.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b8c9d0e1f2a3'
down_revision: Union[str, None] = 'a7d8e9f0b1c2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('cases', sa.Column('closure_review_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column('cases', 'closure_review_at')
