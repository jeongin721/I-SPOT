"""add transcripts.pre_analysis (원문 확정 전 AI 전체 분석)

Revision ID: e9f1a2b3c4d6
Revises: d8e9f1a2b3c4
Create Date: 2026-11-24 12:00:00.000000

ANALYZE_BEFORE_CONFIRM(2026-11-24): STT 결과로 만든 전사 판에 확정 전 AI 전체 분석 결과(AIAnalysisBundle JSON)를 둔다.
원문 인용 · 이름이 들어 있어 pre_analysis_enc 에 암호문으로만 둔다(평문 칸 pre_analysis 는 늘 비어 있음 — 본문 암호화와 같은 모양).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'e9f1a2b3c4d6'
down_revision: Union[str, None] = 'd8e9f1a2b3c4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('transcripts') as batch:
        batch.add_column(sa.Column('pre_analysis', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=True))
        batch.add_column(sa.Column('pre_analysis_enc', sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('transcripts') as batch:
        batch.drop_column('pre_analysis_enc')
        batch.drop_column('pre_analysis')
