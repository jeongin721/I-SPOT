# 종결 검토 요약 · 보고서(GET/POST/PUT /cases/{id}/closure-summary, 2026-10-30, API_CONTRACT 4절). 데이터는 모두 가상이다.
# CI 의 AI_PROVIDER 는 mock 이라 LLM 없이 승인 요약을 묶는 경로(APPROVED_SUMMARIES)를 본다. modeling 경로는 가짜 모듈로.

import re
import sys
import threading
import types
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import settings
from app.core.enums import AuditAction
from app.models.audit_log import AuditLog
from app.services import closure_review_service
from tests.conftest import create_case, create_session
from tests.test_case_context import _approve_with_assessment


def _url(case_id: str) -> str:
    return f"/api/v1/cases/{case_id}/closure-summary"


def _keys(summary: dict) -> list:
    return [item["key"] for group in summary["groups"] for item in group["items"]]


def _drop_keys(items: list) -> list:
    return [{k: v for k, v in item.items() if k != "key"} for item in items]


@pytest.fixture
def ready_case(client: TestClient, counselor_headers) -> dict:
    case = create_case(client, counselor_headers)
    session = create_session(client, counselor_headers, case["id"])
    _approve_with_assessment(client, counselor_headers, session["id"])
    assert client.post(f"/api/v1/cases/{case['id']}/closure-review", headers=counselor_headers).status_code == 200
    return case


def test_get_before_generate_is_empty(client: TestClient, counselor_headers, ready_case: dict) -> None:
    data = client.get(_url(ready_case["id"]), headers=counselor_headers).json()["data"]

    assert data["summary"] is None and data["checks"] == {} and data["edits"] == {}
    assert data["report"] == {"initial_situation": None, "closing_situation": None, "opinion": None, "review_date": None, "closing_date": None}


def test_generate_without_llm_groups_approved_summaries(client: TestClient, counselor_headers, ready_case: dict, db) -> None:
    response = client.post(_url(ready_case["id"]), headers=counselor_headers)

    assert response.status_code == 200, response.text
    summary = response.json()["data"]["summary"]
    assert summary["source"] == "APPROVED_SUMMARIES" and summary["model"] is None and summary["sessions"] == [1]
    by_title = {group["title"]: group["items"] for group in summary["groups"]}
    assert _drop_keys(by_title["위험요인"]) == [{"text": "부의 음주 뒤 체벌", "sessions": [1]}]
    assert all(re.fullmatch(r"[0-9a-f]{6}-\d+-\d+", key) for key in _keys(summary))
    assert by_title["강점과 자원"][0]["text"] == "조모에게 연락하는 방법을 앎"
    assert summary["report"]["initial_situation"] == {"text": "부의 음주 뒤 체벌", "sessions": [1]}
    log = db.scalar(select(AuditLog).where(AuditLog.action == AuditAction.CLOSURE_SUMMARY_GENERATED))
    assert log.detail["source"] == "APPROVED_SUMMARIES" and "체벌" not in str(log.detail)


def test_generate_requires_registration_and_approved_summary(client: TestClient, counselor_headers) -> None:
    case = create_case(client, counselor_headers)

    not_registered = client.post(_url(case["id"]), headers=counselor_headers)
    client.post(f"/api/v1/cases/{case['id']}/closure-review", headers=counselor_headers)
    no_summary = client.post(_url(case["id"]), headers=counselor_headers)

    assert not_registered.status_code == 409 and not_registered.json()["error"]["code"] == "INVALID_CASE_STATE"
    assert no_summary.status_code == 409


