# 일정(GET/POST/PATCH/DELETE /schedule/events, API_CONTRACT 19절, 2026-11-02). 데이터는 모두 가상이다.

from typing import Any, Dict

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.enums import AuditAction
from app.models.audit_log import AuditLog
from tests.conftest import create_case

URL = "/api/v1/schedule/events"


def _consult(case_id: str, **extra: Any) -> Dict[str, Any]:
    body = {"kind": "CONSULT", "case_id": case_id, "consult_type": "REGULAR", "date": "2026-11-05", "time": "15:00", "place": "면담실 A"}
    body.update(extra)
    return body


def _other(**extra: Any) -> Dict[str, Any]:
    body = {"kind": "OTHER", "category": "AGENCY_MEETING", "title": "팀 회의", "date": "2026-11-05", "time": "10:00"}
    body.update(extra)
    return body


def _list(client: TestClient, headers, start: str = "2026-11-01", end: str = "2026-11-30") -> list:
    response = client.get(URL, params={"from": start, "to": end}, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()["data"]["items"]


def test_create_consult_and_list(client: TestClient, counselor_headers, case: dict) -> None:
    created = client.post(URL, json=_consult(case["id"], important=True), headers=counselor_headers)

    assert created.status_code == 201, created.text
    data = created.json()["data"]
    assert data["kind"] == "CONSULT" and data["child_alias"] == case["child_alias"] and data["important"] is True
    assert data["editable"] is True and data["title"] is None and data["deadline_done"] == {}
    items = _list(client, counselor_headers)
    assert [item["id"] for item in items] == [data["id"]]
    assert _list(client, counselor_headers, "2026-12-01", "2026-12-31") == []


def test_list_is_sorted_all_day_first(client: TestClient, counselor_headers, case: dict) -> None:
    client.post(URL, json=_other(time="14:00", title="둘째"), headers=counselor_headers)
    client.post(URL, json=_other(time=None, category="LEAVE", title="연가"), headers=counselor_headers)
    client.post(URL, json=_other(time="09:30", title="첫째"), headers=counselor_headers)

    assert [item["title"] for item in _list(client, counselor_headers)] == ["연가", "첫째", "둘째"]


@pytest.mark.parametrize(
    "body",
    [
        {"kind": "CONSULT", "date": "2026-11-05", "consult_type": "REGULAR"},  # 사례 없음
        {"kind": "OTHER", "date": "2026-11-05"},  # 분류 없음
        {"kind": "OTHER", "category": "INTAKE", "date": "2026-11-05"},  # 최초접수인데 사례 없음
        _other(time="25:00"),
        _other(time="9:00"),
        _other(date="2026-11-05T00:00:00"),
        _other(title="가" * 101),
    ],
)
def test_bad_bodies_are_rejected(client: TestClient, counselor_headers, body) -> None:
    assert client.post(URL, json=body, headers=counselor_headers).status_code == 422


def test_cannot_attach_other_counselors_case(client: TestClient, counselor_headers, other_counselor_headers) -> None:
    others_case = create_case(client, other_counselor_headers)

    response = client.post(URL, json=_consult(others_case["id"]), headers=counselor_headers)

    assert response.status_code == 403


def test_kind_change_clears_fields_that_do_not_fit(client: TestClient, counselor_headers, case: dict) -> None:
    event = client.post(URL, json=_other(case_id=case["id"], category="CASE_MEETING", title="종결평가 회의", shared=True), headers=counselor_headers).json()["data"]

    changed = client.patch(f"{URL}/{event['id']}", json={"kind": "CONSULT", "consult_type": "CLOSING"}, headers=counselor_headers)

    assert changed.status_code == 200, changed.text
    data = changed.json()["data"]
    assert data["category"] is None and data["title"] is None and data["shared"] is False and data["consult_type"] == "CLOSING"


def test_intake_deadlines_done_and_lookback(client: TestClient, counselor_headers, case: dict) -> None:
    """최초접수는 처리 기한 완료 표시를 갖고, 기간 앞 30일 안의 접수도 목록에 온다(기한이 기간 안에 올 수 있어서)."""

    intake = client.post(URL, json=_other(category="INTAKE", case_id=case["id"], date="2026-10-20"), headers=counselor_headers).json()["data"]
    assert intake["deadline_done"] == {"3": False, "7": False, "30": False}

    done = client.patch(f"{URL}/{intake['id']}", json={"deadline_done": {"7": True}}, headers=counselor_headers)

    assert done.json()["data"]["deadline_done"] == {"3": False, "7": True, "30": False}
    assert [item["id"] for item in _list(client, counselor_headers)] == [intake["id"]]
    assert _list(client, counselor_headers, "2026-12-01", "2026-12-31") == []
    assert client.patch(f"{URL}/{intake['id']}", json={"deadline_done": {"5": True}}, headers=counselor_headers).status_code == 422
    meeting = client.post(URL, json=_other(), headers=counselor_headers).json()["data"]
    assert client.patch(f"{URL}/{meeting['id']}", json={"deadline_done": {"3": True}}, headers=counselor_headers).status_code == 422


def test_shared_events_are_visible_read_only(
    client: TestClient, counselor_headers, other_counselor_headers, admin_headers, case: dict
) -> None:
    private = client.post(URL, json=_other(title="개인"), headers=counselor_headers).json()["data"]
    shared = client.post(URL, json=_other(title="공유", shared=True, case_id=case["id"], category="CASE_MEETING"), headers=counselor_headers).json()["data"]

    seen = _list(client, other_counselor_headers)

    assert [item["title"] for item in seen] == ["공유"]
    # 남의 사례는 별칭 · id 를 보이지 않는다.
    assert seen[0]["case_id"] is None and seen[0]["child_alias"] is None and seen[0]["editable"] is False
    assert client.patch(f"{URL}/{shared['id']}", json={"title": "x"}, headers=other_counselor_headers).status_code == 403
    assert client.delete(f"{URL}/{private['id']}", headers=other_counselor_headers).status_code == 404
    # 관리자는 모두 보고 고칠 수 있다.
    assert {item["title"] for item in _list(client, admin_headers)} == {"개인", "공유"}
    assert client.patch(f"{URL}/{private['id']}", json={"important": True}, headers=admin_headers).status_code == 200


def test_delete_and_audit_without_text(client: TestClient, counselor_headers, db) -> None:
    event = client.post(URL, json=_other(title="비밀 제목", place="비밀 장소"), headers=counselor_headers).json()["data"]

    assert client.delete(f"{URL}/{event['id']}", headers=counselor_headers).status_code == 204
    assert _list(client, counselor_headers) == []
    logs = list(db.scalars(select(AuditLog).where(AuditLog.entity_type == "ScheduleEvent")))
    assert {log.action for log in logs} == {AuditAction.SCHEDULE_CREATED, AuditAction.SCHEDULE_DELETED}
    assert all("비밀" not in str(log.detail) for log in logs)


def test_range_limits(client: TestClient, counselor_headers) -> None:
    assert client.get(URL, params={"from": "2026-11-30", "to": "2026-11-01"}, headers=counselor_headers).status_code == 422
    assert client.get(URL, params={"from": "2026-01-01", "to": "2027-12-31"}, headers=counselor_headers).status_code == 422


def test_deleting_case_deletes_its_events(client: TestClient, counselor_headers, admin_headers) -> None:
    doomed = create_case(client, counselor_headers)
    client.post(URL, json=_consult(doomed["id"]), headers=counselor_headers)

    assert client.delete(f"/api/v1/cases/{doomed['id']}", headers=admin_headers).status_code == 204
    assert _list(client, counselor_headers) == []


def test_intake_is_never_shared(client: TestClient, counselor_headers, other_counselor_headers, case: dict) -> None:
    """최초접수는 팀 공유하지 않는다 — 다른 상담사 알림 종 · 달력에 남의 처리 기한이 뜨지 않게(민규 #131 리뷰)."""

    intake = client.post(URL, json=_other(category="INTAKE", case_id=case["id"], shared=True), headers=counselor_headers).json()["data"]
    meeting = client.post(URL, json=_other(shared=True), headers=counselor_headers).json()["data"]
    changed = client.patch(f"{URL}/{meeting['id']}", json={"category": "INTAKE", "case_id": case["id"]}, headers=counselor_headers)

    assert intake["shared"] is False
    assert changed.status_code == 200 and changed.json()["data"]["shared"] is False
    assert _list(client, other_counselor_headers) == []


@pytest.mark.parametrize("body", [{"date": None}, {"kind": None}])
def test_patch_null_kind_or_date_is_422(client: TestClient, counselor_headers, body) -> None:
    """kind · date 는 비울 수 없는 칸이라 null 은 422(전에는 커밋 때 NOT NULL 위반으로 500, 민규 #131 리뷰)."""

    event = client.post(URL, json=_other(), headers=counselor_headers).json()["data"]

    response = client.patch(f"{URL}/{event['id']}", json=body, headers=counselor_headers)

    assert response.status_code == 422
    assert client.get(URL, params={"from": "2026-11-01", "to": "2026-11-30"}, headers=counselor_headers).json()["data"]["items"][0]["date"] == "2026-11-05"
