# 이경진 님 분석 파이프라인 연결 경로(ModelingAIAdapter) 테스트.
#
# 다른 Backend 테스트는 conftest.py 가 AI_PROVIDER=mock 으로 고정해서 ModelingAIAdapter 가 실행되지 않는다.
# 무거운 분석(analyze_audio_session — torch · 가중치 · OpenAI 호출)만 가짜 모듈로 바꾸고,
# 결과를 Contract 모양으로 바꾸는 contract_adapter 와 agent/summary_converter 는 실제 코드를 쓴다.
#   - CI 에는 torch · transformers · openai 가 없다. openai 는 contract_adapter 가 import 만 하므로
#     설치되지 않았으면 가짜 모듈로 채운다.
#   - 아래 녹취 · 분석 결과는 모두 가상 데이터다.

import copy
import importlib
import importlib.abc
import importlib.util
import json
import logging
import sys
import threading
import time
import types
import uuid
from typing import Any, Callable, Dict, List

import pytest
from fastapi.testclient import TestClient

from app.adapters.ai_adapter import (
    AI_TIMEOUT_MESSAGE,
    AIError,
    ModelingAIAdapter,
    get_ai_adapter,
    set_ai_adapter_override,
    start_ai_preload,
)
from app.adapters.module_loader import ensure_repo_root_on_path
from app.core.config import BACKEND_DIR, Settings, settings
from app.core.errors import ErrorCode
from app.main import app
from app.services import analysis_service
from tests.test_analysis import _get_analysis, _run_analysis, confirmed_session

# monkeypatch 가 "ai.modeling.abuse.*" 를 찾으려면 최상위 경로가 필요하다.
ensure_repo_root_on_path()

PACKAGE = "ai.modeling.abuse"
CONTRACT_ADAPTER = "ai.modeling.abuse.contract_adapter"
HEAVY_MODULE = "ai.modeling.abuse.infer_audio_session"

DROPPED_WARNING = "segment 근거가 없는 신호"

TRANSCRIPT = {
    "schema_version": "1.0",
    "segments": [
        {
            "segment_id": "seg_001",
            "speaker": "COUNSELOR",
            "start_ms": 0,
            "end_ms": 1500,
            "text": "요즘 집에서는 어떻게 지내요?",
            "confidence": 0.95,
        },
        {
            "segment_id": "seg_002",
            "speaker": "CHILD",
            "start_ms": 1500,
            "end_ms": 4000,
            "text": "아빠가 화나면 때려요.",
            "confidence": 0.9,
        },
        {
            "segment_id": "seg_003",
            "speaker": "GUARDIAN",
            "start_ms": 4000,
            "end_ms": 6000,
            "text": "애가 요즘 말을 잘 안 들어요.",
            "confidence": 0.88,
        },
    ],
}

GROUNDED_POINT = {
    "text": "아빠가 화나면 때려요.",
    "segment_ids": ["seg_002"],
    "major_type": "신체학대",
    "subtype": "직접 신체 가해",
    "evidence_strength": "높음",
}


def _native_result() -> Dict[str, Any]:
    """analyze_audio_session 이 돌려주는 모양(가상 값). contract_adapter 가 읽는 키를 채운다."""

    return {
        "counseling_summary": "아동이 보호자의 체벌을 진술함.",
        "counseling_record_model": "note-model-test",
        "major_types": {
            "신체학대": {"detected": True},
            "정서학대": {"detected": False},
            "성학대": {"detected": False},
            "방임": {"detected": False},
        },
        "subtype_analysis": {"model": "subtype-model-test", "results": []},
        "record_draft": {
            "child_statement_points": [
                {"text": "아빠가 화나면 때린다고 말함.", "segment_ids": ["seg_002"]},
            ],
            "risk_signal_points": [dict(GROUNDED_POINT)],
        },
        # Contract 에 담지 않는 값 — 결과에 새지 않아야 한다.
        "severity_ratings": [{"major_type": "신체학대", "level": "가상 심각도"}],
        "protective_factors": [
            {"category": "지지 관계", "text": "담임 선생님과 가깝다.", "segment_ids": ["seg_002"]},
        ],
        "session_change_notes": ["가상 회차 변화"],
        "followup_check_points": ["가상 확인사항"],
    }


