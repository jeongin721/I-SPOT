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
         "options": ["잘 자요", "가끔 깨요", "자주 깨요"], "reason": "확인할 사항의 수면 상태와 이어짐"},
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
    # 승인 전 회차라 상담사가 아직 보지 않은 AI 추가 질문 초안은 넣지 않는다(민규 #195 리뷰).
    assert context["counselor_questions"] == []
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
    # 살펴볼 답 기준(amber_any)은 아이 앱으로 가지 않는다.
    assert "amber_any" not in str(pending)
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
    # 고정 문항은 기준대로(잘 잤어요 → 보통), 맞춤 질문은 답하면 무엇이든 살펴볼 답(경진 11/24 · 민규 #195 리뷰).
    assert [item["level"] for item in answer_items] == ["NONE", "AMBER", "AMBER"]
    # 상담사 화면의 짧은 이름 칸은 문장 앞부분만.
    assert len(answer_items[1]["question"]) <= 19 and answer_items[2]["question"].startswith("요즘 기억에")


def test_session_question_skip_stays_skip(client: TestClient, counselor_headers, case, db) -> None:
    device = _linked(client, counselor_headers, case["id"])
    _analyzed(client, counselor_headers, db, case["id"])
    choice, free = _create(client, counselor_headers, case["id"]).json()["data"]["items"]
    client.post(
        f"/api/v1/cases/{case['id']}/child-app/question-sets",
        json={"question_ids": [choice["id"], free["id"]]},
        headers=counselor_headers,
    )
    pending = _home(client, device)["pending"]
    answered = client.post(
        f"/api/v1/child-app/question-sets/{pending['id']}/answers",
        json={"answers": [{"question_id": choice["id"], "skipped": True}, {"question_id": free["id"], "chip": "답하기 어려워요"}]},
        headers=device,
    )
    assert answered.status_code == 200, answered.text
    feed = _view(client, counselor_headers, case["id"])["feed"]
    levels = [item["level"] for item in next(row for row in feed if row["kind"] == "ANSWERS")["payload"]["items"]]
    assert levels == ["SKIP", "SKIP"]


