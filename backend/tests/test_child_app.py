# 아이 앱(콩콩) 1단계: 초대 코드 연결 → 질문 보내기 → 답변 → 상담사 피드.

import hashlib
import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import settings
from app.core.enums import AuditAction
from app.models.audit_log import AuditLog
from app.models.child_app import ChildAppLink
from app.services import signup_service
from tests.conftest import create_case

Headers = Dict[str, str]


@pytest.fixture(autouse=True)
def _limits(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setattr(settings, "CHILD_APP_ENABLED", True)
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
    [[], ["sleep", "sleep", "home"], ["sleep", "home", "nope"]],
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
    from app.core.enums import ScheduleConsultType, ScheduleKind
    from app.models.schedule import ScheduleEvent
    from app.models.user import User

    device = _linked(client, counselor_headers, case["id"])
    owner = db.scalar(select(User))
    today = datetime.now(timezone.utc).date() + timedelta(days=2)
    db.add(ScheduleEvent(owner_id=owner.id, kind=ScheduleKind.CONSULT, consult_type=ScheduleConsultType.REGULAR, case_id=uuid.UUID(case["id"]), title="비공개제목",
                         event_date=today, event_time="16:00", place="기관 상담실"))
    db.commit()
    response = client.get("/api/v1/child-app/home", headers=device)
    assert "비공개제목" not in response.text
    assert response.json()["data"]["next_consult"] == {"date": today.isoformat(), "time": "16:00", "place": "기관 상담실"}


def test_case_view_gives_written_text_and_next_consult(client: TestClient, counselor_headers: Headers, case: dict, db) -> None:
    from app.core.enums import ScheduleConsultType, ScheduleKind
    from app.models.schedule import ScheduleEvent
    from app.models.user import User

    device = _linked(client, counselor_headers, case["id"])
    assert _view(client, counselor_headers, case["id"])["next_consult"] is None

    day = datetime.now(timezone.utc).date() + timedelta(days=3)
    db.add(ScheduleEvent(owner_id=db.scalar(select(User)).id, kind=ScheduleKind.CONSULT, consult_type=ScheduleConsultType.REGULAR,
                         case_id=uuid.UUID(case["id"]), title="정기", event_date=day, event_time="15:30", place="상담실"))
    db.commit()
    _send(client, counselor_headers, case["id"], ["sleep", "safe", "free"])
    pending = _home(client, device)["pending"]
    answers = [
        {"question_id": "sleep", "choice_index": 0},
        {"question_id": "safe", "choice_index": 0},
        {"question_id": "free", "text": "가상의 글", "chip": "만나서 이야기할게요"},
    ]
    response = client.post(f"/api/v1/child-app/question-sets/{pending['id']}/answers", json={"answers": answers}, headers=device)
    assert response.status_code == 200, response.text

    view = _view(client, counselor_headers, case["id"])
    assert view["next_consult"] == {"date": day.isoformat(), "time": "15:30", "place": "상담실"}
    items = {item["question_id"]: item for item in view["feed"][0]["payload"]["items"]}
    assert items["free"]["written"] == "가상의 글"
    assert items["free"]["answer"] == "가상의 글 · 만나서 이야기할게요"
    assert "written" not in items["sleep"]


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


def test_unstorable_child_text_rejected(client: TestClient, counselor_headers: Headers, case: dict) -> None:
    device = _linked(client, counselor_headers, case["id"])
    _send(client, counselor_headers, case["id"], ["sleep", "home", "free"])
    set_id = _home(client, device)["pending"]["id"]
    answers = [
        {"question_id": "sleep", "skipped": True},
        {"question_id": "home", "skipped": True},
        {"question_id": "free", "text": "a\u0000b"},
    ]
    response = client.post(f"/api/v1/child-app/question-sets/{set_id}/answers", json={"answers": answers}, headers=device)
    assert response.status_code == 422


def _alert(client: TestClient, device: Headers) -> None:
    response = client.post("/api/v1/child-app/alerts", headers=device)
    assert response.status_code == 200, response.text
    assert response.json()["data"] == {"received": True}


def _open(client: TestClient, headers: Headers) -> list:
    response = client.get("/api/v1/child-app-alerts/open", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()["data"]


def test_alert_reaches_counselor_and_admin_until_acknowledged(
    client: TestClient, counselor_headers: Headers, admin_headers: Headers, case: dict
) -> None:
    device = _linked(client, counselor_headers, case["id"])
    _alert(client, device)
    mine = _open(client, counselor_headers)
    assert [item["case_id"] for item in mine] == [case["id"]]
    assert [item["id"] for item in _open(client, admin_headers)] == [mine[0]["id"]]
    view = _view(client, counselor_headers, case["id"])
    assert view["feed"][0]["kind"] == "ALERT" and view["feed"][0]["level"] == "RED"
    assert view["last_response_at"] is not None
    assert _view(client, admin_headers, case["id"])["open_alerts"][0]["id"] == mine[0]["id"]

    url = f"/api/v1/cases/{case['id']}/child-app/alerts/{mine[0]['id']}/ack"
    assert client.post(url, headers=counselor_headers).status_code == 204
    first = _view(client, counselor_headers, case["id"])["feed"][0]["acknowledged_at"]
    assert first is not None
    assert client.post(url, headers=admin_headers).status_code == 204
    assert _view(client, counselor_headers, case["id"])["feed"][0]["acknowledged_at"] == first
    assert _open(client, counselor_headers) == [] and _open(client, admin_headers) == []


def test_repeated_alert_while_open_makes_one_alert(client: TestClient, counselor_headers: Headers, case: dict) -> None:
    device = _linked(client, counselor_headers, case["id"])
    _alert(client, device)
    _alert(client, device)
    assert len(_open(client, counselor_headers)) == 1


def test_alert_scope_and_auth(
    client: TestClient, counselor_headers: Headers, other_counselor_headers: Headers, case: dict
) -> None:
    assert client.post("/api/v1/child-app/alerts").status_code == 401
    assert client.post("/api/v1/child-app/alerts", headers=counselor_headers).status_code == 401
    assert client.get("/api/v1/child-app-alerts/open").status_code == 401
    device = _linked(client, counselor_headers, case["id"])
    _alert(client, device)
    assert _open(client, other_counselor_headers) == []
    alert_id = _open(client, counselor_headers)[0]["id"]
    url = f"/api/v1/cases/{case['id']}/child-app/alerts/{alert_id}/ack"
    assert client.post(url, headers=other_counselor_headers).status_code == 403


def test_ack_rejects_alert_of_other_case(client: TestClient, counselor_headers: Headers, case: dict) -> None:
    other = create_case(client, counselor_headers)
    device = _linked(client, counselor_headers, case["id"])
    _alert(client, device)
    alert_id = _open(client, counselor_headers)[0]["id"]
    url = f"/api/v1/cases/{other['id']}/child-app/alerts/{alert_id}/ack"
    assert client.post(url, headers=counselor_headers).status_code == 404


def _answer(client: TestClient, headers: Headers, device: Headers, case_id: str, ids, answers) -> None:
    _send(client, headers, case_id, ids)
    set_id = _home(client, device)["pending"]["id"]
    response = client.post(f"/api/v1/child-app/question-sets/{set_id}/answers", json={"answers": answers}, headers=device)
    assert response.status_code == 200, response.text


def _skips(*ids) -> list:
    return [{"question_id": q, "skipped": True} for q in ids]


def test_red_answer_opens_alert_and_can_be_acknowledged(
    client: TestClient, counselor_headers: Headers, admin_headers: Headers, case: dict
) -> None:
    device = _linked(client, counselor_headers, case["id"])
    _answer(client, counselor_headers, device, case["id"], ["safe", "home", "meal"],
            [{"question_id": "safe", "choice_index": 2}, *_skips("home", "meal")])
    mine = _open(client, counselor_headers)
    assert [item["reason"] for item in mine] == ["RED_ANSWER"]
    assert [item["reason"] for item in _open(client, admin_headers)] == ["NEEDS_CHECK"]
    url = f"/api/v1/cases/{case['id']}/child-app/alerts/{mine[0]['id']}/ack"
    assert client.post(url, headers=counselor_headers).status_code == 204
    assert _open(client, counselor_headers) == []


def test_contact_request_opens_alert(client: TestClient, counselor_headers: Headers, case: dict) -> None:
    device = _linked(client, counselor_headers, case["id"])
    _answer(client, counselor_headers, device, case["id"], ["free", "home", "meal"],
            [{"question_id": "free", "chip": "전화로 연락받고 싶어요"}, *_skips("home", "meal")])
    assert [item["reason"] for item in _open(client, counselor_headers)] == ["CONTACT_REQUEST"]


def test_amber_answer_does_not_open_alert(client: TestClient, counselor_headers: Headers, case: dict) -> None:
    device = _linked(client, counselor_headers, case["id"])
    _answer(client, counselor_headers, device, case["id"], ["safe", "home", "meal"],
            [{"question_id": "safe", "choice_index": 1}, *_skips("home", "meal")])
    assert _open(client, counselor_headers) == []


def test_alert_right_after_ack_is_new_alert(client: TestClient, counselor_headers: Headers, case: dict) -> None:
    device = _linked(client, counselor_headers, case["id"])
    _alert(client, device)
    first = _open(client, counselor_headers)[0]["id"]
    client.post(f"/api/v1/cases/{case['id']}/child-app/alerts/{first}/ack", headers=counselor_headers)
    _alert(client, device)
    opened = _open(client, counselor_headers)
    assert len(opened) == 1 and opened[0]["id"] != first


def test_new_alert_visible_past_list_limit(client: TestClient, counselor_headers: Headers, monkeypatch) -> None:
    from app.services import child_app_service

    monkeypatch.setattr(child_app_service, "OPEN_ALERT_LIMIT", 2)
    cases = [create_case(client, counselor_headers) for _ in range(3)]
    for item in cases:
        _alert(client, _linked(client, counselor_headers, item["id"]))
    opened = _open(client, counselor_headers)
    assert len(opened) == 2 and cases[2]["id"] in [row["case_id"] for row in opened]


def test_unassigned_admin_cannot_invite_or_send(
    client: TestClient, counselor_headers: Headers, admin_headers: Headers, case: dict
) -> None:
    assert client.post(f"/api/v1/cases/{case['id']}/child-app/invite", headers=admin_headers).status_code == 403
    _linked(client, counselor_headers, case["id"])
    response = client.post(
        f"/api/v1/cases/{case['id']}/child-app/question-sets",
        json={"question_ids": ["sleep", "home", "safe"]},
        headers=admin_headers,
    )
    assert response.status_code == 403


def test_visit_consult_place_not_sent(client: TestClient, counselor_headers: Headers, case: dict, db) -> None:
    from app.core.enums import ScheduleConsultType, ScheduleKind
    from app.models.schedule import ScheduleEvent
    from app.models.user import User

    device = _linked(client, counselor_headers, case["id"])
    owner = db.scalar(select(User))
    db.add(ScheduleEvent(owner_id=owner.id, kind=ScheduleKind.CONSULT, consult_type=ScheduleConsultType.VISIT,
                         case_id=uuid.UUID(case["id"]), event_date=datetime.now(timezone.utc).date() + timedelta(days=2),
                         event_time="16:00", place="아이 집 주소"))
    db.commit()
    assert _home(client, device)["next_consult"]["place"] is None


def test_switch_off_returns_503(client: TestClient, counselor_headers: Headers, case: dict, monkeypatch) -> None:
    device = _linked(client, counselor_headers, case["id"])
    monkeypatch.setattr(settings, "CHILD_APP_ENABLED", False)
    for method, url, headers in [
        ("post", "/api/v1/child-app/link", {}),
        ("get", "/api/v1/child-app/home", device),
        ("post", "/api/v1/child-app/alerts", device),
        ("get", "/api/v1/child-app-alerts/open", counselor_headers),
        ("get", f"/api/v1/cases/{case['id']}/child-app", counselor_headers),
        ("post", f"/api/v1/cases/{case['id']}/child-app/invite", counselor_headers),
    ]:
        response = getattr(client, method)(url, headers=headers)
        assert response.status_code == 503, url
        assert response.json()["error"]["code"] == "CHILD_APP_DISABLED"


def test_unassigned_admin_cannot_close_answer_alert_but_can_close_urgent(
    client: TestClient, counselor_headers: Headers, admin_headers: Headers, case: dict
) -> None:
    device = _linked(client, counselor_headers, case["id"])
    _answer(client, counselor_headers, device, case["id"], ["safe", "home", "meal"],
            [{"question_id": "safe", "choice_index": 2}, *_skips("home", "meal")])
    seen = _open(client, admin_headers)[0]
    assert seen["can_ack"] is False
    url = f"/api/v1/cases/{case['id']}/child-app/alerts/{seen['id']}/ack"
    assert client.post(url, headers=admin_headers).status_code == 403
    assert len(_open(client, counselor_headers)) == 1

    _alert(client, device)
    urgent = next(item for item in _open(client, admin_headers) if item["reason"] == "ALERT")
    assert urgent["can_ack"] is True
    url = f"/api/v1/cases/{case['id']}/child-app/alerts/{urgent['id']}/ack"
    assert client.post(url, headers=admin_headers).status_code == 204


def test_open_alert_reports_repeats(client: TestClient, counselor_headers: Headers, case: dict) -> None:
    device = _linked(client, counselor_headers, case["id"])
    _alert(client, device)
    assert _open(client, counselor_headers)[0]["repeat_count"] == 0
    _alert(client, device)
    item = _open(client, counselor_headers)[0]
    assert item["repeat_count"] == 1 and item["last_at"] is not None


def test_written_answer_needs_check_without_grading(
    client: TestClient, counselor_headers: Headers, admin_headers: Headers, case: dict
) -> None:
    device = _linked(client, counselor_headers, case["id"])
    _answer(client, counselor_headers, device, case["id"], ["free", "home", "meal"],
            [{"question_id": "free", "text": "오늘 집에 가기 무서워요"}, *_skips("home", "meal")])
    assert [item["reason"] for item in _open(client, counselor_headers)] == ["TEXT_ANSWER"]
    assert [item["reason"] for item in _open(client, admin_headers)] == ["NEEDS_CHECK"]
    assert _view(client, counselor_headers, case["id"])["feed"][0]["level"] == "NONE"


def test_plain_chip_answer_opens_no_alert(client: TestClient, counselor_headers: Headers, case: dict) -> None:
    device = _linked(client, counselor_headers, case["id"])
    _answer(client, counselor_headers, device, case["id"], ["free", "home", "meal"],
            [{"question_id": "free", "chip": "없어요"}, *_skips("home", "meal")])
    assert _open(client, counselor_headers) == []


def test_text_is_kept_when_chip_also_selected(client: TestClient, counselor_headers: Headers, case: dict) -> None:
    device = _linked(client, counselor_headers, case["id"])
    _answer(client, counselor_headers, device, case["id"], ["free", "home", "meal"],
            [{"question_id": "free", "text": "할 말 있어요", "chip": "전화로 연락받고 싶어요"}, *_skips("home", "meal")])
    assert _open(client, counselor_headers)[0]["reason"] == "CONTACT_REQUEST"
    item = _view(client, counselor_headers, case["id"])["feed"][0]["payload"]["items"][0]
    assert item["answer"] == "할 말 있어요 · 전화로 연락받고 싶어요"


def test_hard_to_answer_chip_keeps_written_text(client: TestClient, counselor_headers: Headers, case: dict) -> None:
    device = _linked(client, counselor_headers, case["id"])
    _answer(client, counselor_headers, device, case["id"], ["free", "home", "meal"],
            [{"question_id": "free", "text": "말하기 무서워요", "chip": "답하기 어려워요"}, *_skips("home", "meal")])
    assert [item["reason"] for item in _open(client, counselor_headers)] == ["TEXT_ANSWER"]
    item = _view(client, counselor_headers, case["id"])["feed"][0]["payload"]["items"][0]
    assert item["answer"] == "말하기 무서워요 · 답하기 어려워요"


def test_hard_to_answer_chip_alone_is_skip(client: TestClient, counselor_headers: Headers, case: dict) -> None:
    device = _linked(client, counselor_headers, case["id"])
    _answer(client, counselor_headers, device, case["id"], ["free", "home", "meal"],
            [{"question_id": "free", "chip": "답하기 어려워요"}, *_skips("home", "meal")])
    assert _open(client, counselor_headers) == []
    assert _view(client, counselor_headers, case["id"])["feed"][0]["payload"]["items"][0]["level"] == "SKIP"


# =========================================================
# AI 초안(확인해 볼 점 · 추가 질문)
# =========================================================
AI_URL = "/api/v1/cases/{}/child-app/ai-draft"


def _fake_drafts(items, written=None, known_identifiers=(), deadline=None):
    return [
        {"question_id": item["question_id"], "note": f"가상 메모 {item['answer']}", "questions": [{"text": "언제 그랬나요?", "options": ["오늘", "어제", "말하기 어려워요"]}]}
        for item in items
    ]


@pytest.fixture
def ai_generator():
    from app.services import child_app_ai_service

    child_app_ai_service.set_generator_override(_fake_drafts)
    child_app_ai_service.reset_limits()
    yield child_app_ai_service
    child_app_ai_service.set_generator_override(None)


def _ai_answer(client: TestClient, headers: Headers, device: Headers, case_id: str, safe: int = 2) -> None:
    _send(client, headers, case_id, ["sleep", "home", "safe"])
    pending = _home(client, device)["pending"]
    answers = [{"question_id": "sleep", "choice_index": 0}, {"question_id": "home", "choice_index": 0}, {"question_id": "safe", "choice_index": safe}]
    assert client.post(f"/api/v1/child-app/question-sets/{pending['id']}/answers", json={"answers": answers}, headers=device).status_code == 200


def _draft(client: TestClient, headers: Headers, case_id: str) -> dict:
    response = client.post(AI_URL.format(case_id), headers=headers)
    assert response.status_code == 200, response.text
    return response.json()["data"]


def test_ai_draft_off_by_default(client: TestClient, counselor_headers: Headers, case: dict) -> None:
    assert _view(client, counselor_headers, case["id"])["ai_enabled"] is False
    response = client.post(AI_URL.format(case["id"]), headers=counselor_headers)
    assert response.status_code == 503 and response.json()["error"]["code"] == "CHILD_APP_AI_DISABLED"


def test_ai_draft_covers_flagged_only_and_is_reused(
    client: TestClient, counselor_headers: Headers, case: dict, db, ai_generator, monkeypatch
) -> None:
    device = _linked(client, counselor_headers, case["id"])
    assert client.post(AI_URL.format(case["id"]), headers=counselor_headers).status_code == 409

    _ai_answer(client, counselor_headers, device, case["id"], safe=0)
    assert client.post(AI_URL.format(case["id"]), headers=counselor_headers).status_code == 409

    seen = {}
    def recording(items, written=None, known_identifiers=(), deadline=None):
        seen.update(items=items, names=list(known_identifiers))
        return _fake_drafts(items)
    ai_generator.set_generator_override(recording)
    _ai_answer(client, counselor_headers, device, case["id"], safe=2)
    draft = _draft(client, counselor_headers, case["id"])

    assert [item["question_id"] for item in seen["items"]] == ["safe"]
    assert seen["items"][0]["previous"] == ["안전해요"] and case["child_alias"] in seen["names"]
    assert _draft(client, counselor_headers, case["id"])["id"] == draft["id"]
    assert _view(client, counselor_headers, case["id"])["ai_draft"]["id"] == draft["id"]

    log = db.scalars(select(AuditLog).where(AuditLog.action == AuditAction.CHILD_APP_AI_DRAFT_CREATED)).one()
    assert "가상 메모" not in str(log.detail)


def test_ai_failure_saves_nothing_and_hides_reason(client: TestClient, counselor_headers: Headers, case: dict, ai_generator) -> None:
    device = _linked(client, counselor_headers, case["id"])
    _ai_answer(client, counselor_headers, device, case["id"])

    def broken(items, **_):
        raise RuntimeError("비공개 사유")

    ai_generator.set_generator_override(broken)
    response = client.post(AI_URL.format(case["id"]), headers=counselor_headers)
    assert response.status_code == 502 and "비공개" not in response.text
    assert _view(client, counselor_headers, case["id"])["ai_draft"] is None


def test_only_assigned_counselor_uses_ai_draft(
    client: TestClient, counselor_headers: Headers, other_counselor_headers: Headers, admin_headers: Headers, case: dict, ai_generator
) -> None:
    device = _linked(client, counselor_headers, case["id"])
    _ai_answer(client, counselor_headers, device, case["id"])
    draft = _draft(client, counselor_headers, case["id"])

    assert client.post(AI_URL.format(case["id"]), headers=other_counselor_headers).status_code in (403, 404)
    assert client.post(AI_URL.format(case["id"]), headers=admin_headers).status_code == 403
    assert _view(client, admin_headers, case["id"])["ai_draft"] is None
    question = draft["items"][0]["questions"][0]["id"]
    url = f"{AI_URL.format(case['id'])}/{draft['id']}/questions/{question}/approval"
    assert client.put(url, json={"approved": True}, headers=admin_headers).status_code == 403


def test_approved_question_reaches_app_and_can_be_withdrawn(client: TestClient, counselor_headers: Headers, case: dict, ai_generator) -> None:
    device = _linked(client, counselor_headers, case["id"])
    _ai_answer(client, counselor_headers, device, case["id"])
    draft = _draft(client, counselor_headers, case["id"])
    question = draft["items"][0]["questions"][0]
    base = f"{AI_URL.format(case['id'])}/{draft['id']}/questions/{question['id']}"

    assert _home(client, device)["pending"] is None

    approved = client.put(f"{base}/approval", json={"approved": True}, headers=counselor_headers)
    assert approved.status_code == 200 and approved.json()["data"]["items"][0]["questions"][0]["approved"] is True
    assert [q["id"] for q in _home(client, device)["pending"]["questions"]] == [question["id"]]
    # 두 번 눌러도 한 번만 간다.
    client.put(f"{base}/approval", json={"approved": True}, headers=counselor_headers)
    assert len(_home(client, device)["pending"]["questions"]) == 1

    withdrawn = client.put(f"{base}/approval", json={"approved": False}, headers=counselor_headers)
    assert withdrawn.json()["data"]["items"][0]["questions"][0]["approved"] is False
    assert _home(client, device)["pending"] is None


def test_editing_returns_to_unapproved_and_answered_cannot_withdraw(client: TestClient, counselor_headers: Headers, case: dict, ai_generator) -> None:
    device = _linked(client, counselor_headers, case["id"])
    _ai_answer(client, counselor_headers, device, case["id"])
    draft = _draft(client, counselor_headers, case["id"])
    question = draft["items"][0]["questions"][0]
    base = f"{AI_URL.format(case['id'])}/{draft['id']}"

    note = client.patch(f"{base}/notes/safe", json={"text": "상담사가 고친 메모"}, headers=counselor_headers)
    assert note.status_code == 200 and note.json()["data"]["items"][0]["note_edited"] is True
    assert client.patch(f"{base}/notes/없는칸", json={"text": "x"}, headers=counselor_headers).status_code == 404

    url = f"{base}/questions/{question['id']}"
    client.put(f"{url}/approval", json={"approved": True}, headers=counselor_headers)
    edited = client.patch(url, json={"text": "고친 질문", "options": ["네", "아니요"]}, headers=counselor_headers)
    item = edited.json()["data"]["items"][0]["questions"][0]
    assert item["edited"] is True and item["approved"] is False and item["text"] == "고친 질문"
    assert _home(client, device)["pending"] is None

    client.put(f"{url}/approval", json={"approved": True}, headers=counselor_headers)
    pending = _home(client, device)["pending"]
    assert pending["questions"][0]["text"] == "고친 질문"
    answer = {"answers": [{"question_id": question["id"], "choice_index": 0}]}
    assert client.post(f"/api/v1/child-app/question-sets/{pending['id']}/answers", json=answer, headers=device).status_code == 200

    assert client.put(f"{url}/approval", json={"approved": False}, headers=counselor_headers).status_code == 409
    assert client.patch(url, json={"text": "또 고침", "options": ["네", "아니요"]}, headers=counselor_headers).status_code == 409
    # 다음 답의 묶음에서도 질문 문장이 남는다.
    feed = _view(client, counselor_headers, case["id"])["feed"]
    assert feed[0]["payload"]["items"][0]["question"] == "고친 질문"


def test_llm_output_is_filtered() -> None:
    from app.adapters.module_loader import load_callable

    HARD_TO_SAY = "말하기 어려워요"
    clean_output = load_callable("ai.modeling.abuse.child_answer_llm", "clean_output")

    items = [{"question_id": "a"}, {"question_id": "b"}, {"question_id": "c"}, {"question_id": "d"}]
    raw = {"items": [
        {"no": 1, "note": "다음 상담에서 살펴봐 주세요.", "question": "요즘 언제 힘들었나요?", "options": ["아침", "저녁"]},
        {"no": 2, "note": "학대로 확정됩니다.", "question": "언제였나요?", "options": ["오늘", "어제"]},
        {"no": 3, "note": "살펴봐 주세요.", "question": "엄마가 때렸지?", "options": ["네", "아니요"]},
        {"no": 4, "note": "살펴봐 주세요.", "question": "[PERSON_01]님이 언제 왔나요?", "options": ["오늘", "어제"]},
        {"no": 9, "note": "없는 번호"},
        "모양이 틀림",
    ]}

    result = clean_output(raw, items)

    assert [entry["question_id"] for entry in result] == ["a", "c", "d"]
    assert result[0]["questions"][0]["options"] == ["아침", "저녁", HARD_TO_SAY]
    assert result[1]["questions"] == [] and result[2]["questions"] == []
    assert clean_output("이상한 값", items) == []


def _approve(client: TestClient, headers: Headers, case_id: str, draft: dict, approved: bool = True) -> dict:
    question = draft["items"][0]["questions"][0]["id"]
    url = f"{AI_URL.format(case_id)}/{draft['id']}/questions/{question}/approval"
    response = client.put(url, json={"approved": approved}, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()["data"]


def _bank_answers() -> dict:
    return {"answers": [{"question_id": "sleep", "choice_index": 0}, {"question_id": "home", "choice_index": 0}, {"question_id": "safe", "choice_index": 2}]}


def test_approval_while_child_answers_keeps_answers_and_carries_question(
    client: TestClient, counselor_headers: Headers, case: dict, ai_generator, db
) -> None:
    device = _linked(client, counselor_headers, case["id"])
    _ai_answer(client, counselor_headers, device, case["id"])
    draft = _draft(client, counselor_headers, case["id"])
    _send(client, counselor_headers, case["id"], ["sleep", "home", "safe"])
    seen = _home(client, device)["pending"]

    _approve(client, counselor_headers, case["id"], draft)
    response = client.post(f"/api/v1/child-app/question-sets/{seen['id']}/answers", json=_bank_answers(), headers=device)
    assert response.status_code == 200, response.text

    carried = _home(client, device)["pending"]
    assert carried["id"] != seen["id"] and [q["id"] for q in carried["questions"]] == [draft["items"][0]["questions"][0]["id"]]
    view = _view(client, counselor_headers, case["id"])
    assert view["feed"][0]["payload"]["items"][2]["answer"] == "안전하지 않아요"
    # 화면은 새 답의 초안을 보이므로, 지난 초안의 질문이 넘긴 묶음을 가리키는지는 표에서 본다.
    from app.models.child_app import ChildAppAiDraft

    db.expire_all()
    stored = db.scalars(select(ChildAppAiDraft)).one().items[0]["questions"][0]
    assert stored["question_set_id"] == carried["id"]


def test_withdrawal_while_child_answers_drops_only_that_answer(
    client: TestClient, counselor_headers: Headers, case: dict, ai_generator, db
) -> None:
    device = _linked(client, counselor_headers, case["id"])
    _ai_answer(client, counselor_headers, device, case["id"])
    draft = _draft(client, counselor_headers, case["id"])
    _send(client, counselor_headers, case["id"], ["sleep", "home", "safe"])
    _approve(client, counselor_headers, case["id"], draft)
    seen = _home(client, device)["pending"]
    ai_id = seen["questions"][-1]["id"]

    _approve(client, counselor_headers, case["id"], draft, approved=False)
    answers = _bank_answers()
    answers["answers"].append({"question_id": ai_id, "choice_index": 0})
    assert client.post(f"/api/v1/child-app/question-sets/{seen['id']}/answers", json=answers, headers=device).status_code == 200
    assert _home(client, device)["pending"] is None

    # 알 수 없는 문항 답이나 빠진 기본 문항은 여전히 거절한다.
    _send(client, counselor_headers, case["id"], ["sleep", "home", "safe"])
    pending = _home(client, device)["pending"]
    bad = {"answers": [{"question_id": "sleep", "choice_index": 0}, {"question_id": "home", "choice_index": 0}]}
    assert client.post(f"/api/v1/child-app/question-sets/{pending['id']}/answers", json=bad, headers=device).status_code == 400

    feed = _view(client, counselor_headers, case["id"])["feed"]
    assert any(event["payload"].get("withdrawn") for event in feed)
    assert db.scalars(select(AuditLog).where(AuditLog.action == AuditAction.CHILD_APP_QUESTION_WITHDRAWN)).one()


def test_followup_answer_needs_check_and_closed_case_gets_no_draft(
    client: TestClient, counselor_headers: Headers, case: dict, ai_generator, db
) -> None:
    from app.core.enums import CaseStatus
    from app.models.case import Case

    device = _linked(client, counselor_headers, case["id"])
    _ai_answer(client, counselor_headers, device, case["id"])
    draft = _draft(client, counselor_headers, case["id"])
    for alert in _view(client, counselor_headers, case["id"])["open_alerts"]:
        client.post(f"/api/v1/cases/{case['id']}/child-app/alerts/{alert['id']}/ack", headers=counselor_headers)

    _approve(client, counselor_headers, case["id"], draft)
    pending = _home(client, device)["pending"]
    answer = {"answers": [{"question_id": pending["questions"][0]["id"], "choice_index": 0}]}
    assert client.post(f"/api/v1/child-app/question-sets/{pending['id']}/answers", json=answer, headers=device).status_code == 200

    view = _view(client, counselor_headers, case["id"])
    assert view["feed"][0]["level"] == "NONE"
    assert [alert["reason"] for alert in view["open_alerts"]] == ["FOLLOWUP_ANSWER"]

    _ai_answer(client, counselor_headers, device, case["id"])
    db.get(Case, uuid.UUID(case["id"])).status = CaseStatus.CLOSED
    db.commit()
    assert client.post(AI_URL.format(case["id"]), headers=counselor_headers).status_code == 409


def test_urgent_flag_and_skipped_followup(
    client: TestClient, counselor_headers: Headers, admin_headers: Headers, case: dict, ai_generator
) -> None:
    device = _linked(client, counselor_headers, case["id"])
    _ai_answer(client, counselor_headers, device, case["id"])
    draft = _draft(client, counselor_headers, case["id"])

    # 담당이 아닌 관리자는 이유를 모르지만 긴급인 것은 안다.
    admin_alert = client.get("/api/v1/child-app-alerts/open", headers=admin_headers).json()["data"][0]
    assert admin_alert["reason"] == "NEEDS_CHECK" and admin_alert["urgent"] is True

    _approve(client, counselor_headers, case["id"], draft)
    pending = _home(client, device)["pending"]
    skipped = {"answers": [{"question_id": pending["questions"][0]["id"], "skipped": True}]}
    assert client.post(f"/api/v1/child-app/question-sets/{pending['id']}/answers", json=skipped, headers=device).status_code == 200

    alerts = _view(client, counselor_headers, case["id"])["open_alerts"]
    # 최신(추가 질문)이 앞이어도 위험 답은 긴급으로 남는다.
    assert [(alert["reason"], alert["urgent"]) for alert in alerts] == [("FOLLOWUP_SKIPPED", False), ("RED_ANSWER", True)]


def test_contact_request_stays_urgent(client: TestClient, counselor_headers: Headers, case: dict) -> None:
    device = _linked(client, counselor_headers, case["id"])
    _send(client, counselor_headers, case["id"], ["sleep", "home", "free"])
    pending = _home(client, device)["pending"]
    answers = {"answers": [
        {"question_id": "sleep", "choice_index": 0},
        {"question_id": "home", "choice_index": 0},
        {"question_id": "free", "chip": "전화로 연락받고 싶어요"},
    ]}
    assert client.post(f"/api/v1/child-app/question-sets/{pending['id']}/answers", json=answers, headers=device).status_code == 200
    alert = _view(client, counselor_headers, case["id"])["open_alerts"][0]
    assert alert["reason"] == "CONTACT_REQUEST" and alert["urgent"] is True


def test_child_link_list_shows_own_cases_and_hides_content_from_admin(
    client: TestClient, counselor_headers: Headers, other_counselor_headers: Headers, admin_headers: Headers, case: dict
) -> None:
    url = "/api/v1/child-app-cases"
    assert client.get(url).status_code == 401

    rows = client.get(url, headers=counselor_headers).json()["data"]
    assert [row["case_id"] for row in rows] == [case["id"]] and rows[0]["status"] == "NOT_LINKED"
    assert client.get(url, headers=other_counselor_headers).json()["data"] == []

    device = _linked(client, counselor_headers, case["id"])
    _ai_answer(client, counselor_headers, device, case["id"], safe=2)

    row = client.get(url, headers=counselor_headers).json()["data"][0]
    assert row["status"] == "LINKED" and row["recent_answers"] == 1 and row["level"] == "RED"
    assert row["open_alert_reason"] == "RED_ANSWER" and row["open_alert_urgent"] is True and row["last_response_at"]

    admin = client.get(url, headers=admin_headers).json()["data"][0]
    assert admin["status"] == "LINKED" and admin["recent_answers"] is None and admin["level"] is None


def test_device_unlink_lets_counselor_link_again(client: TestClient, counselor_headers: Headers, case: dict, db) -> None:
    device = _linked(client, counselor_headers, case["id"])
    _send(client, counselor_headers, case["id"], ["sleep", "home", "safe"])

    assert client.post("/api/v1/child-app/unlink").status_code == 401
    assert client.post("/api/v1/child-app/unlink", headers=device).status_code == 204
    assert client.get("/api/v1/child-app/home", headers=device).status_code == 401

    view = _view(client, counselor_headers, case["id"])
    assert view["status"] == "NOT_LINKED" and view["has_pending_questions"] is False
    assert view["feed"][0]["kind"] == "UNLINKED"
    assert db.scalars(select(AuditLog).where(AuditLog.action == AuditAction.CHILD_APP_UNLINKED)).one()

    again = _linked(client, counselor_headers, case["id"])
    assert _home(client, again)["pending"] is None


def test_alert_after_unlink_in_between_is_401_not_500(client: TestClient, counselor_headers: Headers, case: dict, db) -> None:
    # 인증을 통과한 뒤 그사이 해지가 끝난 경우(민규 #167): 연결 행이 사라져도 500 이 아니라 다시 연결하라는 401.
    from sqlalchemy import delete

    from app.core.errors import APIError
    from app.services import child_app_service

    device = _linked(client, counselor_headers, case["id"])
    link = child_app_service.get_link_by_token(db, device["Authorization"].removeprefix("Bearer "))
    db.execute(delete(ChildAppLink).where(ChildAppLink.id == link.id))
    db.commit()

    with pytest.raises(APIError) as caught:
        child_app_service.send_alert(db, link)
    assert caught.value.status_code == 401
    assert _view(client, counselor_headers, case["id"])["open_alerts"] == []


def test_child_app_stats_counts_sent_and_answered_for_admin_only(
    client: TestClient, counselor_headers: Headers, admin_headers: Headers, case: dict
) -> None:
    device = _linked(client, counselor_headers, case["id"])
    _send(client, counselor_headers, case["id"], ["sleep", "home", "safe"])
    _send(client, counselor_headers, case["id"], ["sleep", "home", "safe"])  # 앞 묶음은 대체된다
    pending = _home(client, device)["pending"]
    answers = {"answers": [{"question_id": q, "choice_index": 0} for q in ("sleep", "home", "safe")]}
    assert client.post(f"/api/v1/child-app/question-sets/{pending['id']}/answers", json=answers, headers=device).status_code == 200

    today = datetime.now(timezone.utc).date()
    url = f"/api/v1/child-app-stats?date_from={today - timedelta(days=1)}&date_to={today + timedelta(days=1)}"
    assert client.get(url, headers=counselor_headers).status_code == 403
    data = client.get(url, headers=admin_headers).json()["data"]
    assert data == {"sent": 2, "answered": 1, "linked_cases": 1}
    bad = f"/api/v1/child-app-stats?date_from={today}&date_to={today - timedelta(days=1)}"
    assert client.get(bad, headers=admin_headers).status_code == 400
