"""add session_overall_risk_assessments table

Revision ID: 1a685a4ac64a
Revises: d8a3b6c1e4f2
Create Date: 2026-10-29 14:29:39.336372

회차 전체 상담원 위험도 판단(상/중/하 하나, API_CONTRACT 11.1절). 10/27 디자인의 SignalReview 화면이 쓴다.
회차당 한 행(session_id 유니크)이고, 유형별 판단 표(session_risk_assessments)는 그대로 둔다.
ai_level 은 판단 당시 유형별 AI 제안(1~5) 가운데 가장 높은 값이다.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '1a685a4ac64a'
down_revision: Union[str, None] = 'd8a3b6c1e4f2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('session_overall_risk_assessments',
    sa.Column('session_id', sa.Uuid(), nullable=False),
    sa.Column('counselor_level', sa.Enum('HIGH', 'MEDIUM', 'LOW', name='risk_level', native_enum=False, length=10), nullable=False),
    sa.Column('reason', sa.String(length=1000), nullable=True),
    sa.Column('ai_level', sa.Integer(), nullable=True),
    sa.Column('assessed_by_id', sa.Uuid(), nullable=True),
    sa.Column('assessed_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint('ai_level IS NULL OR (ai_level >= 1 AND ai_level <= 5)', name='ck_overall_risk_assessment_ai_level'),
    sa.ForeignKeyConstraint(['assessed_by_id'], ['users.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['session_id'], ['consultation_sessions.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('session_id', name='uq_overall_risk_assessment_session')
    )


def downgrade() -> None:
    op.drop_table('session_overall_risk_assessments')
