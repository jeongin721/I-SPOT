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
import importlib.util
import json
import logging
import sys
import types
from typing import Any, Dict

import pytest
from fastapi.testclient import TestClient

from app.adapters.ai_adapter import (
    AIError,
    ModelingAIAdapter,
    get_ai_adapter,
    set_ai_adapter_override,
)
from app.adapters.module_loader import ensure_repo_root_on_path
from app.core.config import settings
from app.core.errors import ErrorCode
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
        # 선택 필드 4개(#49)로 옮겨지는 값. 모양은 각 모듈이 정리해 돌려주는 그대로다
        # (severity_llm._clean_ratings: level 1~5 정수 또는 None · matched_evidence 문자열,
        # session_change · followup_check_llm: 문자열 목록).
        "severity_ratings": [
            {
                "major_type": "신체학대",
                "level": 3,
                "reason": "가상 심각도 근거",
                "matched_evidence": "가상 발췌",
                "reviewed": False,
            },
            {"major_type": "방임", "level": None, "reason": "", "matched_evidence": "", "reviewed": False},
        ],
        "protective_factors": [
            {"category": "지지 관계", "text": "담임 선생님과 가깝다.", "segment_ids": ["seg_002"]},
        ],
        "session_change_notes": ["가상 회차 변화"],
        "followup_check_points": ["가상 확인사항"],
        # Contract 에 담지 않는 값 — 결과에 새지 않아야 한다.
        "full_text": "가상 전체 원문",
        "counseling_note": "가상 일지 본문",
        "checklist_draft": {"items": ["가상 체크리스트 항목"]},
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


def test_optional_fields_are_filled_from_module_output(modeling) -> None:
    """선택 필드 4개(#49)는 모듈 출력을 Contract 모양으로 옮긴다(#57).

    회차 간 변화 · 다음 확인사항은 문자열 목록이라 {text, segment_ids: []} 로 감싼다.
    근거 없는 항목 빼기는 위험 3필드에만 적용하므로 segment_ids 가 빈 항목도 남는다.
    """

    stored = ModelingAIAdapter().analyze(TRANSCRIPT).result.model_dump()

    assert stored["severity_ratings"] == [
        {
            "major_type": "신체학대",
            "level": 3,
            "reason": "가상 심각도 근거",
            "matched_evidence": "가상 발췌",
            "segment_ids": [],
            "reviewed": False,
        },
        {"major_type": "방임", "level": None, "reason": "", "matched_evidence": "", "segment_ids": [], "reviewed": False},
    ]
    assert stored["protective_factors"] == [
        {"category": "지지 관계", "text": "담임 선생님과 가깝다.", "segment_ids": ["seg_002"]},
    ]
    assert stored["session_change_notes"] == [{"text": "가상 회차 변화", "segment_ids": []}]
    assert stored["followup_check_points"] == [{"text": "가상 확인사항", "segment_ids": []}]


def test_module_only_fields_do_not_leak(modeling) -> None:
    """Contract 의 10개 키만 남고, 모듈만 쓰는 값(전체 원문 · 일지 본문 · 체크리스트)은 결과에 새지 않는다."""

    stored = ModelingAIAdapter().analyze(TRANSCRIPT).result.model_dump()

    assert set(stored) == {
        "schema_version",
        "summary",
        "risk_utterances",
        "abuse_signals",
        "risk_factors",
        "warnings",
        "severity_ratings",
        "protective_factors",
        "session_change_notes",
        "followup_check_points",
    }

    dumped = json.dumps(stored, ensure_ascii=False)

    for leaked in ("가상 전체 원문", "가상 일지 본문", "가상 체크리스트 항목"):
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
