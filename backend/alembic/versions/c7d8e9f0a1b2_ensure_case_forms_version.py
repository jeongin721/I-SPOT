"""ensure case_forms version column and one-draft index

Revision ID: c7d8e9f0a1b2
Revises: a9c1d2e3f4b5
Create Date: 2026-11-10 20:00:00.000000

기관 서식 표(case_forms)의 판 번호(version) 칸과 '사례 · 서식마다 임시 저장 하나' 인덱스를, 없을 때만 만든다.

main 은 e5f6a7b8c9d0(case_forms 만들기) 파일을 나중에 고쳐 이 둘을 넣었다. 그 전 파일로 이미 올린 DB
(발표용 데모 서버 deploy/case-tabs-1104)는 alembic 이 끝까지 올라간 것으로 보지만 칸이 없어, main 코드로 바꾸면
기관 서식 화면이 500 이 난다. 새 DB 에서는 e5f6a7b8c9d0 이 이미 만들었으므로 아무것도 하지 않는다.

임시 저장이 이미 둘 이상인 사례가 있으면 인덱스는 만들지 않고 경고만 남긴다(상담원 기록을 지우지 않는다).
판 번호 대조로 겹쳐 쓰기는 그대로 막히고, 중복을 정리한 뒤 다시 올리면 인덱스가 생긴다.
"""
import logging
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c7d8e9f0a1b2'
down_revision: Union[str, None] = 'a9c1d2e3f4b5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_INDEX = 'uq_case_forms_one_draft'
log = logging.getLogger('alembic.runtime.migration')


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if 'version' not in {column['name'] for column in inspector.get_columns('case_forms')}:
        with op.batch_alter_table('case_forms') as batch:
            batch.add_column(sa.Column('version', sa.Integer(), nullable=False, server_default='1'))

    if _INDEX in {index['name'] for index in inspector.get_indexes('case_forms')}:
        return

    duplicates = bind.execute(
        sa.text(
            "SELECT case_id, form_type FROM case_forms WHERE status = 'DRAFT' "
            "GROUP BY case_id, form_type HAVING COUNT(*) > 1"
        )
    ).fetchall()
    if duplicates:
        log.warning('%s: 임시 저장이 둘 이상인 사례 · 서식 %d건이 있어 인덱스를 만들지 않습니다.', _INDEX, len(duplicates))
        return

    op.create_index(
        _INDEX, 'case_forms', ['case_id', 'form_type'], unique=True,
        sqlite_where=sa.text("status = 'DRAFT'"), postgresql_where=sa.text("status = 'DRAFT'"),
    )


def downgrade() -> None:
    # e5f6a7b8c9d0 이 만든 칸 · 인덱스와 구분할 수 없어 되돌리지 않는다.
    pass
