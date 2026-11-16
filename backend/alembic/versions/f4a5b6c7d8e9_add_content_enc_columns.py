"""add *_enc columns for counseling content encryption (stage 1)

Revision ID: f4a5b6c7d8e9
Revises: c7d8e9f0a1b2
Create Date: 2026-11-16 12:00:00.000000

상담 본문 앱 암호화 1단계(2026-11-16, 민규님과 합의). 아래 칸마다 암호문 칸 `<칸>_enc`(Text, null 허용)를 더한다.

- documents.content
- transcript_segments.text
- consultation_summaries.overview · key_points · counselor_note
- consultation_sessions.memo
- ai_analyses.result

새 코드는 `_enc` 에만 쓰고 평문 칸은 빈 값으로 둔다. 기존 평문은 scripts/encrypt_content_columns.py 로 옮긴다.
평문 칸은 여기서 지우지 않는다(옮기기 · 확인 뒤 다음 PR).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'f4a5b6c7d8e9'
down_revision: Union[str, None] = 'c7d8e9f0a1b2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

COLUMNS = (
    ('documents', 'content_enc'),
    ('transcript_segments', 'text_enc'),
    ('consultation_summaries', 'overview_enc'),
    ('consultation_summaries', 'key_points_enc'),
    ('consultation_summaries', 'counselor_note_enc'),
    ('consultation_sessions', 'memo_enc'),
    ('ai_analyses', 'result_enc'),
)


def upgrade() -> None:
    for table, column in COLUMNS:
        with op.batch_alter_table(table) as batch:
            batch.add_column(sa.Column(column, sa.Text(), nullable=True))


def downgrade() -> None:
    # 내리기 전에 암호문을 평문 칸으로 되돌려 놓지 않으면 새 코드가 쓴 본문이 사라진다
    # (scripts/encrypt_content_columns.py --decrypt-back).
    for table, column in reversed(COLUMNS):
        with op.batch_alter_table(table) as batch:
            batch.drop_column(column)
