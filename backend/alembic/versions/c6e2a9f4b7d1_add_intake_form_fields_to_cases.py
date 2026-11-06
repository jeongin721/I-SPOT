"""add intake form fields to cases

Revision ID: c6e2a9f4b7d1
Revises: f7b8c9d0e1a2
Create Date: 2026-11-05 16:00:00.000000

서식 4 의 '준비 중' 칸 열기(2026-11-05).
① 조치결과 · 피해아동(child_action_result) · 조치결과 · 사례관리대상자(target_action_result) · 위험도(우선, counselor_risk_level) ·
사례연계 경위(linked_background), ② 가족유형(intake_family_type, 11/03 디자인 21개) · 보호자와 아동과의 관계 · 문제력 ·
대상자 태도 · 물리적 환경 · 상담원 소견 및 향후 계획. 모두 비울 수 있고 기존 사례는 null 이다.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c6e2a9f4b7d1'
down_revision: Union[str, None] = 'f7b8c9d0e1a2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TEXT_COLUMNS = (
    'linked_background',
    'intake_guardian_relation',
    'intake_problem',
    'intake_attitude',
    'intake_environment',
    'intake_opinion',
)


def upgrade() -> None:
    op.add_column('cases', sa.Column('child_action_result', sa.Enum('HOME', 'RELATIVE', 'ACQUAINTANCE', 'FOSTER', 'FACILITY', 'HOSPITAL', 'OTHER', name='child_action_result', native_enum=False, length=20), nullable=True))
    op.add_column('cases', sa.Column('target_action_result', sa.Enum('OBSERVATION', 'SEPARATION', 'COMPLAINT', 'OTHER', name='target_action_result', native_enum=False, length=20), nullable=True))
    op.add_column('cases', sa.Column('counselor_risk_level', sa.Enum('HIGH', 'MEDIUM', 'LOW', name='counselor_risk_level', native_enum=False, length=10), nullable=True))
    op.add_column('cases', sa.Column('intake_family_type', sa.Enum('GENERAL', 'FATHER_BEREAVED', 'FATHER_DIVORCED', 'FATHER_LEFT', 'FATHER_SEPARATED', 'MOTHER_BEREAVED', 'MOTHER_DIVORCED', 'MOTHER_LEFT', 'MOTHER_SEPARATED', 'UNMARRIED_FATHER', 'UNMARRIED_MOTHER', 'UNMARRIED_PARENTS', 'FATHER_STEPMOTHER', 'MOTHER_STEPFATHER', 'RELATIVE_CARE', 'FATHER_PARTNER', 'MOTHER_PARTNER', 'FOSTER', 'ADOPTIVE', 'FACILITY', 'OTHER', name='intake_family_type', native_enum=False, length=20), nullable=True))
    for column in TEXT_COLUMNS:
        op.add_column('cases', sa.Column(column, sa.Text(), nullable=True))


def downgrade() -> None:
    for column in reversed(TEXT_COLUMNS):
        op.drop_column('cases', column)
    op.drop_column('cases', 'intake_family_type')
    op.drop_column('cases', 'counselor_risk_level')
    op.drop_column('cases', 'target_action_result')
    op.drop_column('cases', 'child_action_result')
