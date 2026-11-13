# 아이 앱(콩콩) 질문 '발송 예약'(API_CONTRACT 24절, 2026-11-11).
#
# 예약 실행기는 없다. 묶음에 '언제부터 보이는지'(deliver_at)를 적고 읽을 때 거른다 — 시험은 서비스의 시계만 옮긴다.

import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, Iterator, List, Optional
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import settings
from app.core.enums import AuditAction, ChildQuestionSetStatus
from app.models.audit_log import AuditLog
from app.models.child_app import ChildQuestionSet
from app.services import child_app_ai_service, child_app_service, signup_service
from tests.conftest import create_case

Headers = Dict[str, str]
KST = ZoneInfo("Asia/Seoul")
IDS = ["sleep", "home", "safe"]


class Clock:
    """child_app_service 의 시계. 정하기 전에는 실제 시각이다(초대 코드 만료 등은 실제 시각으로 지나간다).

    옮기는 날은 모레다 — 묶음의 created_at 은 실제 시각으로 찍히므로, 시험의 예약 시각이 늘 그 뒤에 온다.
    """

    def __init__(self) -> None:
        self.now: Optional[datetime] = None
        self.day = (datetime.now(KST) + timedelta(days=2)).date()

    def __call__(self) -> datetime:
        return self.now or datetime.now(timezone.utc)

    def kst(self, hour: int, minute: int = 0) -> datetime:
        return datetime(self.day.year, self.day.month, self.day.day, hour, minute, tzinfo=KST)

    def at(self, hour: int, minute: int = 0) -> None:
        self.now = self.kst(hour, minute).astimezone(timezone.utc)


@pytest.fixture(autouse=True)
def _limits(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setattr(settings, "CHILD_APP_ENABLED", True)
    signup_service.reset_limits()
    yield
    signup_service.reset_limits()


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch) -> Clock:
    value = Clock()
    monkeypatch.setattr(child_app_service, "_utcnow", value)
    return value


def _linked(client: TestClient, headers: Headers, case_id: str) -> Headers:
    code = client.post(f"/api/v1/cases/{case_id}/child-app/invite", headers=headers).json()["data"]["code"]
    response = client.post("/api/v1/child-app/link", json={"code": code})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['data']['device_token']}"}


def _send(client: TestClient, headers: Headers, case_id: str, ids: List[str], deliver: Optional[str] = None) -> None:
    body: dict = {"question_ids": ids}
    if deliver is not None:
        body["deliver"] = deliver
    response = client.post(f"/api/v1/cases/{case_id}/child-app/question-sets", json=body, headers=headers)
    assert response.status_code == 204, response.text


def _pending(client: TestClient, device: Headers) -> Optional[dict]:
    response = client.get("/api/v1/child-app/home", headers=device)
    assert response.status_code == 200, response.text
    return response.json()["data"]["pending"]


