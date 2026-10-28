# POST /law-guide/questions — 법령 · 매뉴얼 AI 질문(API_CONTRACT 16절, 2026-10-28).
#
# 실제 AI 모듈(openai · law · manual 패키지)은 CI 에 없다. modeling 경로는 가짜 모듈을 sys.modules 에 넣어 돌린다
# (test_modeling_ai_adapter 와 같은 방식). mock 경로는 그대로 돈다.
import json
import os
import sys
import threading
import time
import types
from typing import Any, Dict, List, Optional

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.adapters import law_qa_adapter
from app.adapters.law_qa_adapter import (
    MOCK_MODEL,
    LawQAAnswer,
    export_law_env,
    set_law_qa_adapter_override,
    start_law_qa_preload,
)
from app.adapters.module_loader import ensure_repo_root_on_path
from app.core.config import Settings, settings
from app.core.enums import AuditAction
from app.models.audit_log import AuditLog
from app.services import law_guide_service

ensure_repo_root_on_path()

URL = "/api/v1/law-guide/questions"
QUESTION = "응급조치 기간은 얼마나 돼요?"
QA_MODULE = "ai.modeling.abuse.legal_manual_qa_llm"
BACKEND_MODULE = "ai.modeling.abuse.llm_backend"

CITED = [
    {
        "law_name": "아동학대범죄의 처벌 등에 관한 특례법",
        "article": "제12조",
        "title": "피해아동 등에 대한 응급조치",
        "content": "③ 응급조치는 72시간을 넘을 수 없다.",
        "effective_date": "20261002",
        "article_number": "12",
        "article_branch": "",
        "portal_url": "https://www.law.go.kr/LSW/lsInfoP.do?lsiSeq=1&joNo=0012&joBrNo=00",
    },
    {"law_name": "아동복지법", "article": "제17조", "title": "금지행위", "content": "…"},
    {"law_name": "", "article": "제1조"},  # 법령명 없음 → 버림
    "garbage",
]


@pytest.fixture(autouse=True)
def _clean_limits():
    law_guide_service.reset_limits()
    set_law_qa_adapter_override(None)
    yield
    law_guide_service.reset_limits()
    set_law_qa_adapter_override(None)


def _ask(client: TestClient, headers, question: str = QUESTION):
    return client.post(URL, json={"question": question}, headers=headers)


def _install_fake_modules(
    monkeypatch: pytest.MonkeyPatch,
    *,
    result: Optional[Dict[str, Any]] = None,
    raises: Optional[BaseException] = None,
    sleep_seconds: float = 0.0,
) -> Dict[str, Any]:
    """가짜 legal_manual_qa_llm · llm_backend · law 패키지를 sys.modules 에 넣는다. calls 에 받은 인자가 쌓인다."""

    state: Dict[str, Any] = {"calls": [], "cache_calls": []}

    qa = types.ModuleType(QA_MODULE)

    class LawQAOutputError(ValueError):
        pass

    class LawQALLMError(RuntimeError):
        pass

    def answer_legal_manual_question(client, model, question, *, law_names=None, deadline=None):
        state["calls"].append({"client": client, "model": model, "question": question, "deadline": deadline})

        if sleep_seconds:
            time.sleep(sleep_seconds)

        if raises is not None:
            raise raises

        return result

    qa.DEFAULT_MODEL = "fake-law-model"
    qa.LawQAOutputError = LawQAOutputError
    qa.LawQALLMError = LawQALLMError
    qa.answer_legal_manual_question = answer_legal_manual_question

    backend = types.ModuleType(BACKEND_MODULE)
    backend.build_openai_client_and_model = lambda default_model: ("fake-client", default_model)

    law_pkg = types.ModuleType("law")
    law_pkg.__path__ = []  # 패키지처럼
    law_client = types.ModuleType("law.client")

    class LawApiError(RuntimeError):
        pass

    class LawApiClient:
        def get_law_by_name(self, law_name, **kwargs):
            state["cache_calls"].append(law_name)
            return {}

    law_client.LawApiError = LawApiError
    law_client.LawApiClient = LawApiClient
    law_config = types.ModuleType("law.config")
    law_config.LAW_TARGET_LAWS = ("아동복지법", "아동학대범죄의 처벌 등에 관한 특례법")

    for name, module in {
        QA_MODULE: qa,
        BACKEND_MODULE: backend,
        "law": law_pkg,
        "law.client": law_client,
        "law.config": law_config,
    }.items():
        monkeypatch.setitem(sys.modules, name, module)

    state["exceptions"] = {
        "LawQAOutputError": LawQAOutputError,
        "LawQALLMError": LawQALLMError,
        "LawApiError": LawApiError,
    }

    return state


