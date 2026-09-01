# SQLAlchemy 2.x Engine / Session 구성.
#
# 기본 DB 는 PostgreSQL 이지만, 팀원 모두가 Postgres 없이도 테스트를 돌릴 수 있도록
# SQLite 에서도 동작하는 타입만 사용한다. (docs/04_DEVELOPMENT.md - Local 실행 우선)

from typing import Any, Dict, Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings


def _engine_kwargs(database_url: str) -> Dict[str, Any]:
    kwargs: Dict[str, Any] = {
        "echo": settings.DB_ECHO,
        "future": True,
        "pool_pre_ping": True,
    }

    if database_url.startswith("sqlite"):
        # 테스트에서 여러 thread(BackgroundTasks) 가 같은 연결을 쓰기 때문에 필요하다.
        kwargs["connect_args"] = {"check_same_thread": False}
        kwargs.pop("pool_pre_ping")

    return kwargs


engine = create_engine(settings.DATABASE_URL, **_engine_kwargs(settings.DATABASE_URL))


if settings.DATABASE_URL.startswith("sqlite"):

    @event.listens_for(engine, "connect")
    def _enable_sqlite_foreign_keys(dbapi_connection: Any, _: Any) -> None:
        """
        SQLite 는 기본적으로 FK 를 강제하지 않는다.
        ON DELETE CASCADE 동작을 PostgreSQL 과 맞추기 위해 활성화한다.
        """

        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
    class_=Session,
)


def get_db() -> Generator[Session, None, None]:
    """FastAPI Dependency: Request 단위 DB Session."""

    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()
