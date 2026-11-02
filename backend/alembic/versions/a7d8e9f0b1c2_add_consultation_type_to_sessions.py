"""add consultation_type to consultation_sessions

Revision ID: a7d8e9f0b1c2
Revises: f1c2d3e4a5b6
Create Date: 2026-10-30 15:00:00.000000

상담 유형(초기면담 · 정기상담 · 방문상담 · 기관 면담 · 전화상담). 비울 수 있다.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a7d8e9f0b1c2'
down_revision: Union[str, None] = 'f1c2d3e4a5b6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'consultation_sessions',
        sa.Column(
            'consultation_type',
            sa.Enum('INITIAL', 'REGULAR', 'VISIT', 'OFFICE', 'PHONE', name='consultation_type', native_enum=False, length=20),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column('consultation_sessions', 'consultation_type')
