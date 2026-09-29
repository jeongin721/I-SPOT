# LangGraph Agent Adapter 를 검증한다.
#
# 그래프 내부 동작은 tests/test_agent_graph.py 에서 본다.
# 여기서는 Backend 쪽 계약만 확인한다.
#
#   - AI_PROVIDER=langgraph 로 전환되는가
#   - 결과가 AI Output Contract 를 만족하는가
#   - 중간 산물이 Contract 밖으로 새지 않는가
#   - 근거 발화가 없는 위험 항목이 저장 전에 빠지는가
#   - 실패가 AIError 로 변환되고, 예외 문구가 저장·응답으로 새지 않는가

import logging

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.adapters.module_loader import ensure_repo_root_on_path

# langgraph 는 Backend 단독 실행에 필요 없는 선택 의존성이다.
# 설치되지 않은 환경에서는 이 파일을 통째로 건너뛴다.
#   pip install -r ../requirements-agent.txt
pytest.importorskip("langgraph")

# monkeypatch 가 "agent.graph.*" 를 찾으려면 최상위 경로가 필요하다.
# 이 줄이 없으면 파일 하나만 돌릴 때 앞선 테스트가 경로를 넣어 주지 않아 실패한다.
ensure_repo_root_on_path()

from agent.nodes import require_deidentified  # noqa: E402
from app.adapters.ai_adapter import (  # noqa: E402
    AIError,
    LangGraphAIAdapter,
    drop_ungrounded_risk_items,
    get_ai_adapter,
    set_ai_adapter_override,
)
from app.core.config import Settings, settings  # noqa: E402
from app.core.errors import ErrorCode  # noqa: E402
from app.schemas.contracts import AIAnalysisResult  # noqa: E402
from tests.test_analysis import _get_analysis, _run_analysis, confirmed_session  # noqa: E402

TRANSCRIPT = {
    "schema_version": "1.0",
    "segments": [
        {"segment_id": "seg_001", "speaker": "COUNSELOR", "text": "오늘 어땠어요?"},
        {"segment_id": "seg_002", "speaker": "CHILD", "text": "아빠가 때렸어요."},
    ],
}

LINKED_SIGNAL = {"abuse_type": "PHYSICAL", "detected": True, "segment_ids": ["seg_002"]}
UNLINKED_SIGNAL = {"abuse_type": "EMOTIONAL", "detected": True, "segment_ids": []}

DROPPED_WARNING = "segment 근거가 없는 신호"


@pytest.fixture
def use_langgraph(monkeypatch):
    monkeypatch.setattr(settings, "AI_PROVIDER", "langgraph")


def _patch_risk_node(monkeypatch, **fields):
    """risk_node 가 주어진 위험 필드를 돌려주도록 바꾼다(AI-02 전이라 본문이 비어 있다)."""

    result = {"risk_utterances": [], "abuse_signals": [], "risk_factors": []}
    result.update(fields)

    monkeypatch.setattr("agent.graph.risk_node", lambda state: dict(result))


def _raise_in_graph(monkeypatch, error: Exception) -> None:
    def boom(_payload):
        raise error

    monkeypatch.setattr("agent.graph.run", boom)


# =========================================================
# Provider 전환
# =========================================================

def test_factory_returns_langgraph_adapter(use_langgraph):
    assert get_ai_adapter().name == "langgraph"


def test_unknown_provider_is_rejected():
    """Literal 로 막아 두어 오타가 조용히 mock 으로 떨어지지 않는다."""

    with pytest.raises(ValidationError):
        Settings(AI_PROVIDER="langraph")  # 오타


# =========================================================
# Contract
# =========================================================

def test_result_satisfies_contract():
    bundle = LangGraphAIAdapter().analyze(TRANSCRIPT)

    assert bundle.provider == "langgraph"
    assert bundle.result.schema_version == "1.0"

    # 노드 본문이 비어 있는 동안에는 위험 필드가 빈 배열이다.
    assert bundle.result.risk_utterances == []
    assert bundle.result.abuse_signals == []
    assert bundle.result.risk_factors == []