def _view(client: TestClient, headers: Headers, case_id: str) -> dict:
    response = client.get(f"/api/v1/cases/{case_id}/child-app", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()["data"]


def _cancel(client: TestClient, headers: Headers, case_id: str, set_id: str) -> int:
    return client.delete(f"/api/v1/cases/{case_id}/child-app/question-sets/{set_id}", headers=headers).status_code


def _answer(client: TestClient, device: Headers, set_id: str, ids: List[str]) -> int:
    answers = {"answers": [{"question_id": item, "choice_index": 0} for item in ids]}
    return client.post(f"/api/v1/child-app/question-sets/{set_id}/answers", json=answers, headers=device).status_code


def _status(db, set_id: str) -> ChildQuestionSetStatus:
    db.expire_all()
    return db.scalar(select(ChildQuestionSet.status).where(ChildQuestionSet.id == uuid.UUID(set_id)))


def test_reservation_is_hidden_until_deliver_hour(
    client: TestClient, counselor_headers: Headers, case: dict, clock: Clock, db
) -> None:
    device = _linked(client, counselor_headers, case["id"])
    clock.at(14)
    _send(client, counselor_headers, case["id"], IDS, deliver="EVENING")

    view = _view(client, counselor_headers, case["id"])
    scheduled = view["scheduled_questions"]
    assert scheduled["count"] == 3
    assert datetime.fromisoformat(scheduled["deliver_at"]) == clock.kst(18)
    assert view["has_pending_questions"] is True
    # 피드 · 감사 기록에 예약이라는 것이 남는다. 질문 문장은 넣지 않는다.
    assert view["feed"][0]["kind"] == "QUESTIONS_SENT"
    assert view["feed"][0]["payload"] == {"count": 3, "deliver_at": clock.kst(18).astimezone(timezone.utc).isoformat()}
    log = db.scalars(select(AuditLog).where(AuditLog.action == AuditAction.CHILD_APP_QUESTIONS_SENT)).one()
    assert log.detail == {"count": 3, "scheduled": True}

    # 예약 시각 전: 아이 앱에는 없고, 묶음 번호를 알아도 답할 수 없다.
    assert _pending(client, device) is None
    assert _answer(client, device, scheduled["id"], IDS) == 404
    clock.at(17, 59)
    assert _pending(client, device) is None

    # 예약 시각부터 보이고 답할 수 있다. 아이 앱 응답에는 예약 시각을 넣지 않는다.
    clock.at(18)
    home = client.get("/api/v1/child-app/home", headers=device)
    assert home.json()["data"]["pending"]["id"] == scheduled["id"]
    assert "deliver_at" not in home.text
    assert _view(client, counselor_headers, case["id"])["scheduled_questions"] is None
    assert _answer(client, device, scheduled["id"], IDS) == 200
    assert _status(db, scheduled["id"]) == ChildQuestionSetStatus.ANSWERED


@pytest.mark.parametrize("hour,minute", [(18, 0), (18, 30), (23, 59)])
def test_reservation_after_deliver_hour_goes_now(
    client: TestClient, counselor_headers: Headers, case: dict, clock: Clock, hour: int, minute: int
) -> None:
    device = _linked(client, counselor_headers, case["id"])
    clock.at(hour, minute)
    _send(client, counselor_headers, case["id"], IDS, deliver="EVENING")

    assert _pending(client, device) is not None
    view = _view(client, counselor_headers, case["id"])
    assert view["scheduled_questions"] is None
    assert view["feed"][0]["payload"] == {"count": 3}


def test_deliver_hour_follows_setting(
    client: TestClient, counselor_headers: Headers, case: dict, clock: Clock, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "CHILD_APP_DELIVER_HOUR", 20)
    _linked(client, counselor_headers, case["id"])
    clock.at(19)
    _send(client, counselor_headers, case["id"], IDS, deliver="EVENING")

    scheduled = _view(client, counselor_headers, case["id"])["scheduled_questions"]
    assert datetime.fromisoformat(scheduled["deliver_at"]) == clock.kst(20)


def test_default_and_now_send_stay_immediate(
    client: TestClient, counselor_headers: Headers, case: dict, clock: Clock
) -> None:
    device = _linked(client, counselor_headers, case["id"])
    clock.at(9)
    _send(client, counselor_headers, case["id"], IDS)
    first = _pending(client, device)
    assert first is not None
    _send(client, counselor_headers, case["id"], ["meal"], deliver="NOW")
    second = _pending(client, device)
    assert second["id"] != first["id"]
    assert _view(client, counselor_headers, case["id"])["scheduled_questions"] is None

    response = client.post(
        f"/api/v1/cases/{case['id']}/child-app/question-sets",
        json={"question_ids": IDS, "deliver": "TOMORROW"},
        headers=counselor_headers,
    )
    assert response.status_code == 422


def test_cancel_reservation_before_deliver_hour(
    client: TestClient, counselor_headers: Headers, case: dict, clock: Clock, db
) -> None:
    device = _linked(client, counselor_headers, case["id"])
    clock.at(14)
    _send(client, counselor_headers, case["id"], IDS, deliver="EVENING")
    set_id = _view(client, counselor_headers, case["id"])["scheduled_questions"]["id"]

    assert _cancel(client, counselor_headers, case["id"], set_id) == 204
    assert _status(db, set_id) == ChildQuestionSetStatus.CANCELED
    view = _view(client, counselor_headers, case["id"])
    assert view["scheduled_questions"] is None and view["has_pending_questions"] is False
    assert view["feed"][0]["payload"] == {"count": 3, "withdrawn": True}
    log = db.scalars(select(AuditLog).where(AuditLog.action == AuditAction.CHILD_APP_QUESTION_WITHDRAWN)).one()
    assert log.detail == {"count": 3, "scheduled": True}

    # 다시 눌러도 204 이고 기록이 늘지 않는다.
    assert _cancel(client, counselor_headers, case["id"], set_id) == 204
    assert len(db.scalars(select(AuditLog).where(AuditLog.action == AuditAction.CHILD_APP_QUESTION_WITHDRAWN)).all()) == 1

    # 예약 시각이 돼도 아이 앱에 나오지 않는다.
    clock.at(18, 1)
    assert _pending(client, device) is None


def test_cancel_rejected_once_shown_or_answered(
    client: TestClient, counselor_headers: Headers, case: dict, clock: Clock, db
) -> None:
    device = _linked(client, counselor_headers, case["id"])
    clock.at(14)
    _send(client, counselor_headers, case["id"], IDS, deliver="EVENING")
    set_id = _view(client, counselor_headers, case["id"])["scheduled_questions"]["id"]

    clock.at(18)
    response = client.delete(
        f"/api/v1/cases/{case['id']}/child-app/question-sets/{set_id}", headers=counselor_headers
    )
    assert response.status_code == 409 and response.json()["error"]["code"] == "INVALID_CASE_STATE"
    assert _status(db, set_id) == ChildQuestionSetStatus.PENDING

    assert _answer(client, device, set_id, IDS) == 200
    assert _cancel(client, counselor_headers, case["id"], set_id) == 409

    # 예약이 아닌(바로 보낸) 묶음도 취소할 수 없다.
    _send(client, counselor_headers, case["id"], IDS)
    assert _cancel(client, counselor_headers, case["id"], _pending(client, device)["id"]) == 409


def test_cancel_is_for_assigned_counselor_and_own_case(
    client: TestClient,
    counselor_headers: Headers,
    other_counselor_headers: Headers,
    admin_headers: Headers,
    case: dict,
    clock: Clock,
    db,
) -> None:
    _linked(client, counselor_headers, case["id"])
    clock.at(14)
    _send(client, counselor_headers, case["id"], IDS, deliver="EVENING")
    set_id = _view(client, counselor_headers, case["id"])["scheduled_questions"]["id"]

    assert _cancel(client, other_counselor_headers, case["id"], set_id) == 403
    assert _cancel(client, admin_headers, case["id"], set_id) == 403
    # 담당이 아닌 관리자는 예약 내용을 받지 않는다(답 전 질문이 있다는 것만).
    admin_view = _view(client, admin_headers, case["id"])
    assert admin_view["scheduled_questions"] is None and admin_view["has_pending_questions"] is True

    # 다른 사례의 주소로는 찾지 못한다.
    other = create_case(client, counselor_headers)
    assert _cancel(client, counselor_headers, other["id"], set_id) == 404
    assert _cancel(client, counselor_headers, case["id"], str(uuid.uuid4())) == 404
    assert _status(db, set_id) == ChildQuestionSetStatus.PENDING


def test_new_send_cancels_earlier_reservation(
    client: TestClient, counselor_headers: Headers, case: dict, clock: Clock, db
) -> None:
    device = _linked(client, counselor_headers, case["id"])
    clock.at(10)
    _send(client, counselor_headers, case["id"], IDS, deliver="EVENING")
    first = _view(client, counselor_headers, case["id"])["scheduled_questions"]["id"]

    # 다시 예약하면 앞 예약은 보이기 전에 거둔 것(CANCELED)이다.
    _send(client, counselor_headers, case["id"], ["meal", "week"], deliver="EVENING")
    second = _view(client, counselor_headers, case["id"])["scheduled_questions"]
    assert second["id"] != first and second["count"] == 2
    assert _status(db, first) == ChildQuestionSetStatus.CANCELED

    # 바로 보내도 예약은 거둔다.
    _send(client, counselor_headers, case["id"], ["school"])
    assert _status(db, second["id"]) == ChildQuestionSetStatus.CANCELED
    assert [item["id"] for item in _pending(client, device)["questions"]] == ["school"]
    assert _view(client, counselor_headers, case["id"])["scheduled_questions"] is None
    clock.at(18, 1)
    assert [item["id"] for item in _pending(client, device)["questions"]] == ["school"]


def test_shown_set_stays_until_reservation_takes_over(
    client: TestClient, counselor_headers: Headers, case: dict, clock: Clock, db
) -> None:
    device = _linked(client, counselor_headers, case["id"])
    clock.at(10)
    _send(client, counselor_headers, case["id"], IDS)
    shown = _pending(client, device)["id"]
    _send(client, counselor_headers, case["id"], ["meal", "week"], deliver="EVENING")
    reserved = _view(client, counselor_headers, case["id"])["scheduled_questions"]["id"]

    # 예약 시각 전에는 앞 질문이 그대로 보인다.
    clock.at(17)
    assert _pending(client, device)["id"] == shown
    assert _status(db, shown) == ChildQuestionSetStatus.PENDING

    # 예약 시각이 되면 새 질문이 대신하고, 앞 질문의 답은 끝난 질문(409)이다.
    clock.at(18)
    assert _pending(client, device)["id"] == reserved
    assert _answer(client, device, shown, IDS) == 409
    assert _answer(client, device, reserved, ["meal", "week"]) == 200
    assert _status(db, shown) == ChildQuestionSetStatus.REPLACED


def test_shown_set_can_still_be_answered_before_reservation(
    client: TestClient, counselor_headers: Headers, case: dict, clock: Clock, db
) -> None:
    device = _linked(client, counselor_headers, case["id"])
    clock.at(10)
    _send(client, counselor_headers, case["id"], IDS)
    shown = _pending(client, device)["id"]
    _send(client, counselor_headers, case["id"], ["meal"], deliver="EVENING")
    reserved = _view(client, counselor_headers, case["id"])["scheduled_questions"]["id"]

    assert _answer(client, device, shown, IDS) == 200
    assert _pending(client, device) is None
    assert _status(db, reserved) == ChildQuestionSetStatus.PENDING
    clock.at(18)
    assert _pending(client, device)["id"] == reserved


def test_unlink_cancels_reservation(client: TestClient, counselor_headers: Headers, case: dict, clock: Clock, db) -> None:
    device = _linked(client, counselor_headers, case["id"])
    clock.at(10)
    _send(client, counselor_headers, case["id"], IDS)
    shown = _pending(client, device)["id"]
    _send(client, counselor_headers, case["id"], ["meal"], deliver="EVENING")
    reserved = _view(client, counselor_headers, case["id"])["scheduled_questions"]["id"]

    assert client.post("/api/v1/child-app/unlink", headers=device).status_code == 204
    assert _status(db, shown) == ChildQuestionSetStatus.REPLACED
    assert _status(db, reserved) == ChildQuestionSetStatus.CANCELED
    view = _view(client, counselor_headers, case["id"])
    assert view["scheduled_questions"] is None and view["has_pending_questions"] is False


def test_stats_skip_canceled_and_unshown_reservations(
    client: TestClient, counselor_headers: Headers, admin_headers: Headers, case: dict, clock: Clock
) -> None:
    _linked(client, counselor_headers, case["id"])
    url = f"/api/v1/child-app-stats?date_from={clock.day - timedelta(days=3)}&date_to={clock.day + timedelta(days=1)}"

    def sent() -> int:
        return client.get(url, headers=admin_headers).json()["data"]["sent"]

    clock.at(10)
    _send(client, counselor_headers, case["id"], IDS, deliver="EVENING")
    first = _view(client, counselor_headers, case["id"])["scheduled_questions"]["id"]
    assert sent() == 0
    assert _cancel(client, counselor_headers, case["id"], first) == 204
    _send(client, counselor_headers, case["id"], IDS, deliver="EVENING")
    assert sent() == 0

    # 아이에게 보이기 시작하면 보낸 것으로 센다. 취소한 예약은 끝까지 세지 않는다.
    clock.at(18)
    assert sent() == 1
    # 보인 날짜로 센다: 예약 시각 전날까지만 보면 0.
    before = f"/api/v1/child-app-stats?date_from={clock.day - timedelta(days=3)}&date_to={clock.day - timedelta(days=1)}"
    assert client.get(before, headers=admin_headers).json()["data"]["sent"] == 0


def test_switch_off_blocks_cancel(
    client: TestClient, counselor_headers: Headers, case: dict, clock: Clock, monkeypatch: pytest.MonkeyPatch
) -> None:
    _linked(client, counselor_headers, case["id"])
    clock.at(10)
    _send(client, counselor_headers, case["id"], IDS, deliver="EVENING")
    set_id = _view(client, counselor_headers, case["id"])["scheduled_questions"]["id"]

    monkeypatch.setattr(settings, "CHILD_APP_ENABLED", False)
    response = client.delete(f"/api/v1/cases/{case['id']}/child-app/question-sets/{set_id}", headers=counselor_headers)
    assert response.status_code == 503 and response.json()["error"]["code"] == "CHILD_APP_DISABLED"


# =========================================================
# AI 추가 질문은 예약과 따로, 승인하는 즉시 간다
# =========================================================

def _fake_drafts(items, written=None, known_identifiers=(), deadline=None):
    return [
        {"question_id": item["question_id"], "note": "가상 메모", "questions": [{"text": "언제 그랬나요?", "options": ["오늘", "어제"]}]}
        for item in items
    ]


@pytest.fixture
def ai_generator():
    child_app_ai_service.set_generator_override(_fake_drafts)
    child_app_ai_service.reset_limits()
    yield child_app_ai_service
    child_app_ai_service.set_generator_override(None)


def test_ai_question_goes_now_and_leaves_reservation(
    client: TestClient, counselor_headers: Headers, case: dict, clock: Clock, db, ai_generator
) -> None:
    device = _linked(client, counselor_headers, case["id"])
    clock.at(9)
    _send(client, counselor_headers, case["id"], IDS)
    answers = [{"question_id": "sleep", "choice_index": 0}, {"question_id": "home", "choice_index": 0}, {"question_id": "safe", "choice_index": 2}]
    first = _pending(client, device)["id"]
    assert client.post(f"/api/v1/child-app/question-sets/{first}/answers", json={"answers": answers}, headers=device).status_code == 200
    draft = client.post(f"/api/v1/cases/{case['id']}/child-app/ai-draft", headers=counselor_headers).json()["data"]
    question = draft["items"][0]["questions"][0]
    approval = f"/api/v1/cases/{case['id']}/child-app/ai-draft/{draft['id']}/questions/{question['id']}/approval"

    clock.at(10)
    _send(client, counselor_headers, case["id"], ["meal", "week"], deliver="EVENING")
    reserved = _view(client, counselor_headers, case["id"])["scheduled_questions"]

    # 승인한 추가 질문은 바로 보이고, 예약해 둔 묶음은 그대로다(추가 질문이 예약 묶음에 붙지 않는다).
    approved = client.put(approval, json={"approved": True}, headers=counselor_headers)
    assert approved.status_code == 200 and approved.json()["data"]["items"][0]["questions"][0]["approved"] is True
    shown = _pending(client, device)
    assert [item["id"] for item in shown["questions"]] == [question["id"]]
    assert shown["id"] != reserved["id"]
    assert _view(client, counselor_headers, case["id"])["scheduled_questions"] == reserved
    assert len(db.scalar(select(ChildQuestionSet).where(ChildQuestionSet.id == uuid.UUID(reserved["id"]))).questions) == 2

    # 예약 시각이 되면 예약 묶음이 대신한다. 답하지 못한 추가 질문은 앱에 없으니 승인 전으로 보인다.
    clock.at(18)
    assert _pending(client, device)["id"] == reserved["id"]
    view = _view(client, counselor_headers, case["id"])
    assert view["ai_draft"]["items"][0]["questions"][0]["approved"] is False

    # 그 뒤에 다시 승인하면 지금 보이는 묶음에 붙는다.
    again = client.put(approval, json={"approved": True}, headers=counselor_headers)
    assert again.status_code == 200 and again.json()["data"]["items"][0]["questions"][0]["approved"] is True
    assert [item["id"] for item in _pending(client, device)["questions"]] == ["meal", "week", question["id"]]
    assert _status(db, shown["id"]) == ChildQuestionSetStatus.REPLACED