def _audit_rows(db) -> List[AuditLog]:
    return list(db.scalars(select(AuditLog).where(AuditLog.action == AuditAction.LAW_QA_ASKED).order_by(AuditLog.created_at)))


# =========================================================
# mock · 검증 · 권한
# =========================================================


def test_mock_answer_has_contract_shape(client: TestClient, counselor_headers) -> None:
    response = _ask(client, counselor_headers)

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["model"] == MOCK_MODEL
    assert data["answer"].strip() and "참고용" in data["answer"]
    assert set(data["sources"]) == {"laws", "manual"}
    assert data["sources"]["manual"] == []
    law = data["sources"]["laws"][0]
    assert set(law) == {"law_name", "article", "title", "content", "effective_date", "portal_url"}
    assert law["article"] == "제12조" and law["portal_url"].startswith("https://www.law.go.kr/")
    assert data["answered_at"]


@pytest.mark.parametrize("question", ["", "   ", "x" * 501, " " + "x" * 501 + " "])
def test_question_must_be_1_to_500_chars_after_strip(client: TestClient, counselor_headers, question: str) -> None:
    response = _ask(client, counselor_headers, question)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_question_is_stripped_and_500_chars_allowed(client: TestClient, counselor_headers) -> None:
    captured: List[str] = []

    class Capture:
        name = "capture"

        def answer(self, question: str, *, time_limit_seconds: float) -> LawQAAnswer:
            captured.append(question)
            return LawQAAnswer(answer="답", model="capture")

    set_law_qa_adapter_override(Capture())

    assert _ask(client, counselor_headers, "  " + "x" * 500 + "\n").status_code == 200
    assert captured == ["x" * 500]


def test_requires_login_and_allows_admin(client: TestClient, admin_headers) -> None:
    assert client.post(URL, json={"question": QUESTION}).status_code == 401
    assert _ask(client, admin_headers).status_code == 200


def test_provider_off_is_503(client: TestClient, counselor_headers, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "LAW_QA_PROVIDER", "off")

    response = _ask(client, counselor_headers)

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "LAW_QA_DISABLED"


# =========================================================
# 한도 · 동시 실행 · 시간 제한
# =========================================================


def test_rate_limit_is_per_user(
    client: TestClient, counselor_headers, other_counselor_headers, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "LAW_QA_RATE_LIMIT_PER_MINUTE", 2)

    assert _ask(client, counselor_headers).status_code == 200
    assert _ask(client, counselor_headers).status_code == 200
    third = _ask(client, counselor_headers)
    assert third.status_code == 429
    assert third.json()["error"]["code"] == "RATE_LIMITED"
    # 다른 사용자는 따로 센다.
    assert _ask(client, other_counselor_headers).status_code == 200


def test_no_free_slot_within_time_limit_is_504(
    client: TestClient, counselor_headers, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "LAW_QA_MAX_CONCURRENCY", 1)
    monkeypatch.setattr(settings, "LAW_QA_TIMEOUT_SECONDS", 0.2)
    law_guide_service.reset_limits()

    # 유일한 자리를 시험이 쥐고 있는다.
    assert law_guide_service._limits.slots.acquire(timeout=1)

    try:
        response = _ask(client, counselor_headers)
    finally:
        law_guide_service._limits.slots.release()

    assert response.status_code == 504
    assert response.json()["error"]["code"] == "AI_TIMEOUT"
    # 자리는 돌려받는다 — 다음 질문은 된다.
    assert _ask(client, counselor_headers).status_code == 200


def test_slow_adapter_is_504(client: TestClient, counselor_headers, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "LAW_QA_TIMEOUT_SECONDS", 0.2)

    class Slow:
        name = "slow"

        def answer(self, question: str, *, time_limit_seconds: float) -> LawQAAnswer:
            time.sleep(1.0)
            return LawQAAnswer(answer="늦은 답", model="slow")

    set_law_qa_adapter_override(Slow())

    response = _ask(client, counselor_headers)

    assert response.status_code == 504
    assert response.json()["error"]["code"] == "AI_TIMEOUT"


# =========================================================
# modeling — 가짜 모듈
# =========================================================


