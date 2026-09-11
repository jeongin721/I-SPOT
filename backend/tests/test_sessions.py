# Session CRUD 테스트.

import uuid

from fastapi.testclient import TestClient

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
