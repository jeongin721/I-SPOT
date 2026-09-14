# 실제 AI 연결 경로(PipelineAIAdapter) 테스트.
#
# 다른 Backend 테스트는 conftest.py 가 AI_PROVIDER=mock 으로 고정해서, 운영에서 쓰는
# PipelineAIAdapter.analyze → _to_bundle 이 한 번도 실행되지 않았다. 그래서 AI 결과 형식이
# Backend Contract 와 어긋나도 테스트가 통과했다(ai-modeling 의 key_points 변경이 그 예).
#
# LLM 을 부르는 run_analysis_pipeline 하나만 가짜로 바꾸고 나머지는 실제 코드를 쓴다.
#   - ai/schemas, ai/services/evidence_linker 는 pydantic 만 써서 CI 에서도 import 된다.
#   - ai/services/analysis_pipeline 은 openai 가 필요한데 CI 에 없으므로 가짜 모듈로 바꾼다.

import sys
import types
from typing import Any, Dict

import pytest
from fastapi.testclient import TestClient

from app.adapters.ai_adapter import AIError, PipelineAIAdapter, set_ai_adapter_override
from app.adapters.module_loader import ensure_repo_root_on_path
from app.core.errors import ErrorCode
from app.schemas.contracts import AIAnalysisResult
from tests.test_analysis import _get_analysis, _run_analysis, confirmed_session

ensure_repo_root_on_path()

from ai.schemas.analysis import AIAnalysisOutput, Summary  # noqa: E402
from ai.services.evidence_linker import EvidenceLink  # noqa: E402

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
    ],
}

KEY_POINT = "아동이 보호자의 체벌을 진술함"

# ai-modeling 브랜치가 쓰는 형식. key_points 가 문자열이 아니라 객체다.
CONTRACT_BREAKING_ANALYSIS = {
    "schema_version": "1.0",
    "summary": {
        "overview": "아동이 보호자의 체벌을 진술함.",
        "key_points": [{"point": KEY_POINT, "segment_ids": ["seg_002"]}],
    },
}


# =========================================================
# 가짜 pipeline
# =========================================================

def _valid_analysis() -> AIAnalysisOutput:
    """ai 패키지의 실제 Schema 로 만든 정상 결과."""

    return AIAnalysisOutput(
        summary=Summary(overview="아동이 보호자의 체벌을 진술함.", key_points=[KEY_POINT])
    )


def _pipeline_result(analysis: Any, evidence=None) -> types.SimpleNamespace:
    """run_analysis_pipeline 의 반환값(AnalysisPipelineResult) 과 같은 모양."""

    return types.SimpleNamespace(analysis=analysis, summary_evidence=evidence or [])


@pytest.fixture
def pipeline(monkeypatch: pytest.MonkeyPatch) -> Dict[str, Any]:
    """ai.services.analysis_pipeline 을 가짜 모듈로 바꾼다.

    result 에 값 또는 transcript 를 받는 함수를, error 에 예외를 넣어 동작을 정한다.
    calls 에는 pipeline 이 받은 Transcript 가 쌓인다.
    """

    state: Dict[str, Any] = {"result": None, "error": None, "calls": []}

    def run_analysis_pipeline(transcript):
        state["calls"].append(transcript)

        if state["error"] is not None:
            raise state["error"]

        result = state["result"]
        return result(transcript) if callable(result) else result

    module = types.ModuleType("ai.services.analysis_pipeline")
    module.run_analysis_pipeline = run_analysis_pipeline
    monkeypatch.setitem(sys.modules, "ai.services.analysis_pipeline", module)

    return state


# =========================================================
# 형식 일치 — ai 결과 Schema ↔ Backend Contract
# =========================================================

def _shape(schema: Dict[str, Any], node: Dict[str, Any]) -> Any:
    """JSON Schema 에서 설명·기본값을 빼고 구조(키와 타입)만 남긴다."""

    while "$ref" in node:
        node = schema["$defs"][node["$ref"].split("/")[-1]]

    if "const" in node:
        return {"const": node["const"]}

    if node.get("type") == "array":
        return [_shape(schema, node.get("items", {}))]

    if node.get("type") == "object" and "properties" in node:
        return {key: _shape(schema, value) for key, value in node["properties"].items()}

    return node.get("type", "any")


def test_ai_output_schema_matches_backend_contract() -> None:
    """ai 패키지의 결과 형식이 Backend AI Output Contract 와 같아야 한다.

    어긋나면 운영에서 _to_bundle 이 모든 분석을 AI_INVALID_OUTPUT 으로 실패시킨다.
    이 테스트가 깨지면 ai/schemas/analysis.py 와 backend/app/schemas/contracts.py 중
    한쪽만 바뀐 것이다. Contract 변경은 02_ARCHITECTURE.md §8 절차를 따른다.
    """

    ai_schema = AIAnalysisOutput.model_json_schema()
    backend_schema = AIAnalysisResult.model_json_schema()

    assert _shape(ai_schema, ai_schema) == _shape(backend_schema, backend_schema)


# =========================================================
# Adapter 단위 — analyze → _to_bundle
# =========================================================

