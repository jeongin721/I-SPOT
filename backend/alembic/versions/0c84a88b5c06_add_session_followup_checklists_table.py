"""add session_followup_checklists table

Revision ID: 0c84a88b5c06
Revises: 1a685a4ac64a
Create Date: 2026-10-30 11:10:54.801254

다음 상담 체크리스트(19절, specs followup-rag-checklist). 회차마다 한 행(session_id 유니크)에 rag 로 만든
'다음 상담 전 확인할 사항' 과 추가 질문 AI 초안의 공식 근거(검토 통과분만)를 JSON 하나로 둔다.
attempt 는 만들기를 시작할 때마다 1 씩 올려, 늦게 끝난 앞 작업이 새 결과를 덮지 않게 한다.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '0c84a88b5c06'
down_revision: Union[str, None] = '1a685a4ac64a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('session_followup_checklists',
    sa.Column('session_id', sa.Uuid(), nullable=False),
    sa.Column('analysis_id', sa.Uuid(), nullable=True),
    sa.Column('transcript_version', sa.Integer(), nullable=True),
    sa.Column('status', sa.Enum('PROCESSING', 'COMPLETED', 'FAILED', name='followup_checklist_status', native_enum=False, length=20), nullable=False),
    sa.Column('attempt', sa.Integer(), nullable=False),
    sa.Column('provider', sa.String(length=50), nullable=True),
    sa.Column('result', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=True),
    sa.Column('error_code', sa.String(length=50), nullable=True),
    sa.Column('error_message', sa.String(length=500), nullable=True),
    sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['analysis_id'], ['ai_analyses.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['session_id'], ['consultation_sessions.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_session_followup_checklists_session_id'), 'session_followup_checklists', ['session_id'], unique=True)


def downgrade() -> None:
    op.drop_index(op.f('ix_session_followup_checklists_session_id'), table_name='session_followup_checklists')
    op.drop_table('session_followup_checklists')
