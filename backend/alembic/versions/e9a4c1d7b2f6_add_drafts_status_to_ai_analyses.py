"""add drafts_status to ai_analyses

Revision ID: e9a4c1d7b2f6
Revises: 7a1c5e9b3d20
Create Date: 2026-11-04 12:00:00.000000

AI 분석 두 번 저장(I-SPOT_DOCS/docs/PROPOSAL_analysis_signals_first.md §7-2). 학대 신호 확인(2단계) 값을 먼저 저장하고
3 · 4단계 초안을 뒤에 채우는 동안의 상태와 실패 코드. 기존 행은 한 번에 저장한 분석이라 DONE 이다.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e9a4c1d7b2f6'
down_revision: Union[str, None] = '7a1c5e9b3d20'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'ai_analyses',
        sa.Column(
            'drafts_status',
            sa.Enum('PENDING', 'DONE', 'FAILED', name='drafts_status', native_enum=False, length=20),
            server_default='DONE',
            nullable=False,
        ),
    )
    op.add_column('ai_analyses', sa.Column('drafts_error_code', sa.String(length=50), nullable=True))


def downgrade() -> None:
    op.drop_column('ai_analyses', 'drafts_error_code')
    op.drop_column('ai_analyses', 'drafts_status')