def test_no_signal_means_no_warning():
    """검출된 신호가 없는 정상 상담에는 "근거 부족" 경고를 달지 않는다.

    신호가 없는 것은 근거가 부족한 것이 아니다. 경고가 붙으면 모든 상담에
    같은 경고가 달려 상담사가 경고를 무시하게 된다.
    """

    bundle = LangGraphAIAdapter().analyze(TRANSCRIPT)

    assert bundle.result.warnings == []


def test_gives_up_with_reason_not_silently(monkeypatch):
    """근거 발화가 끝내 연결되지 않으면 억지로 채우지 않고 사유를 남긴다.

    05_RULES.md §3 "근거 부족 시 빈 결과 허용", "결과를 억지로 생성하지 않음".
    """

    _patch_risk_node(monkeypatch, abuse_signals=[UNLINKED_SIGNAL])

    bundle = LangGraphAIAdapter().analyze(TRANSCRIPT)

    assert any("근거가 부족" in w for w in bundle.result.warnings)
    # 근거 없는 신호 자체는 저장 전에 빠진다.
    assert bundle.result.abuse_signals == []
    assert any(DROPPED_WARNING in w for w in bundle.result.warnings)


def test_intermediate_state_does_not_leak():
    """rag_documents / retry_count / deidentified 는 중간 산물이라 Contract 에 담지 않는다.

    05_RULES.md §3 "내부 chain-of-thought 를 결과 데이터로 저장하지 않음".
    """

    bundle = LangGraphAIAdapter().analyze(TRANSCRIPT)
    dumped = bundle.result.model_dump()

    assert "rag_documents" not in dumped
    assert "retry_count" not in dumped
    assert "deidentified" not in dumped
    assert "summary_evidence" not in dumped


# =========================================================
# 근거 없는 위험 항목 제외 (05_RULES.md §1)
# =========================================================

def test_items_without_segment_are_dropped_with_count(monkeypatch):
    """세 필드 모두에서 segment 근거가 빈 항목을 빼고, 뺀 건수를 남긴다."""

    grounded_utterance = {"segment_id": "seg_002", "text": "아빠가 때렸어요.", "reason": "체벌 진술"}

    _patch_risk_node(
        monkeypatch,
        risk_utterances=[grounded_utterance, {"segment_id": "", "reason": "근거 없음"}],
        abuse_signals=[LINKED_SIGNAL, UNLINKED_SIGNAL],
        risk_factors=[{"code": "RETALIATION_FEAR", "label": "보복 두려움"}],
    )

    bundle = LangGraphAIAdapter().analyze(TRANSCRIPT)

    assert bundle.result.risk_utterances == [grounded_utterance]
    assert bundle.result.abuse_signals == [LINKED_SIGNAL]
    assert bundle.result.risk_factors == []
    assert "segment 근거가 없는 신호 3건을 제외했습니다." in bundle.result.warnings


def test_items_pointing_to_unknown_segment_are_dropped(monkeypatch):
    """Transcript 에 없는 번호를 근거로 든 항목도 뺀다. 하나라도 없으면 뺀다."""

    _patch_risk_node(
        monkeypatch,
        risk_utterances=[{"segment_id": "seg_999", "reason": "없는 발화"}],
        abuse_signals=[{**LINKED_SIGNAL, "segment_ids": ["seg_002", "seg_999"]}],
        risk_factors=[{"code": "RETALIATION_FEAR", "segment_ids": ["seg_001"]}],
    )

    bundle = LangGraphAIAdapter().analyze(TRANSCRIPT)

    assert bundle.result.risk_utterances == []
    assert bundle.result.abuse_signals == []
    assert bundle.result.risk_factors == [
        {"code": "RETALIATION_FEAR", "segment_ids": ["seg_001"]}
    ]
    assert "segment 근거가 없는 신호 2건을 제외했습니다." in bundle.result.warnings


