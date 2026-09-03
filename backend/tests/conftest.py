import os
import tempfile

import pytest

# Point the app at a throwaway SQLite database *before* importing it so tests
# are hermetic and do not require a running Postgres instance.
_DB_FD, _DB_PATH = tempfile.mkstemp(suffix=".db")
os.environ["DATABASE_URL"] = f"sqlite+pysqlite:///{_DB_PATH}"

from fastapi.testclient import TestClient  # noqa: E402

from app.database import Base, engine, get_db  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)
    os.close(_DB_FD)
    os.remove(_DB_PATH)


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c
