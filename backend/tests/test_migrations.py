# Migration 테스트.
#
# 다른 테스트는 migration 대신 metadata.create_all 로 표를 만든다(conftest).
# 기존 행을 고치는 migration 은 그 방식으로는 확인되지 않아, 임시 SQLite 파일에
# 실제로 alembic 을 돌려 본다. 개발 DB 와 테스트 DB 는 건드리지 않는다.

import os
import subprocess
import sys
from pathlib import Path

from sqlalchemy import create_engine, text

BACKEND_DIR = Path(__file__).resolve().parents[1]

# 계정 상태 칸을 추가하기 바로 전 revision
BEFORE_ACCOUNT_STATE = "a4d05486e8c9"


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
