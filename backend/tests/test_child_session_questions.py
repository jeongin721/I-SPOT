# 아이 앱 '이번 회차 맞춤 질문'(child_session_question_service, 2026-11-24). 데이터는 모두 가상이다.

import uuid
from typing import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import settings
from app.core.enums import AnalysisStatus, AuditAction, CaseStatus, SessionStatus
from app.models.analysis import AIAnalysis
from app.models.audit_log import AuditLog
from app.models.case import Case
from app.models.session import ConsultationSession
from app.services import child_app_ai_service, child_session_question_service
from tests.conftest import create_session
from tests.test_child_app import Headers, _home, _limits, _linked, _view  # noqa: F401  (_limits 는 autouse 픽스처)

URL = "/api/v1/cases/{}/child-app/session-questions"
CHECK = "밤에 큰 소리가 나면 잠을 못 잔다고 함 — 수면 상태 확인"
calls: list = []


def _fake(context, known_identifiers=(), deadline=None):
    calls.append({"context": context, "names": list(known_identifiers)})
    label = context["session_label"]

    return [
        {"category": "생활", "type": "choice", "text": f"{label} 뒤로 밤에 잠은 잘 자나요?",
         "options": ["잘 자요", "가끔 깨요", "자주 깨요", "말하기 어려워요"], "concern": ["자주 깨요"],
         "reason": "확인할 사항의 수면 상태와 이어짐"},
        {"category": "마음", "type": "text", "text": "요즘 기억에 남는 일을 짧게 알려 줄래요?", "options": [], "reason": "지낸 이야기"},
    ]


@pytest.fixture(autouse=True)
def generator() -> Iterator[None]:
    calls.clear()
    child_session_question_service.set_generator_override(_fake)
    child_app_ai_service.reset_limits()
    yield
    child_session_question_service.set_generator_override(None)


def _analyzed(client: TestClient, headers: Headers, db, case_id: str, status=SessionStatus.AI_REVIEW_REQUIRED) -> str:
    session_id = create_session(client, headers, case_id)["id"]
    row = db.get(ConsultationSession, uuid.UUID(session_id))
    row.status = status
    db.add(
        AIAnalysis(
            session_id=row.id,
            status=AnalysisStatus.COMPLETED,
            result={"followup_check_points": [{"text": CHECK}], "followup_questions": [{"text": "요즘 잠은 몇 시쯤 자나요?"}]},
        )
    )
    db.commit()

    return session_id


def _create(client: TestClient, headers: Headers, case_id: str, regenerate: bool = False):
    return client.post(URL.format(case_id) + ("?regenerate=true" if regenerate else ""), headers=headers)


def test_view_offers_creation_only_after_analysis(client: TestClient, counselor_headers, case, db) -> None:
    view = _view(client, counselor_headers, case["id"])
    assert view["session_questions"] is None and view["session_questions_available"] is False
    assert _create(client, counselor_headers, case["id"]).status_code == 409

    _analyzed(client, counselor_headers, db, case["id"])
    assert _view(client, counselor_headers, case["id"])["session_questions_available"] is True


def test_create_uses_latest_session_and_is_cached(client: TestClient, counselor_headers, case, db) -> None:
    _analyzed(client, counselor_headers, db, case["id"], SessionStatus.APPROVED)
    latest = _analyzed(client, counselor_headers, db, case["id"])

    response = _create(client, counselor_headers, case["id"])
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["session_id"] == latest and data["session_label"] == "2회차"
    assert [item["type"] for item in data["items"]] == ["choice", "text"]
    assert all(item["id"].startswith("sq_") for item in data["items"])
    assert data["items"][0]["reason"]

    context = calls[0]["context"]
    assert context["checks"] == [CHECK]
    assert context["counselor_questions"] == ["요즘 잠은 몇 시쯤 자나요?"]
    # 고정 문항은 '이미 보낸 질문' 으로 넘어가 겹치지 않게 한다. 사례 이름은 가리기에만 쓴다.
    assert "최근 일주일 동안 잠은 잘 잤나요?" in context["sent"]
    assert "child_alias" not in str(context)

    # 다시 부르면 AI 를 부르지 않고 같은 초안을 돌려준다.
    assert _create(client, counselor_headers, case["id"]).json()["data"]["items"] == data["items"]
    assert len(calls) == 1
    assert _view(client, counselor_headers, case["id"])["session_questions"]["items"] == data["items"]

    regenerated = _create(client, counselor_headers, case["id"], regenerate=True).json()["data"]
    assert len(calls) == 2 and regenerated["items"][0]["id"] != data["items"][0]["id"]
    logs = db.scalars(select(AuditLog).where(AuditLog.action == AuditAction.CHILD_APP_SESSION_QUESTIONS_CREATED)).all()
    assert [log.detail for log in logs] == [{"questions": 2, "regenerate": False}, {"questions": 2, "regenerate": True}]


