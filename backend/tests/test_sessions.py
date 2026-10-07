# Session CRUD 테스트.

import uuid
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.core.database import SessionLocal
from app.models.base import as_utc
from app.models.session import ConsultationSession
from tests.conftest import create_session


def test_create_session_starts_in_created_status(
    client: TestClient, counselor_headers, case: dict
) -> None:
    data = create_session(client, counselor_headers, case["id"])

    assert data["status"] == "CREATED"
    assert data["session_number"] == 1
    assert data["case_id"] == case["id"]


def test_session_numbers_increment_per_case(
    client: TestClient, counselor_headers, case: dict
) -> None:
    first = create_session(client, counselor_headers, case["id"])
    second = create_session(client, counselor_headers, case["id"])

    assert first["session_number"] == 1
    assert second["session_number"] == 2


def test_create_session_in_missing_case_returns_case_not_found(
    client: TestClient, counselor_headers
) -> None:
    response = client.post(
        f"/api/v1/cases/{uuid.uuid4()}/sessions",
        json={"title": "없는 사례"},
        headers=counselor_headers,
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "CASE_NOT_FOUND"


def test_get_missing_session_returns_session_not_found(
    client: TestClient, counselor_headers
) -> None:
    response = client.get(f"/api/v1/sessions/{uuid.uuid4()}", headers=counselor_headers)

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "SESSION_NOT_FOUND"


def test_session_detail_reports_empty_progress(
    client: TestClient, counselor_headers, session: dict
) -> None:
    response = client.get(f"/api/v1/sessions/{session['id']}", headers=counselor_headers)

    assert response.status_code == 200

    data = response.json()["data"]

    assert data["has_audio"] is False
    assert data["has_transcript"] is False
    assert data["has_analysis"] is False
    assert data["has_summary"] is False
    assert data["summary_approved"] is False
    assert data["error"] is None


def test_update_session_fields(
    client: TestClient, counselor_headers, session: dict
) -> None:
    response = client.patch(
        f"/api/v1/sessions/{session['id']}",
        json={"title": "수정된 회기", "location": "상담실 2"},
        headers=counselor_headers,
    )

    assert response.status_code == 200

    data = response.json()["data"]

    assert data["title"] == "수정된 회기"
    assert data["location"] == "상담실 2"


def test_update_session_rejects_unknown_field_values(
    client: TestClient, counselor_headers, session: dict
) -> None:
    response = client.patch(
        f"/api/v1/sessions/{session['id']}",
        json={"consulted_at": "not-a-datetime"},
        headers=counselor_headers,
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_list_sessions_returns_paged_envelope(
    client: TestClient, counselor_headers, case: dict
) -> None:
    create_session(client, counselor_headers, case["id"])
    create_session(client, counselor_headers, case["id"])

    response = client.get(
        f"/api/v1/cases/{case['id']}/sessions", headers=counselor_headers
    )

    assert response.status_code == 200

    data = response.json()["data"]

    assert data["meta"]["total"] == 2
    # 최신 회기가 먼저 노출된다.
    assert data["items"][0]["session_number"] == 2


def test_delete_session_removes_it(
    client: TestClient, counselor_headers, session: dict
) -> None:
    response = client.delete(
        f"/api/v1/sessions/{session['id']}", headers=counselor_headers
    )

    assert response.status_code == 204

    follow_up = client.get(
        f"/api/v1/sessions/{session['id']}", headers=counselor_headers
    )

    assert follow_up.status_code == 404


def test_deleting_case_cascades_to_sessions(
    client: TestClient, counselor_headers, admin_headers, case: dict
) -> None:
    session = create_session(client, counselor_headers, case["id"])

    assert client.delete(f"/api/v1/cases/{case['id']}", headers=admin_headers).status_code == 204

    response = client.get(f"/api/v1/sessions/{session['id']}", headers=admin_headers)

    assert response.status_code == 404


# =========================================================
# 상담 시각 입력 정규화 (API_CONTRACT 1.5)
# =========================================================

def _stored_consulted_at(session_id: str) -> datetime:
    """DB 에 저장된 상담 시각을 UTC 로 읽는다(SQLite 는 시간대 없이 UTC 글자만 돌려준다)."""

    db = SessionLocal()

    try:
        row = db.get(ConsultationSession, uuid.UUID(session_id))

        return as_utc(row.consulted_at)
    finally:
        db.close()


@pytest.mark.parametrize(
    "sent",
    [
        "2026-09-01T14:30:00+09:00",
        "2026-09-01T05:30:00Z",
        "2026-09-01T05:30:00",
        "2026-08-31T22:30:00-07:00",
    ],
)
def test_create_session_stores_consulted_at_as_utc(
    client: TestClient, counselor_headers, case: dict, sent: str
) -> None:
    """표시 없는 값은 UTC 로, 오프셋이 붙은 값은 같은 순간의 UTC 로 저장한다."""

    response = client.post(
        f"/api/v1/cases/{case['id']}/sessions",
        json={"consulted_at": sent},
        headers=counselor_headers,
    )

    assert response.status_code == 201, response.text

    expected = datetime(2026, 9, 1, 5, 30, tzinfo=timezone.utc)

    assert _stored_consulted_at(response.json()["data"]["id"]) == expected


def test_update_session_stores_consulted_at_as_utc(
    client: TestClient, counselor_headers, session: dict
) -> None:
    response = client.patch(
        f"/api/v1/sessions/{session['id']}",
        json={"consulted_at": "2026-09-01T14:30:00+09:00"},
        headers=counselor_headers,
    )

    assert response.status_code == 200, response.text
    assert _stored_consulted_at(session["id"]) == datetime(
        2026, 9, 1, 5, 30, tzinfo=timezone.utc
    )


def test_consulted_at_at_date_limit_does_not_crash(
    client: TestClient, counselor_headers, case: dict
) -> None:
    """UTC 로 바꾸면 날짜 범위를 벗어나는 값도 500 이 아니라 정상 응답(가장 이른 시각으로 저장)이다."""

    response = client.post(
        f"/api/v1/cases/{case['id']}/sessions",
        json={"consulted_at": "0001-01-01T00:00:00+09:00"},
        headers=counselor_headers,
    )

    assert response.status_code == 201, response.text


def test_last_session_at_reflects_offset_consulted_at(
    client: TestClient, counselor_headers, case: dict
) -> None:
    """사례 목록 최근 상담일이 +09:00 으로 보낸 값의 실제 순간을 가리킨다."""

    client.post(
        f"/api/v1/cases/{case['id']}/sessions",
        json={"consulted_at": "2026-09-01T14:30:00+09:00"},
        headers=counselor_headers,
    )

    detail = client.get(f"/api/v1/cases/{case['id']}", headers=counselor_headers)
    value = detail.json()["data"]["last_session_at"]
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    parsed = parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)

    assert parsed == datetime(2026, 9, 1, 5, 30, tzinfo=timezone.utc)
