# [계획] LangGraph AI Agent 도입 방향

> 팀장님이 제안하신 LangGraph Agent 구조를 현재 코드베이스에 맞춰 구체화한 문서입니다.
> 확정 전이며, 아래 **6. 막혀 있는 것** 이 먼저 풀려야 착수할 수 있습니다.
>
> 작성: mingyu · 2026-09-11 · 관련 [PROPOSAL_risk_fields.md](./PROPOSAL_risk_fields.md)

---

## 1. 이 문서의 목적

LangGraph 로 분석 파이프라인을 재구성할 때 **기존 Backend 와 충돌하지 않도록** 경계를 정합니다.

이 문서를 읽는 사람(또는 AI)은 다음을 알 수 있어야 합니다.

- LangGraph 코드를 **어디에 둘 것인가**
- 기존 어댑터 계약을 **어떻게 만족시킬 것인가**
- 지금 **착수 가능한 것과 막힌 것**

---

## 2. 현재 코드베이스 사실

착수 전에 반드시 확인해야 할 실제 상태입니다. 추측이 아니라 코드에서 확인한 내용입니다.

### 2-1. 이미 오케스트레이션이 존재합니다

Backend 가 세션 상태 기계로 흐름을 강제합니다. 순서를 어기면 `409 INVALID_SESSION_STATE` 를 반환합니다.

```text
CREATED → AUDIO_UPLOADED → STT_PROCESSING → STT_REVIEW_REQUIRED
       → STT_CONFIRMED → AI_PROCESSING → AI_REVIEW_REQUIRED → APPROVED
```

`STT_REVIEW_REQUIRED` 와 `AI_REVIEW_REQUIRED` 는 **사람(상담사)이 개입하는 지점** 입니다. 자동 그래프로 통과시킬 수 없습니다.

실패 상태 두 개가 별도로 있습니다.

```text
STT_FAILED   AI_FAILED
```

`backend/app/services/analysis_service.py:140` 이 **어떤 예외가 발생해도** 세션을 `AI_REVIEW_REQUIRED` 또는 `AI_FAILED` 로 마감합니다.

따라서 **어댑터는 상태 전이를 직접 하지 않습니다.** 실패 시 `AIError` 에 `ErrorCode` 를 담아 던지기만 하면 됩니다. 기존 `PipelineAIAdapter` 와 동일한 규약입니다.

```python
raise AIError("LangGraph 실행에 실패했습니다.", ErrorCode.AI_FAILED)
```

### 2-2. AI 는 교체 가능한 어댑터로 연결돼 있습니다

```python
# backend/app/adapters/ai_adapter.py:38
class AIAdapter(Protocol):
    def analyze(self, transcript_payload: Dict[str, Any]) -> AIAnalysisBundle: ...
```

```python
# backend/app/adapters/ai_adapter.py:29
@dataclass
class AIAnalysisBundle:
    result: AIAnalysisResult
    summary_evidence: List[SummaryEvidenceItem] = field(default_factory=list)
    provider: str = "mock"
    model: Optional[str] = None
```

현재 구현체는 둘입니다.

| `AI_PROVIDER` | 클래스 | 동작 |
| --- | --- | --- |
| `mock` | `MockAIAdapter` | 외부 호출 없이 **Transcript 에서 파생** |
| `pipeline` | `PipelineAIAdapter` | `ai.services.analysis_pipeline` 호출 |

`mock` 은 고정 응답이 아닙니다. Transcript 를 읽어 다음을 만들어 냅니다.

- `CHILD` 발화 앞 3건을 `key_points` 로
- 그 각각에 `segment_id` 를 연결해 `summary_evidence` 로
- `confidence < 0.7` 인 구간 수를 세어 `warnings` 에
- segment 가 하나도 없으면 `AIError(AI_INVALID_OUTPUT)`

위험 필드 3종만 빈 배열로 고정돼 있습니다. **그 부분만 새 구조의 예시 값으로 바꾸면** 그래프 분기를 검증할 수 있습니다.

```python
# backend/app/core/config.py:88
AI_PROVIDER: Literal["mock", "pipeline"] = "mock"
```

### 2-3. 분석은 비동기입니다

