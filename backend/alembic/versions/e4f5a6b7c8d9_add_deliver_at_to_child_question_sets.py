"""add deliver_at to child_question_sets

Revision ID: e4f5a6b7c8d9
Revises: c7d8e9f0a1b2
Create Date: 2026-11-11 15:00:00.000000

아이 앱 질문 '발송 예약'(API_CONTRACT 24절). 이 시각부터 아이 앱에 보인다. 비어 있으면 만든 즉시 보인다 —
이미 있는 행은 모두 비어 있으므로 동작이 바뀌지 않는다. 상태 값 CANCELED 는 문자열 칸이라 DB 변경이 없다.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e4f5a6b7c8d9'
down_revision: Union[str, None] = 'c7d8e9f0a1b2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('child_question_sets') as batch:
        batch.add_column(sa.Column('deliver_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    # 예약해 둔 묶음(PENDING, 예약 시각 전)은 칸이 없어지면 바로 보이게 된다. 내리기 전에 취소 상태로 바꿔 둔다.
    # CANCELED 는 옛 코드가 모르는 값이므로, 보이기 전에 거둔 것도 옛 값 REPLACED 로 돌린다.
    op.execute(
        "UPDATE child_question_sets SET status = 'REPLACED' "
        "WHERE status = 'CANCELED' OR (status = 'PENDING' AND deliver_at > CURRENT_TIMESTAMP)"
    )

    with op.batch_alter_table('child_question_sets') as batch:
        batch.drop_column('deliver_at')
