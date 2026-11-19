# Migration 테스트.
#
# 다른 테스트는 migration 대신 metadata.create_all 로 표를 만든다(conftest).
# 기존 행을 고치는 migration 은 그 방식으로는 확인되지 않아, 임시 SQLite 파일에
# 실제로 alembic 을 돌려 본다. 개발 DB 와 테스트 DB 는 건드리지 않는다.

import os
import subprocess
import sys
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, text

BACKEND_DIR = Path(__file__).resolve().parents[1]

# 계정 상태 칸을 추가하기 바로 전 revision
BEFORE_ACCOUNT_STATE = "a4d05486e8c9"

# ai_analyses 에 drafts_status 를 더한 revision(2026-11-04). 부모는 머지 때 main head 로 바뀔 수 있어 파일에서 읽는다.
DRAFTS_STATUS = "e9a4c1d7b2f6"


def _alembic(database_url: str, *args: str) -> None:
    result = subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=BACKEND_DIR,
        env={**os.environ, "DATABASE_URL": database_url},
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr.decode("utf-8", errors="replace")


def test_existing_users_get_last_login_at_so_they_do_not_go_dormant(tmp_path) -> None:
    """
    last_login_at 을 비워 두면 휴면 판정이 created_at 을 쓴다.
    만든 지 60일이 넘은 기존 계정이 배포 뒤 첫 로그인에서 곧바로 휴면이 되면 안 된다.
    """

    database_url = f"sqlite+pysqlite:///{(tmp_path / 'migration.db').as_posix()}"

    _alembic(database_url, "upgrade", BEFORE_ACCOUNT_STATE)

    engine = create_engine(database_url)

    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO users "
                    "(id, email, hashed_password, name, role, is_active, created_at, updated_at) "
                    "VALUES ('0123456789abcdef0123456789abcdef', 'old@example.com', 'x', '기존 계정', "
                    "'COUNSELOR', 1, '2025-01-01 00:00:00', '2025-01-01 00:00:00')"
                )
            )

        _alembic(database_url, "upgrade", "head")

        with engine.connect() as connection:
            last_login_at = connection.scalar(text("SELECT last_login_at FROM users"))

        assert last_login_at is not None

        # 되돌렸다가 다시 올려도 된다.
        _alembic(database_url, "downgrade", "-1")
        _alembic(database_url, "upgrade", "head")
    finally:
        engine.dispose()


def _parent_of(revision: str) -> str:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))

    return ScriptDirectory.from_config(config).get_revision(revision).down_revision


def test_existing_analyses_get_drafts_done_and_downgrade_drops_columns(tmp_path) -> None:
    """
    drafts_status 전에 만든 분석은 한 번에 저장한 것이라 DONE 이 된다(PROPOSAL_analysis_signals_first.md §7-2).
    내리면 두 칸이 없어지고, 다시 올려도 된다.
    """

    database_url = f"sqlite+pysqlite:///{(tmp_path / 'migration.db').as_posix()}"
    before = _parent_of(DRAFTS_STATUS)

    _alembic(database_url, "upgrade", before)

    engine = create_engine(database_url)

    try:
        with engine.begin() as connection:
            # 외래 키는 이 연결에서 강제하지 않는다(SQLite 기본). 분석 행만 있으면 된다.
            connection.execute(
                text(
                    "INSERT INTO ai_analyses (id, session_id, status, schema_version, created_at, updated_at) "
                    "VALUES ('0123456789abcdef0123456789abcdef', 'fedcba9876543210fedcba9876543210', "
                    "'COMPLETED', '1.0', '2026-11-01 00:00:00', '2026-11-01 00:00:00')"
                )
            )

        _alembic(database_url, "upgrade", "head")

        with engine.connect() as connection:
            row = connection.execute(text("SELECT drafts_status, drafts_error_code FROM ai_analyses")).one()

        assert tuple(row) == ("DONE", None)

        _alembic(database_url, "downgrade", before)

        with engine.connect() as connection:
            columns = {item[1] for item in connection.execute(text("PRAGMA table_info(ai_analyses)"))}

        assert "drafts_status" not in columns
        assert "drafts_error_code" not in columns

        _alembic(database_url, "upgrade", "head")
    finally:
        engine.dispose()


# 아이 앱 질문 발송 예약 칸(deliver_at)을 더하는 revision(2026-11-11).
ADD_DELIVER_AT = "e4f5a6b7c8d9"


