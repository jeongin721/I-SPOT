# 회차 상담 유형(consultation_type, 2026-10-30, API_CONTRACT 5절) — 만들 때 · 고칠 때 · 비우기 · 모르는 값. 데이터는 모두 가상이다.

import pytest
from fastapi.testclient import TestClient

from tests.conftest import create_case


def _create(client: TestClient, headers, case_id: str, **body):
    return client.post(f"/api/v1/cases/{case_id}/sessions", json=body, headers=headers)


def test_session_without_type_has_null(client: TestClient, counselor_headers, case: dict) -> None:
    created = _create(client, counselor_headers, case["id"])

    assert created.status_code == 201
    assert created.json()["data"]["consultation_type"] is None


def test_type_is_saved_on_create_and_shown_in_detail_and_list(client: TestClient, counselor_headers, case: dict) -> None:
    created = _create(client, counselor_headers, case["id"], consultation_type="VISIT").json()["data"]

    detail = client.get(f"/api/v1/sessions/{created['id']}", headers=counselor_headers).json()["data"]
    listed = client.get(f"/api/v1/cases/{case['id']}/sessions", headers=counselor_headers).json()["data"]["items"][0]

    assert created["consultation_type"] == "VISIT"
    assert detail["consultation_type"] == "VISIT"
    assert listed["consultation_type"] == "VISIT"


def test_patch_changes_and_clears_type(client: TestClient, counselor_headers, case: dict) -> None:
    created = _create(client, counselor_headers, case["id"], consultation_type="REGULAR").json()["data"]
    url = f"/api/v1/sessions/{created['id']}"

    changed = client.patch(url, json={"consultation_type": "PHONE"}, headers=counselor_headers)
    kept = client.patch(url, json={"memo": "다른 칸만"}, headers=counselor_headers)
    cleared = client.patch(url, json={"consultation_type": None}, headers=counselor_headers)

    assert changed.json()["data"]["consultation_type"] == "PHONE"
    assert kept.json()["data"]["consultation_type"] == "PHONE"
    assert cleared.json()["data"]["consultation_type"] is None


@pytest.mark.parametrize("value", ["정기상담", "regular", "OTHER", 3])
def test_unknown_type_is_rejected(client: TestClient, counselor_headers, value) -> None:
    case = create_case(client, counselor_headers)

    assert _create(client, counselor_headers, case["id"], consultation_type=value).status_code == 422