@pytest.fixture
def modeling(monkeypatch: pytest.MonkeyPatch) -> Dict[str, Any]:
    """ai.modeling.abuse.infer_audio_session 을 가짜 모듈로 바꾼다.

    result 에 값 또는 stt_result 를 받는 함수를, error 에 예외를 넣어 동작을 정한다.
    calls 에는 가짜 analyze_audio_session 이 받은 인자가 쌓인다.
    """

    state: Dict[str, Any] = {"result": _native_result(), "error": None, "calls": []}

    def analyze_audio_session(stt_result, client=None, case_id=None, **kwargs):
        state["calls"].append({"stt_result": stt_result, "client": client, "case_id": case_id})

        if state["error"] is not None:
            raise state["error"]

        result = state["result"]
        return result(stt_result) if callable(result) else copy.deepcopy(result)

    heavy = types.ModuleType(HEAVY_MODULE)
    heavy.analyze_audio_session = analyze_audio_session
    monkeypatch.setitem(sys.modules, HEAVY_MODULE, heavy)

    if importlib.util.find_spec("openai") is None:
        fake_openai = types.ModuleType("openai")
        fake_openai.OpenAI = object
        monkeypatch.setitem(sys.modules, "openai", fake_openai)

    # 앞선 시험이 다른 가짜 모듈로 import 해 둔 contract_adapter 를 쓰지 않게 매번 새로 import 한다.
    # import 하면 sys.modules 와 부모 패키지 속성 두 곳에 남으므로 둘 다 비우고, 끝나면 원래대로 되돌린다.
    package = importlib.import_module(PACKAGE)
    saved_module = sys.modules.pop(CONTRACT_ADAPTER, None)
    saved_attr = package.__dict__.pop("contract_adapter", None)

    yield state

    sys.modules.pop(CONTRACT_ADAPTER, None)
    package.__dict__.pop("contract_adapter", None)

    if saved_module is not None:
        sys.modules[CONTRACT_ADAPTER] = saved_module

    if saved_attr is not None:
        package.contract_adapter = saved_attr


# =========================================================
# Provider 전환
# =========================================================

def test_factory_returns_modeling_adapter(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "AI_PROVIDER", "modeling")

    assert isinstance(get_ai_adapter(), ModelingAIAdapter)


# =========================================================
# Adapter 단위 — analyze → Contract
# =========================================================

def test_result_is_converted_to_contract(modeling) -> None:
    bundle = ModelingAIAdapter().analyze(TRANSCRIPT)
    result = bundle.result

    assert bundle.provider == "modeling"
    assert bundle.model == "subtype-model-test"

    assert result.summary.overview == "아동이 보호자의 체벌을 진술함."
    assert result.summary.key_points == ["아빠가 화나면 때린다고 말함."]
    assert [(e.key_point, e.segment_ids) for e in bundle.summary_evidence] == [
        ("아빠가 화나면 때린다고 말함.", ["seg_002"]),
    ]

    assert result.risk_utterances == [GROUNDED_POINT]
    assert result.abuse_signals == [
        {"major_type": "신체학대", "detected": True, "segment_ids": ["seg_002"]},
        {"major_type": "정서학대", "detected": False, "segment_ids": []},
        {"major_type": "성학대", "detected": False, "segment_ids": []},
        {"major_type": "방임", "detected": False, "segment_ids": []},
    ]
    assert result.risk_factors == []

    # 검출되지 않은 유형은 근거가 없어도 남고 경고도 붙지 않는다.
    assert result.warnings == []


def test_fields_outside_contract_do_not_leak(modeling) -> None:
    """심각도 · 보호요인 · 회차 간 변화 · 다음 확인사항은 아직 담지 않는다.

    #49 가 같은 이름의 정식 선택 필드(기본값 빈 배열)를 더해도 이 어댑터는 채우지 않으므로
    기본 6필드 밖의 값은 모두 비어 있어야 한다. contract_adapter 가 채우기 시작하면
    이 시험을 그때의 계약에 맞춰 바꾼다.
    """

    stored = ModelingAIAdapter().analyze(TRANSCRIPT).result.model_dump()
    core = {"schema_version", "summary", "risk_utterances", "abuse_signals", "risk_factors", "warnings"}

    assert core <= set(stored)
    assert {key: value for key, value in stored.items() if key not in core and value} == {}

    dumped = json.dumps(stored, ensure_ascii=False)

    for leaked in ("담임 선생님", "가상 심각도", "가상 회차 변화", "가상 확인사항"):
        assert leaked not in dumped


def test_pipeline_receives_contract_transcript_without_case_id(modeling) -> None:
    """case_id 는 넘기지 않는다(실명 저장 결정 전). 입력은 STT Contract 의 6개 키만 받는다."""

    ModelingAIAdapter().analyze(TRANSCRIPT)

    [call] = modeling["calls"]

    assert call["case_id"] is None
    assert [s["segment_id"] for s in call["stt_result"]["segments"]] == ["seg_001", "seg_002", "seg_003"]
    assert set(call["stt_result"]["segments"][0]) == {
        "segment_id",
        "speaker",
        "start_ms",
        "end_ms",
        "text",
        "confidence",
    }


