# 권한 테스트.
#
# counselor 는 담당 Case 만 접근할 수 있고 admin 은 전체를 접근할 수 있다.
# Frontend 메뉴 숨김이 아니라 Backend 에서 차단되는지 확인한다.

import uuid

from fastapi.testclient import TestClient

from tests.conftest import create_case, create_session


def test_counselor_list_excludes_other_counselor_cases(
    client: TestClient, counselor_headers, other_counselor_headers
) -> None:
    create_case(client, counselor_headers, title="A 담당 사례")
    create_case(client, other_counselor_headers, title="B 담당 사례")

    response = client.get("/api/v1/cases", headers=counselor_headers)

    assert response.status_code == 200

    titles = [item["title"] for item in response.json()["data"]["items"]]

    assert titles == ["A 담당 사례"]


def test_admin_list_includes_all_cases(
    client: TestClient, counselor_headers, other_counselor_headers, admin_headers
) -> None:
    create_case(client, counselor_headers, title="A 담당 사례")
    create_case(client, other_counselor_headers, title="B 담당 사례")

    response = client.get("/api/v1/cases", headers=admin_headers)

    assert response.status_code == 200
    assert response.json()["data"]["meta"]["total"] == 2


def test_counselor_cannot_read_other_case(
    client: TestClient, counselor_headers, other_counselor_headers
) -> None:
    other_case = create_case(client, other_counselor_headers, title="B 담당 사례")

    response = client.get(f"/api/v1/cases/{other_case['id']}", headers=counselor_headers)

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


def test_counselor_cannot_update_other_case(
    client: TestClient, counselor_headers, other_counselor_headers
) -> None:
    other_case = create_case(client, other_counselor_headers)

    response = client.patch(
        f"/api/v1/cases/{other_case['id']}",
        json={"title": "무단 수정"},
        headers=counselor_headers,
    )

    assert response.status_code == 403


def test_counselor_cannot_list_sessions_of_other_case(
    client: TestClient, counselor_headers, other_counselor_headers
) -> None:
    other_case = create_case(client, other_counselor_headers)

    response = client.get(
        f"/api/v1/cases/{other_case['id']}/sessions", headers=counselor_headers
    )

    assert response.status_code == 403


def test_counselor_cannot_create_session_in_other_case(
    client: TestClient, counselor_headers, other_counselor_headers
) -> None:
    other_case = create_case(client, other_counselor_headers)

    response = client.post(
        f"/api/v1/cases/{other_case['id']}/sessions",
        json={"title": "무단 생성"},
        headers=counselor_headers,
    )

    assert response.status_code == 403


def test_counselor_cannot_read_other_session_subresources(
    client: TestClient, counselor_headers, other_counselor_headers
) -> None:
    other_case = create_case(client, other_counselor_headers)
    other_session = create_session(client, other_counselor_headers, other_case["id"])

    session_id = other_session["id"]

    endpoints = [
        f"/api/v1/sessions/{session_id}",
        f"/api/v1/sessions/{session_id}/audio",
        f"/api/v1/sessions/{session_id}/transcript",
        f"/api/v1/sessions/{session_id}/analysis",
        f"/api/v1/sessions/{session_id}/summary",
        f"/api/v1/sessions/{session_id}/documents",
    ]

    for endpoint in endpoints:
        response = client.get(endpoint, headers=counselor_headers)

        assert response.status_code == 403, endpoint
        assert response.json()["error"]["code"] == "FORBIDDEN", endpoint


def test_counselor_cannot_trigger_stt_on_other_session(
    client: TestClient, counselor_headers, other_counselor_headers
) -> None:
    other_case = create_case(client, other_counselor_headers)
    other_session = create_session(client, other_counselor_headers, other_case["id"])

    response = client.post(
        f"/api/v1/sessions/{other_session['id']}/transcript",
        headers=counselor_headers,
    )

    assert response.status_code == 403


def test_admin_can_read_any_session(
    client: TestClient, admin_headers, other_counselor_headers
) -> None:
    other_case = create_case(client, other_counselor_headers)
    other_session = create_session(client, other_counselor_headers, other_case["id"])

    response = client.get(
        f"/api/v1/sessions/{other_session['id']}", headers=admin_headers
    )

    assert response.status_code == 200


def test_all_protected_endpoints_require_authentication(client: TestClient) -> None:
    random_id = uuid.uuid4()

    endpoints = [
        ("GET", "/api/v1/cases"),
        ("POST", "/api/v1/cases"),
        ("GET", f"/api/v1/cases/{random_id}"),
        ("GET", f"/api/v1/sessions/{random_id}"),
        ("GET", f"/api/v1/sessions/{random_id}/transcript"),
        ("POST", f"/api/v1/sessions/{random_id}/analysis"),
        ("GET", f"/api/v1/sessions/{random_id}/summary"),
    ]

    for method, endpoint in endpoints:
        response = client.request(method, endpoint, json={})

        assert response.status_code == 401, f"{method} {endpoint}"
        assert response.json()["error"]["code"] == "UNAUTHORIZED"
