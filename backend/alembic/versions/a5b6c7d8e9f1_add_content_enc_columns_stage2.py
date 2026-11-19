"""add *_enc columns for counseling content encryption (stage 2)

Revision ID: a5b6c7d8e9f1
Revises: f4a5b6c7d8e9
Create Date: 2026-11-17 10:00:00.000000

상담 본문 앱 암호화 2단계(2026-11-16, 민규님과 합의 — 1단계에 바로 이어서). 아래 칸마다 암호문 칸 `<칸>_enc`(Text, null 허용)를 더한다.

- session_source_documents.text · note_draft · followup_draft
- cases.linked_background · intake_guardian_relation · intake_problem · intake_attitude · intake_environment · intake_opinion · notes
- session_followup_questions.questions
- case_closure_reviews.summary · edits · report
- case_forms.values
- child_app_events.payload · child_app_ai_drafts.items
- docbox_files.preview_text

1단계와 같이 새 코드는 `_enc` 에만 쓰고 평문 칸은 빈 값으로 둔다. 기존 평문은 scripts/encrypt_content_columns.py 로 옮긴다.
평문 칸은 여기서 지우지 않는다(옮기기 · 확인 뒤 다음 PR).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a5b6c7d8e9f1'
down_revision: Union[str, None] = 'f4a5b6c7d8e9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

COLUMNS = {
    'session_source_documents': ('text_enc', 'note_draft_enc', 'followup_draft_enc'),
    'cases': (
        'linked_background_enc',
        'intake_guardian_relation_enc',
        'intake_problem_enc',
        'intake_attitude_enc',
        'intake_environment_enc',
        'intake_opinion_enc',
        'notes_enc',
    ),
    'session_followup_questions': ('questions_enc',),
    'case_closure_reviews': ('summary_enc', 'edits_enc', 'report_enc'),
    'case_forms': ('values_enc',),
    'child_app_events': ('payload_enc',),
    'child_app_ai_drafts': ('items_enc',),
    'docbox_files': ('preview_text_enc',),
}


def upgrade() -> None:
    for table, columns in COLUMNS.items():
        with op.batch_alter_table(table) as batch:
            for column in columns:
                batch.add_column(sa.Column(column, sa.Text(), nullable=True))


def downgrade() -> None:
    # 내리기 전에 암호문을 평문 칸으로 되돌려 놓지 않으면 새 코드가 쓴 값이 사라진다
    # (scripts/encrypt_content_columns.py --decrypt-back --apply).
    for table, columns in reversed(list(COLUMNS.items())):
        with op.batch_alter_table(table) as batch:
            for column in reversed(columns):
                batch.drop_column(column)