def test_new_session_gets_new_questions(client: TestClient, counselor_headers, case, db) -> None:
    _analyzed(client, counselor_headers, db, case["id"])
    first = _create(client, counselor_headers, case["id"]).json()["data"]
    _analyzed(client, counselor_headers, db, case["id"])

    assert _view(client, counselor_headers, case["id"])["session_questions"] is None
    second = _create(client, counselor_headers, case["id"]).json()["data"]
    assert second["session_label"] == "2회차" and second["items"][0]["text"] != first["items"][0]["text"]


def test_send_mixes_bank_and_session_questions(client: TestClient, counselor_headers, case, db) -> None:
    device = _linked(client, counselor_headers, case["id"])
    _analyzed(client, counselor_headers, db, case["id"])
    items = _create(client, counselor_headers, case["id"]).json()["data"]["items"]

    response = client.post(
        f"/api/v1/cases/{case['id']}/child-app/question-sets",
        json={"question_ids": ["sleep", items[0]["id"], items[1]["id"]]},
        headers=counselor_headers,
    )
    assert response.status_code == 204, response.text

    pending = _home(client, device)["pending"]
    by_id = {question["id"]: question for question in pending["questions"]}
    assert by_id[items[0]["id"]]["options"] == items[0]["options"]
    assert items[0]["concern"] == ["자주 깨요"]
    # 살펴볼 답(판정 기준)은 아이 앱으로 가지 않는다.
    assert "flag_options" not in str(pending)
    assert by_id[items[1]["id"]]["type"] == "text" and by_id[items[1]["id"]]["chips"]
    # 상담사용 이유는 아이 앱으로 가지 않는다.
    assert "reason" not in str(pending)

    answers = [
        {"question_id": "sleep", "choice_index": 0},
        {"question_id": items[0]["id"], "choice_index": 1},
        {"question_id": items[1]["id"], "text": "학교에서 발표했어요"},
    ]
    answered = client.post(f"/api/v1/child-app/question-sets/{pending['id']}/answers", json={"answers": answers}, headers=device)
    assert answered.status_code == 200, answered.text
    feed = _view(client, counselor_headers, case["id"])["feed"]
    answer_items = next(row for row in feed if row["kind"] == "ANSWERS")["payload"]["items"]
    assert [item["answer"] for item in answer_items][1:] == ["가끔 깨요", "학교에서 발표했어요"]
    assert [item["level"] for item in answer_items][1:] == ["NONE", "NONE"]


def test_concern_answer_shows_as_amber(client: TestClient, counselor_headers, case, db) -> None:
    device = _linked(client, counselor_headers, case["id"])
    _analyzed(client, counselor_headers, db, case["id"])
    item = _create(client, counselor_headers, case["id"]).json()["data"]["items"][0]
    client.post(
        f"/api/v1/cases/{case['id']}/child-app/question-sets", json={"question_ids": [item["id"]]}, headers=counselor_headers
    )
    pending = _home(client, device)["pending"]

    for index, level in ((2, "AMBER"), (3, "NONE")):  # 자주 깨요 → 살펴볼 답, 말하기 어려워요 → 아님
        if index == 3:
            client.post(
                f"/api/v1/cases/{case['id']}/child-app/question-sets", json={"question_ids": [item["id"]]}, headers=counselor_headers
            )
            pending = _home(client, device)["pending"]
        answered = client.post(
            f"/api/v1/child-app/question-sets/{pending['id']}/answers",
            json={"answers": [{"question_id": item["id"], "choice_index": index}]},
            headers=device,
        )
        assert answered.status_code == 200, answered.text
        feed = _view(client, counselor_headers, case["id"])["feed"]
        assert next(row for row in feed if row["kind"] == "ANSWERS")["payload"]["items"][0]["level"] == level


def test_send_rejects_unknown_or_old_session_question(client: TestClient, counselor_headers, case, db) -> None:
    _linked(client, counselor_headers, case["id"])
    _analyzed(client, counselor_headers, db, case["id"])
    old = _create(client, counselor_headers, case["id"]).json()["data"]["items"][0]["id"]
    _analyzed(client, counselor_headers, db, case["id"])
    _create(client, counselor_headers, case["id"])

    for bad in (old, "sq_0000000000000000"):
        response = client.post(
            f"/api/v1/cases/{case['id']}/child-app/question-sets", json={"question_ids": [bad]}, headers=counselor_headers
        )
        assert response.status_code == 400, response.text


def test_only_assigned_counselor_on_active_case(client: TestClient, counselor_headers, other_counselor_headers, admin_headers, case, db) -> None:
    _analyzed(client, counselor_headers, db, case["id"])
    assert _create(client, admin_headers, case["id"]).status_code == 403
    assert _view(client, admin_headers, case["id"])["session_questions_available"] is False

    db.get(Case, uuid.UUID(case["id"])).status = CaseStatus.CLOSED
    db.commit()
    assert _create(client, counselor_headers, case["id"]).status_code == 409
    assert calls == []