def test_save_checks_edits_report_and_regenerate_clears_checks(client: TestClient, counselor_headers, ready_case: dict) -> None:
    first, second = _keys(client.post(_url(ready_case["id"]), headers=counselor_headers).json()["data"]["summary"])[:2]

    saved = client.put(
        _url(ready_case["id"]),
        json={
            "checks": {first: True},
            "edits": {first: "  부의 음주 뒤 체벌(상담사 고침)  ", second: ""},
            "report": {"opinion": "종결 가능", "review_date": "2026-10-30"},
        },
        headers=counselor_headers,
    )
    later = client.put(_url(ready_case["id"]), json={"report": {"closing_situation": "새 진술 없음"}}, headers=counselor_headers)
    again = client.post(_url(ready_case["id"]), headers=counselor_headers).json()["data"]

    assert saved.status_code == 200, saved.text
    assert saved.json()["data"]["checks"] == {first: True}
    assert saved.json()["data"]["edits"] == {first: "부의 음주 뒤 체벌(상담사 고침)"}
    assert later.json()["data"]["report"]["opinion"] == "종결 가능"  # 보낸 칸만 바뀐다
    assert later.json()["data"]["report"]["closing_situation"] == "새 진술 없음"
    # 다시 만들면 체크 · 고침은 비우고 보고서 칸은 남긴다.
    assert again["checks"] == {} and again["edits"] == {} and again["report"]["opinion"] == "종결 가능"


def test_stale_tab_cannot_save_onto_regenerated_summary(client: TestClient, counselor_headers, ready_case: dict) -> None:
    """민규 #128 리뷰: 다시 만든 뒤 예전 탭이 옛 key 로 저장하면 새 문장에 붙지 않고 422 여야 한다."""

    old_key = _keys(client.post(_url(ready_case["id"]), headers=counselor_headers).json()["data"]["summary"])[0]
    new_keys = _keys(client.post(_url(ready_case["id"]), headers=counselor_headers).json()["data"]["summary"])

    stale = client.put(_url(ready_case["id"]), json={"checks": {old_key: True}, "edits": {old_key: "문장 A 고침"}}, headers=counselor_headers)
    data = client.get(_url(ready_case["id"]), headers=counselor_headers).json()["data"]

    assert old_key not in new_keys
    assert stale.status_code == 422 and "새로고침" in stale.json()["error"]["message"]
    assert data["checks"] == {} and data["edits"] == {}


def test_save_requires_registration(client: TestClient, counselor_headers, ready_case: dict) -> None:
    """등록하지 않았거나 취소한 사례에는 PUT 도 409(POST 와 같게)."""

    fresh = create_case(client, counselor_headers)
    client.delete(f"/api/v1/cases/{ready_case['id']}/closure-review", headers=counselor_headers)

    for case_id in (fresh["id"], ready_case["id"]):
        response = client.put(_url(case_id), json={"report": {"opinion": "종결 가능"}}, headers=counselor_headers)
        assert response.status_code == 409 and response.json()["error"]["code"] == "INVALID_CASE_STATE"


def test_unknown_item_keys_are_rejected(client: TestClient, counselor_headers, ready_case: dict) -> None:
    client.post(_url(ready_case["id"]), headers=counselor_headers)

    assert client.put(_url(ready_case["id"]), json={"checks": {"000000-9-9": True}}, headers=counselor_headers).status_code == 422


def test_other_counselor_is_forbidden(client: TestClient, counselor_headers, other_counselor_headers, ready_case: dict) -> None:
    assert client.get(_url(ready_case["id"]), headers=other_counselor_headers).status_code == 403
    assert client.post(_url(ready_case["id"]), headers=other_counselor_headers).status_code == 403


@pytest.fixture
def modeling(monkeypatch):
    calls = {}
    module = types.ModuleType("ai.modeling.abuse.closure_summary_llm")

    def generate_closure_summary(sessions, known_identifiers=None, deadline=None):
        calls["sessions"], calls["known"] = sessions, known_identifiers
        behaviour = calls.get("raise")
        if behaviour:
            raise behaviour
        return {"groups": [{"title": "학대 관련 진술", "items": [{"text": "새 진술 없음", "sessions": [1]}]}], "report": {}, "model": "m"}

    module.generate_closure_summary = generate_closure_summary
    monkeypatch.setitem(sys.modules, "ai.modeling.abuse.closure_summary_llm", module)
    monkeypatch.setattr(settings, "AI_PROVIDER", "modeling")
    closure_review_service.reset_limits()
    yield calls
    closure_review_service.reset_limits()