def test_model_name_falls_back_to_note_model_when_nothing_detected(modeling) -> None:
    modeling["result"]["subtype_analysis"] = {"results": [], "note": "탐지된 대분류 없음"}

    assert ModelingAIAdapter().analyze(TRANSCRIPT).model == "note-model-test"


# =========================================================
# 근거 관문 — 근거 발화가 없는 위험 항목은 저장 전에 뺀다
# =========================================================

def test_unverified_evidence_and_signal_without_evidence_are_dropped(modeling, caplog) -> None:
    """원문 대조에 실패한 근거(segment_ids=[])와 근거 없이 검출된 유형은 빠지고 건수가 남는다."""

    draft = modeling["result"]["record_draft"]
    draft["risk_signal_points"].append({**GROUNDED_POINT, "text": "원문에 없는 인용(가상)", "segment_ids": []})
    modeling["result"]["major_types"]["정서학대"] = {"detected": True}

    with caplog.at_level(logging.WARNING):
        result = ModelingAIAdapter().analyze(TRANSCRIPT).result

    assert result.risk_utterances == [GROUNDED_POINT]
    assert [(s["major_type"], s["detected"]) for s in result.abuse_signals] == [
        ("신체학대", True),
        ("성학대", False),
        ("방임", False),
    ]
    assert result.warnings == ["segment 근거가 없는 신호 2건을 제외했습니다."]

    assert "provider=modeling count=2" in caplog.text
    assert "원문에 없는 인용" not in caplog.text


def test_items_pointing_to_unknown_segment_are_dropped(modeling) -> None:
    modeling["result"]["record_draft"]["risk_signal_points"].append(
        {**GROUNDED_POINT, "major_type": "성학대", "subtype": "가상", "segment_ids": ["seg_999"]}
    )
    modeling["result"]["major_types"]["성학대"] = {"detected": True}

    result = ModelingAIAdapter().analyze(TRANSCRIPT).result

    assert result.risk_utterances == [GROUNDED_POINT]
    assert "성학대" not in [s["major_type"] for s in result.abuse_signals]
    assert any(DROPPED_WARNING in warning for warning in result.warnings)


def test_gate_checks_against_adapter_input_not_module_output(modeling) -> None:
    """모듈이 돌려준 segments 에 없는 번호가 있어도 관문은 어댑터가 받은 Transcript 로 대조한다."""

    modeling["result"]["segments"] = [{"segment_id": "seg_999", "speaker": "CHILD", "text": "가상"}]
    modeling["result"]["record_draft"]["risk_signal_points"] = [
        {**GROUNDED_POINT, "segment_ids": ["seg_999"]},
    ]

    result = ModelingAIAdapter().analyze(TRANSCRIPT).result

    assert result.risk_utterances == []
    assert any(DROPPED_WARNING in warning for warning in result.warnings)


# =========================================================
# 실패 처리 — 서버는 그대로, 그 분석만 실패
# =========================================================

def test_missing_heavy_dependency_is_reported_as_ai_failed(modeling, monkeypatch: pytest.MonkeyPatch) -> None:
    """torch · transformers 가 없는 서버에서도 import 실패가 AIError 로 바뀐다."""

    monkeypatch.setitem(sys.modules, HEAVY_MODULE, None)

    with pytest.raises(AIError) as raised:
        ModelingAIAdapter().analyze(TRANSCRIPT)

    assert raised.value.error_code == ErrorCode.AI_FAILED
    assert "import" in str(raised.value)


@pytest.mark.parametrize(
    "error_name",
    ["RuntimeError", "ValueError", "PrivacyGatewayBlocked"],
)
def test_pipeline_exception_text_is_not_stored(modeling, error_name: str) -> None:
    """알 수 없는 예외의 문구는 AIError 에 싣지 않는다. 예외 종류 이름만 남긴다."""

    modeling["error"] = type(error_name, (Exception,), {})("아빠가 때렸어요 발화 처리 중 오류")

    with pytest.raises(AIError) as raised:
        ModelingAIAdapter().analyze(TRANSCRIPT)

    assert raised.value.error_code == ErrorCode.AI_FAILED
    assert "아빠가 때렸어요" not in str(raised.value)
    assert error_name in str(raised.value)


def test_transcript_ai_cannot_read_is_rejected_before_pipeline(modeling) -> None:
    broken = {
        "schema_version": "1.0",
        "segments": [{"segment_id": "seg_001", "speaker": "MOTHER", "text": "..."}],
    }

    with pytest.raises(AIError) as raised:
        ModelingAIAdapter().analyze(broken)

    assert raised.value.error_code == ErrorCode.AI_INVALID_OUTPUT
    assert modeling["calls"] == [], "입력이 틀리면 분석을 부르지 않는다"


