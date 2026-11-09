# 아이 앱(콩콩) 1단계: 초대 코드 연결 → 질문 보내기 → 답변 → 상담사 피드.

import hashlib
import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.models.child_app import ChildAppLink
from app.services import signup_service
from tests.conftest import create_case

Headers = Dict[str, str]


@pytest.fixture(autouse=True)
def _limits() -> Iterator[None]:
    signup_service.reset_limits()
    yield
    signup_service.reset_limits()


def _invite(client: TestClient, headers: Headers, case_id: str) -> str:
    response = client.post(f"/api/v1/cases/{case_id}/child-app/invite", headers=headers)
    assert response.status_code == 201, response.text
    return response.json()["data"]["code"]


def _link(client: TestClient, code: str) -> Headers:
    response = client.post("/api/v1/child-app/link", json={"code": code})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['data']['device_token']}"}


def _send(client: TestClient, headers: Headers, case_id: str, ids) -> None:
    response = client.post(
        f"/api/v1/cases/{case_id}/child-app/question-sets", json={"question_ids": ids}, headers=headers
    )
    assert response.status_code == 204, response.text


def _home(client: TestClient, device: Headers) -> dict:
    response = client.get("/api/v1/child-app/home", headers=device)
    assert response.status_code == 200, response.text
    return response.json()["data"]


