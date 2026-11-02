"""add signup tables

Revision ID: 7a1c5e9b3d20
Revises: d0e1f2a3b4c5
Create Date: 2026-11-02 16:16:23.914832

회원가입(이메일 인증번호 → 대기 신청 → 관리자 승인). API_CONTRACT 3절 '회원가입'.
인증번호 단계(signup_email_codes, 이메일당 한 행)와 대기 신청(signup_requests)을 나눈다(app/models/signup.py 머리말).
대기 신청은 이메일당 하나(status = 'PENDING' 부분 유일 색인). 기존 표는 바꾸지 않는다.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '7a1c5e9b3d20'
down_revision: Union[str, None] = 'd0e1f2a3b4c5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('signup_email_codes',
    sa.Column('email', sa.String(length=255), nullable=False),
    sa.Column('code_hash', sa.String(length=64), nullable=True),
    sa.Column('code_expires_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('failed_attempts', sa.Integer(), server_default=sa.text('0'), nullable=False),
    sa.Column('last_sent_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('window_started_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('send_count', sa.Integer(), nullable=False),
    sa.Column('token_hash', sa.String(length=64), nullable=True),
    sa.Column('token_expires_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('email'),
    sa.UniqueConstraint('token_hash')
    )
    op.create_index(op.f('ix_signup_email_codes_last_sent_at'), 'signup_email_codes', ['last_sent_at'], unique=False)
    op.create_table('signup_requests',
    sa.Column('email', sa.String(length=255), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('hashed_password', sa.String(length=255), nullable=True),
    sa.Column('status', sa.Enum('PENDING', 'APPROVED', 'REJECTED', name='signup_request_status', native_enum=False, length=20), nullable=False),
    sa.Column('role', sa.Enum('COUNSELOR', 'ADMIN', name='signup_request_role', native_enum=False, length=20), nullable=True),
    sa.Column('user_id', sa.Uuid(), nullable=True),
    sa.Column('decided_by_id', sa.Uuid(), nullable=True),
    sa.Column('decided_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['decided_by_id'], ['users.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_signup_requests_email'), 'signup_requests', ['email'], unique=False)
    op.create_index(op.f('ix_signup_requests_status'), 'signup_requests', ['status'], unique=False)
    op.create_index('uq_signup_requests_pending_email', 'signup_requests', ['email'], unique=True, postgresql_where=sa.text("status = 'PENDING'"), sqlite_where=sa.text("status = 'PENDING'"))


def downgrade() -> None:
    op.drop_index('uq_signup_requests_pending_email', table_name='signup_requests', postgresql_where=sa.text("status = 'PENDING'"), sqlite_where=sa.text("status = 'PENDING'"))
    op.drop_index(op.f('ix_signup_requests_status'), table_name='signup_requests')
    op.drop_index(op.f('ix_signup_requests_email'), table_name='signup_requests')
    op.drop_table('signup_requests')
    op.drop_index(op.f('ix_signup_email_codes_last_sent_at'), table_name='signup_email_codes')
    op.drop_table('signup_email_codes')
