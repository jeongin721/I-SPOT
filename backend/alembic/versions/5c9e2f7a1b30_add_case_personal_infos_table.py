"""add case_personal_infos table

Revision ID: 5c9e2f7a1b30
Revises: 1a685a4ac64a
Create Date: 2026-10-30 12:00:00.000000

사례의 개인 식별 정보(서식 4 의 아동 실명 · 생년월일 · 사례관리대상자 · 면접대상자 · 가족관계 · 건강정도)를
AES-256-GCM 으로 암호화해 사례당 한 행으로 둔다(2026-10-30 팀 결정, app/core/pii_crypto.py).
값 칸은 모두 암호문(Text)이고, child_name_index 는 이름 정확 검색용 HMAC 이다.

되돌리면(downgrade) 이 표를 지우므로 저장한 실명이 모두 사라진다(backend/README.md).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '5c9e2f7a1b30'
down_revision: Union[str, None] = '1a685a4ac64a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('case_personal_infos',
    sa.Column('case_id', sa.Uuid(), nullable=False),
    sa.Column('child_name_enc', sa.Text(), nullable=True),
    sa.Column('child_name_index', sa.String(length=64), nullable=True),
    sa.Column('child_birth_date_enc', sa.Text(), nullable=True),
    sa.Column('target_person_enc', sa.Text(), nullable=True),
    sa.Column('interviewee_enc', sa.Text(), nullable=True),
    sa.Column('family_members_enc', sa.Text(), nullable=True),
    sa.Column('health_enc', sa.Text(), nullable=True),
    sa.Column('updated_by_id', sa.Uuid(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['case_id'], ['cases.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['updated_by_id'], ['users.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('case_id')
    )
    op.create_index(op.f('ix_case_personal_infos_child_name_index'), 'case_personal_infos', ['child_name_index'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_case_personal_infos_child_name_index'), table_name='case_personal_infos')
    op.drop_table('case_personal_infos')