def _view(client: TestClient, headers: Headers, case_id: str) -> dict:
    response = client.get(f"/api/v1/cases/{case_id}/child-app", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()["data"]


def _linked(client: TestClient, headers: Headers, case_id: str) -> Headers:
    return _link(client, _invite(client, headers, case_id))


def test_full_flow_reaches_counselor_feed(client: TestClient, counselor_headers: Headers, case: dict) -> None:
    assert _view(client, counselor_headers, case["id"])["status"] == "NOT_LINKED"
    device = _linked(client, counselor_headers, case["id"])
    assert _view(client, counselor_headers, case["id"])["status"] == "LINKED"
    assert _home(client, device)["pending"] is None

    _send(client, counselor_headers, case["id"], ["sleep", "safe", "school", "free"])
    pending = _home(client, device)["pending"]
    assert [item["id"] for item in pending["questions"]] == ["sleep", "safe", "school", "free"]

    response = client.post(
        f"/api/v1/child-app/question-sets/{pending['id']}/answers",
        json={"answers": [
            {"question_id": "sleep", "choice_index": 3},
            {"question_id": "safe", "choice_index": 2},
            {"question_id": "school", "skipped": True},
            {"question_id": "free", "text": "요즘 집에 가기 싫어요"},
        ]},
        headers=device,
    )
    assert response.status_code == 200, response.text
    assert response.json()["data"]["ticket_awarded"] == 1
    assert _home(client, device)["pending"] is None

    view = _view(client, counselor_headers, case["id"])
    assert view["last_response_at"] is not None
    assert view["has_pending_questions"] is False
    assert [event["kind"] for event in view["feed"]] == ["ANSWERS", "QUESTIONS_SENT", "LINKED"]
    answers = view["feed"][0]
    assert answers["level"] == "RED"
    assert [(i["answer"], i["level"]) for i in answers["payload"]["items"]] == [
        ("잘 못 잤어요", "AMBER"),
        ("안전하지 않아요", "RED"),
        ("답하기 어려워요", "SKIP"),
        ("요즘 집에 가기 싫어요", "NONE"),
    ]


def test_device_receives_no_identity_or_grading(client: TestClient, counselor_headers: Headers) -> None:
    case = create_case(client, counselor_headers, child_alias="노출금지별칭")
    device = _linked(client, counselor_headers, case["id"])
    _send(client, counselor_headers, case["id"], ["safe", "home", "meal"])
    response = client.get("/api/v1/child-app/home", headers=device)
    assert "노출금지별칭" not in response.text
    assert case["id"] not in response.text
    for question in response.json()["data"]["pending"]["questions"]:
        assert "flag" not in question and "red" not in question


def test_code_is_single_use_and_stored_hashed(client: TestClient, counselor_headers: Headers, case: dict, db) -> None:
    code = _invite(client, counselor_headers, case["id"])
    normalized = code.replace("-", "")
    row = db.scalar(select(ChildAppLink))
    assert row.code_hash == hashlib.sha256(normalized.encode()).hexdigest()
    assert _link(client, code.lower())
    again = client.post("/api/v1/child-app/link", json={"code": code})
    assert again.status_code == 400
    assert again.json()["error"]["code"] == "INVALID_CHILD_CODE"


def test_expired_code_rejected(client: TestClient, counselor_headers: Headers, case: dict, db) -> None:
    code = _invite(client, counselor_headers, case["id"])
    row = db.scalar(select(ChildAppLink))
    row.code_expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    db.commit()
    assert client.post("/api/v1/child-app/link", json={"code": code}).status_code == 400


def test_link_attempts_rate_limited(client: TestClient) -> None:
    for _ in range(20):
        assert client.post("/api/v1/child-app/link", json={"code": "KONG-NOPE22"}).status_code == 400
    assert client.post("/api/v1/child-app/link", json={"code": "KONG-NOPE22"}).status_code == 429


def test_reinvite_invalidates_previous_code(client: TestClient, counselor_headers: Headers, case: dict) -> None:
    old = _invite(client, counselor_headers, case["id"])
    new = _invite(client, counselor_headers, case["id"])
    assert client.post("/api/v1/child-app/link", json={"code": old}).status_code == 400
    assert _link(client, new)
    assert client.post(f"/api/v1/cases/{case['id']}/child-app/invite", headers=counselor_headers).status_code == 409


def test_invalid_device_token_rejected(client: TestClient) -> None:
    assert client.get("/api/v1/child-app/home").status_code == 401
    assert client.get("/api/v1/child-app/home", headers={"Authorization": "Bearer nope"}).status_code == 401


def test_other_counselor_blocked(
    client: TestClient, counselor_headers: Headers, other_counselor_headers: Headers, case: dict
) -> None:
    assert client.get(f"/api/v1/cases/{case['id']}/child-app", headers=other_counselor_headers).status_code == 403
    assert client.post(f"/api/v1/cases/{case['id']}/child-app/invite", headers=other_counselor_headers).status_code == 403


def test_counselor_token_cannot_call_device_api(client: TestClient, counselor_headers: Headers) -> None:
    assert client.get("/api/v1/child-app/home", headers=counselor_headers).status_code == 401


def test_device_token_cannot_answer_other_case(client: TestClient, counselor_headers: Headers, case: dict) -> None:
    other = create_case(client, counselor_headers)
    first = _linked(client, counselor_headers, case["id"])
    second = _linked(client, counselor_headers, other["id"])
    _send(client, counselor_headers, other["id"], ["safe", "home", "meal"])
    set_id = _home(client, second)["pending"]["id"]
    response = client.post(f"/api/v1/child-app/question-sets/{set_id}/answers", json={"answers": []}, headers=first)
    assert response.status_code == 404


@pytest.mark.parametrize(
    "ids",
    [["sleep", "home"], ["sleep", "home", "safe", "meal", "free"], ["sleep", "sleep", "home"], ["sleep", "home", "nope"]],
)
def test_send_validates_question_ids(client: TestClient, counselor_headers: Headers, case: dict, ids) -> None:
    _linked(client, counselor_headers, case["id"])
    response = client.post(
        f"/api/v1/cases/{case['id']}/child-app/question-sets", json={"question_ids": ids}, headers=counselor_headers
    )
    assert response.status_code in (400, 422)


def test_send_requires_linked(client: TestClient, counselor_headers: Headers, case: dict) -> None:
    response = client.post(
        f"/api/v1/cases/{case['id']}/child-app/question-sets",
        json={"question_ids": ["sleep", "home", "safe"]},
        headers=counselor_headers,
    )
    assert response.status_code == 409


def test_new_set_replaces_unanswered_and_old_answer_rejected(
    client: TestClient, counselor_headers: Headers, case: dict
) -> None:
    device = _linked(client, counselor_headers, case["id"])
    _send(client, counselor_headers, case["id"], ["sleep", "home", "safe"])
    old_id = _home(client, device)["pending"]["id"]
    _send(client, counselor_headers, case["id"], ["meal", "school", "week"])
    pending = _home(client, device)["pending"]
    assert pending["id"] != old_id
    answers = [{"question_id": q, "skipped": True} for q in ["sleep", "home", "safe"]]
    response = client.post(f"/api/v1/child-app/question-sets/{old_id}/answers", json={"answers": answers}, headers=device)
    assert response.status_code == 409


def test_answers_must_match_and_cannot_repeat(client: TestClient, counselor_headers: Headers, case: dict) -> None:
    device = _linked(client, counselor_headers, case["id"])
    _send(client, counselor_headers, case["id"], ["sleep", "home", "safe"])
    set_id = _home(client, device)["pending"]["id"]
    url = f"/api/v1/child-app/question-sets/{set_id}/answers"
    assert client.post(url, json={"answers": [{"question_id": "sleep", "choice_index": 0}]}, headers=device).status_code == 400
    bad = [{"question_id": q, "choice_index": 99} for q in ["sleep", "home", "safe"]]
    assert client.post(url, json={"answers": bad}, headers=device).status_code == 400
    good = [{"question_id": q, "choice_index": 0} for q in ["sleep", "home", "safe"]]
    assert client.post(url, json={"answers": good}, headers=device).status_code == 200
    assert client.post(url, json={"answers": good}, headers=device).status_code == 409


def test_closed_case_stops_device(client: TestClient, counselor_headers: Headers, case: dict, db) -> None:
    from app.core.enums import CaseStatus
    from app.models.case import Case

    device = _linked(client, counselor_headers, case["id"])
    row = db.scalar(select(Case))
    row.status = CaseStatus.CLOSED
    db.commit()
    assert client.get("/api/v1/child-app/home", headers=device).status_code == 401


def test_next_consult_exposes_only_date_time_place(client: TestClient, counselor_headers: Headers, case: dict, db) -> None:
    from app.core.enums import ScheduleKind
    from app.models.schedule import ScheduleEvent
    from app.models.user import User

    device = _linked(client, counselor_headers, case["id"])
    owner = db.scalar(select(User))
    today = datetime.now(timezone.utc).date() + timedelta(days=2)
    db.add(ScheduleEvent(owner_id=owner.id, kind=ScheduleKind.CONSULT, case_id=uuid.UUID(case["id"]), title="비공개제목",
                         event_date=today, event_time="16:00", place="기관 상담실"))
    db.commit()
    response = client.get("/api/v1/child-app/home", headers=device)
    assert "비공개제목" not in response.text
    assert response.json()["data"]["next_consult"] == {"date": today.isoformat(), "time": "16:00", "place": "기관 상담실"}


def test_admin_sees_status_but_not_child_content(
    client: TestClient, counselor_headers: Headers, admin_headers: Headers, case: dict
) -> None:
    device = _linked(client, counselor_headers, case["id"])
    _send(client, counselor_headers, case["id"], ["safe", "home", "meal"])
    pending = _home(client, device)["pending"]
    answers = [{"question_id": q["id"], "skipped": True} for q in pending["questions"]]
    client.post(f"/api/v1/child-app/question-sets/{pending['id']}/answers", json={"answers": answers}, headers=device)
    view = _view(client, admin_headers, case["id"])
    assert view["status"] == "LINKED"
    assert view["last_response_at"] is not None
    assert view["feed"] == []
