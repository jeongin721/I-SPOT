"""notices table, audio_files.consent_at, AMBER answers need ack

Revision ID: d8e9f1a2b3c4
Revises: c7d8e9f1a2b3
Create Date: 2026-11-20 18:00:00.000000

- 사내 공지사항(상담사 앱 · 홈, API_CONTRACT 28절).
- 폰 앱 녹음의 '녹음 동의 완료'를 확인한 시각(audio_files.consent_at).
- 살펴볼 답(AMBER)도 상담사가 확인하면 '확인 필요'가 꺼지게 확인할 줄(needs_ack)로 남긴다. 이미 있는 줄은 사례마다
  가장 최근 답 묶음이 AMBER 일 때만 바꾼다(지금 목록에 '확인 필요'로 떠 있는 것만 — 지난 답이 한꺼번에 알림으로 뜨지 않게).
  아이가 만든 데이터는 지우지 않는다(확인 표시 칸만 바꾼다).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd8e9f1a2b3c4'
down_revision: Union[str, None] = 'c7d8e9f1a2b3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'notices',
        sa.Column('title', sa.String(length=120), nullable=False),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('important', sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column('team', sa.String(length=40), nullable=True),
        sa.Column('author_id', sa.Uuid(), nullable=True),
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['author_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )

    with op.batch_alter_table('audio_files') as batch:
        batch.add_column(sa.Column('consent_at', sa.DateTime(timezone=True), nullable=True))

    bind = op.get_bind()
    rows = bind.execute(
        sa.text(
            "SELECT id, case_id, level, needs_ack FROM child_app_events "
            "WHERE kind = 'ANSWERS' ORDER BY case_id, created_at DESC"
        )
    ).fetchall()
    seen = set()
    flip = []

    for event_id, case_id, level, needs_ack in rows:
        if case_id in seen:
            continue

        seen.add(case_id)

        if level == 'AMBER' and not needs_ack:
            flip.append(event_id)

    for event_id in flip:
        bind.execute(sa.text("UPDATE child_app_events SET needs_ack = :yes WHERE id = :id"), {"yes": True, "id": event_id})


def downgrade() -> None:
    # needs_ack 로 바꾼 AMBER 줄은 되돌리지 않는다(확인 기록이 남았을 수 있다).
    with op.batch_alter_table('audio_files') as batch:
        batch.drop_column('consent_at')

    op.drop_table('notices')
