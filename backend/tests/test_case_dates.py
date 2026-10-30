# 사례 날짜 셋(서식 4 ①) — 신고접수일 · 사례연계일 · 최초면접일(2026-10-30, API_CONTRACT 4절). 데이터는 모두 가상이다.

import pytest
from fastapi.testclient import TestClient

from tests.conftest import create_case

DATES = {"report_date": "2026-07-28", "linked_date": "2026-07-29", "first_interview_date": "2026-07-30"}


def test_new_case_without_dates_has_nulls(client: TestClient, counselor_headers) -> None:
    case = create_case(client, counselor_headers)

    assert {key: case[key] for key in DATES} == {key: None for key in DATES}


def test_dates_are_saved_on_create_and_read_back(client: TestClient, counselor_headers) -> None:
    case = create_case(client, counselor_headers, **DATES)

    detail = client.get(f"/api/v1/cases/{case['id']}", headers=counselor_headers).json()["data"]
    listed = client.get("/api/v1/cases", headers=counselor_headers).json()["data"]["items"][0]

    assert {key: detail[key] for key in DATES} == DATES
    assert {key: listed[key] for key in DATES} == DATES


def test_patch_changes_and_clears_only_sent_dates(client: TestClient, counselor_headers) -> None:
    case = create_case(client, counselor_headers, **DATES)

    response = client.patch(
        f"/api/v1/cases/{case['id']}",
        json={"linked_date": "2026-08-01", "first_interview_date": None},
        headers=counselor_headers,
    )

    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["report_date"] == "2026-07-28"
    assert data["linked_date"] == "2026-08-01"
    assert data["first_interview_date"] is None


@pytest.mark.parametrize("value", ["1899-12-31", "2101-01-01", "2026-13-01", "어제", "2026-07-28T10:00:00"])
def test_bad_dates_are_rejected(client: TestClient, counselor_headers, value: str) -> None:
    response = client.post(
        "/api/v1/cases",
        json={"title": "t", "child_alias": "a", "report_date": value},
        headers=counselor_headers,
    )

    assert response.status_code == 422