@pytest.mark.parametrize(
    "item",
    [
        pytest.param({"segment_ids": None}, id="None"),
        pytest.param({"segment_ids": [None]}, id="목록-안-None"),
        pytest.param({"segment_ids": [{"id": "seg_002"}]}, id="목록-안-객체"),
        pytest.param({"segment_id": 2}, id="숫자"),
    ],
)
def test_malformed_segment_refs_are_treated_as_ungrounded(item):
    """형식이 틀린 근거도 근거 없음으로 본다. 오류로 죽지 않는다."""

    result = AIAnalysisResult(abuse_signals=[item])

    filtered, dropped = drop_ungrounded_risk_items(result, TRANSCRIPT)

    assert dropped == 1
    assert filtered.abuse_signals == []


def test_not_detected_signals_are_kept_without_warning():
    """검출되지 않은 유형(detected=False)은 근거가 없어도 빼지 않고 경고도 달지 않는다.

    모델은 네 유형을 모두 내보낸다. 이것을 빼면 정상 상담마다
    "신호 4건을 제외" 경고가 붙는다.
    """

    not_detected = [
        {"type": abuse_type, "confidence": 0.1, "detected": False, "segment_ids": []}
        for abuse_type in ("PHYSICAL", "EMOTIONAL", "SEXUAL", "NEGLECT")
    ]
    result = AIAnalysisResult(abuse_signals=not_detected)

    filtered, dropped = drop_ungrounded_risk_items(result, TRANSCRIPT)

    assert dropped == 0
    assert filtered.abuse_signals == not_detected
    assert filtered.warnings == []


def test_grounded_result_is_left_untouched():
    """모두 근거가 있으면 결과를 바꾸지 않고 경고도 달지 않는다."""

    result = AIAnalysisResult(
        risk_utterances=[{"segment_id": "seg_002"}],
        abuse_signals=[{**LINKED_SIGNAL, "segment_ids": ["seg_001", "seg_002"]}],
        risk_factors=[{"segment_ids": ["seg_002"]}],
    )

    filtered, dropped = drop_ungrounded_risk_items(result, TRANSCRIPT)

    assert dropped == 0
    assert filtered == result
    assert filtered.warnings == []


# =========================================================
# summary_evidence
# =========================================================

def test_summary_evidence_is_carried_to_bundle(monkeypatch):
    """PipelineAIAdapter 와 같은 방식으로 summary_evidence 를 옮긴다."""

    key_point = "아버지의 체벌 진술"

    monkeypatch.setattr(
        "agent.graph.analysis_node",
        lambda state: {
            "summary": {"overview": "", "key_points": [key_point]},
            "summary_evidence": [
                {"text": key_point, "segment_ids": ["seg_002"], "score": 0.8}
            ],
        },
    )

    bundle = LangGraphAIAdapter().analyze(TRANSCRIPT)

    [evidence] = bundle.summary_evidence
    assert (evidence.key_point, evidence.segment_ids, evidence.score) == (
        key_point,
        ["seg_002"],
        0.8,
    )


def test_malformed_summary_evidence_is_invalid_output(monkeypatch):
    monkeypatch.setattr(
        "agent.graph.analysis_node",
        lambda state: {
            "summary": {"overview": "", "key_points": []},
            "summary_evidence": [{"text": "요약", "score": "높음"}],
        },
    )

    with pytest.raises(AIError) as exc:
        LangGraphAIAdapter().analyze(TRANSCRIPT)

    assert exc.value.error_code == ErrorCode.AI_INVALID_OUTPUT


# =========================================================
# 실패 처리
# =========================================================

@pytest.mark.parametrize(
    "payload",
    [
        pytest.param({}, id="빈-payload"),
        pytest.param({"schema_version": "1.0", "segments": []}, id="segments-빈-배열"),
    ],
)
def test_empty_transcript_is_rejected(payload):
    """빈 Transcript 는 거부한다. MockAIAdapter 와 같은 규약이다.

    통과시키면 "근거 부족" 경고만 달린 정상 결과처럼 저장되어, 상류(STT/
    검수)가 깨진 것이 묻힌다. AI_PROVIDER 를 바꿨다고 오류 동작이 달라지면
    어댑터를 바꿔 끼울 수 없다.
    """

    with pytest.raises(AIError) as exc:
        LangGraphAIAdapter().analyze(payload)

    assert exc.value.error_code == ErrorCode.AI_INVALID_OUTPUT