def test_modeling_maps_module_result_to_contract(
    client: TestClient, counselor_headers, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "LAW_QA_PROVIDER", "modeling")
    state = _install_fake_modules(
        monkeypatch,
        result={
            "answer": "  응급조치는 72시간을 넘을 수 없습니다(아동학대범죄의 처벌 등에 관한 특례법 제12조).  ",
            "law_names": ["아동복지법", "아동학대범죄의 처벌 등에 관한 특례법"],
            "cited_articles": CITED,
            "manual_references": [{"id": "ref3_risk_scale_1", "title": "참고자료3", "page": "350"}, {"id": "", "title": "x"}, "no"],
        },
    )
    before = time.monotonic()

    response = _ask(client, counselor_headers)

    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["model"] == "fake-law-model"
    assert data["answer"].startswith("응급조치는") and not data["answer"].endswith(" ")
    assert data["sources"]["laws"] == [
        {
            "law_name": "아동학대범죄의 처벌 등에 관한 특례법",
            "article": "제12조",
            "title": "피해아동 등에 대한 응급조치",
            "content": "③ 응급조치는 72시간을 넘을 수 없다.",
            "effective_date": "20261002",
            "portal_url": "https://www.law.go.kr/LSW/lsInfoP.do?lsiSeq=1&joNo=0012&joBrNo=00",
        },
        {"law_name": "아동복지법", "article": "제17조", "title": "금지행위", "content": "…", "effective_date": None, "portal_url": None},
    ]
    assert data["sources"]["manual"] == [{"id": "ref3_risk_scale_1", "title": "참고자료3", "page": "350"}]

    call = state["calls"][0]
    assert call["client"] == "fake-client" and call["model"] == "fake-law-model" and call["question"] == QUESTION
    # 마감 = 시작 + LAW_QA_TIMEOUT_SECONDS(60) − AI_DEADLINE_MARGIN_SECONDS(10).
    expected = before + settings.LAW_QA_TIMEOUT_SECONDS - settings.AI_DEADLINE_MARGIN_SECONDS
    assert abs(call["deadline"] - expected) < 5


@pytest.mark.parametrize(
    ("exception_name", "status", "code"),
    [
        ("LawQAOutputError", 502, "AI_INVALID_OUTPUT"),
        ("LawQALLMError", 502, "AI_FAILED"),
        ("LawApiError", 503, "LAW_SOURCE_UNAVAILABLE"),
        ("TimeoutError", 504, "AI_TIMEOUT"),
        ("RuntimeError", 502, "AI_FAILED"),
    ],
)
def test_modeling_exceptions_map_to_codes_without_leaking_messages(
    client: TestClient,
    counselor_headers,
    db,
    monkeypatch: pytest.MonkeyPatch,
    exception_name: str,
    status: int,
    code: str,
) -> None:
    monkeypatch.setattr(settings, "LAW_QA_PROVIDER", "modeling")
    secret = "SECRET-OC=abc123 https://openai.example/v1/responses"
    state = _install_fake_modules(monkeypatch)
    exc_type = state["exceptions"].get(exception_name) or {"TimeoutError": TimeoutError, "RuntimeError": RuntimeError}[exception_name]
    monkeypatch.setitem(
        sys.modules[QA_MODULE].__dict__,
        "answer_legal_manual_question",
        lambda *args, **kwargs: (_ for _ in ()).throw(exc_type(secret)),
    )

    response = _ask(client, counselor_headers)

    assert response.status_code == status, response.text
    error = response.json()["error"]
    assert error["code"] == code
    assert "SECRET" not in response.text and "openai.example" not in response.text

    rows = _audit_rows(db)
    assert rows[-1].status == "FAILED" and rows[-1].error_code == code
    assert "SECRET" not in json.dumps(rows[-1].detail, ensure_ascii=False)


def test_modeling_empty_answer_is_invalid_output(
    client: TestClient, counselor_headers, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "LAW_QA_PROVIDER", "modeling")
    _install_fake_modules(monkeypatch, result={"answer": "   ", "cited_articles": []})

    response = _ask(client, counselor_headers)

    assert response.status_code == 502
    assert response.json()["error"]["code"] == "AI_INVALID_OUTPUT"


def test_modeling_import_failure_is_ai_failed(
    client: TestClient, counselor_headers, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "LAW_QA_PROVIDER", "modeling")
    # sys.modules 에 None 을 두면 import 가 ImportError 로 끝난다.
    monkeypatch.setitem(sys.modules, QA_MODULE, None)

    response = _ask(client, counselor_headers)

    assert response.status_code == 502
    assert response.json()["error"]["code"] == "AI_FAILED"
    assert "legal_manual_qa_llm" not in response.text


def test_modeling_deadline_timeout_is_504(
    client: TestClient, counselor_headers, monkeypatch: pytest.MonkeyPatch
) -> None:
    """모듈이 마감을 넘겨 내장 TimeoutError(고정 문구)를 내면 504 AI_TIMEOUT."""

    monkeypatch.setattr(settings, "LAW_QA_PROVIDER", "modeling")
    _install_fake_modules(monkeypatch, raises=TimeoutError("법령 질의가 제한 시간 안에 끝나지 않았습니다."))

    response = _ask(client, counselor_headers)

    assert response.status_code == 504
    assert response.json()["error"]["code"] == "AI_TIMEOUT"


