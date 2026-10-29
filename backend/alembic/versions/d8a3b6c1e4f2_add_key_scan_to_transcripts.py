"""add key_scan to transcripts

Revision ID: d8a3b6c1e4f2
Revises: c5e1f7a2d9b3
Create Date: 2026-10-28 18:00:00.000000

STT 검수 '1차 임시 핵심 발화'(API_CONTRACT 7절, PROPOSAL_stt_key_scan.md). {status, model, segments} 를 JSON 으로 둔다.
기존 전사본은 null(스캔 안 함).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'd8a3b6c1e4f2'
down_revision: Union[str, None] = 'c5e1f7a2d9b3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('transcripts', sa.Column('key_scan', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=True))


def downgrade() -> None:
    op.drop_column('transcripts', 'key_scan')
