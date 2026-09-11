# pytest 공통 fixture.
#
# 테스트는 PostgreSQL 없이도 실행 가능해야 한다.(docs/04_DEVELOPMENT.md)
# app import 전에 환경변수를 설정해 SQLite + 임시 Storage 를 사용한다.

import os
import shutil
import struct
import tempfile
import uuid
from pathlib import Path
from typing import Dict, Iterator, Tuple

import pytest

_TMP_ROOT = Path(tempfile.mkdtemp(prefix="ispot-backend-test-"))

os.environ["ENV"] = "test"
os.environ["DEBUG"] = "false"
os.environ["DATABASE_URL"] = f"sqlite+pysqlite:///{(_TMP_ROOT / 'test.db').as_posix()}"
os.environ["AUDIO_STORAGE_ROOT"] = str(_TMP_ROOT / "audio")
os.environ["JWT_SECRET_KEY"] = "test-only-secret-key-not-for-production-use-0123456789"
os.environ["STT_PROVIDER"] = "mock"
os.environ["AI_PROVIDER"] = "mock"
os.environ["AUDIO_MAX_SIZE_MB"] = "1"
os.environ["STT_TIMEOUT_SECONDS"] = "5"
os.environ["AI_TIMEOUT_SECONDS"] = "5"
os.environ["LOG_LEVEL"] = "WARNING"

from fastapi.testclient import TestClient  # noqa: E402

from app.adapters.ai_adapter import set_ai_adapter_override  # noqa: E402
from app.adapters.stt_adapter import set_stt_adapter_override  # noqa: E402
from app.core.database import SessionLocal, engine  # noqa: E402
from app.core.enums import UserRole  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Base, User  # noqa: E402

COUNSELOR_PASSWORD = "counselor-pass-1234"
ADMIN_PASSWORD = "admin-pass-1234"


# =========================================================
# DB
# =========================================================

@pytest.fixture(scope="session", autouse=True)
def _create_schema() -> Iterator[None]:
    Base.metadata.create_all(bind=engine)

    yield

    Base.metadata.drop_all(bind=engine)
    engine.dispose()
    shutil.rmtree(_TMP_ROOT, ignore_errors=True)


@pytest.fixture(autouse=True)
def _reset_state() -> Iterator[None]:
    """각 테스트를 독립적으로 유지한다."""

    set_stt_adapter_override(None)
    set_ai_adapter_override(None)

    yield

    set_stt_adapter_override(None)
    set_ai_adapter_override(None)

    with engine.begin() as connection:
        for table in reversed(Base.metadata.sorted_tables):
            connection.execute(table.delete())

    audio_root = Path(os.environ["AUDIO_STORAGE_ROOT"])

    if audio_root.exists():
        shutil.rmtree(audio_root, ignore_errors=True)


@pytest.fixture
def db() -> Iterator[SessionLocal]:
    session = SessionLocal()

    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


# =========================================================
# 사용자 / 인증
# =========================================================

def _create_user(email: str, name: str, role: UserRole, password: str) -> uuid.UUID:
    session = SessionLocal()

    try:
        user = User(
            email=email,
            name=name,
            role=role,
            hashed_password=hash_password(password),
            is_active=True,
        )

        session.add(user)
        session.commit()

        return user.id
    finally:
        session.close()


@pytest.fixture
def counselor_id() -> uuid.UUID:
    return _create_user(
        "counselor.a@ispot.example.com", "상담사A", UserRole.COUNSELOR, COUNSELOR_PASSWORD
    )


@pytest.fixture
def other_counselor_id() -> uuid.UUID:
    return _create_user(
        "counselor.b@ispot.example.com", "상담사B", UserRole.COUNSELOR, COUNSELOR_PASSWORD
    )


@pytest.fixture
def admin_id() -> uuid.UUID:
    return _create_user("admin@ispot.example.com", "관리자", UserRole.ADMIN, ADMIN_PASSWORD)


def _login(client: TestClient, email: str, password: str) -> Dict[str, str]:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )

    assert response.status_code == 200, response.text

    token = response.json()["data"]["access_token"]

    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def counselor_headers(client: TestClient, counselor_id: uuid.UUID) -> Dict[str, str]:
    return _login(client, "counselor.a@ispot.example.com", COUNSELOR_PASSWORD)


@pytest.fixture
def other_counselor_headers(
    client: TestClient, other_counselor_id: uuid.UUID
) -> Dict[str, str]:
    return _login(client, "counselor.b@ispot.example.com", COUNSELOR_PASSWORD)


@pytest.fixture
def admin_headers(client: TestClient, admin_id: uuid.UUID) -> Dict[str, str]:
    return _login(client, "admin@ispot.example.com", ADMIN_PASSWORD)


# =========================================================
# Case / Session helper
# =========================================================

def create_case(client: TestClient, headers: Dict[str, str], **overrides) -> dict:
    payload = {
        "title": "테스트 사례",
        "child_alias": "아동_001",
        "child_birth_year": 2015,
    }
    payload.update(overrides)

    response = client.post("/api/v1/cases", json=payload, headers=headers)

    assert response.status_code == 201, response.text

    return response.json()["data"]


def create_session(client: TestClient, headers: Dict[str, str], case_id: str) -> dict:
    response = client.post(
        f"/api/v1/cases/{case_id}/sessions",
        json={"title": "1회기 상담"},
        headers=headers,
    )

    assert response.status_code == 201, response.text

    return response.json()["data"]


@pytest.fixture
def case(client: TestClient, counselor_headers: Dict[str, str]) -> dict:
    return create_case(client, counselor_headers)


@pytest.fixture
def session(
    client: TestClient, counselor_headers: Dict[str, str], case: dict
) -> dict:
    return create_session(client, counselor_headers, case["id"])


# =========================================================
# 합성 음성 데이터 (실제 상담 음성을 사용하지 않는다)
# =========================================================

def make_wav_bytes(duration_ms: int = 1000, sample_rate: int = 8000) -> bytes:
    """유효한 WAV header 를 가진 무음 파일을 생성한다."""

    channels = 1
    bits_per_sample = 16
    byte_rate = sample_rate * channels * bits_per_sample // 8
    data_size = int(byte_rate * duration_ms / 1000)

    header = b"RIFF"
    header += struct.pack("<I", 36 + data_size)
    header += b"WAVE"
    header += b"fmt "
    header += struct.pack("<I", 16)
    header += struct.pack("<H", 1)
    header += struct.pack("<H", channels)
    header += struct.pack("<I", sample_rate)
    header += struct.pack("<I", byte_rate)
    header += struct.pack("<H", channels * bits_per_sample // 8)
    header += struct.pack("<H", bits_per_sample)
    header += b"data"
    header += struct.pack("<I", data_size)

    return header + b"\x00" * data_size


def upload_audio(
    client: TestClient,
    headers: Dict[str, str],
    session_id: str,
    *,
    filename: str = "consultation.wav",
    content: bytes | None = None,
    content_type: str = "audio/wav",
) -> Tuple[int, dict]:
    payload = content if content is not None else make_wav_bytes()

    response = client.post(
        f"/api/v1/sessions/{session_id}/audio",
        files={"file": (filename, payload, content_type)},
        headers=headers,
    )

    return response.status_code, response.json() if response.content else {}