def test_modeling_provider_uses_ai_module(client: TestClient, counselor_headers, ready_case: dict, modeling) -> None:
    summary = client.post(_url(ready_case["id"]), headers=counselor_headers).json()["data"]["summary"]

    assert summary["source"] == "AI" and summary["model"] == "m"
    assert _drop_keys(summary["groups"][0]["items"]) == [{"text": "새 진술 없음", "sessions": [1]}]
    # 별칭은 가려 달라고 넘기고, 회차 입력에는 승인 요약 4칸 · 신호만 간다.
    assert modeling["known"] == [ready_case["child_alias"]]
    assert set(modeling["sessions"][0]) == {"number", "date", "assessment", "signals"}


@pytest.mark.parametrize(
    ("error", "status", "code"),
    [(TimeoutError(), 504, "AI_TIMEOUT"), (type("ClosureSummaryOutputError", (Exception,), {})("원문"), 502, "AI_INVALID_OUTPUT"), (RuntimeError("원문"), 502, "AI_FAILED")],
)
def test_modeling_errors_map_to_codes_without_text(
    client: TestClient, counselor_headers, ready_case: dict, modeling, error, status, code
) -> None:
    modeling["raise"] = error

    response = client.post(_url(ready_case["id"]), headers=counselor_headers)

    assert response.status_code == status and response.json()["error"]["code"] == code
    assert "원문" not in response.text


def test_modeling_same_case_runs_one_at_a_time(client: TestClient, counselor_headers, ready_case: dict, modeling) -> None:
    """만드는 중인 사례에 다시 누르면 429(504 뒤 다시 눌러도 뒤에서 호출이 쌓이지 않게). 끝나면 다시 된다."""

    case_id = uuid.UUID(ready_case["id"])
    closure_review_service._limits.running.add(case_id)

    busy = client.post(_url(ready_case["id"]), headers=counselor_headers)
    closure_review_service._limits.running.discard(case_id)
    after = client.post(_url(ready_case["id"]), headers=counselor_headers)

    assert busy.status_code == 429 and busy.json()["error"]["code"] == "RATE_LIMITED"
    assert after.status_code == 200


def test_modeling_server_slots_are_returned_after_timeout(
    client: TestClient, counselor_headers, ready_case: dict, modeling, monkeypatch
) -> None:
    """제한 시간이 지나도 실제 호출이 끝날 때까지 자리를 잡고 있다가, 끝나면 돌려준다."""

    monkeypatch.setattr(settings, "CLOSURE_SUMMARY_MAX_CONCURRENCY", 1)
    monkeypatch.setattr(settings, "CLOSURE_SUMMARY_TIMEOUT_SECONDS", 0.05)
    closure_review_service.reset_limits()
    gate, done = threading.Event(), threading.Event()
    module = sys.modules["ai.modeling.abuse.closure_summary_llm"]
    original = module.generate_closure_summary

    def slow(sessions, known_identifiers=None, deadline=None):
        try:
            gate.wait(5)
            return original(sessions, known_identifiers=known_identifiers, deadline=deadline)
        finally:
            done.set()

    module.generate_closure_summary = slow

    timed_out = client.post(_url(ready_case["id"]), headers=counselor_headers)
    while_running = client.post(_url(ready_case["id"]), headers=counselor_headers)
    gate.set()
    assert done.wait(5)
    for _ in range(50):
        if not closure_review_service._limits.running:
            break
        threading.Event().wait(0.02)
    module.generate_closure_summary = original
    monkeypatch.setattr(settings, "CLOSURE_SUMMARY_TIMEOUT_SECONDS", 5)
    after = client.post(_url(ready_case["id"]), headers=counselor_headers)

    assert timed_out.status_code == 504
    assert while_running.status_code == 429
    assert after.status_code == 200, after.text