def test_pipeline_result_is_converted_to_bundle(pipeline) -> None:
    pipeline["result"] = _pipeline_result(
        _valid_analysis(),
        [EvidenceLink(text=KEY_POINT, segment_ids=["seg_002"], score=0.8)],
    )

    bundle = PipelineAIAdapter().analyze(TRANSCRIPT)

    assert bundle.provider == "pipeline"
    assert bundle.result.summary.key_points == [KEY_POINT]
    assert bundle.result == AIAnalysisResult.model_validate(_valid_analysis().model_dump())

    assert len(bundle.summary_evidence) == 1
    evidence = bundle.summary_evidence[0]
    assert (evidence.key_point, evidence.segment_ids, evidence.score) == (
        KEY_POINT,
        ["seg_002"],
        0.8,
    )

    # pipeline 은 ai 패키지의 Transcript 로 변환된 입력을 받는다.
    [transcript] = pipeline["calls"]
    assert [s.segment_id for s in transcript.segments] == ["seg_001", "seg_002"]


def test_output_breaking_contract_becomes_invalid_output_error(pipeline) -> None:
    """ai 쪽 형식이 바뀌면 조용히 저장되지 않고 AI_INVALID_OUTPUT 으로 막힌다."""

    pipeline["result"] = _pipeline_result(CONTRACT_BREAKING_ANALYSIS)

    with pytest.raises(AIError) as raised:
        PipelineAIAdapter().analyze(TRANSCRIPT)

    assert raised.value.error_code == ErrorCode.AI_INVALID_OUTPUT


def test_result_without_analysis_is_invalid_output(pipeline) -> None:
    pipeline["result"] = types.SimpleNamespace(summary_evidence=[])

    with pytest.raises(AIError) as raised:
        PipelineAIAdapter().analyze(TRANSCRIPT)

    assert raised.value.error_code == ErrorCode.AI_INVALID_OUTPUT


def test_transcript_ai_cannot_read_is_rejected_before_pipeline(pipeline) -> None:
    broken = {
        "schema_version": "1.0",
        "segments": [{"segment_id": "seg_001", "speaker": "CHILD", "text": "..."}],
    }

    with pytest.raises(AIError) as raised:
        PipelineAIAdapter().analyze(broken)

    assert raised.value.error_code == ErrorCode.AI_INVALID_OUTPUT
    assert pipeline["calls"] == [], "입력이 틀리면 LLM 을 부르지 않는다"


def test_pipeline_exception_is_mapped_during_analyze(pipeline) -> None:
    """오류 코드 변환이 analyze 경로에서도 적용된다(기존 테스트는 변환 함수만 확인)."""

    pipeline["error"] = type("SummaryTimeoutError", (Exception,), {})("LLM 응답 시간 초과")

    with pytest.raises(AIError) as raised:
        PipelineAIAdapter().analyze(TRANSCRIPT)

    assert raised.value.error_code == ErrorCode.AI_TIMEOUT


def test_missing_ai_package_is_reported_as_ai_failed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "ai.services.analysis_pipeline", None)

    with pytest.raises(AIError) as raised:
        PipelineAIAdapter().analyze(TRANSCRIPT)

    assert raised.value.error_code == ErrorCode.AI_FAILED


# =========================================================
# API 전체 흐름 — 분석 요청 → Background 처리 → 저장
# =========================================================

def test_pipeline_result_is_stored_through_api(
    client: TestClient, counselor_headers, session: dict, pipeline
) -> None:
    confirmed_session(client, counselor_headers, session["id"])
    set_ai_adapter_override(PipelineAIAdapter())

    pipeline["result"] = lambda transcript: _pipeline_result(
        _valid_analysis(),
        [EvidenceLink(text=KEY_POINT, segment_ids=[transcript.segments[0].segment_id], score=0.8)],
    )

    assert _run_analysis(client, counselor_headers, session["id"]).status_code == 202

    envelope = _get_analysis(client, counselor_headers, session["id"]).json()["data"]

    assert envelope["session_status"] == "AI_REVIEW_REQUIRED"

    analysis = envelope["analysis"]
    assert analysis["status"] == "COMPLETED"
    assert analysis["provider"] == "pipeline"
    assert analysis["result"]["summary"]["key_points"] == [KEY_POINT]

    [transcript] = pipeline["calls"]
    assert analysis["summary_evidence"][0]["segment_ids"] == [transcript.segments[0].segment_id]


def test_contract_break_fails_session_instead_of_hanging(
    client: TestClient, counselor_headers, session: dict, pipeline
) -> None:
    """형식이 어긋난 결과가 오면 세션이 처리 중에 멈추지 않고 실패로 마감된다."""

    confirmed_session(client, counselor_headers, session["id"])
    set_ai_adapter_override(PipelineAIAdapter())
    pipeline["result"] = _pipeline_result(CONTRACT_BREAKING_ANALYSIS)

    assert _run_analysis(client, counselor_headers, session["id"]).status_code == 202

    envelope = _get_analysis(client, counselor_headers, session["id"]).json()["data"]

    assert envelope["session_status"] == "AI_FAILED"
    assert envelope["error"]["code"] == "AI_INVALID_OUTPUT"
    assert envelope["analysis"]["status"] == "FAILED"
    assert envelope["analysis"]["result"] is None
