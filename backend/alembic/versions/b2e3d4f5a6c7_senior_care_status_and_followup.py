"""senior care status, profile fields, follow-up links

Revision ID: b2e3d4f5a6c7
Revises: a1d2c3e4f5b6
Create Date: 2026-11-16 14:00:00.000000

고령자(feature/senior, API_CONTRACT 27절): 기본정보에 복약 여부 · 복약 메모 · 돌봄 필요사항, 돌봄 상태(상담 완료 · 재방문 필요 ·
후속조치 진행 · 서비스 종료), 확인사항에 종류(확인 · 조치) · 기한 · 이어 붙인 일정.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'b2e3d4f5a6c7'
down_revision: Union[str, None] = 'a1d2c3e4f5b6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

JSON = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql')


def upgrade() -> None:
    with op.batch_alter_table('senior_profiles') as batch:
        batch.add_column(sa.Column('takes_medication', sa.Boolean(), nullable=True))
        batch.add_column(sa.Column('medication_notes', sa.Text(), nullable=True))
        batch.add_column(sa.Column('care_needs', JSON, nullable=False, server_default='[]'))
        batch.add_column(sa.Column('care_needs_note', sa.Text(), nullable=True))
        batch.add_column(sa.Column('care_status', sa.Enum('CONSULT_DONE', 'REVISIT_NEEDED', 'FOLLOWUP_IN_PROGRESS', 'SERVICE_ENDED', name='care_status', native_enum=False, length=25), nullable=True))
        batch.add_column(sa.Column('care_status_note', sa.Text(), nullable=True))
        batch.add_column(sa.Column('care_status_changed_at', sa.DateTime(timezone=True), nullable=True))
        batch.create_index(batch.f('ix_senior_profiles_care_status'), ['care_status'], unique=False)

    with op.batch_alter_table('next_checks') as batch:
        batch.add_column(sa.Column('kind', sa.Enum('CHECK', 'ACTION', name='next_check_kind', native_enum=False, length=10), nullable=False, server_default='CHECK'))
        batch.add_column(sa.Column('due_date', sa.Date(), nullable=True))
        batch.add_column(sa.Column('schedule_event_id', sa.Uuid(), nullable=True))
        batch.create_index(batch.f('ix_next_checks_due_date'), ['due_date'], unique=False)
        batch.create_index(batch.f('ix_next_checks_schedule_event_id'), ['schedule_event_id'], unique=False)
        batch.create_foreign_key('next_checks_schedule_event_id_fkey', 'schedule_events', ['schedule_event_id'], ['id'], ondelete='SET NULL')


def downgrade() -> None:
    with op.batch_alter_table('next_checks') as batch:
        batch.drop_constraint('next_checks_schedule_event_id_fkey', type_='foreignkey')
        batch.drop_index(batch.f('ix_next_checks_schedule_event_id'))
        batch.drop_index(batch.f('ix_next_checks_due_date'))
        batch.drop_column('schedule_event_id')
        batch.drop_column('due_date')
        batch.drop_column('kind')

    with op.batch_alter_table('senior_profiles') as batch:
        batch.drop_index(batch.f('ix_senior_profiles_care_status'))
        batch.drop_column('care_status_changed_at')
        batch.drop_column('care_status_note')
        batch.drop_column('care_status')
        batch.drop_column('care_needs_note')
        batch.drop_column('care_needs')
        batch.drop_column('medication_notes')
        batch.drop_column('takes_medication')