def test_output_breaking_contract_becomes_invalid_output_error(
    modeling, monkeypatch: pytest.MonkeyPatch
) -> None:
    contract_adapter = importlib.import_module(CONTRACT_ADAPTER)
    monkeypatch.setattr(
        contract_adapter,
        "analyze_audio_session_as_contract",
        lambda **kwargs: ({"schema_version": "2.0"}, [], "subtype-model-test"),
    )

    with pytest.raises(AIError) as raised:
        ModelingAIAdapter().analyze(TRANSCRIPT)

    assert raised.value.error_code == ErrorCode.AI_INVALID_OUTPUT


# =========================================================
# API 전체 흐름 — 분석 요청 → Background 처리 → 저장
# =========================================================

def _result_for(stt_result: Dict[str, Any]) -> Dict[str, Any]:
    """mock STT 대본의 아동 발화 하나를 근거로 쓰고, 근거 없는 항목을 하나 섞는다."""

    child_id = next(s["segment_id"] for s in stt_result["segments"] if s["speaker"] == "CHILD")
    result = _native_result()
    result["record_draft"]["child_statement_points"] = [
        {"text": "인사를 나눔.", "segment_ids": [child_id]},
    ]
    result["record_draft"]["risk_signal_points"] = [
        {**GROUNDED_POINT, "segment_ids": [child_id]},
        {**GROUNDED_POINT, "text": "원문에 없는 인용(가상)", "segment_ids": []},
    ]

    return result


def test_modeling_result_is_stored_through_api(
    client: TestClient, counselor_headers, session: dict, modeling
) -> None:
    confirmed_session(client, counselor_headers, session["id"])
    set_ai_adapter_override(ModelingAIAdapter())
    modeling["result"] = _result_for

    assert _run_analysis(client, counselor_headers, session["id"]).status_code == 202

    envelope = _get_analysis(client, counselor_headers, session["id"]).json()["data"]

    assert envelope["session_status"] == "AI_REVIEW_REQUIRED"

    analysis = envelope["analysis"]
    assert analysis["status"] == "COMPLETED"
    assert analysis["provider"] == "modeling"
    assert analysis["model"] == "subtype-model-test"

    stored = analysis["result"]
    assert [u["text"] for u in stored["risk_utterances"]] == [GROUNDED_POINT["text"]]
    assert stored["risk_factors"] == []
    assert "segment 근거가 없는 신호 1건을 제외했습니다." in stored["warnings"]

    [call] = modeling["calls"]
    child_id = next(s["segment_id"] for s in call["stt_result"]["segments"] if s["speaker"] == "CHILD")
    assert analysis["summary_evidence"][0]["segment_ids"] == [child_id]


def test_pipeline_failure_fails_session_instead_of_hanging(
    client: TestClient, counselor_headers, session: dict, modeling
) -> None:
    confirmed_session(client, counselor_headers, session["id"])
    set_ai_adapter_override(ModelingAIAdapter())
    modeling["error"] = RuntimeError("아빠가 때렸어요 발화 처리 중 오류")

    assert _run_analysis(client, counselor_headers, session["id"]).status_code == 202

    envelope = _get_analysis(client, counselor_headers, session["id"]).json()["data"]

    assert envelope["session_status"] == "AI_FAILED"
    assert envelope["error"]["code"] == "AI_FAILED"
    assert "아빠가 때렸어요" not in envelope["error"]["message"]
    assert envelope["analysis"]["result"] is None


# =========================================================
# 시간 제한 — 마감 시각 · 모델 로드
# =========================================================

def test_pipeline_timeout_error_is_stored_as_ai_timeout(
    client: TestClient, counselor_headers, session: dict, modeling
) -> None:
    """모듈이 마감 시각을 넘겨 내장 TimeoutError 를 던지면 AI_TIMEOUT 으로 저장한다. 문구는 고정 문구다."""

    confirmed_session(client, counselor_headers, session["id"])
    set_ai_adapter_override(ModelingAIAdapter())
    modeling["error"] = TimeoutError("아빠가 때렸어요 발화를 분석하다 마감 시각을 넘음")

    assert _run_analysis(client, counselor_headers, session["id"]).status_code == 202

    envelope = _get_analysis(client, counselor_headers, session["id"]).json()["data"]

    assert envelope["session_status"] == "AI_FAILED"
    assert envelope["error"]["code"] == "AI_TIMEOUT"
    assert envelope["analysis"]["error"]["code"] == "AI_TIMEOUT"
    assert "아빠가 때렸어요" not in envelope["error"]["message"]


