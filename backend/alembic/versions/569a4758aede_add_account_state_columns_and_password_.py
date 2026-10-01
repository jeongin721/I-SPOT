"""계정 상태 칸과 비밀번호 이력 표 추가

팀 회의 결정(2026-09-18) — 임시 비밀번호 강제 변경, 로그인 5회 실패 잠금,
2개월 미접속 휴면, 이전 비밀번호 재사용 금지, 강제 로그아웃, 접속 기록(IP · 브라우저).

기존 행이 있으므로 필수 칸에는 server_default 를 준다.
Boolean 기본값은 sa.false() 를 쓴다 — PostgreSQL 은 0 을 받지 않는다.

기존 계정의 last_login_at 은 배포 시각으로 채운다. 비워 두면 휴면 판정이 created_at 을
쓰므로, 만든 지 60일(DORMANT_AFTER_DAYS)이 넘은 기존 계정이 배포 뒤 첫 로그인에서
곧바로 휴면이 된다. 이전 로그인 기록이 없으니 "배포 시점부터 센다" 로 본다.
CURRENT_TIMESTAMP 는 SQLite · PostgreSQL 모두에서 된다.

Revision ID: 569a4758aede
Revises: a4d05486e8c9
Create Date: 2026-09-18 17:16:05.931862

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '569a4758aede'
down_revision: Union[str, None] = 'a4d05486e8c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('user_password_history',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('hashed_password', sa.String(length=255), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_user_password_history_user_id'), 'user_password_history', ['user_id'], unique=False)
    op.add_column('audit_logs', sa.Column('status', sa.String(length=20), server_default='SUCCESS', nullable=False))
    op.add_column('audit_logs', sa.Column('error_code', sa.String(length=100), nullable=True))
    op.add_column('audit_logs', sa.Column('ip_address', sa.String(length=45), nullable=True))
    op.add_column('audit_logs', sa.Column('user_agent', sa.String(length=255), nullable=True))
    op.create_index(op.f('ix_audit_logs_status'), 'audit_logs', ['status'], unique=False)
    op.add_column('users', sa.Column('must_change_password', sa.Boolean(), server_default=sa.false(), nullable=False))
    op.add_column('users', sa.Column('password_changed_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('users', sa.Column('last_login_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('users', sa.Column('dormant_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('users', sa.Column('failed_login_count', sa.Integer(), server_default=sa.text('0'), nullable=False))
    op.add_column('users', sa.Column('locked_until', sa.DateTime(timezone=True), nullable=True))
    op.add_column('users', sa.Column('anonymized_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('users', sa.Column('token_version', sa.Integer(), server_default=sa.text('0'), nullable=False))
    # 기존 계정이 배포 뒤 첫 로그인에서 바로 휴면이 되지 않게 한다(위 설명).
    op.execute(sa.text("UPDATE users SET last_login_at = CURRENT_TIMESTAMP WHERE last_login_at IS NULL"))
    op.create_index(op.f('ix_users_dormant_at'), 'users', ['dormant_at'], unique=False)
    op.create_index(op.f('ix_users_last_login_at'), 'users', ['last_login_at'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_users_last_login_at'), table_name='users')
    op.drop_index(op.f('ix_users_dormant_at'), table_name='users')
    op.drop_column('users', 'token_version')
    op.drop_column('users', 'anonymized_at')
    op.drop_column('users', 'locked_until')
    op.drop_column('users', 'failed_login_count')
    op.drop_column('users', 'dormant_at')
    op.drop_column('users', 'last_login_at')
    op.drop_column('users', 'password_changed_at')
    op.drop_column('users', 'must_change_password')
    op.drop_index(op.f('ix_audit_logs_status'), table_name='audit_logs')
    op.drop_column('audit_logs', 'user_agent')
    op.drop_column('audit_logs', 'ip_address')
    op.drop_column('audit_logs', 'error_code')
    op.drop_column('audit_logs', 'status')
    op.drop_index(op.f('ix_user_password_history_user_id'), table_name='user_password_history')
    op.drop_table('user_password_history')
