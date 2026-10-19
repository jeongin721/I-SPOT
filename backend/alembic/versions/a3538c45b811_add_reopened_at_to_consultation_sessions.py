"""add reopened_at to consultation_sessions

Revision ID: a3538c45b811
Revises: d2abcbfb23b7
Create Date: 2026-10-16 16:49:15.141045

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a3538c45b811'
down_revision: Union[str, None] = 'd2abcbfb23b7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 요약 승인을 마지막으로 푼 시각. 옛 행은 비어 있고, 처리 대기 업무는 그때 AI 완료 시각만 쓴다.
    op.add_column('consultation_sessions', sa.Column('reopened_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column('consultation_sessions', 'reopened_at')