class _SlowImport(importlib.abc.MetaPathFinder, importlib.abc.Loader):
    """infer_audio_session 을 import 하는 데 seconds 초가 걸리게 한다(가중치 로드 흉내).

    실제 모듈은 import 할 때 모델을 올린다(infer_abuse_v3_adapter · pii_masking 의 모듈 수준 코드).
    """

    def __init__(self, seconds: float, analyze: Callable[..., Any]) -> None:
        self.seconds = seconds
        self.analyze = analyze
        self.imports = 0

    def find_spec(self, fullname, path, target=None):
        if fullname != HEAVY_MODULE:
            return None

        return importlib.util.spec_from_loader(fullname, self)

    def create_module(self, spec):
        return None

    def exec_module(self, module) -> None:
        self.imports += 1
        time.sleep(self.seconds)
        module.analyze_audio_session = self.analyze


def test_module_import_time_is_outside_ai_time_limit(
    client: TestClient,
    counselor_headers,
    session: dict,
    modeling,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """모델을 올리는(import) 데 AI_TIMEOUT_SECONDS 보다 오래 걸려도 분석 시간에 들어가지 않는다."""

    slow = _SlowImport(seconds=1.0, analyze=sys.modules[HEAVY_MODULE].analyze_audio_session)
    monkeypatch.delitem(sys.modules, HEAVY_MODULE)
    monkeypatch.setattr(sys, "meta_path", [slow, *sys.meta_path])
    # import 가 부모 패키지에 남기는 속성도 시험 뒤 되돌린다.
    monkeypatch.setattr(importlib.import_module(PACKAGE), "infer_audio_session", None, raising=False)

    confirmed_session(client, counselor_headers, session["id"])
    monkeypatch.setattr(settings, "AI_TIMEOUT_SECONDS", 0.5)
    set_ai_adapter_override(ModelingAIAdapter())
    modeling["result"] = _result_for

    assert _run_analysis(client, counselor_headers, session["id"]).status_code == 202

    envelope = _get_analysis(client, counselor_headers, session["id"]).json()["data"]

    assert envelope["session_status"] == "AI_REVIEW_REQUIRED", envelope["error"]
    assert slow.imports == 1


def test_import_failure_in_prepare_fails_session(
    client: TestClient,
    counselor_headers,
    session: dict,
    modeling,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """준비 단계(import)가 실패해도 그 분석만 AI_FAILED 로 끝난다."""

    confirmed_session(client, counselor_headers, session["id"])
    monkeypatch.setitem(sys.modules, HEAVY_MODULE, None)
    set_ai_adapter_override(ModelingAIAdapter())

    assert _run_analysis(client, counselor_headers, session["id"]).status_code == 202

    envelope = _get_analysis(client, counselor_headers, session["id"]).json()["data"]

    assert envelope["session_status"] == "AI_FAILED"
    assert envelope["error"]["code"] == "AI_FAILED"
    # import 예외 문구("import of … halted; None in sys.modules")는 응답에 싣지 않는다.
    assert "halted" not in envelope["error"]["message"]
    assert modeling["calls"] == []


def _patch_contract_function(
    monkeypatch: pytest.MonkeyPatch,
    make: Callable[[Callable[..., Any], List[Dict[str, Any]]], Callable[..., Any]],
) -> List[Dict[str, Any]]:
    """contract_adapter.analyze_audio_session_as_contract 를 make 가 만든 함수로 바꾼다.

    make 는 (원래 함수, 받은 인자를 쌓을 목록)을 받아 새 함수를 돌려준다.
    새 함수가 원래 함수를 부르므로 결과는 그대로 Contract 모양이다.
    """

    contract_adapter = importlib.import_module(CONTRACT_ADAPTER)
    calls: List[Dict[str, Any]] = []
    monkeypatch.setattr(
        contract_adapter,
        "analyze_audio_session_as_contract",
        make(contract_adapter.analyze_audio_session_as_contract, calls),
    )

    return calls


def test_deadline_is_passed_when_pipeline_accepts_it(modeling, monkeypatch: pytest.MonkeyPatch) -> None:
    """deadline 을 받는 판이면 time.monotonic() 기준 마감 시각(분석 시작 + 제한 시간 - 여유)을 넘긴다."""

    def make(original, calls):
        def accepts_deadline(stt_result, client=None, case_id=None, *, deadline=None):
            calls.append({"deadline": deadline})
            return original(stt_result=stt_result, client=client, case_id=case_id)

        return accepts_deadline

    calls = _patch_contract_function(monkeypatch, make)
    monkeypatch.setattr(settings, "AI_TIMEOUT_SECONDS", 100.0)
    monkeypatch.setattr(settings, "AI_DEADLINE_MARGIN_SECONDS", 7.0)

    before = time.monotonic()
    ModelingAIAdapter().analyze(TRANSCRIPT)
    after = time.monotonic()

    [call] = calls
    assert before + 93.0 <= call["deadline"] <= after + 93.0


@pytest.mark.parametrize("variant", ["no_deadline_parameter", "only_kwargs"])
def test_deadline_is_not_passed_when_pipeline_does_not_accept_it(
    modeling, monkeypatch: pytest.MonkeyPatch, variant: str
) -> None:
    """deadline 을 이름으로 받지 않는 판에는 넘기지 않는다. **kwargs 만 있어도 넘기지 않는다."""

    def make(original, calls):
        def no_deadline_parameter(stt_result, client=None, case_id=None):
            calls.append({})
            return original(stt_result=stt_result, client=client, case_id=case_id)

        def only_kwargs(stt_result, **kwargs):
            calls.append(kwargs)
            return original(stt_result=stt_result)

        return {"no_deadline_parameter": no_deadline_parameter, "only_kwargs": only_kwargs}[variant]

    calls = _patch_contract_function(monkeypatch, make)

    ModelingAIAdapter().analyze(TRANSCRIPT)

    assert calls == [{}]


def test_pipeline_stopping_at_deadline_ends_before_backend_time_limit(
    client: TestClient,
    counselor_headers,
    session: dict,
    modeling,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """마감 시각에 모듈이 스스로 멈추면 Backend 제한 시간 전에 AI_TIMEOUT(고정 문구)으로 끝난다.

    Backend 제한 시간에 걸렸다면 문구가 run_with_timeout 의 "외부 서비스 응답이 …" 였을 것이다.
    """

    def make(original, calls):
        def stops_at_deadline(stt_result, client=None, case_id=None, deadline=None):
            calls.append({"deadline": deadline})
            time.sleep(max(0.0, deadline - time.monotonic()))
            raise TimeoutError("아빠가 때렸어요 발화 분석 중 마감 시각을 넘음")

        return stops_at_deadline

    confirmed_session(client, counselor_headers, session["id"])
    calls = _patch_contract_function(monkeypatch, make)
    monkeypatch.setattr(settings, "AI_TIMEOUT_SECONDS", 2.0)
    monkeypatch.setattr(settings, "AI_DEADLINE_MARGIN_SECONDS", 1.5)
    set_ai_adapter_override(ModelingAIAdapter())

    assert _run_analysis(client, counselor_headers, session["id"]).status_code == 202

    envelope = _get_analysis(client, counselor_headers, session["id"]).json()["data"]

    assert envelope["session_status"] == "AI_FAILED"
    assert envelope["error"] == {"code": "AI_TIMEOUT", "message": AI_TIMEOUT_MESSAGE}
    assert len(calls) == 1


# #57(이경진 님)의 _call_llm_with_retry 는 마감에 걸린 LLM 호출의 응답을 '남은 시간 + 5초' 까지 기다린 뒤
# TimeoutError 를 낸다(ai/modeling/abuse/second_stage_llm.py 의 result_queue.get(timeout=effective_timeout + 5)).
# 그래서 모듈은 마감 시각보다 최대 5초 늦게 멈춘다.
MODELING_LATE_REPLY_WAIT_SECONDS = 5.0
DEFAULT_DEADLINE_MARGIN = Settings.model_fields["AI_DEADLINE_MARGIN_SECONDS"].default


def _env_example_value(name: str) -> str:
    for line in (BACKEND_DIR / ".env.example").read_text(encoding="utf-8").splitlines():
        if line.startswith(f"{name}="):
            return line.split("=", 1)[1].strip()

    raise AssertionError(f"backend/.env.example 에 {name} 가 없다")


def test_default_deadline_margin_is_longer_than_modeling_late_reply_wait() -> None:
    """기본 여유가 모듈이 마감 뒤 더 기다리는 5초보다 길어야 모듈이 Backend 제한 시간보다 먼저 멈춘다.

    5초 이하면 모듈과 Backend 제한이 같은 순간 끝나 Backend(run_with_timeout)가 먼저 잡는다.
    .env.example 을 그대로 옮겨 쓰면 거기 적힌 값이 쓰이므로 그 값도 기본값과 같은지 본다.
    """

    assert DEFAULT_DEADLINE_MARGIN > MODELING_LATE_REPLY_WAIT_SECONDS
    assert float(_env_example_value("AI_DEADLINE_MARGIN_SECONDS")) == DEFAULT_DEADLINE_MARGIN


def test_pipeline_waiting_after_deadline_still_ends_before_backend_time_limit(
    client: TestClient,
    counselor_headers,
    session: dict,
    modeling,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """모듈이 #57 처럼 마감 시각 + 5초에 TimeoutError 를 내도, 기본 여유면 Backend 제한 시간 전에 고정 문구로 끝난다.

    시간은 모두 같은 비율(SCALE)로 줄여 돈다. 여유 · 기다림 · 제한 시간의 관계는 그대로다
    (제한 20초 · 여유 10초 · 기다림 5초 → 모듈 15초에 멈춤. 여유 5초면 20초로 Backend 와 같아진다).
    """

    scale = 0.1
    late_wait = MODELING_LATE_REPLY_WAIT_SECONDS * scale
    # 예외가 모듈 단계들을 거쳐 올라오는 데 드는 시간. 이것 때문에 여유 5초면 늘 Backend 가 먼저 잡는다.
    unwind = 0.05

    def make(original, calls):
        def stops_after_late_reply_wait(stt_result, client=None, case_id=None, deadline=None):
            calls.append({"deadline": deadline})
            time.sleep(max(0.0, deadline + late_wait + unwind - time.monotonic()))
            raise TimeoutError("아빠가 때렸어요 발화 분석 중 마감 시각을 넘음")

        return stops_after_late_reply_wait

    confirmed_session(client, counselor_headers, session["id"])
    calls = _patch_contract_function(monkeypatch, make)
    monkeypatch.setattr(settings, "AI_TIMEOUT_SECONDS", 20.0 * scale)
    monkeypatch.setattr(settings, "AI_DEADLINE_MARGIN_SECONDS", DEFAULT_DEADLINE_MARGIN * scale)
    set_ai_adapter_override(ModelingAIAdapter())

    assert _run_analysis(client, counselor_headers, session["id"]).status_code == 202

    envelope = _get_analysis(client, counselor_headers, session["id"]).json()["data"]

    # Backend 제한에 걸렸다면 "외부 서비스 응답이 2.0초 안에 …" 였을 것이다.
    assert envelope["error"] == {"code": "AI_TIMEOUT", "message": AI_TIMEOUT_MESSAGE}
    assert len(calls) == 1


def _record_deadline(original, calls):
    def accepts_deadline(stt_result, client=None, case_id=None, *, deadline=None):
        calls.append({"deadline": deadline, "now": time.monotonic()})
        return original(stt_result=stt_result, client=client, case_id=case_id)

    return accepts_deadline


def test_deadline_uses_time_limit_given_by_analysis_service(
    modeling, monkeypatch: pytest.MonkeyPatch
) -> None:
    """analysis_service 가 작업 전체 마감에 맞춰 줄인 분석 제한 시간을 넘기면 마감 시각도 그 기준이다."""

    calls = _patch_contract_function(monkeypatch, _record_deadline)
    monkeypatch.setattr(settings, "AI_TIMEOUT_SECONDS", 100.0)
    monkeypatch.setattr(settings, "AI_DEADLINE_MARGIN_SECONDS", 7.0)

    before = time.monotonic()
    ModelingAIAdapter().analyze(TRANSCRIPT, time_limit_seconds=40.0)
    after = time.monotonic()

    [call] = calls
    assert before + 33.0 <= call["deadline"] <= after + 33.0


def test_deadline_follows_job_deadline_when_worker_started_late(
    client: TestClient,
    counselor_headers,
    counselor_id,
    session: dict,
    modeling,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """작업 시작이 늦어 분석 제한 시간이 줄면, modeling 에 넘기는 마감 시각도 줄어든 제한 - 여유다.

    시험 설정: 분석 제한 5초 · 여유 1초 · 준비 제한 45초 → 작업 전체 50초. 요청 뒤 47초가 흘렀으면
    분석 제한은 약 3초, 마감 시각은 분석 시작 + 약 2초다(줄이지 않으면 + 4초).
    """

    from tests.test_analysis_late_results import _reserve, _shift_requested_at

    confirmed_session(client, counselor_headers, session["id"])
    calls = _patch_contract_function(monkeypatch, _record_deadline)
    set_ai_adapter_override(ModelingAIAdapter())

    analysis_id = _reserve(session["id"], counselor_id)
    _shift_requested_at(session["id"], 47)

    analysis_service.process_analysis(uuid.UUID(session["id"]), analysis_id)

    [call] = calls
    left = call["deadline"] - call["now"]

    assert 1.5 <= left <= 3.0 - settings.AI_DEADLINE_MARGIN_SECONDS
    assert _get_analysis(client, counselor_headers, session["id"]).json()["data"]["session_status"] == (
        "AI_REVIEW_REQUIRED"
    )


class _BrokenSignature:
    """서명 정보(__signature__)를 읽으면 RuntimeError 가 나는 호출 가능 객체. 원래 함수를 그대로 부른다."""

    def __init__(self, original, calls) -> None:
        self.original = original
        self.calls = calls

    @property
    def __signature__(self):
        raise RuntimeError("가상 서명 오류")

    def __call__(self, stt_result, client=None, case_id=None, **kwargs):
        self.calls.append(kwargs)
        return self.original(stt_result=stt_result, client=client, case_id=case_id)


def test_signature_read_error_means_deadline_is_not_passed(
    modeling, monkeypatch: pytest.MonkeyPatch
) -> None:
    """함수 서명을 읽다가 TypeError · ValueError 가 아닌 예외가 나도 '받지 않음' 으로 보고 분석을 계속한다."""

    calls = _patch_contract_function(monkeypatch, _BrokenSignature)

    bundle = ModelingAIAdapter().analyze(TRANSCRIPT)

    assert bundle.provider == "modeling"
    assert calls == [{}]


def test_import_error_message_keeps_only_exception_type(
    modeling, monkeypatch: pytest.MonkeyPatch
) -> None:
    """import 실패 문구에는 예외 종류 이름만 싣는다. 예외 문구(모듈 경로 · 내려받기 주소 등)는 DB · API 로 가지 않는다."""

    monkeypatch.setitem(sys.modules, HEAVY_MODULE, None)

    with pytest.raises(AIError) as raised:
        ModelingAIAdapter().prepare()

    assert raised.value.error_code == ErrorCode.AI_FAILED
    assert str(raised.value) == "Modeling Pipeline module 을 import 할 수 없습니다: ModuleNotFoundError"


# =========================================================
# 서버 시작 때 미리 불러오기
# =========================================================

@pytest.mark.parametrize("provider", ["mock", "pipeline", "langgraph"])
def test_providers_without_prepare_start_no_preload(
    monkeypatch: pytest.MonkeyPatch, provider: str
) -> None:
    monkeypatch.setattr(settings, "AI_PROVIDER", provider)

    assert start_ai_preload() is None


def test_preload_imports_modeling_module_in_background(
    modeling, monkeypatch: pytest.MonkeyPatch, caplog
) -> None:
    monkeypatch.setattr(settings, "AI_PROVIDER", "modeling")

    with caplog.at_level(logging.INFO):
        thread = start_ai_preload()
        thread.join(timeout=30)

    assert thread.daemon
    assert not thread.is_alive()
    assert CONTRACT_ADAPTER in sys.modules
    assert "AI 모듈을 미리 불러왔습니다. provider=modeling" in caplog.text


def test_startup_preload_failure_does_not_stop_server(
    modeling, monkeypatch: pytest.MonkeyPatch, caplog
) -> None:
    """torch 등이 없어 미리 불러오기가 실패해도 서버는 뜨고, 로그에는 예외 종류 이름만 남는다."""

    monkeypatch.setattr(settings, "AI_PROVIDER", "modeling")
    monkeypatch.setitem(sys.modules, HEAVY_MODULE, None)

    with caplog.at_level(logging.WARNING), TestClient(app) as started:
        thread = app.state.ai_preload
        thread.join(timeout=30)
        health = started.get("/health")

    assert not thread.is_alive()
    assert health.status_code == 200
    assert health.json()["data"]["ai_provider"] == "modeling"

    assert "AI 모듈을 미리 불러오지 못했습니다" in caplog.text
    assert "type=ModuleNotFoundError" in caplog.text
    # 예외 문구("import of … halted; None in sys.modules")는 남기지 않는다.
    assert "halted" not in caplog.text


class _BlockingPrepareAdapter:
    """release 가 켜질 때까지 준비 단계가 끝나지 않는 어댑터(내려받기가 오래 걸리는 새 서버 흉내)."""

    name = "blocking-prepare"

    def __init__(self) -> None:
        self.started = threading.Event()
        self.release = threading.Event()

    def prepare(self) -> None:
        self.started.set()
        self.release.wait(timeout=30)

    def analyze(self, transcript_payload):
        raise AssertionError("시작 때는 분석하지 않는다")


def test_startup_preload_does_not_block_health() -> None:
    adapter = _BlockingPrepareAdapter()
    set_ai_adapter_override(adapter)

    try:
        with TestClient(app) as started:
            assert adapter.started.wait(timeout=10)
            health = started.get("/health")
            thread = app.state.ai_preload
            still_loading = thread.is_alive()
    finally:
        adapter.release.set()

    thread.join(timeout=10)

    assert health.status_code == 200
    assert still_loading
