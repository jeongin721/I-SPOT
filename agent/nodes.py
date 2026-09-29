# LangGraph Agent 의 노드와 라우터.
#
# 설계 근거: I-SPOT_DOCS/docs/PLAN_langgraph_agent.md §4-1, §4-5, §4-6, §4-7
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
#
# 외부 LLM 호출 전 비식별 필수 (9/18 회의 결정)
#   외부 LLM 에는 로컬(Ollama)에서 비식별한 텍스트만 보낸다.
#   외부 LLM 을 부르는 노드는 호출 직전에 require_deidentified(state) 를 부른다.
#   지금 노드들은 LLM 을 부르지 않으므로 이 확인 없이도 원문이 밖으로 나가지 않는다.

from typing import List

from agent.state import AgentState

# 재분석 최대 횟수.
#
# evidence_check -> rag -> reanalysis -> evidence_check 는 닫힌 고리다.
# 이 값이 없으면 무한 루프가 되고, 매 바퀴가 LLM 호출이라 비용도 계속 든다.
MAX_RETRY = 2


class DeidentificationRequiredError(RuntimeError):
    """비식별하지 않은 상담 원문을 외부 LLM 으로 보내려 했다."""


def require_deidentified(state: AgentState) -> None:
    """외부 LLM 을 부르기 직전에 확인한다. 비식별 전이면 예외를 던진다.

    9/18 회의 결정: 외부 LLM 에는 로컬(Ollama)에서 비식별한 텍스트만 보낸다.

    값이 없거나 True 가 아니면 모두 막는다. 키를 빠뜨린 State 를
    "비식별 끝남" 으로 보면 원문이 그대로 나간다.
    예외는 그래프 밖으로 올라가 어댑터에서 AI_FAILED 로 바뀐다.
    """

    if state.get("deidentified") is not True:
        raise DeidentificationRequiredError(
            "비식별하지 않은 상담 원문은 외부 LLM 으로 보낼 수 없습니다."
        )


# =========================================================
# 노드
# =========================================================

def deidentify_node(state: AgentState) -> dict:
    """외부 LLM 에 보내기 전에 상담 원문에서 개인 식별 정보를 가린다.

    그래프의 맨 앞 노드다. 뒤의 어느 노드가 외부 LLM 을 부르더라도
    이 노드를 먼저 지나게 하려는 자리다.

    TODO(AI-02): 로컬 비식별을 연결한다(9/18 회의 결정).
      - ai-modeling 의 ai/modeling/abuse/pii_masking.mask_pii
        (정규식 + koelectra NER) 를 쓸 수 있다. PLAN §4-7 "합칠 때 할 일" 참조
      - 토큰 ↔ 원문 대응표(entity_map)는 State 에 두더라도 외부로 보내지 않는다
      - 연결한 뒤에만 deidentified=True 를 돌려준다

    지금은 원문을 그대로 두고 deidentified=False 만 남긴다.
    현재 노드들은 외부 LLM 을 부르지 않으므로 동작은 바뀌지 않는다.
    """

    return {"deidentified": False}


def analysis_node(state: AgentState) -> dict:
    """상담 요약과 요약 근거(summary_evidence)를 만든다.

    TODO(AI-02): ai/services 의 요약 경로를 연결한다.
      - 외부 LLM 호출 전 require_deidentified(state) 필수(9/18 회의 결정).
        develop 의 ai/services/summary_service.summarize_consultation 은
        Transcript 원문을 비식별 없이 OpenAI 로 보낸다. 그대로 붙이면
        아동 발화 원문이 외부로 나간다
      - summary_evidence 는 PipelineAIAdapter 와 같은 모양으로 채운다
    """

    return {
        "summary": state.get("summary") or {"overview": "", "key_points": []},
        "summary_evidence": state.get("summary_evidence") or [],
    }


def risk_node(state: AgentState) -> dict:
    """위험 발화·학대 신호·위험 요인을 추출한다.

    TODO(AI-02): 구조 합의 후 실제 값을 채운다.
      - 필드 구조: PROPOSAL_risk_fields.md §7
      - 요약 단계가 아니라 이 단계에서 채워야 한다(요약 쪽에 거부 가드가 있다)
      - 로컬 분류 모델은 원문을 써도 되지만, 외부 LLM(2차 세부유형 등)을
        부르기 전에는 require_deidentified(state) 필수(9/18 회의 결정)
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
      feature/rag 의 판정 단계(rag/evidence_analyzer.py)는 상담 원문을
      OpenAI 로 보낸다. 연결할 때 require_deidentified(state) 필수(9/18 회의 결정).

    반환값은 rag_documents 에 누적된다(reducer). 빈 목록을 돌려주면
    근거가 늘지 않아 재분석이 계속 "부족" 으로 판정되지만,
    MAX_RETRY 가 있어 무한 루프로는 가지 않는다.
    """

    return {"rag_documents": []}


def reanalysis_node(state: AgentState) -> dict:
    """RAG 문서를 참고해 위험 판정을 다시 한다.

    TODO(AI-02): 재판정 진입점을 연결한다.
      외부 LLM 호출 전 require_deidentified(state) 필수(9/18 회의 결정).

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

    검출된 신호가 없는 경우("none")는 부족이 아니라 정상 결과이므로
    경고를 달지 않는다. segment 연결이 없는 검출 신호가 남은 채로
    재분석 한도에 닿은 경우만 경고한다.
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

    세 갈래로 나눈다.

      none          검출(detected)된 신호가 없다. 재분석할 것이 없으므로
                    바로 결과 작성으로 간다. 경고도 달지 않는다
      sufficient    검출된 신호가 모두 근거 발화(segment_ids)에 연결돼 있다
      insufficient  근거 발화가 연결되지 않은 검출 신호가 하나라도 있다

    신호가 없는 정상 상담을 "부족" 으로 보면 매번 재분석을 MAX_RETRY 번
    돌고 "근거가 부족" 경고가 붙는다. 그래서 none 을 따로 둔다.

    단일 확신도 기준(confidence >= 0.7)을 쓰지 않는다. 학대 유형별
    임계값이 다르고 모델 버전마다 또 달라서, Agent 가 기준을 따로 두면
    모델 교체 때마다 어긋난다. 모델이 계산한 detected 를 그대로 쓴다.
    근거: PROPOSAL_risk_fields.md §7-2

    키가 없을 수 있으므로 .get() 을 쓴다. 구조 합의 전이거나 AI 가 필드를
    빠뜨리면 KeyError 로 그래프 전체가 죽는다.
    """

    detected = [s for s in state.get("abuse_signals") or [] if s.get("detected")]

    if not detected:
        return "none"

    if all(s.get("segment_ids") for s in detected):
        return "sufficient"

    return "insufficient"


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
    "DeidentificationRequiredError",
    "require_deidentified",
    "deidentify_node",
    "analysis_node",
    "risk_node",
    "rag_node",
    "reanalysis_node",
    "report_node",
    "evidence_verdict",
    "route_after_risk",
]