```python
# backend/app/api/v1/analysis.py:21
status_code=status.HTTP_202_ACCEPTED
```

`POST /analysis` 는 즉시 `202` 를 돌려주고 `BackgroundTasks` 로 처리한 뒤, 클라이언트가 폴링으로 결과를 가져갑니다.

### 2-4. RAG 는 V1 골격이 있습니다

`feature/rag` 브랜치, 커밋 13개. 검색까지만 되고 **답변 생성은 없습니다.**

```python
# rag/retriever.py:9   (feature/rag 브랜치. 이 브랜치에는 없습니다 — 아래 주의 참조)
def search_evidence(
    query: str, *, top_k: int = TOP_K,
    source_type: str | None = None,
    abuse_type: str | None = None,
) -> list[dict[str, Any]]:
    """반환: [{"content": str, "metadata": dict}, ...]"""
    ...
```

원본 PDF 는 `rag_data/` 에 두며 `.gitignore` 대상입니다. **각자 로컬에 준비해야 합니다.**

#### ⚠️ `rag/` 패키지는 아직 `feature/rag` 브랜치에만 있습니다

| 브랜치 | `rag/` |
| --- | --- |
| `feature/rag` | 있음 |
| `develop` | **없음** |
| `integration/develop-consolidation` | **없음** |

따라서 지금 `rag_node` 에서 아래처럼 쓰면 `ModuleNotFoundError` 가 납니다.

```python
from rag.retriever import search_evidence   # 아직 import 불가
```

`feature/rag` 가 `develop` 에 머지되기 전까지는 `rag_node` 를 **인터페이스만 정의하고 비워두거나**, 고정 응답을 돌려주는 stub 으로 둡니다. 그래프 구조 검증은 stub 으로도 가능합니다.

```python
def rag_node(state: AgentState) -> dict:
    # TODO: feature/rag 머지 후 search_evidence() 로 교체
    return {"rag_documents": []}
```

노드는 State 전체가 아니라 **바뀐 부분만 `dict` 로** 돌려줍니다(4-1). stub 이 빈 목록을 돌려주면 근거가 늘지 않아 재분석이 계속 "부족" 으로 판정되지만, `MAX_RETRY` 가 있어 무한 루프로는 가지 않습니다(4-5).

### 2-5. LangGraph 는 아직 어디에도 없습니다

`requirements*.txt` 전체에 `langgraph` 항목이 없습니다. 의존성 추가가 첫 작업입니다.

---

## 3. 설계 결정 — LangGraph 를 어디에 둘 것인가

### 결론: `AI_PROVIDER=langgraph` 어댑터 안에 둡니다

```text
Frontend
   ↓
FastAPI  (세션 상태·권한·저장·에러 — 기존 그대로)
   ↓
ai_adapter.py  →  LangGraphAIAdapter        ← 신규
                     ↓
                  LangGraph
                     ├─ 분석
                     ├─ 근거 판정
                     ├─ RAG
                     └─ 재분석
                     ↓
                  AIAnalysisBundle 반환
```

### 왜 별도 오케스트레이터로 두지 않는가

Backend 가 이미 세션 상태로 흐름을 관리합니다(2-1). LangGraph 를 최상위에 두면 **"지금 이 상담이 어느 단계인가" 의 정답이 두 곳** 이 됩니다.

```text
DB 의 session.status      vs      LangGraph 의 state
```

둘이 어긋나면 어느 쪽이 맞는지 판단할 근거가 없습니다. 상태 저장 주체는 **DB 하나로 유지**합니다.

### `stt_node` 는 그래프에 넣지 않습니다

STT 는 분 단위로 걸리고(2-3), 중간에 **상담사 검수 단계** 가 있습니다(2-1). 그래프 노드로 넣으면 그래프가 몇 분간 블로킹되거나 사람 개입에서 멈춥니다.

```text
[그래프 밖]  음성 업로드 → STT → 상담사 검수·확정
                                      ↓
[그래프 안]  분석 → 위험요인 → 근거판정 → (RAG → 재분석) → 결과
```

그래프는 **`STT_CONFIRMED` 이후에 시작** 합니다. 어댑터가 호출되는 시점과 정확히 일치합니다.

