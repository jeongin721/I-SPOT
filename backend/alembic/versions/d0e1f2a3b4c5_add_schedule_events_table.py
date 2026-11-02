"""add schedule_events table

Revision ID: d0e1f2a3b4c5
Revises: c9d0e1f2a3b4
Create Date: 2026-11-02 10:00:00.000000

일정(상담 일정 · 개인 · 기관 일정 · 최초접수 법정 기한 완료 표시). API_CONTRACT 19절.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'd0e1f2a3b4c5'
down_revision: Union[str, None] = 'c9d0e1f2a3b4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_JSON = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql')


def upgrade() -> None:
    op.create_table('schedule_events',
    sa.Column('owner_id', sa.Uuid(), nullable=False),
    sa.Column('kind', sa.Enum('CONSULT', 'OTHER', name='schedule_kind', native_enum=False, length=20), nullable=False),
    sa.Column('consult_type', sa.Enum('REGULAR', 'INITIAL', 'VISIT', 'PHONE', 'CLOSING', name='schedule_consult_type', native_enum=False, length=20), nullable=True),
    sa.Column('category', sa.Enum('AGENCY_MEETING', 'CASE_MEETING', 'INTAKE', 'SUPERVISION', 'TRAINING', 'FIELD_WORK', 'LEAVE', 'ETC', name='schedule_category', native_enum=False, length=30), nullable=True),
    sa.Column('case_id', sa.Uuid(), nullable=True),
    sa.Column('title', sa.String(length=100), nullable=True),
    sa.Column('event_date', sa.Date(), nullable=False),
    sa.Column('event_time', sa.String(length=5), nullable=True),
    sa.Column('place', sa.String(length=100), nullable=True),
    sa.Column('important', sa.Boolean(), nullable=False),
    sa.Column('shared', sa.Boolean(), nullable=False),
    sa.Column('deadline_done', _JSON, nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['case_id'], ['cases.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['owner_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_schedule_events_case_id'), 'schedule_events', ['case_id'], unique=False)
    op.create_index(op.f('ix_schedule_events_event_date'), 'schedule_events', ['event_date'], unique=False)
    op.create_index(op.f('ix_schedule_events_owner_id'), 'schedule_events', ['owner_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_schedule_events_owner_id'), table_name='schedule_events')
    op.drop_index(op.f('ix_schedule_events_event_date'), table_name='schedule_events')
    op.drop_index(op.f('ix_schedule_events_case_id'), table_name='schedule_events')
    op.drop_table('schedule_events')
