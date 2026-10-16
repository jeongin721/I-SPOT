# 사례 검색어 · 보호자 메모 · 수정 요청의 null 처리 테스트.

import pytest
from fastapi.testclient import TestClient

from tests.conftest import create_case


# =========================================================
# 검색어의 % _ 는 글자 그대로 찾는다
# =========================================================

def test_search_treats_percent_as_text(client: TestClient, counselor_headers) -> None:
    """"10%" 로 찾으면 "10" 이 들어간 모든 사례가 아니라 "10%" 가 들어간 사례만 나와야 한다."""

    create_case(client, counselor_headers, title="진행률 10% 사례")
    create_case(client, counselor_headers, title="10살 사례")

    response = client.get(
        "/api/v1/cases", params={"search": "10%"}, headers=counselor_headers
    )

    assert response.status_code == 200

    items = response.json()["data"]["items"]

    assert [item["title"] for item in items] == ["진행률 10% 사례"]


def test_search_treats_underscore_as_text(client: TestClient, counselor_headers) -> None:
    """별칭은 "아동_001" 처럼 _ 를 쓰므로, _ 가 아무 글자 하나로 동작하면 검색이 틀린다."""

    create_case(client, counselor_headers, child_alias="아동_001")
    create_case(client, counselor_headers, child_alias="아동A001")

    response = client.get(
        "/api/v1/cases", params={"search": "아동_0"}, headers=counselor_headers
    )

    assert response.status_code == 200

    items = response.json()["data"]["items"]

    assert [item["child_alias"] for item in items] == ["아동_001"]


def test_search_treats_escape_character_as_text(
    client: TestClient, counselor_headers
) -> None:
    """escape 문자로 쓰는 "/" 자체를 검색해도 글자 그대로 찾아야 한다."""

    create_case(client, counselor_headers, title="A/B 사례")
    create_case(client, counselor_headers, title="AB 사례")

    response = client.get(
        "/api/v1/cases", params={"search": "A/B"}, headers=counselor_headers
    )

    assert response.status_code == 200

    items = response.json()["data"]["items"]

    assert [item["title"] for item in items] == ["A/B 사례"]


# =========================================================
# 보호자 메모는 OTHER 일 때만 남는다
# =========================================================

def _create_other_guardian_case(client: TestClient, headers) -> dict:
    return create_case(client, headers, guardian_type="OTHER", guardian_note="외조모")


def test_changing_guardian_type_clears_note(client: TestClient, counselor_headers) -> None:
    """OTHER 에서 다른 유형으로 바꾸면 이전 메모가 남으면 안 된다."""

    case = _create_other_guardian_case(client, counselor_headers)

    response = client.patch(
        f"/api/v1/cases/{case['id']}",
        json={"guardian_type": "MOTHER"},
        headers=counselor_headers,
    )

    assert response.status_code == 200
    assert response.json()["data"]["guardian_type"] == "MOTHER"
    assert response.json()["data"]["guardian_note"] is None

    detail = client.get(f"/api/v1/cases/{case['id']}", headers=counselor_headers)

    assert detail.json()["data"]["guardian_note"] is None


def test_clearing_guardian_type_clears_note(client: TestClient, counselor_headers) -> None:
    case = _create_other_guardian_case(client, counselor_headers)

    response = client.patch(
        f"/api/v1/cases/{case['id']}",
        json={"guardian_type": None},
        headers=counselor_headers,
    )

    assert response.status_code == 200
    assert response.json()["data"]["guardian_type"] is None
    assert response.json()["data"]["guardian_note"] is None


def test_note_only_update_on_other_case(client: TestClient, counselor_headers) -> None:
    """이미 OTHER 인 사례는 메모만 고칠 수 있어야 한다. 유형을 다시 보낼 필요가 없다."""

    case = _create_other_guardian_case(client, counselor_headers)

    response = client.patch(
        f"/api/v1/cases/{case['id']}",
        json={"guardian_note": "외삼촌"},
        headers=counselor_headers,
    )

    assert response.status_code == 200
    assert response.json()["data"]["guardian_type"] == "OTHER"
    assert response.json()["data"]["guardian_note"] == "외삼촌"


def test_note_only_update_on_non_other_case_is_rejected(
    client: TestClient, counselor_headers
) -> None:
    case = create_case(client, counselor_headers, guardian_type="MOTHER")

    response = client.patch(
        f"/api/v1/cases/{case['id']}",
        json={"guardian_note": "친모"},
        headers=counselor_headers,
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"

    detail = client.get(f"/api/v1/cases/{case['id']}", headers=counselor_headers)

    assert detail.json()["data"]["guardian_note"] is None


def test_note_with_non_other_type_is_still_rejected(
    client: TestClient, counselor_headers
) -> None:
    """유형과 메모를 함께 보낼 때의 기존 규칙은 그대로다."""

    case = _create_other_guardian_case(client, counselor_headers)

    response = client.patch(
        f"/api/v1/cases/{case['id']}",
        json={"guardian_type": "MOTHER", "guardian_note": "친모"},
        headers=counselor_headers,
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


# =========================================================
# 비울 수 없는 필드에 null
# =========================================================

@pytest.mark.parametrize("field", ["title", "child_alias", "status"])
def test_null_for_required_field_is_rejected(
    client: TestClient, counselor_headers, case: dict, field: str
) -> None:
    """필수 필드를 null 로 보내면 DB 저장에서 500 이 나지 않고 422 로 거부되어야 한다."""

    response = client.patch(
        f"/api/v1/cases/{case['id']}",
        json={field: None},
        headers=counselor_headers,
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
