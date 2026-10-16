# LangGraph Agent 그래프의 배선을 검증한다.
#
# 노드 본문은 아직 비어 있으므로(AI-02 대기) 여기서 확인하는 것은
# "값이 맞는가" 가 아니라 "구조가 의도대로 도는가" 다.
#
#   - 검출된 신호가 없으면 재분석 없이, 경고 없이 끝나는가
#   - 근거가 충분하면 재분석 없이 끝나는가
#   - 근거가 부족해도 MAX_RETRY 에서 멈추는가 (무한 루프 방지)
#   - reducer 구분이 맞는가 (누적 vs 교체)
#   - 비식별 전에는 외부 LLM 을 부를 수 없는가 (9/18 회의 결정)
#
# 이 파일은 원래 최상위 tests/ 에 있었는데, CI 와 scripts/check.sh 는
# backend/ 에서 pytest 를 돌려 이 파일을 한 번도 실행하지 않았다.
# 그래서 backend/tests 로 옮겼다. agent/ 는 저장소 최상위에 있으므로
# import 전에 최상위 경로를 sys.path 에 넣는다.

import pytest

from app.adapters.module_loader import ensure_repo_root_on_path

# langgraph 는 선택 의존성이다. 설치되지 않은 환경에서는 건너뛴다.
#   pip install -r ../requirements-agent.txt
pytest.importorskip("langgraph")

ensure_repo_root_on_path()

from agent.graph import build_graph  # noqa: E402
from agent.nodes import (  # noqa: E402
    MAX_RETRY,
    DeidentificationRequiredError,
    evidence_verdict,
    require_deidentified,
    route_after_risk,
)
from agent.state import initial_state  # noqa: E402

TRANSCRIPT = {
    "schema_version": "1.0",
    "segments": [
        {"segment_id": "seg_001", "speaker": "COUNSELOR", "text": "오늘 어땠어요?"},
        {"segment_id": "seg_002", "speaker": "CHILD", "text": "아빠가 때렸어요."},
    ],
}

DETECTED_SIGNAL = {
    "abuse_type": "PHYSICAL",
    "confidence": 0.72,
    "threshold": 0.72,
    "detected": True,
    "segment_ids": ["seg_002"],
}

# 검출됐지만 근거 발화가 연결되지 않은 신호. "근거 부족" 의 실제 모습이다.
UNLINKED_SIGNAL = {**DETECTED_SIGNAL, "abuse_type": "EMOTIONAL", "segment_ids": []}


# =========================================================
# 판정 함수
# =========================================================

def test_verdict_is_none_without_detected_signal():
    """검출된 신호가 없으면 부족이 아니라 "none" 이다.

    부족으로 보면 정상 상담도 재분석을 MAX_RETRY 번 돌고
    "근거가 부족" 경고가 붙는다.
    """

    state = initial_state(TRANSCRIPT)
    assert evidence_verdict(state) == "none"

    state["abuse_signals"] = [{**DETECTED_SIGNAL, "detected": False}]
    assert evidence_verdict(state) == "none"


def test_verdict_is_sufficient_when_every_detected_signal_is_linked():
    state = initial_state(TRANSCRIPT)
    state["abuse_signals"] = [DETECTED_SIGNAL]

    assert evidence_verdict(state) == "sufficient"


def test_verdict_requires_segment_link():
    """근거 발화가 연결되지 않은 판정은 충분으로 보지 않는다.

    05_RULES.md §1 "근거 없는 위험 신호 생성" 금지에 따른다.
    """

    state = initial_state(TRANSCRIPT)
    state["abuse_signals"] = [UNLINKED_SIGNAL]

    assert evidence_verdict(state) == "insufficient"


def test_verdict_is_insufficient_if_any_detected_signal_is_unlinked():
    """연결된 신호가 하나 있어도, 연결 안 된 검출 신호가 남아 있으면 부족이다."""

    state = initial_state(TRANSCRIPT)
    state["abuse_signals"] = [DETECTED_SIGNAL, UNLINKED_SIGNAL]

    assert evidence_verdict(state) == "insufficient"


def test_verdict_tolerates_missing_keys():
    """구조 합의 전이거나 AI 가 필드를 빠뜨려도 KeyError 로 죽지 않는다."""

    state = initial_state(TRANSCRIPT)

    state["abuse_signals"] = [{"abuse_type": "PHYSICAL"}]
    assert evidence_verdict(state) == "none"

    state["abuse_signals"] = [{"detected": True}]
    assert evidence_verdict(state) == "insufficient"


@pytest.mark.parametrize("threshold", [0.32, 0.39, 0.53, 0.72])
def test_verdict_does_not_apply_its_own_threshold(threshold):
    """Agent 는 확신도 기준을 따로 두지 않는다.

    학대 유형별 임계값이 0.32~0.72 로 다르고 모델 버전마다 또 달라서,
    Agent 가 단일 기준을 두면 일부 유형을 놓친다. 모델이 계산한
    detected 만 본다. confidence 가 얼마든 detected 면 충분이다.
    """

    state = initial_state(TRANSCRIPT)
    state["abuse_signals"] = [
        {**DETECTED_SIGNAL, "confidence": threshold, "threshold": threshold}
    ]

    assert evidence_verdict(state) == "sufficient"


# =========================================================
# 라우터
# =========================================================

def test_router_gives_up_at_max_retry():
    """한도에 닿으면 부족하더라도 결과 작성으로 보낸다."""

    state = initial_state(TRANSCRIPT)
    state["abuse_signals"] = [UNLINKED_SIGNAL]
    state["retry_count"] = MAX_RETRY

    assert evidence_verdict(state) == "insufficient"
    assert route_after_risk(state) == "sufficient"