---

## 4. 그래프 정의

### 4-1. 노드

| 노드 | 입력 | 반환(State 부분 갱신) | 담당 |
| --- | --- | --- | --- |
| `analysis_node` | `transcript` | `summary` | AI |
| `risk_node` | `transcript` | `risk_utterances`, `abuse_signals`, `risk_factors` | AI |
| `rag_node` | 부족한 근거 | `rag_documents` | RAG |
| `reanalysis_node` | 원본 + `rag_documents` | 위험 필드 3종 + `retry_count` | AI |
| `report_node` | 전체 State | `warnings` (필요 시) | Agent |

#### `evidence_check` 는 노드가 아니라 **조건부 엣지 함수** 입니다

팀장님 그림에는 `evidence_check_node` 로 표기돼 있으나, LangGraph 에서 분기 판정은 **노드가 아니라 라우터** 로 구현합니다.

```python
graph.add_conditional_edges(
    "risk_node",                    # 이 노드 다음에
    route_after_risk,               # 이 함수가 다음 목적지를 고른다
    {"sufficient": "report_node", "insufficient": "rag_node"},
)
```

라우터는 **State 를 바꾸지 않고 목적지 이름만 돌려줍니다.** 노드는 State 부분 갱신을 `dict` 로 돌려주고, 라우터는 `str` 을 돌려준다는 점이 다릅니다.

라우터 안에서 State 를 고치면 **반영이 보장되지 않습니다.** 갱신은 노드가 돌려준 `dict` 를 통해서만 이뤄지기 때문입니다. 라우터는 판단만 하고, 기록이 필요하면 노드에서 합니다.

> **이 절의 LangGraph 동작 서술은 라이브러리 규약을 따른 것이고, 이 저장소에서
> 실행으로 확인한 것이 아닙니다.** `langgraph` 가 아직 설치되어 있지 않습니다(2-5).
> 착수 시 설치한 버전의 문서로 한 번 대조해 주세요.

### 4-2. 엣지

```text
START → analysis_node → risk_node ─┬─[sufficient]───→ report_node → END
                                   │
                                   └─[insufficient]─→ rag_node
                                                         ↓
                                                   reanalysis_node
                                                         │
                                        ┌────────────────┘
                                        │  (같은 라우터를 다시 통과)
                                        └─┬─[sufficient]───→ report_node
                                          └─[insufficient]─→ rag_node
```

`risk_node` 와 `reanalysis_node` 뒤에 **같은 라우터**(`route_after_risk`)를 붙입니다.

### 4-3. State

여러 노드가 같은 키에 쓰는 항목은 **reducer** 를 지정해야 합니다. 지정하지 않으면 뒤에 쓴 값이 **앞의 값을 덮어씁니다.**

```python
import operator
from typing import Annotated, TypedDict

class AgentState(TypedDict):
    transcript: dict                                    # 입력. Transcript Contract
    summary: dict
    risk_utterances: list[dict]
    abuse_signals: list[dict]
    risk_factors: list[dict]

    # 재분석을 돌 때마다 쌓여야 하므로 누적 reducer 를 쓴다.
    rag_documents: Annotated[list[dict], operator.add]
    warnings: Annotated[list[str], operator.add]
    retry_count: Annotated[int, operator.add]           # 노드가 1 을 돌려주면 +1
```

위험 필드 3종은 **재분석 결과로 교체**되는 값이므로 reducer 를 두지 않습니다. `rag_documents` 는 검색할수록 쌓여야 하므로 누적입니다. 이 구분을 틀리면 재분석이 이전 근거를 지우거나, 반대로 중복이 무한히 쌓입니다.

### 4-4. ⚠️ 재분석 루프는 팀 규칙과 긴장 관계에 있습니다

`05_RULES.md` §3 에 다음 두 줄이 있습니다.

```text
- 근거 부족 시 빈 결과 허용
- 결과를 억지로 생성하지 않음
```

제안된 구조는 **근거가 부족하면 자료를 더 찾아 다시 판단** 합니다. 이것이 "억지로 생성" 에 해당하는지 **팀 판단이 필요합니다.**

이 문서는 다음 전제로 설계했습니다.

