"""add intake dates to cases

Revision ID: f1c2d3e4a5b6
Revises: e4b7c9a1f2d6
Create Date: 2026-10-30 13:00:00.000000

서식 4 ① 날짜 셋 — 신고접수일(report_date) · 사례연계일(linked_date) · 최초면접일(first_interview_date). 모두 비울 수 있다.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'f1c2d3e4a5b6'
down_revision: Union[str, None] = 'e4b7c9a1f2d6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('cases', sa.Column('report_date', sa.Date(), nullable=True))
    op.add_column('cases', sa.Column('linked_date', sa.Date(), nullable=True))
    op.add_column('cases', sa.Column('first_interview_date', sa.Date(), nullable=True))


def downgrade() -> None:
    op.drop_column('cases', 'first_interview_date')
    op.drop_column('cases', 'linked_date')
    op.drop_column('cases', 'report_date')
