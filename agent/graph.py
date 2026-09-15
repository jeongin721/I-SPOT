# LangGraph Agent 그래프 배선.
#
# 설계 근거: I-SPOT_DOCS/docs/PLAN_langgraph_agent.md §4-2
#
#   START → analysis_node → risk_node ─┬─[sufficient]───→ report_node → END
#                                      │
#                                      └─[insufficient]─→ rag_node
#                                                            ↓
#                                                      reanalysis_node
#                                                            │
#                                           (같은 라우터를 다시 통과)
#
# stt_node 는 그래프에 없다. STT 는 분 단위로 걸리고 중간에 상담사 검수
# 단계가 있어, 그래프가 블로킹되거나 사람 개입에서 멈춘다. 그래프는
# STT_CONFIRMED 이후, 즉 Backend 어댑터가 호출되는 시점부터 시작한다.
#
# evidence_check 는 노드가 아니라 조건부 엣지 함수(라우터)다.

from typing import Any, Dict

from langgraph.graph import END, START, StateGraph

from agent.nodes import (
    analysis_node,
    rag_node,
    reanalysis_node,
    report_node,
    risk_node,
    route_after_risk,
)
from agent.state import AgentState, initial_state

_ROUTES = {
    "sufficient": "report_node",
    "insufficient": "rag_node",
}


def build_graph():
    """그래프를 조립해 컴파일한다."""

    graph = StateGraph(AgentState)

    graph.add_node("analysis_node", analysis_node)
    graph.add_node("risk_node", risk_node)
    graph.add_node("rag_node", rag_node)
    graph.add_node("reanalysis_node", reanalysis_node)
    graph.add_node("report_node", report_node)

    graph.add_edge(START, "analysis_node")
    graph.add_edge("analysis_node", "risk_node")

    # 위험 판정 뒤와 재분석 뒤에 같은 라우터를 붙인다.
    graph.add_conditional_edges("risk_node", route_after_risk, _ROUTES)
    graph.add_conditional_edges("reanalysis_node", route_after_risk, _ROUTES)

    graph.add_edge("rag_node", "reanalysis_node")
    graph.add_edge("report_node", END)

    return graph.compile()


def run(transcript: Dict[str, Any]) -> AgentState:
    """Transcript 하나를 그래프에 태워 최종 State 를 돌려준다."""

    return build_graph().invoke(initial_state(transcript))


__all__ = ["build_graph", "run"]