def test_empty_transcript_matches_mock_behaviour():
    """두 어댑터가 같은 오류 코드를 낸다."""

    from app.adapters.ai_adapter import MockAIAdapter

    payload = {"schema_version": "1.0", "segments": []}

    with pytest.raises(AIError) as mock_exc:
        MockAIAdapter().analyze(payload)

    with pytest.raises(AIError) as graph_exc:
        LangGraphAIAdapter().analyze(payload)

    assert mock_exc.value.error_code == graph_exc.value.error_code


def test_graph_failure_becomes_ai_error(monkeypatch):
    """어댑터는 상태 전이를 하지 않고 AIError 만 던진다.

    세션 마감은 analysis_service 가 한다.
    """

    _raise_in_graph(monkeypatch, RuntimeError("그래프 폭발"))

    with pytest.raises(AIError) as exc:
        LangGraphAIAdapter().analyze(TRANSCRIPT)

    assert exc.value.error_code == ErrorCode.AI_FAILED


def test_graph_failure_message_hides_exception_text(monkeypatch):
    """알 수 없는 예외는 고정 문구와 예외 종류 이름만 담는다.

    예외 문구에는 상담 발화가 섞일 수 있는데 AIError 문구는 DB 와 응답까지 간다.
    """

    _raise_in_graph(monkeypatch, RuntimeError("아빠가 때렸어요 라는 발화 처리 중 오류"))

    with pytest.raises(AIError) as exc:
        LangGraphAIAdapter().analyze(TRANSCRIPT)

    message = str(exc.value)
    assert "아빠가 때렸어요" not in message
    assert "RuntimeError" in message
    assert isinstance(exc.value.__cause__, RuntimeError), "원인은 로그용으로 이어 둔다"


def test_known_ai_error_keeps_its_code(monkeypatch):
    """PipelineAIAdapter 와 같은 변환표를 쓴다."""

    timeout = type("SummaryTimeoutError", (Exception,), {})
    _raise_in_graph(monkeypatch, timeout("LLM 상담 요약 요청 시간이 초과되었습니다."))

    with pytest.raises(AIError) as exc:
        LangGraphAIAdapter().analyze(TRANSCRIPT)

    assert exc.value.error_code == ErrorCode.AI_TIMEOUT


def test_llm_node_before_deidentification_fails_safely(monkeypatch):
    """비식별 전에 외부 LLM 을 부르려는 노드는 AI_FAILED 로 멈춘다(9/18 회의 결정)."""

    def analysis_calling_llm(state):
        require_deidentified(state)
        return {"summary": {"overview": "", "key_points": []}}

    monkeypatch.setattr("agent.graph.analysis_node", analysis_calling_llm)

    with pytest.raises(AIError) as exc:
        LangGraphAIAdapter().analyze(TRANSCRIPT)

    assert exc.value.error_code == ErrorCode.AI_FAILED
    assert "DeidentificationRequiredError" in str(exc.value)


def test_graph_failure_detail_is_logged_with_session_id_not_stored(
    client: TestClient,
    counselor_headers,
    session: dict,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """예외 문구는 저장·응답에 싣지 않고, session_id 와 함께 로그에만 남긴다."""

    secret = "아빠가 때렸어요 라는 발화 처리 중 오류"

    confirmed_session(client, counselor_headers, session["id"])
    set_ai_adapter_override(LangGraphAIAdapter())
    _raise_in_graph(monkeypatch, RuntimeError(secret))

    with caplog.at_level(logging.ERROR):
        assert _run_analysis(client, counselor_headers, session["id"]).status_code == 202

    envelope = _get_analysis(client, counselor_headers, session["id"]).json()["data"]

    assert envelope["error"]["code"] == "AI_FAILED"
    assert secret not in envelope["error"]["message"]
    assert "RuntimeError" in envelope["error"]["message"]

    logged = [r for r in caplog.records if r.exc_info and session["id"] in r.getMessage()]
    assert logged, "원인 예외를 session_id 와 함께 남겨야 한다"
    assert secret in caplog.text
