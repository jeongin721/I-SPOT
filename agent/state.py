# LangGraph Agent 의 State 정의.
#
# 설계 근거: I-SPOT_DOCS/docs/PLAN_langgraph_agent.md §4-3
#
# reducer 를 붙일지 말지가 이 파일의 핵심이다. langgraph 1.2.11 로 직접
# 확인한 동작은 다음과 같다.
#
#   Annotated[list, operator.add]  →  노드가 돌려준 값이 누적된다
#   reducer 없음                    →  나중에 쓴 노드가 앞의 값을 덮어쓴다
#
# 덮어쓰기는 오류 없이 조용히 일어나므로, 구분을 틀리면 재분석이 이전
# 결과를 지워도 아무도 모른다.

import operator
from typing import Annotated, Any, Dict, List, TypedDict


class AgentState(TypedDict, total=False):
    """상담 1회차 분석이 그래프를 도는 동안 들고 다니는 값."""

    # -----------------------------------------------------
    # 입력
    # -----------------------------------------------------
    # STT 확정 후의 Transcript. 그래프는 이 값을 바꾸지 않는다.
    transcript: Dict[str, Any]

    # -----------------------------------------------------
    # 교체되는 값 (reducer 없음)
    # -----------------------------------------------------
    # 재분석이 돌면 이전 판정을 대체해야 하므로 누적하지 않는다.
    # 누적시키면 같은 근거가 중복으로 쌓인다.
    summary: Dict[str, Any]
    risk_utterances: List[Dict[str, Any]]
    abuse_signals: List[Dict[str, Any]]
    risk_factors: List[Dict[str, Any]]

    # -----------------------------------------------------
    # 누적되는 값 (reducer 있음)
    # -----------------------------------------------------
    # RAG 는 돌 때마다 새 문서를 가져오므로 쌓여야 한다.
    rag_documents: Annotated[List[Dict[str, Any]], operator.add]

    # 각 노드가 남기는 사유. 마지막 노드 것만 남으면 안 된다.
    warnings: Annotated[List[str], operator.add]

    # 노드가 1 을 돌려주면 reducer 가 더한다. 루프 종료 판단에 쓴다.
    retry_count: Annotated[int, operator.add]


def initial_state(transcript: Dict[str, Any]) -> AgentState:
    """그래프 진입값. reducer 가 붙은 키는 빈 값으로 시작해야 한다."""

    return AgentState(
        transcript=transcript,
        summary={},
        risk_utterances=[],
        abuse_signals=[],
        risk_factors=[],
        rag_documents=[],
        warnings=[],
        retry_count=0,
    )


__all__ = ["AgentState", "initial_state"]
