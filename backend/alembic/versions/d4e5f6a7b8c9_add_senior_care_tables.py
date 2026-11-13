"""add senior care tables

Revision ID: d4e5f6a7b8c9
Revises: c7d8e9f0a1b2
Create Date: 2026-11-13 11:00:00.000000

고령자 건강상담(API_CONTRACT 27절, feature/senior). 사례 대상 종류(cases.subject_type, 있던 사례는 모두 CHILD),
고령자 기본정보(senior_profiles, 사례 1건에 1줄), 건강측정(health_measurements, 측정 1번에 1줄 · 그 밖 결과 JSON),
다음 상담 확인사항(next_checks).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'd4e5f6a7b8c9'
down_revision: Union[str, None] = 'c7d8e9f0a1b2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('senior_profiles',
    sa.Column('case_id', sa.Uuid(), nullable=False),
    sa.Column('living_arrangement', sa.Enum('ALONE', 'COUPLE', 'WITH_FAMILY', 'FACILITY', 'OTHER', name='living_arrangement', native_enum=False, length=20), nullable=True),
    sa.Column('care_grade', sa.Enum('GRADE_1', 'GRADE_2', 'GRADE_3', 'GRADE_4', 'GRADE_5', 'COGNITIVE_SUPPORT', 'NONE', 'UNKNOWN', name='long_term_care_grade', native_enum=False, length=20), nullable=True),
    sa.Column('health_notes', sa.Text(), nullable=True),
    sa.Column('care_notes', sa.Text(), nullable=True),
    sa.Column('updated_by_id', sa.Uuid(), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['case_id'], ['cases.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['updated_by_id'], ['users.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_senior_profiles_case_id'), 'senior_profiles', ['case_id'], unique=True)
    op.create_table('health_measurements',
    sa.Column('case_id', sa.Uuid(), nullable=False),
    sa.Column('session_id', sa.Uuid(), nullable=True),
    sa.Column('measured_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('systolic', sa.Integer(), nullable=True),
    sa.Column('diastolic', sa.Integer(), nullable=True),
    sa.Column('pulse', sa.Integer(), nullable=True),
    sa.Column('blood_glucose', sa.Integer(), nullable=True),
    sa.Column('glucose_timing', sa.Enum('FASTING', 'POST_MEAL', 'RANDOM', name='glucose_timing', native_enum=False, length=10), nullable=True),
    sa.Column('weight_kg', sa.Float(), nullable=True),
    sa.Column('body_temp_c', sa.Float(), nullable=True),
    sa.Column('extra_results', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=False),
    sa.Column('note', sa.Text(), nullable=True),
    sa.Column('created_by_id', sa.Uuid(), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['case_id'], ['cases.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['created_by_id'], ['users.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['session_id'], ['consultation_sessions.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_health_measurements_case_id'), 'health_measurements', ['case_id'], unique=False)
    op.create_index(op.f('ix_health_measurements_measured_at'), 'health_measurements', ['measured_at'], unique=False)
    op.create_index(op.f('ix_health_measurements_session_id'), 'health_measurements', ['session_id'], unique=False)
    op.create_table('next_checks',
    sa.Column('case_id', sa.Uuid(), nullable=False),
    sa.Column('source_session_id', sa.Uuid(), nullable=True),
    sa.Column('text', sa.Text(), nullable=False),
    sa.Column('basis', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=False),
    sa.Column('origin', sa.Enum('AI', 'RULE', 'COUNSELOR', name='next_check_origin', native_enum=False, length=10), nullable=False),
    sa.Column('edited', sa.Boolean(), nullable=False),
    sa.Column('status', sa.Enum('OPEN', 'DONE', 'DROPPED', name='next_check_status', native_enum=False, length=10), nullable=False),
    sa.Column('checked_session_id', sa.Uuid(), nullable=True),
    sa.Column('checked_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('result_note', sa.Text(), nullable=True),
    sa.Column('created_by_id', sa.Uuid(), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['case_id'], ['cases.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['checked_session_id'], ['consultation_sessions.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['created_by_id'], ['users.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['source_session_id'], ['consultation_sessions.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_next_checks_case_id'), 'next_checks', ['case_id'], unique=False)
    op.create_index(op.f('ix_next_checks_source_session_id'), 'next_checks', ['source_session_id'], unique=False)
    op.create_index(op.f('ix_next_checks_status'), 'next_checks', ['status'], unique=False)
    op.add_column('cases', sa.Column('subject_type', sa.Enum('CHILD', 'SENIOR', name='subject_type', native_enum=False, length=10), server_default='CHILD', nullable=False))
    op.create_index(op.f('ix_cases_subject_type'), 'cases', ['subject_type'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_cases_subject_type'), table_name='cases')
    op.drop_column('cases', 'subject_type')
    op.drop_index(op.f('ix_next_checks_status'), table_name='next_checks')
    op.drop_index(op.f('ix_next_checks_source_session_id'), table_name='next_checks')
    op.drop_index(op.f('ix_next_checks_case_id'), table_name='next_checks')
    op.drop_table('next_checks')
    op.drop_index(op.f('ix_health_measurements_session_id'), table_name='health_measurements')
    op.drop_index(op.f('ix_health_measurements_measured_at'), table_name='health_measurements')
    op.drop_index(op.f('ix_health_measurements_case_id'), table_name='health_measurements')
    op.drop_table('health_measurements')
    op.drop_index(op.f('ix_senior_profiles_case_id'), table_name='senior_profiles')
    op.drop_table('senior_profiles')