- RAG 로 가져오는 것은 **지침·판례 등 판단 기준** 이지 새 근거 발화가 아닙니다.
  상담 발화에 없는 내용을 만들어내지 않습니다.
- 재분석 후에도 부족하면 **빈 결과로 종료** 합니다(§3 "빈 결과 허용").
  억지로 채우지 않고 `warnings` 에 사유를 남깁니다.
- 최종 판단은 상담사가 합니다(§1 "AI 가 학대 여부를 최종 확정" 금지, §2 Human-in-the-loop).

**이 전제가 팀 합의와 다르면 재분석 루프 자체를 빼야 합니다.** 8절에서 확인 부탁드립니다.

> 또한 `05_RULES.md` §3 은 **"내부 chain-of-thought 를 결과 데이터로 저장하지 않음"** 을
> 규정합니다. `AgentState` 의 `rag_documents` · `retry_count` 는 **중간 산물이므로
> DB 에 저장하지 않습니다.** 어댑터는 `AIAnalysisBundle` 에 담을 값만 추려서 돌려줍니다.

### 4-5. ⚠️ 루프 종료 조건은 필수입니다

`evidence_check → rag → reanalysis → evidence_check` 는 **닫힌 고리** 입니다. 종료 조건이 없으면 무한 루프가 되고, 매 바퀴가 LLM 호출이므로 비용도 계속 발생합니다.

라우터는 State 를 바꿀 수 없으므로(4-1), **횟수 판단은 라우터가 하고 사유 기록은 `report_node` 가** 합니다.

```python
MAX_RETRY = 2

# 라우터 — 목적지만 고른다
def route_after_risk(state: AgentState) -> str:
    if state["retry_count"] >= MAX_RETRY:
        return "sufficient"           # 더 못 돌므로 결과 작성으로 보낸다
    return evidence_verdict(state)    # 4-6 참조

# 노드 — 포기한 경우 사유를 남긴다
def report_node(state: AgentState) -> dict:
    if state["retry_count"] >= MAX_RETRY and evidence_verdict(state) == "insufficient":
        return {"warnings": ["근거가 부족한 상태로 분석을 종료했습니다."]}
    return {}

# 노드 — 재분석 때마다 1 을 돌려주면 reducer 가 더한다
def reanalysis_node(state: AgentState) -> dict:
    ...
    return {"risk_utterances": ..., "abuse_signals": ..., "retry_count": 1}
```

`reanalysis_node` 가 `retry_count` 를 올리지 않으면 **무한 루프가 됩니다.**

### 4-6. 판정 기준

**단일 확신도 기준(`>= 0.7`)을 쓰면 안 됩니다.** 학대 유형별 임계값이 두 배 넘게 차이납니다.

| 유형 | threshold |
| --- | --- |
| 신체학대 | 0.72 |
| 정서학대 | 0.39 |
| 성학대 | 0.53 |
| 방임 | **0.32** |

모델이 이미 계산한 `detected` 를 그대로 사용합니다. 근거 상세는 [PROPOSAL_risk_fields.md](./PROPOSAL_risk_fields.md) §7-4 를 따릅니다.

```python
def evidence_verdict(state: AgentState) -> str:
    """근거 충족 여부만 판단한다. State 를 바꾸지 않는다."""
    signals = [s for s in state["abuse_signals"] if s.get("detected")]
    linked = [s for s in signals if s.get("segment_ids")]
    return "sufficient" if len(linked) >= 1 else "insufficient"
```

`s["detected"]` 가 아니라 `s.get("detected")` 를 씁니다. 구조 합의 전이거나 AI 가 필드를 빠뜨린 경우 `KeyError` 로 그래프 전체가 죽는 것을 막습니다.

---

## 5. 담당별 할 일

### 5-0. `TASKS.md` 에 Task 를 추가해야 합니다

`TASKS.md` 의 현재 MVP 표에 Agent·RAG 항목이 없습니다. 새 Task 추가 규칙에 따라 아래를 등록해 주십시오.

```text
| AI-03  | AI     | RAG 문서 색인/검색       | mingyu | TODO | -     |
| BE-08  | Backend| LangGraph Agent Adapter | mingyu | TODO | AI-02 |
```

