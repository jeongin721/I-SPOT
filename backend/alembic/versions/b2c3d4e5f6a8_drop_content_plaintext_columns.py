"""drop plaintext columns of encrypted counseling content

Revision ID: b2c3d4e5f6a8
Revises: a1b2c3d4e5f7
Create Date: 2026-11-27 10:00:00.000000

상담 본문 앱 암호화 마지막 단계(2026-11-27). 1 · 2단계(f4a5b6c7d8e9 · a5b6c7d8e9f1)가 `<칸>_enc` 를 더했고,
데모 DB 는 11/26 scripts/encrypt_content_columns --apply · --check(종료 0)로 옮기기를 끝냈다. 이제 옛 평문 칸을 지운다.

평문 칸에 값이 하나라도 남았으면(옮기기 전 · 옮기기 실패) 지우지 않고 멈춘다 — 그 값은 아직 암호문 칸에 없을 수 있다.
남은 칸 이름만 알리고 값은 출력하지 않는다.

내리기(downgrade)는 빈 평문 칸만 다시 만든다. 값은 되살리지 않는다(암호문 칸이 그대로라 1 · 2단계 코드는 암호문을 읽는다).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'b2c3d4e5f6a8'
down_revision: Union[str, None] = 'a1b2c3d4e5f7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TEXT = 'text'
JSON = 'json'

# 표 → (평문 칸, 종류). 내리기 때 다시 만들 모양.
COLUMNS = {
    'ai_analyses': (('result', JSON),),
    'case_closure_reviews': (('summary', JSON), ('edits', JSON), ('report', JSON)),
    'case_forms': (('values', JSON),),
    'cases': (
        ('linked_background', TEXT),
        ('intake_guardian_relation', TEXT),
        ('intake_problem', TEXT),
        ('intake_attitude', TEXT),
        ('intake_environment', TEXT),
        ('intake_opinion', TEXT),
        ('notes', TEXT),
    ),
    'child_app_ai_drafts': (('items', JSON),),
    'child_app_events': (('payload', JSON),),
    'child_session_question_drafts': (('items', JSON),),
    'consultation_sessions': (('memo', TEXT),),
    'consultation_summaries': (('overview', TEXT), ('key_points', JSON), ('counselor_note', TEXT)),
    'docbox_files': (('preview_text', TEXT),),
    'documents': (('content', TEXT),),
    'session_followup_questions': (('questions', JSON),),
    'session_source_documents': (('text', TEXT), ('note_draft', JSON), ('followup_draft', JSON)),
    'transcript_segments': (('text', TEXT),),
    'transcripts': (('pre_analysis', JSON),),
}

# 비었다고 보는 값(옮기기 script 와 같다): NULL · 빈 글자 · JSON null · [] · {}.
_EMPTY_JSON_TEXT = ("null", "[]", "{}")


def _left_count(bind, table: str, column: str, kind: str) -> int:
    col = sa.column(column, sa.JSON() if kind == JSON else sa.Text())
    tbl = sa.table(table, col)

    if kind == TEXT:
        where = sa.and_(col.is_not(None), col != "")
    else:
        as_text = sa.cast(col, sa.Text())
        where = sa.and_(col.is_not(None), sa.func.replace(as_text, " ", "").not_in(_EMPTY_JSON_TEXT))

    return bind.execute(sa.select(sa.func.count()).select_from(tbl).where(where)).scalar_one()


def upgrade() -> None:
    bind = op.get_bind()
    left = [
        f"{table}.{column}"
        for table, columns in COLUMNS.items()
        for column, kind in columns
        if _left_count(bind, table, column, kind)
    ]

    if left:
        raise RuntimeError(
            "평문 칸에 값이 남아 지우지 않습니다. 먼저 옮기기(scripts.encrypt_content_columns --apply → --check)를 "
            f"이 마이그레이션 전 코드로 끝내 주세요: {', '.join(left)}"
        )

    for table, columns in COLUMNS.items():
        with op.batch_alter_table(table) as batch:
            for column, _kind in columns:
                batch.drop_column(column)


def downgrade() -> None:
    json_type = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql')

    for table, columns in reversed(list(COLUMNS.items())):
        with op.batch_alter_table(table) as batch:
            for column, kind in reversed(columns):
                batch.add_column(sa.Column(column, json_type if kind == JSON else sa.Text(), nullable=True))
