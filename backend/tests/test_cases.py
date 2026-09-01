# Case CRUD / Validation / 없는 Case 테스트.

import uuid

from fastapi.testclient import TestClient

from tests.conftest import create_case


def test_create_case_assigns_requester_as_counselor(
    client: TestClient, counselor_headers, counselor_id: uuid.UUID
) -> None:
    data = create_case(client, counselor_headers, title="첫 사례")

    assert data["title"] == "첫 사례"
    assert data["counselor_id"] == str(counselor_id)
    assert data["status"] == "ACTIVE"
    assert data["case_number"].startswith("C-")


def test_create_case_generates_sequential_case_numbers(
    client: TestClient, counselor_headers
) -> None:
    first = create_case(client, counselor_headers)
    second = create_case(client, counselor_headers)

    assert first["case_number"] != second["case_number"]


def test_create_case_rejects_duplicate_case_number(
    client: TestClient, counselor_headers
) -> None:
    create_case(client, counselor_headers, case_number="C-FIXED-0001")

    response = client.post(
        "/api/v1/cases",
        json={
            "title": "중복 번호",
            "child_alias": "아동_002",
            "case_number": "C-FIXED-0001",
        },
        headers=counselor_headers,
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "DUPLICATE_RESOURCE"


def test_create_case_requires_title_and_alias(
    client: TestClient, counselor_headers
) -> None:
    response = client.post("/api/v1/cases", json={"title": ""}, headers=counselor_headers)

    assert response.status_code == 422

    body = response.json()

    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["details"]["fields"]


def test_create_case_rejects_invalid_birth_year(
    client: TestClient, counselor_headers
) -> None:
    response = client.post(
        "/api/v1/cases",
        json={"title": "잘못된 연도", "child_alias": "아동_003", "child_birth_year": 1500},
        headers=counselor_headers,
    )

    assert response.status_code == 422


def test_list_cases_returns_paged_envelope(
    client: TestClient, counselor_headers
) -> None:
    for index in range(3):
        create_case(client, counselor_headers, title=f"사례 {index}")

    response = client.get(
        "/api/v1/cases", params={"page": 1, "page_size": 2}, headers=counselor_headers
    )

    assert response.status_code == 200

    data = response.json()["data"]

    assert len(data["items"]) == 2
    assert data["meta"]["total"] == 3
    assert data["meta"]["total_pages"] == 2


def test_list_cases_search_by_alias(client: TestClient, counselor_headers) -> None:
    create_case(client, counselor_headers, child_alias="아동_특이케이스")
    create_case(client, counselor_headers, child_alias="아동_기본")

    response = client.get(
        "/api/v1/cases", params={"search": "특이케이스"}, headers=counselor_headers
    )

    assert response.status_code == 200

    items = response.json()["data"]["items"]

    assert len(items) == 1
    assert items[0]["child_alias"] == "아동_특이케이스"


def test_get_case_detail_includes_counselor_and_session_count(
    client: TestClient, counselor_headers, case: dict
) -> None:
    client.post(
        f"/api/v1/cases/{case['id']}/sessions",
        json={"title": "1회기"},
        headers=counselor_headers,
    )

    response = client.get(f"/api/v1/cases/{case['id']}", headers=counselor_headers)

    assert response.status_code == 200

    data = response.json()["data"]

    assert data["session_count"] == 1
    assert data["counselor"]["email"] == "counselor.a@ispot.example.com"


def test_get_missing_case_returns_case_not_found(
    client: TestClient, counselor_headers
) -> None:
    response = client.get(f"/api/v1/cases/{uuid.uuid4()}", headers=counselor_headers)

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "CASE_NOT_FOUND"


def test_malformed_case_id_returns_validation_error(
    client: TestClient, counselor_headers
) -> None:
    response = client.get("/api/v1/cases/not-a-uuid", headers=counselor_headers)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_update_case_changes_fields(
    client: TestClient, counselor_headers, case: dict
) -> None:
    response = client.patch(
        f"/api/v1/cases/{case['id']}",
        json={"title": "수정된 제목", "status": "CLOSED"},
        headers=counselor_headers,
    )

    assert response.status_code == 200

    data = response.json()["data"]

    assert data["title"] == "수정된 제목"
    assert data["status"] == "CLOSED"


def test_counselor_cannot_delete_case(
    client: TestClient, counselor_headers, case: dict
) -> None:
    response = client.delete(f"/api/v1/cases/{case['id']}", headers=counselor_headers)

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


def test_admin_can_delete_case(
    client: TestClient, counselor_headers, admin_headers, case: dict
) -> None:
    response = client.delete(f"/api/v1/cases/{case['id']}", headers=admin_headers)

    assert response.status_code == 204

    follow_up = client.get(f"/api/v1/cases/{case['id']}", headers=admin_headers)

    assert follow_up.status_code == 404


def test_counselor_cannot_assign_case_to_another_counselor(
    client: TestClient, counselor_headers, other_counselor_id: uuid.UUID
) -> None:
    response = client.post(
        "/api/v1/cases",
        json={
            "title": "타인 배정 시도",
            "child_alias": "아동_004",
            "counselor_id": str(other_counselor_id),
        },
        headers=counselor_headers,
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


def test_admin_can_assign_case_to_counselor(
    client: TestClient, admin_headers, counselor_id: uuid.UUID
) -> None:
    response = client.post(
        "/api/v1/cases",
        json={
            "title": "관리자 배정",
            "child_alias": "아동_005",
            "counselor_id": str(counselor_id),
        },
        headers=admin_headers,
    )

    assert response.status_code == 201
    assert response.json()["data"]["counselor_id"] == str(counselor_id)


def test_admin_assign_to_unknown_user_returns_user_not_found(
    client: TestClient, admin_headers
) -> None:
    response = client.post(
        "/api/v1/cases",
        json={
            "title": "없는 사용자",
            "child_alias": "아동_006",
            "counselor_id": str(uuid.uuid4()),
        },
        headers=admin_headers,
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "USER_NOT_FOUND"
