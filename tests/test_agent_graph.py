# LangGraph Agent 그래프의 배선을 검증한다.
#
# 노드 본문은 아직 비어 있으므로(AI-02 대기) 여기서 확인하는 것은
# "값이 맞는가" 가 아니라 "구조가 의도대로 도는가" 다.
#
#   - 근거가 충분하면 재분석 없이 끝나는가
#   - 근거가 부족해도 MAX_RETRY 에서 멈추는가 (무한 루프 방지)
#   - reducer 구분이 맞는가 (누적 vs 교체)

import pytest

from agent.graph import build_graph
from agent.nodes import MAX_RETRY, evidence_verdict, route_after_risk
from agent.state import initial_state

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


# =========================================================
# 판정 함수
# =========================================================

def test_verdict_requires_detected_signal():
    state = initial_state(TRANSCRIPT)
    assert evidence_verdict(state) == "insufficient"

    state["abuse_signals"] = [DETECTED_SIGNAL]
    assert evidence_verdict(state) == "sufficient"


def test_verdict_requires_segment_link():
    """근거 발화가 연결되지 않은 판정은 충분으로 보지 않는다.

    05_RULES.md §1 "근거 없는 위험 신호 생성" 금지에 따른다.
    """

    state = initial_state(TRANSCRIPT)
    state["abuse_signals"] = [{**DETECTED_SIGNAL, "segment_ids": []}]

    assert evidence_verdict(state) == "insufficient"


def test_verdict_tolerates_missing_keys():
    """구조 합의 전이거나 AI 가 필드를 빠뜨려도 KeyError 로 죽지 않는다."""

    state = initial_state(TRANSCRIPT)
    state["abuse_signals"] = [{"abuse_type": "PHYSICAL"}]

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
    state["retry_count"] = MAX_RETRY

    assert evidence_verdict(state) == "insufficient"
    assert route_after_risk(state) == "sufficient"


# =========================================================
# 그래프 전체
# =========================================================

def test_graph_terminates_without_evidence():
    """근거가 없어도 무한 루프에 빠지지 않는다."""

    out = build_graph().invoke(initial_state(TRANSCRIPT))

    assert out["retry_count"] == MAX_RETRY
    assert any("근거가 부족한" in w for w in out["warnings"])


def _with_detected_risk_node(monkeypatch):
    """risk_node 가 검출된 신호를 돌려주도록 바꾼다.

    초기 State 에 값을 넣는 방식은 통하지 않는다. risk_node 가 먼저 돌면서
    abuse_signals 를 덮어쓰기 때문이다(reducer 가 없으므로 의도된 동작).
    AI-02 가 노드 본문을 채우면 이 patch 없이도 같은 경로를 타게 된다.
    """

    monkeypatch.setattr(
        "agent.graph.risk_node",
        lambda state: {
            "risk_utterances": [],
            "abuse_signals": [DETECTED_SIGNAL],
            "risk_factors": [],
        },
    )


def test_graph_skips_reanalysis_when_evidence_sufficient(monkeypatch):
    """근거가 충분하면 재분석을 돌지 않는다."""

    _with_detected_risk_node(monkeypatch)

    out = build_graph().invoke(initial_state(TRANSCRIPT))

    assert out["retry_count"] == 0
    assert out["warnings"] == []


def test_risk_fields_are_replaced_not_accumulated(monkeypatch):
    """위험 필드에 reducer 가 붙어 있지 않아야 한다.

    누적되면 재분석마다 같은 근거가 중복으로 쌓인다. 오류가 나지 않고
    조용히 늘어나므로 테스트로 고정한다.
    """

    _with_detected_risk_node(monkeypatch)

    out = build_graph().invoke(initial_state(TRANSCRIPT))

    assert len(out["abuse_signals"]) == 1