def test_ai_off_and_failure(client: TestClient, counselor_headers, case, db, monkeypatch: pytest.MonkeyPatch) -> None:
    _analyzed(client, counselor_headers, db, case["id"])
    child_session_question_service.set_generator_override(None)
    monkeypatch.setattr(settings, "CHILD_APP_AI_PROVIDER", "off")
    assert _create(client, counselor_headers, case["id"]).status_code == 503
    assert _view(client, counselor_headers, case["id"])["session_questions_available"] is False

    child_session_question_service.set_generator_override(lambda *a, **k: [])
    assert _create(client, counselor_headers, case["id"]).status_code == 502

    def broken(*args, **kwargs):
        raise RuntimeError("가상 실패")

    child_session_question_service.set_generator_override(broken)
    response = _create(client, counselor_headers, case["id"])
    assert response.status_code == 502 and "가상" not in response.text


def test_mock_provider(client: TestClient, counselor_headers, case, db, monkeypatch: pytest.MonkeyPatch) -> None:
    _analyzed(client, counselor_headers, db, case["id"])
    child_session_question_service.set_generator_override(None)
    monkeypatch.setattr(settings, "CHILD_APP_AI_PROVIDER", "mock")
    data = _create(client, counselor_headers, case["id"]).json()["data"]
    assert len(data["items"]) == 2 and "1회차" in data["items"][0]["reason"]


def test_llm_output_filter_keeps_phone_safe_questions() -> None:
    from app.adapters.module_loader import load_callable

    module = "ai.modeling.abuse.child_session_question_llm"
    clean_output = load_callable(module, "clean_output")
    format_input = load_callable(module, "format_input")
    hard_to_say = "말하기 어려워요"

    raw = {
        "questions": [
            {"category": "집", "type": "choice", "text": "아빠가 소리 지를 때 무서웠나요?", "options": ["네", "아니요"], "reason": "가족"},
            {"category": "생활", "type": "choice", "text": "최근 일주일 동안 잠은 잘 잤나요?", "options": ["네", "아니요"], "reason": "겹침"},
            {"category": "마음", "type": "choice", "text": "요즘 집에 있을 때 마음이 편한가요?", "options": ["편해요", "조금 불편해요", "말하기 어려워요"],
             "concern": ["조금 불편해요", "없는 보기"], "reason": "확인할 사항 1"},
            {"category": "생활", "type": "choice", "text": "요즘 아침은 먹고 가나요?", "options": ["먹어요", "못 먹어요"],
             "concern": ["먹어요", "못 먹어요"], "reason": "모든 보기가 살펴볼 답 → 없앰"},
            {"category": "안전", "type": "choice", "text": "[PERSON_01] 님과 지내는 게 괜찮나요?", "options": ["네", "아니요"], "reason": "토큰"},
            {"category": "마음", "type": "choice", "text": "학대를 받은 적이 있나요?", "options": ["네", "아니요"], "reason": "용어"},
            {"category": "학교", "type": "text", "text": "학교에서 있었던 일을 알려 줄래요?", "options": [], "reason": "학교"},
            {"category": "학교", "type": "text", "text": "친구 이야기를 해 줄래요?", "options": [], "reason": "글 두 번째"},
            {"category": "기타", "type": "choice", "text": "어때요?", "options": ["좋아요", "싫어요"], "reason": "분류 밖"},
            {"category": "마음", "type": "choice", "text": "오늘 기분은 어떤가요?", "options": ["좋아요"], "reason": "보기 하나"},
            {"category": "안전", "type": "choice", "text": "최근에 너무 힘들 때, 나를 다치게 하고 싶은 생각이 든 적이 있나요?",
             "options": ["없었어요", "가끔 있었어요", "지금도 있어요"], "reason": "자해 — 앱으로 묻지 않음"},
            {"category": "마음", "type": "choice", "text": "요즘 기운은 어때요?", "options": ["괜찮아요", "사라지고 싶어요"], "reason": "보기에 자해 말"},
        ]
    }

    cleaned = clean_output(raw, sent=["최근 일주일 동안 잠은 잘 잤나요?"])

    assert [item["text"] for item in cleaned] == [
        "요즘 집에 있을 때 마음이 편한가요?",
        "요즘 아침은 먹고 가나요?",
        "학교에서 있었던 일을 알려 줄래요?",
    ]
    assert [item["concern"] for item in cleaned] == [["조금 불편해요"], [], []]
    # '말하기 어려워요' 는 한 번만, 맨 끝에.
    assert cleaned[0]["options"] == ["편해요", "조금 불편해요", hard_to_say]
    assert cleaned[2]["options"] == []
    assert clean_output({"questions": "x"}) == [] and clean_output(None) == []

    text = format_input({"child": {"age_band": "만 10~13세"}, "session_label": "3회차", "checks": [CHECK], "sent": []})
    assert "3회차" in text and CHECK in text and "- 없음" in text