`BE-08` 이 `AI-02`(Summary/위험 발화 분석)에 의존한다는 점이 중요합니다. **`AI-02` 는 현재 담당자가 비어 있고 `TODO` 상태입니다.** 그래서 6-1 이 막혀 있습니다.

### 5-1. Agent / Backend (mingyu)

```text
브랜치  feat/langgraph-agent   (integration/develop-consolidation 에서 분기)
```

1. `requirements-agent.txt` 추가 — `langgraph` 의존성
2. `agent/` 패키지 신설 — `state.py`, `nodes.py`, `graph.py`
3. `backend/app/adapters/ai_adapter.py` 에 `LangGraphAIAdapter` 추가
4. `AI_PROVIDER` 에 `"langgraph"` 허용값 추가 (`backend/app/core/config.py:88`)
5. 루프 종료·에러 처리·타임아웃
6. 그래프 결과를 `AIAnalysisBundle` 로 변환

**기존 어댑터 계약을 바꾸지 않습니다.** `analyze(transcript_payload) -> AIAnalysisBundle` 을 그대로 만족시킵니다. 기존 `mock` / `pipeline` 은 건드리지 않습니다.

### 5-2. AI 모델 (이경진)

1. `risk_utterances` / `abuse_signals` / `risk_factors` 를 **실제로 채우기**
   — 현재 `ai/services/summary_service.py:215-221` 에서 빈 배열로 고정돼 있습니다
2. 각 필드 구조 확정 — [PROPOSAL_risk_fields.md](./PROPOSAL_risk_fields.md) §8 질문 답변
3. `abuse_model` 결과를 `abuse_signals` 로 넘기는 경로
   — 현재 최상위 `main.py` 에서만 쓰이고 Backend 로 전달되지 않습니다
4. `reanalysis_node` 용 함수 — RAG 문서를 받아 재판정하는 진입점

### 5-3. RAG (mingyu, 팀장님 V1 이어받음)

1. 임베딩 모델 확정 — **나중에 바꾸면 전체 재색인이 필요합니다**
2. `rag_data/` 원본 PDF 확보 (팀장님께 기존 수집본 확인)
3. `rag/README.md` §6 의 메타데이터 정확도 작업
4. `search_evidence()` 를 `rag_node` 에서 호출할 때의 쿼리 구성 규칙

### 5-4. Frontend (다솔)

1. 재분석이 일어난 경우를 화면에 표시할지 결정
   — `warnings` 는 **이미 Contract 에 있습니다**(`backend/app/schemas/contracts.py:77`). 근거가 부족한 채로
     종료하면 그래프가 여기에 사유를 넣으므로, 추가 작업 없이 표시할 수 있습니다.
   — `retry_count`(재분석 횟수)는 **Contract 에 없습니다.** 화면에 필요하다면
     필드 추가가 필요하고, 그것은 Contract 변경입니다.
2. RAG 근거 문서를 화면에 노출할지 결정
   — `AIAnalysisBundle` 의 값은 API 응답까지 그대로 나갑니다(`backend/app/schemas/analysis.py:32`
     의 `summary_evidence` 가 전례). 따라서 노출하려면 **API 응답 스키마 변경**이
     필요합니다. 단, `02_ARCHITECTURE.md` §7 의 **AI Output Contract 변경은 아닙니다**
     — `summary_evidence` 와 같이 Contract 밖 부가 정보로 둘 수 있습니다.

### 5-5. STT (정담원)

이번 작업에서 **변경 없습니다.** STT 는 그래프 밖에 남습니다(3절).

---

## 6. 막혀 있는 것

### 6-1. 근거 충족 판정(`evidence_verdict`)을 작성할 수 없습니다 🔴

```python
# ai/schemas/analysis.py:40-42
risk_utterances: List[Dict[str, Any]]
abuse_signals: List[Dict[str, Any]]
risk_factors: List[Dict[str, Any]]
```

`Dict[str, Any]` 는 내부 키를 정의하지 않습니다. `s["detected"]` 나 `s.get("segment_ids")` 가 존재한다는 보장이 없어 판정 코드를 쓸 수 없습니다.