# =========================================================
# 감사 기록 · 설정 · 준비
# =========================================================


def test_audit_log_keeps_counts_but_not_question(client: TestClient, counselor_headers, db) -> None:
    assert _ask(client, counselor_headers, "아동 홍길동 사례의 응급조치 기간은?").status_code == 200

    rows = _audit_rows(db)

    assert len(rows) == 1
    row = rows[0]
    assert row.status == "SUCCESS" and row.error_code is None and row.entity_type == "LawGuideQuestion"
    assert row.actor_id is not None
    assert row.detail["provider"] == "mock" and row.detail["model"] == MOCK_MODEL
    assert row.detail["law_count"] == 1 and row.detail["manual_count"] == 0
    assert isinstance(row.detail["duration_ms"], int)
    assert "홍길동" not in json.dumps(row.detail, ensure_ascii=False)


def test_rate_limited_call_is_audited(client: TestClient, counselor_headers, db, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "LAW_QA_RATE_LIMIT_PER_MINUTE", 1)

    assert _ask(client, counselor_headers).status_code == 200
    assert _ask(client, counselor_headers).status_code == 429

    rows = _audit_rows(db)
    assert [row.status for row in rows] == ["SUCCESS", "FAILED"]
    assert rows[1].error_code == "RATE_LIMITED"


def test_production_requires_explicit_allow_for_modeling() -> None:
    with pytest.raises(ValueError, match="LAW_QA_ALLOW_IN_PRODUCTION"):
        Settings(_env_file=None, ENV="production", LAW_QA_PROVIDER="modeling")

    allowed = Settings(_env_file=None, ENV="production", LAW_QA_PROVIDER="modeling", LAW_QA_ALLOW_IN_PRODUCTION=True)
    assert allowed.LAW_QA_PROVIDER == "modeling"
    # mock · off 는 잠금과 상관없다.
    assert Settings(_env_file=None, ENV="production", LAW_QA_PROVIDER="off").LAW_QA_PROVIDER == "off"


def test_deadline_margin_must_be_shorter_than_time_limit_for_modeling() -> None:
    with pytest.raises(ValueError, match="LAW_QA_TIMEOUT_SECONDS"):
        Settings(_env_file=None, LAW_QA_PROVIDER="modeling", LAW_QA_TIMEOUT_SECONDS=5, AI_DEADLINE_MARGIN_SECONDS=10)

    # modeling 이 아니면 보지 않는다(짧은 제한으로 mock 을 돌리는 설정을 막지 않게).
    assert Settings(_env_file=None, LAW_QA_PROVIDER="mock", LAW_QA_TIMEOUT_SECONDS=5, AI_DEADLINE_MARGIN_SECONDS=10)


def test_unknown_provider_is_rejected() -> None:
    with pytest.raises(ValueError):
        Settings(_env_file=None, LAW_QA_PROVIDER="pipeline")


def test_preload_only_for_modeling_and_warms_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    assert start_law_qa_preload() is None  # 기본 mock

    monkeypatch.setattr(settings, "LAW_QA_PROVIDER", "modeling")
    state = _install_fake_modules(monkeypatch, result={"answer": "x", "cited_articles": []})

    thread = start_law_qa_preload()

    assert isinstance(thread, threading.Thread)
    thread.join(timeout=5)
    assert not thread.is_alive()
    assert state["cache_calls"] == ["아동복지법", "아동학대범죄의 처벌 등에 관한 특례법"]


def test_preload_failure_does_not_raise(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    monkeypatch.setattr(settings, "LAW_QA_PROVIDER", "modeling")
    monkeypatch.setitem(sys.modules, QA_MODULE, None)

    with caplog.at_level("WARNING", logger=law_qa_adapter.__name__):
        thread = start_law_qa_preload()
        thread.join(timeout=5)

    assert not thread.is_alive()
    assert any("미리 준비하지 못했습니다" in record.getMessage() for record in caplog.records)


def test_law_env_is_exported_from_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LAW_API_OC", "")
    monkeypatch.setenv("LAW_CACHE_DIR", "")
    monkeypatch.setattr(settings, "LAW_API_OC", "oc-from-settings")
    monkeypatch.setattr(settings, "LAW_CACHE_DIR", "")

    export_law_env()

    assert os.environ["LAW_API_OC"] == "oc-from-settings"
    # 비어 있으면 넘기지 않는다.
    assert os.environ["LAW_CACHE_DIR"] == ""

    # 이미 환경에 있으면 그 값이 우선이다.
    monkeypatch.setenv("LAW_API_OC", "oc-from-env")
    export_law_env()
    assert os.environ["LAW_API_OC"] == "oc-from-env"