# =========================================================
# 그래프 전체
# =========================================================

def _patch_risk_node(monkeypatch, signals):
    """risk_node 가 주어진 신호를 돌려주도록 바꾼다.

    초기 State 에 값을 넣는 방식은 통하지 않는다. risk_node 가 먼저 돌면서
    abuse_signals 를 덮어쓰기 때문이다(reducer 가 없으므로 의도된 동작).
    AI-02 가 노드 본문을 채우면 이 patch 없이도 같은 경로를 타게 된다.
    """

    monkeypatch.setattr(
        "agent.graph.risk_node",
        lambda state: {
            "risk_utterances": [],
            "abuse_signals": list(signals),
            "risk_factors": [],
        },
    )


def test_graph_without_signals_skips_reanalysis_and_warning():
    """검출된 신호가 없는 정상 상담은 재분석도, 경고도 없이 끝난다."""

    out = build_graph().invoke(initial_state(TRANSCRIPT))

    assert out["retry_count"] == 0
    assert out["warnings"] == []


def test_graph_terminates_when_evidence_stays_unlinked(monkeypatch):
    """근거 발화가 끝내 연결되지 않아도 무한 루프에 빠지지 않고 사유를 남긴다."""

    _patch_risk_node(monkeypatch, [UNLINKED_SIGNAL])

    out = build_graph().invoke(initial_state(TRANSCRIPT))

    assert out["retry_count"] == MAX_RETRY
    assert any("근거가 부족한" in w for w in out["warnings"])


def test_graph_skips_reanalysis_when_evidence_sufficient(monkeypatch):
    """근거가 충분하면 재분석을 돌지 않는다."""

    _patch_risk_node(monkeypatch, [DETECTED_SIGNAL])

    out = build_graph().invoke(initial_state(TRANSCRIPT))

    assert out["retry_count"] == 0
    assert out["warnings"] == []


def test_risk_fields_are_replaced_not_accumulated(monkeypatch):
    """위험 필드에 reducer 가 붙어 있지 않아야 한다.

    누적되면 재분석마다 같은 근거가 중복으로 쌓인다. 오류가 나지 않고
    조용히 늘어나므로 테스트로 고정한다.
    """

    _patch_risk_node(monkeypatch, [DETECTED_SIGNAL])

    out = build_graph().invoke(initial_state(TRANSCRIPT))

    assert len(out["abuse_signals"]) == 1


def test_summary_evidence_is_carried_to_final_state(monkeypatch):
    """요약 근거가 State 를 거쳐 최종 결과까지 온다. 교체형이라 한 번만 담긴다."""

    link = {"text": "아버지의 체벌 진술", "segment_ids": ["seg_002"], "score": 0.8}

    monkeypatch.setattr(
        "agent.graph.analysis_node",
        lambda state: {
            "summary": {"overview": "", "key_points": [link["text"]]},
            "summary_evidence": [link],
        },
    )

    out = build_graph().invoke(initial_state(TRANSCRIPT))

    assert initial_state(TRANSCRIPT)["summary_evidence"] == []
    assert out["summary_evidence"] == [link]


# =========================================================
# 비식별 (9/18 회의 결정: 외부 LLM 에는 로컬에서 비식별한 텍스트만)
# =========================================================

def test_graph_leaves_deidentified_false_until_masking_is_connected():
    """비식별을 아직 연결하지 않았으므로 완료로 표시하지 않는다. 원문도 그대로다."""

    out = build_graph().invoke(initial_state(TRANSCRIPT))

    assert out["deidentified"] is False
    assert out["transcript"] == TRANSCRIPT


@pytest.mark.parametrize(
    "state",
    [
        pytest.param(initial_state(TRANSCRIPT), id="초기값-False"),
        pytest.param({"transcript": TRANSCRIPT}, id="키-없음"),
        pytest.param({"deidentified": "yes"}, id="True-아닌-값"),
    ],
)
def test_require_deidentified_blocks_raw_text(state):
    """비식별 완료가 확실하지 않으면 모두 막는다."""

    with pytest.raises(DeidentificationRequiredError):
        require_deidentified(state)


def test_require_deidentified_passes_after_masking():
    require_deidentified({"deidentified": True})


def test_external_llm_node_is_blocked_before_deidentification(monkeypatch):
    """외부 LLM 을 부르는 노드는 호출 전에 막히고, 호출은 일어나지 않는다."""

    sent = []

    def analysis_calling_llm(state):
        require_deidentified(state)
        sent.append(state["transcript"])
        return {"summary": {"overview": "", "key_points": []}}

    monkeypatch.setattr("agent.graph.analysis_node", analysis_calling_llm)

    with pytest.raises(DeidentificationRequiredError):
        build_graph().invoke(initial_state(TRANSCRIPT))

    assert sent == []


def test_deidentify_node_runs_before_analysis(monkeypatch):
    """비식별 노드가 맨 앞에 있어, 완료로 표시하면 뒤 노드가 통과한다."""

    monkeypatch.setattr(
        "agent.graph.deidentify_node", lambda state: {"deidentified": True}
    )

    def analysis_calling_llm(state):
        require_deidentified(state)
        return {"summary": {"overview": "", "key_points": []}}

    monkeypatch.setattr("agent.graph.analysis_node", analysis_calling_llm)

    out = build_graph().invoke(initial_state(TRANSCRIPT))

    assert out["deidentified"] is True
