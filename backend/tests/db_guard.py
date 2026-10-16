# 테스트가 개발 DB 를 지우지 않게 막는 검사.
#
# conftest 의 fixture 는 매 테스트마다 모든 표를 비우고 끝나면 표를 지운다.
# 그래서 TEST_DATABASE_URL 로 받은 DB 는 이름이 _test 로 끝나야 한다.
# 주소의 이름만 보면 ?dbname=ispot 같은 접속 옵션이나 PGDATABASE 로 실제 연결 DB 가
# 바뀌어도 모르므로, 연결한 뒤 실제 DB 이름(current_database())도 확인한다.

from typing import Optional

import pytest
from sqlalchemy import text
from sqlalchemy.engine import Engine, make_url

TEST_DATABASE_SUFFIX = "_test"


def require_test_database_name(database: Optional[str], source: str) -> None:
    if not (database or "").endswith(TEST_DATABASE_SUFFIX):
        raise pytest.UsageError(
            f"{source} 의 DB 이름은 {TEST_DATABASE_SUFFIX} 로 끝나야 합니다(지금: {database!r}). "
            "테스트가 표를 비우고 지우므로 개발 DB 와 따로 만듭니다."
        )


def check_test_database_url(url: str) -> None:
    """주소에 적힌 DB 이름을 본다. 연결 전에 빨리 멈추기 위한 것이다."""

    require_test_database_name(make_url(url).database, "TEST_DATABASE_URL")


def check_connected_test_database(engine: Engine) -> None:
    """실제로 연결된 DB 이름을 본다. SQLite 임시 파일은 건너뛴다."""

    if engine.dialect.name == "sqlite":
        return

    with engine.connect() as connection:
        database = connection.execute(text("SELECT current_database()")).scalar_one()

    require_test_database_name(database, "실제로 연결된 DB(TEST_DATABASE_URL)")