def test_approved_session_uses_ai_question_drafts(client: TestClient, counselor_headers, case, db) -> None:
    _analyzed(client, counselor_headers, db, case["id"], SessionStatus.APPROVED)
    _create(client, counselor_headers, case["id"])
    assert calls[0]["context"]["counselor_questions"] == ["요즘 잠은 몇 시쯤 자나요?"]


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

    raw = {
        "questions": [
            {"category": "집", "type": "choice", "text": "아빠가 소리 지를 때 무서웠나요?", "options": ["네", "아니요"], "reason": "가족"},
            {"category": "생활", "type": "choice", "text": "최근 일주일 동안 잠은 잘 잤나요?", "options": ["네", "아니요"], "reason": "겹침"},
            {"category": "마음", "type": "choice", "text": "요즘 집에 있을 때 마음이 편한가요?", "options": ["편해요", "조금 불편해요", "말하기 어려워요"],
             "reason": "확인할 사항 1"},
            {"category": "생활", "type": "choice", "text": "요즘 아침은 먹고 가나요?", "options": ["먹어요", "못 먹어요", "하늘이랑 먹어요"],
             "reason": "보기에 등록 이름 → 그 보기만 뺌"},
            {"category": "집", "type": "choice", "text": "형에게 맞은 적이 있나요?", "options": ["네", "아니요"], "reason": "형 · 사건"},
            {"category": "집", "type": "choice", "text": "요즘 가족이 화를 낼 때 무서운가요?", "options": ["네", "아니요"], "reason": "가족"},
            {"category": "집", "type": "choice", "text": "술 마신 날에는 집이 어떤가요?", "options": ["조용해요", "시끄러워요"], "reason": "사건"},
            {"category": "학교", "type": "choice", "text": "학원 선생님이 무섭게 한 적이 있나요?", "options": ["네", "아니요"], "reason": "선생님"},
            {"category": "마음", "type": "choice", "text": "하늘이는 요즘 기분이 어때요?", "options": ["좋아요", "나빠요"], "reason": "등록 이름"},
            {"category": "마음", "type": "choice", "text": "살기 싫다는 생각이 든 적이 있나요?", "options": ["네", "아니요"], "reason": "자해"},
            {"category": "마음", "type": "choice", "text": "좋아하는 인형이 있나요?", "options": ["있어요", "없어요"], "reason": "인형은 남김"},
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

    cleaned = clean_output(raw, sent=["최근 일주일 동안 잠은 잘 잤나요?"], names=["김하늘", "하늘", "김"])

    assert [item["text"] for item in cleaned] == [
        "요즘 집에 있을 때 마음이 편한가요?",
        "요즘 아침은 먹고 가나요?",
        "좋아하는 인형이 있나요?",
        "학교에서 있었던 일을 알려 줄래요?",
    ]
    # 건너뛰기 같은 보기 · 등록 이름이 든 보기는 뺀다(앱에 건너뛰기가 따로 있다). AI 가 정하는 살펴볼 답은 없다.
    assert cleaned[0]["options"] == ["편해요", "조금 불편해요"]
    assert cleaned[1]["options"] == ["먹어요", "못 먹어요"]
    assert all("concern" not in item for item in cleaned)
    assert cleaned[3]["options"] == []
    assert clean_output({"questions": "x"}) == [] and clean_output(None) == []

    text = format_input({"child": {"age_band": "만 10~13세"}, "session_label": "3회차", "checks": [CHECK], "sent": []})
    assert "3회차" in text and CHECK in text and "- 없음" in text


def _patch(client: TestClient, headers: Headers, case_id: str, question_id: str, body: dict):
    return client.patch(f"/api/v1/cases/{case_id}/child-app/session-questions/{question_id}", json=body, headers=headers)


def test_counselor_edits_question_and_sends_edited_text(client: TestClient, counselor_headers, case, db) -> None:
    device = _linked(client, counselor_headers, case["id"])
    _analyzed(client, counselor_headers, db, case["id"])
    choice, free = _create(client, counselor_headers, case["id"]).json()["data"]["items"]

    response = _patch(
        client, counselor_headers, case["id"], choice["id"],
        {"text": " 요즘 밤에 잠은 어때요? ", "options": ["잘 자요", "자주 깨요", "잘 자요", "무서워서 깨요"]},
    )
    assert response.status_code == 200, response.text
    edited = response.json()["data"]["items"][0]
    assert edited["text"] == "요즘 밤에 잠은 어때요?" and edited["edited"] is True
    # 겹친 보기는 하나로.
    assert edited["options"] == ["잘 자요", "자주 깨요", "무서워서 깨요"]
    assert _view(client, counselor_headers, case["id"])["session_questions"]["items"][0]["edited"] is True

    assert _patch(client, counselor_headers, case["id"], free["id"], {"text": "이번 주 이야기를 들려줄래요?"}).status_code == 200

    client.post(
        f"/api/v1/cases/{case['id']}/child-app/question-sets",
        json={"question_ids": [choice["id"], free["id"]]},
        headers=counselor_headers,
    )
    pending = _home(client, device)["pending"]
    assert [question["text"] for question in pending["questions"]] == ["요즘 밤에 잠은 어때요?", "이번 주 이야기를 들려줄래요?"]
    answered = client.post(
        f"/api/v1/child-app/question-sets/{pending['id']}/answers",
        json={"answers": [{"question_id": choice["id"], "choice_index": 2}, {"question_id": free["id"], "skipped": True}]},
        headers=device,
    )
    assert answered.status_code == 200, answered.text
    feed = _view(client, counselor_headers, case["id"])["feed"]
    assert next(row for row in feed if row["kind"] == "ANSWERS")["payload"]["items"][0]["level"] == "AMBER"

    log = db.scalar(select(AuditLog).where(AuditLog.action == AuditAction.CHILD_APP_SESSION_QUESTIONS_EDITED))
    assert log.detail == {"what": "question"} and "밤에" not in str(log.detail)


def test_edit_rules(client: TestClient, counselor_headers, other_counselor_headers, case, db) -> None:
    _analyzed(client, counselor_headers, db, case["id"])
    choice, free = _create(client, counselor_headers, case["id"]).json()["data"]["items"]
    url_case = case["id"]

    bad = [
        (free["id"], {"text": "이번 주는?", "options": ["좋아요", "싫어요"]}),  # 짧은 글에 보기
        (choice["id"], {"text": "잠은?", "options": ["잘 자요"]}),  # 보기 하나
        (choice["id"], {"text": "잠은?", "options": ["1", "2", "3", "4", "5", "6"]}),  # 보기 여섯
    ]
    for question_id, body in bad:
        assert _patch(client, counselor_headers, url_case, question_id, body).status_code == 400, body

    assert _patch(client, counselor_headers, url_case, choice["id"], {"text": ""}).status_code == 422
    assert _patch(client, counselor_headers, url_case, "sq_0000000000000000", {"text": "잠은?"}).status_code == 404
    assert _patch(client, other_counselor_headers, url_case, choice["id"], {"text": "잠은?", "options": ["a", "b"]}).status_code in (403, 404)
    assert _view(client, counselor_headers, url_case)["session_questions"]["items"][0]["text"] == choice["text"]


def test_edit_rejects_blank_text(client: TestClient, counselor_headers, case, db) -> None:
    """공백만 보내면 빈 질문이 아이 앱으로 나간다(민규 #195 머지 뒤 리뷰 1)."""

    _analyzed(client, counselor_headers, db, case["id"])
    free = _create(client, counselor_headers, case["id"]).json()["data"]["items"][1]

    assert _patch(client, counselor_headers, case["id"], free["id"], {"text": "   "}).status_code == 400
    assert _view(client, counselor_headers, case["id"])["session_questions"]["items"][1]["text"] == free["text"]


def test_llm_filter_edges_from_review() -> None:
    """민규 #195 머지 뒤 리뷰 3: 붙여 쓴 호칭 · 다른 어른 · 사건 낱말은 버리고, 평범한 말은 남긴다."""

    from app.adapters.module_loader import load_callable

    clean_output = load_callable("ai.modeling.abuse.child_session_question_llm", "clean_output")

    def kept(text: str) -> bool:
        raw = {"questions": [{"category": "마음", "type": "choice", "text": text, "options": ["네", "아니요"], "reason": "가상"}]}
        return bool(clean_output(raw))

    for text in ("우리형이 무섭나요?", "의붓형이랑 지내는 건 어때요?", "담임 쌤이 뭐라고 했나요?", "원장님이 화를 냈나요?",
                 "이웃 사람이 무섭나요?", "꼬집은 적이 있나요?", "발로 찬 적이 있나요?"):
        assert not kept(text), text

    for text in ("미술 시간은 재미있나요?", "맞은편 자리 친구와 친한가요?", "요즘 몸이 아프게 느껴질 때가 있나요?"):
        assert kept(text), text


def test_edit_refuses_self_harm_words(client: TestClient, counselor_headers, case, db) -> None:
    """상담사가 고칠 때도 자해 · 죽음 말은 받지 않는다(경진 11/24). 문장 · 보기 둘 다."""

    _analyzed(client, counselor_headers, db, case["id"])
    choice, free = _create(client, counselor_headers, case["id"]).json()["data"]["items"]

    for question_id, body in (
        (free["id"], {"text": "요즘 죽고 싶다는 생각이 든 적이 있나요?"}),
        (choice["id"], {"text": "요즘 기분은 어때요?", "options": ["괜찮아요", "살기 싫어요"]}),
        (choice["id"], {"text": "스스로 상처를 낸 적이 있나요?", "options": ["네", "아니요"]}),
        (choice["id"], {"text": "내 몸을 일부러 아프게 한 적이 있나요?", "options": ["네", "아니요"]}),  # 민규 리뷰
    ):
        response = _patch(client, counselor_headers, case["id"], question_id, body)
        assert response.status_code == 400 and "상담에서 직접" in response.text, body

    items = _view(client, counselor_headers, case["id"])["session_questions"]["items"]
    assert [item["text"] for item in items] == [choice["text"], free["text"]]
    # 평범한 말은 그대로 된다.
    assert _patch(client, counselor_headers, case["id"], free["id"], {"text": "요즘 몸이 아프게 느껴질 때가 있나요?"}).status_code == 200


def test_edit_self_harm_check_lets_ordinary_sentences_through(client: TestClient, counselor_headers, case, db) -> None:
    """고치기 거절은 뜻이 분명한 말만 본다(민규 #198 리뷰 — AI 초안용 넓은 목록이 평범한 문장까지 막았다)."""

    _analyzed(client, counselor_headers, db, case["id"])
    free = _create(client, counselor_headers, case["id"]).json()["data"]["items"][1]

    for text in ("요즘 입맛이 없어졌나요?", "걱정이 좀 사라졌나요?", "아침에 죽을 먹었나요?", "친구들 앞에서 기죽은 적이 있나요?",
                 "숙제를 빨리 끝내고 싶을 때가 있나요?", "힘이 없어지는 때가 있나요?", "그림에 선을 긋는 걸 좋아하나요?"):
        assert _patch(client, counselor_headers, case["id"], free["id"], {"text": text}).status_code == 200, text

    for text in ("내가 죽었으면 좋겠다고 생각한 적이 있나요?", "그만 살고 싶다고 느낀 적이 있나요?", "손목을 긋고 싶은 적이 있나요?"):
        assert _patch(client, counselor_headers, case["id"], free["id"], {"text": text}).status_code == 400, text