또한 같은 필드가 세 곳에서 다르게 정의돼 있습니다.

| 위치 | 정의 |
| --- | --- |
| `ai/schemas/analysis.py:40-42` | `List[Dict[str, Any]]` |
| `ai/services/summary_service.py:78-80` | `List[str]` |
| `ispotvscode/src/api/types.ts:282-284` | `RiskUtterance[]` / `string[]` |

**[PROPOSAL_risk_fields.md](./PROPOSAL_risk_fields.md) 가 합의되어야 착수 가능합니다.**

### 6-2. 값이 비어 있어 그래프를 검증할 수 없습니다 🟡

구조가 정해져도 `summarize_consultation` 이 값을 채우기 전에는 분기가 항상 한쪽으로만 흐릅니다. `AI_PROVIDER=mock` 이 새 구조의 예시 데이터를 반환하도록 먼저 수정하면, AI 작업과 병행해서 그래프를 개발할 수 있습니다.

### 6-3. PRD 상 RAG 는 Later 항목입니다 🟡

```text
01_PRD.md §7 Later
- 과거 중대사건 RAG
Must Have 가 안정적으로 동작하기 전에는 Later 기능을 우선 구현하지 않는다.
```

또한 PRD 의 RAG 는 **"과거 중대사건"**(내부 상담 기록 검색)이고, `feature/rag` 는 **지침·판례·매뉴얼**(외부 공개 문서)입니다. 서로 다른 기능입니다.

Must Have 중 `위험 관련 발화 탐지` · `신체/정서/성/방임 관련 신호` · `Risk Factor 추출` · `근거 문장 제공` 이 아직 미구현입니다(6-1 과 같은 원인).

**팀장님 확인 필요** — Later 를 먼저 진행할지, 범위를 조정할지.

---

## 7. 착수 순서

```text
1.  PROPOSAL_risk_fields.md 합의            ← 여기서 막혀 있음
       ↓
2.  mock provider 를 새 구조로 수정          (Backend, 반나절)
       ↓
3.  그래프 골격 + 루프 종료 구현             (Agent, mock 으로 검증 가능)
       │   rag_node 는 stub 으로 둔다 (2-4 참조)
       ↓
4.  AI 가 실제 값 채우기                     (AI, 병행 가능)
       ↓
5.  feature/rag 머지 → rag_node 를 실제 연결  (RAG)
       ↓
6.  reanalysis 품질 조정
```

**2번과 3번은 1번만 끝나면 AI 작업을 기다리지 않고 진행할 수 있습니다.** mock 이 새 구조를 돌려주면 그래프 분기를 검증할 수 있기 때문입니다.

**5번은 `feature/rag` 머지가 선행되어야 합니다.** 현재 `rag/` 는 그 브랜치에만 있고 PR 도 없습니다(2-4).

---

## 8. 확인 부탁드릴 사항

**팀장님**

1. LangGraph 를 `AI_PROVIDER=langgraph` 어댑터 안에 두는 방식(3절)에 동의하시는지요? 별도 오케스트레이터로 두면 세션 상태가 이중 관리됩니다.
2. `stt_node` 를 그래프에서 빼고 `STT_CONFIRMED` 이후부터 시작하는 것(3절)이 괜찮으신지요?
3. PRD §7 상 RAG 는 Later 인데, Must Have 미구현 항목보다 먼저 진행할지 판단 부탁드립니다(6-3).
4. **재분석 루프가 `05_RULES.md` §3 의 "결과를 억지로 생성하지 않음" 에 저촉되지 않는지** 확인 부탁드립니다(4-4). 이 문서는 "RAG 로 가져오는 것은 판단 기준이지 새 근거가 아니며, 부족하면 빈 결과로 종료한다" 는 전제로 설계했습니다. 전제가 다르면 루프를 빼야 합니다.

**이경진 님**

5. 5-2 의 4개 항목 중 착수 가능한 것과 예상 시점을 알려주시면 순서를 맞추겠습니다.

**다솔 님**

6. 5-4 의 두 가지(재분석 표시 / RAG 근거 노출)는 지금 정하지 않아도 되지만, 필요하다고 판단되면 Contract 변경이 되므로 미리 말씀해주세요.