def test_deliver_at_downgrade_retires_reservations(tmp_path) -> None:
    """내리면 예약 시각 칸이 없어진다. 예약해 둔 묶음이 바로 보이지 않게, 옛 코드가 모르는 CANCELED 가 남지 않게 REPLACED 로 돌린다."""

    database_url = f"sqlite+pysqlite:///{(tmp_path / 'deliver_at.db').as_posix()}"
    _alembic(database_url, "upgrade", ADD_DELIVER_AT)
    rows = {
        "1": ("PENDING", "'2999-01-01 00:00:00'"),  # 예약해 둔 묶음
        "2": ("PENDING", "'2000-01-01 00:00:00'"),  # 예약 시각이 지나 보이는 묶음
        "3": ("PENDING", "NULL"),  # 바로 보낸 묶음
        "4": ("CANCELED", "'2000-01-01 00:00:00'"),
        "5": ("ANSWERED", "NULL"),
    }

    engine = create_engine(database_url)
    try:
        with engine.begin() as connection:
            for key, (status, deliver_at) in rows.items():
                connection.execute(
                    text(
                        "INSERT INTO child_question_sets (id, case_id, status, questions, deliver_at, created_at, updated_at) "
                        f"VALUES ('{int(key):032x}', 'fedcba9876543210fedcba9876543210', '{status}', '[]', {deliver_at}, "
                        "'2026-11-01 00:00:00', '2026-11-01 00:00:00')"
                    )
                )

        _alembic(database_url, "downgrade", _parent_of(ADD_DELIVER_AT))

        with engine.connect() as connection:
            columns = {row[1] for row in connection.execute(text("PRAGMA table_info('child_question_sets')"))}
            statuses = [row[0] for row in connection.execute(text("SELECT status FROM child_question_sets ORDER BY id"))]
    finally:
        engine.dispose()

    assert "deliver_at" not in columns
    assert statuses == ["REPLACED", "PENDING", "PENDING", "REPLACED", "ANSWERED"]


# case_forms 판 번호 · 임시 저장 하나 인덱스를 없을 때만 채우는 revision(2026-11-10, 데모 서버 DB 를 main 으로 올리기).
ENSURE_CASE_FORMS_VERSION = "c7d8e9f0a1b2"


def _old_case_forms_db(tmp_path, name: str, drafts: int) -> str:
    """판 번호 칸 · 인덱스가 없던 옛 e5f6a7b8c9d0 으로 만든 DB(발표용 데모 서버)를 흉내 낸다."""

    database_url = f"sqlite+pysqlite:///{(tmp_path / name).as_posix()}"
    _alembic(database_url, "upgrade", _parent_of(ENSURE_CASE_FORMS_VERSION))

    engine = create_engine(database_url)
    try:
        with engine.begin() as connection:
            connection.execute(text("DROP INDEX uq_case_forms_one_draft"))
            connection.execute(text("ALTER TABLE case_forms DROP COLUMN version"))
            for round_no in range(1, drafts + 1):
                connection.execute(
                    text(
                        "INSERT INTO case_forms (id, case_id, form_type, round, status, \"values\", created_at, updated_at) "
                        f"VALUES ('{round_no:032x}', 'fedcba9876543210fedcba9876543210', 'RISK_SCALE', {round_no}, "
                        "'DRAFT', '{}', '2026-11-01 00:00:00', '2026-11-01 00:00:00')"
                    )
                )
    finally:
        engine.dispose()

    return database_url


def _case_forms_state(database_url: str):
    engine = create_engine(database_url)
    try:
        with engine.connect() as connection:
            versions = [row[0] for row in connection.execute(text("SELECT version FROM case_forms"))]
            indexes = {row[1] for row in connection.execute(text("PRAGMA index_list('case_forms')"))}
    finally:
        engine.dispose()

    return versions, "uq_case_forms_one_draft" in indexes


def test_old_case_forms_get_version_and_one_draft_index(tmp_path) -> None:
    database_url = _old_case_forms_db(tmp_path, "old.db", drafts=1)

    _alembic(database_url, "upgrade", "head")

    assert _case_forms_state(database_url) == ([1], True)


def test_duplicate_drafts_keep_rows_and_skip_index(tmp_path) -> None:
    # 상담원 기록은 지우지 않는다. 판 번호 칸은 생기고, 인덱스만 건너뛴다.
    database_url = _old_case_forms_db(tmp_path, "dup.db", drafts=2)

    _alembic(database_url, "upgrade", "head")

    assert _case_forms_state(database_url) == ([1, 1], False)
