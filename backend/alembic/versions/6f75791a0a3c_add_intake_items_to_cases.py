"""add intake child traits and family situations to cases

Revision ID: 6f75791a0a3c
Revises: a3538c45b811
Create Date: 2026-10-16 17:30:00.000000

초기면접(서식 4 ②)에서 고른 아동 특성 · 가정상황(서식 항목 이름 목록).
기존 사례는 null 로 두고 응답에서 빈 목록으로 보인다.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = '6f75791a0a3c'
down_revision: Union[str, None] = 'a3538c45b811'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('cases', sa.Column('intake_child_traits', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=True))
    op.add_column('cases', sa.Column('intake_family_situations', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=True))


def downgrade() -> None:
    op.drop_column('cases', 'intake_family_situations')
    op.drop_column('cases', 'intake_child_traits')
