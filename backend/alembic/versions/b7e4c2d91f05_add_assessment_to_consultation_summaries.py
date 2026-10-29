"""add assessment to consultation summaries

Revision ID: b7e4c2d91f05
Revises: 6f75791a0a3c
Create Date: 2026-10-27 12:00:00.000000

상담 요약 사정 관점 4칸(조사 후 변화 · 강점과 자원 · 위험요인 · 원하는 변화, 10/27 디자인 NoteWrite).
{칸 이름: {text, segment_ids}} 하나를 JSON 으로 둔다. 기존 요약은 null 로 두고 응답에서 빈 칸으로 보인다.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'b7e4c2d91f05'
down_revision: Union[str, None] = '6f75791a0a3c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('consultation_summaries', sa.Column('assessment', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=True))


def downgrade() -> None:
    op.drop_column('consultation_summaries', 'assessment')
