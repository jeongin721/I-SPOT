# 종결 검토 등록 · 취소(POST/DELETE /cases/{id}/closure-review, 2026-10-30, API_CONTRACT 4절). 데이터는 모두 가상이다.

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.enums import AuditAction
from app.models.audit_log import AuditLog
from tests.conftest import create_case


def _url(case_id: str) -> str:
    return f"/api/v1/cases/{case_id}/closure-review"


def test_new_case_is_not_registered(client: TestClient, counselor_headers) -> None:
    assert create_case(client, counselor_headers)["closure_review_at"] is None


def test_register_then_cancel(client: TestClient, counselor_headers) -> None:
    case = create_case(client, counselor_headers)

    registered = client.post(_url(case["id"]), headers=counselor_headers)
    listed = client.get("/api/v1/cases", headers=counselor_headers).json()["data"]["items"][0]
    canceled = client.delete(_url(case["id"]), headers=counselor_headers)

    assert registered.status_code == 200, registered.text
    assert registered.json()["data"]["closure_review_at"] is not None
    assert listed["closure_review_at"] == registered.json()["data"]["closure_review_at"]
    assert canceled.status_code == 200
    assert canceled.json()["data"]["closure_review_at"] is None


def test_register_twice_keeps_first_time_and_audits_once(client: TestClient, counselor_headers, db) -> None:
    case = create_case(client, counselor_headers)

    first = client.post(_url(case["id"]), headers=counselor_headers).json()["data"]["closure_review_at"]
    second = client.post(_url(case["id"]), headers=counselor_headers).json()["data"]["closure_review_at"]
    client.delete(_url(case["id"]), headers=counselor_headers)
    client.delete(_url(case["id"]), headers=counselor_headers)

    assert first == second
    actions = [log.action for log in db.scalars(select(AuditLog).where(AuditLog.entity_type == "Case").order_by(AuditLog.created_at))]
    assert actions.count(AuditAction.CLOSURE_REVIEW_REGISTERED) == 1
    assert actions.count(AuditAction.CLOSURE_REVIEW_CANCELED) == 1


def test_closed_case_cannot_be_registered(client: TestClient, counselor_headers) -> None:
    case = create_case(client, counselor_headers)
    client.patch(f"/api/v1/cases/{case['id']}", json={"status": "CLOSED"}, headers=counselor_headers)

    response = client.post(_url(case["id"]), headers=counselor_headers)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "INVALID_CASE_STATE"


def test_other_counselor_is_forbidden(client: TestClient, counselor_headers, other_counselor_headers) -> None:
    case = create_case(client, counselor_headers)

    assert client.post(_url(case["id"]), headers=other_counselor_headers).status_code == 403
    assert client.delete(_url(case["id"]), headers=other_counselor_headers).status_code == 403
