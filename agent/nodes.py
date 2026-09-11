# LangGraph Agent 의 노드와 라우터.
#
# 설계 근거: I-SPOT_DOCS/docs/PLAN_langgraph_agent.md §4-1, §4-5, §4-6
#
# 노드와 라우터는 반환 타입이 다르다.
#
#   노드   (state) -> dict   State 중 바뀐 부분만 돌려준다
#   라우터 (state) -> str    다음 목적지 이름만 돌려준다. State 를 바꾸지 않는다
#
# 라우터 안에서 State 를 고치면 반영되지 않는다(langgraph 1.2.11 로 확인).
# 기록이 필요하면 노드에서 한다.
#
# 현재 노드 본문은 비어 있다. 값을 채우는 것은 AI 담당(TASKS.md AI-02)이고,
# 이 파일은 그래프가 실제로 도는지 검증할 수 있는 골격을 제공한다.

from typing import Dict, List

from agent.state import AgentState

# 재분석 최대 횟수.
#
# evidence_check -> rag -> reanalysis -> evidence_check 는 닫힌 고리다.
# 이 값이 없으면 무한 루프가 되고, 매 바퀴가 LLM 호출이라 비용도 계속 든다.
MAX_RETRY = 2


# =========================================================
# 노드
# =========================================================

def analysis_node(state: AgentState) -> dict:
    """상담 요약을 만든다.

    TODO(AI-02): ai/services 의 요약 경로를 연결한다.
    """

    return {"summary": state.get("summary") or {"overview": "", "key_points": []}}


def risk_node(state: AgentState) -> dict:
    """위험 발화·학대 신호·위험 요인을 추출한다.

    TODO(AI-02): 구조 합의 후 실제 값을 채운다.
      - 필드 구조: PROPOSAL_risk_fields.md §7
      - 요약 단계가 아니라 이 단계에서 채워야 한다(요약 쪽에 거부 가드가 있다)
    """

    return {
        "risk_utterances": [],
        "abuse_signals": [],
        "risk_factors": [],
    }


def rag_node(state: AgentState) -> dict:
    """판단 기준이 될 지침·판례를 검색한다.

    TODO(AI-03): feature/rag 머지 후 rag.retriever.search_evidence() 로 교체한다.
      현재 rag/ 패키지는 feature/rag 브랜치에만 있어 import 할 수 없다.

    반환값은 rag_documents 에 누적된다(reducer). 빈 목록을 돌려주면
    근거가 늘지 않아 재분석이 계속 "부족" 으로 판정되지만,
    MAX_RETRY 가 있어 무한 루프로는 가지 않는다.
    """

    return {"rag_documents": []}


def reanalysis_node(state: AgentState) -> dict:
    """RAG 문서를 참고해 위험 판정을 다시 한다.

    TODO(AI-02): 재판정 진입점을 연결한다.

    retry_count 를 1 돌려주지 않으면 MAX_RETRY 가 올라가지 않아
    무한 루프가 된다. 이 줄을 지우지 말 것.
    """

    return {
        "risk_utterances": state.get("risk_utterances") or [],
        "abuse_signals": state.get("abuse_signals") or [],
        "risk_factors": state.get("risk_factors") or [],
        "retry_count": 1,
    }


def report_node(state: AgentState) -> dict:
    """결과를 마무리한다. 근거가 부족한 채 끝났으면 사유를 남긴다.

    05_RULES.md §3 "근거 부족 시 빈 결과 허용" 에 따라 억지로 채우지 않는다.
    대신 상담사가 알 수 있도록 warnings 에 적는다.
    """

    warnings: List[str] = []

    if state.get("retry_count", 0) >= MAX_RETRY and evidence_verdict(state) == "insufficient":
        warnings.append(
            "근거가 부족한 상태로 분석을 종료했습니다. 상담사 검토가 필요합니다."
        )

    return {"warnings": warnings}


# =========================================================
# 라우터 (조건부 엣지 함수)
# =========================================================

def evidence_verdict(state: AgentState) -> str:
    """근거 충족 여부만 판단한다. State 를 바꾸지 않는다.

    단일 확신도 기준(confidence >= 0.7)을 쓰지 않는다. 학대 유형별
    임계값이 다르고 모델 버전마다 또 달라서, Agent 가 기준을 따로 두면
    모델 교체 때마다 어긋난다. 모델이 계산한 detected 를 그대로 쓴다.
    근거: PROPOSAL_risk_fields.md §7-2

    키가 없을 수 있으므로 .get() 을 쓴다. 구조 합의 전이거나 AI 가 필드를
    빠뜨리면 KeyError 로 그래프 전체가 죽는다.
    """

    signals = [s for s in state.get("abuse_signals") or [] if s.get("detected")]
    linked = [s for s in signals if s.get("segment_ids")]

    return "sufficient" if len(linked) >= 1 else "insufficient"


def route_after_risk(state: AgentState) -> str:
    """위험 판정 뒤 다음 목적지를 고른다.

    재분석 횟수가 한도에 닿으면 부족하더라도 결과 작성으로 보낸다.
    사유 기록은 report_node 가 한다. 라우터는 State 를 바꿀 수 없다.
    """

    if state.get("retry_count", 0) >= MAX_RETRY:
        return "sufficient"

    return evidence_verdict(state)


__all__ = [
    "MAX_RETRY",
    "analysis_node",
    "risk_node",
    "rag_node",
    "reanalysis_node",
    "report_node",
    "evidence_verdict",
    "route_after_risk",
]
