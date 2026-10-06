# 테스트가 개발 DB 를 지우지 않게 막는 검사(tests/db_guard.py).
#
# 주소의 DB 이름이 _test 로 끝나도 ?dbname=... 접속 옵션이 붙으면 PostgreSQL 은 다른 DB 에 붙는다.
# 그 경우를 실제 연결로 확인하는 테스트는 TEST_DATABASE_URL 로 PostgreSQL 에서 돌 때만 실행된다.

import pytest
from sqlalchemy import create_engine

from app.core.database import engine
from tests.db_guard import check_connected_test_database, check_test_database_url

requires_postgres = pytest.mark.skipif(
    engine.dialect.name != "postgresql",
    reason="TEST_DATABASE_URL 로 PostgreSQL 에서 돌릴 때만 확인한다(README 3절)",
)


def test_url_with_test_suffix_is_accepted() -> None:
    check_test_database_url("postgresql+psycopg://ispot:ispot@localhost:5432/ispot_test")


@pytest.mark.parametrize(
    "url",
    [
        "postgresql+psycopg://ispot:ispot@localhost:5432/ispot",
        "postgresql+psycopg://ispot:ispot@localhost:5432/",
        "postgresql+psycopg://ispot:ispot@localhost:5432/ispot_test_backup",
    ],
)
def test_url_without_test_suffix_is_rejected(url: str) -> None:
    with pytest.raises(pytest.UsageError, match="_test"):
        check_test_database_url(url)


@requires_postgres
def test_connected_test_database_is_accepted() -> None:
    check_connected_test_database(engine)


@requires_postgres
def test_dbname_option_pointing_elsewhere_is_rejected() -> None:
    # 주소의 이름은 그대로 *_test 라 주소만 보는 검사는 통과한다.
    url = engine.url.update_query_dict({"dbname": "postgres"})
    check_test_database_url(url.render_as_string(hide_password=False))

    other = create_engine(url)

    try:
        with pytest.raises(pytest.UsageError, match="'postgres'"):
            check_connected_test_database(other)
    finally:
        other.dispose()
