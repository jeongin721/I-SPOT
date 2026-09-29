# [계획] LangGraph AI Agent 도입 방향

> 팀장님이 제안하신 LangGraph Agent 구조를 현재 코드베이스에 맞춰 구체화한 문서입니다.
> 확정 전이며, 아래 **6. 막혀 있는 것** 이 먼저 풀려야 착수할 수 있습니다.
>
> 작성: 최민규 · 2026-09-11 · 관련 [PROPOSAL_risk_fields.md](./PROPOSAL_risk_fields.md)
>
> 갱신 · 2026-09-29 — 근거 판정을 세 갈래로 나눔(4-6), 외부 LLM 호출 전 비식별 자리 추가(4-7, 9/18 회의 결정),
> `feature/rag` 의 9/22 연결 반영(2-4, 8절)

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
except Exception as error:
    raise map_ai_error(error) from error
```

`map_ai_error` 는 `PipelineAIAdapter` 와 함께 씁니다. 알 수 없는 예외는 문구를 버리고 `"AI 분석에 실패했습니다: RuntimeError"` 처럼 **예외 종류 이름만** 담습니다. `AIError` 의 문구는 DB 와 API 응답까지 가는데, 예외 문구에는 상담 발화가 섞일 수 있기 때문입니다. 자세한 내용은 `analysis_service` 가 `session_id` 와 함께 `logger.exception` 으로 남깁니다.

### 2-2. AI 는 교체 가능한 어댑터로 연결돼 있습니다

```python
# backend/app/adapters/ai_adapter.py:38
class AIAdapter(Protocol):
    def analyze(self, transcript_payload: Dict[str, Any]) -> AIAnalysisBundle: ...
```

```python
# backend/app/adapters/ai_adapter.py:28
@dataclass
class AIAnalysisBundle:
    result: AIAnalysisResult
    summary_evidence: List[SummaryEvidenceItem] = field(default_factory=list)
    provider: str = "mock"
    model: Optional[str] = None
```

구현체는 셋입니다. `langgraph` 는 이 PR(#10)에서 추가했습니다(5-1).

| `AI_PROVIDER` | 클래스 | 동작 |
| --- | --- | --- |
| `mock` | `MockAIAdapter` | 외부 호출 없이 **Transcript 에서 파생** |
| `pipeline` | `PipelineAIAdapter` | `ai.services.analysis_pipeline` 호출 |
| `langgraph` | `LangGraphAIAdapter` | `agent.graph.run` 호출 — **이 PR 에서 추가** |

`mock` 은 고정 응답이 아닙니다. Transcript 를 읽어 다음을 만들어 냅니다.

- `CHILD` 발화 앞 3건을 `key_points` 로
- 그 각각에 `segment_id` 를 연결해 `summary_evidence` 로
- `confidence < 0.7` 인 구간 수를 세어 `warnings` 에
- segment 가 하나도 없으면 `AIError(AI_INVALID_OUTPUT)`

위험 필드 3종만 빈 배열로 고정돼 있습니다. **그 부분만 새 구조의 예시 값으로 바꾸면** 그래프 분기를 검증할 수 있습니다.

```python
# backend/app/core/config.py:89
AI_PROVIDER: Literal["mock", "pipeline", "langgraph"] = "mock"
```

### 2-3. 분석은 비동기입니다

```python
# backend/app/api/v1/analysis.py:21
status_code=status.HTTP_202_ACCEPTED
```

`POST /analysis` 는 즉시 `202` 를 돌려주고 `BackgroundTasks` 로 처리한 뒤, 클라이언트가 폴링으로 결과를 가져갑니다.

### 2-4. RAG 는 V2 까지 있습니다

`feature/rag` 브랜치, `develop` 에 없는 커밋 38개(끝 `02ffb4d`, 2026-09-22). 검색에 더해 **상담사용 결과를 생성합니다.** 9/11 오후에 체크리스트 판정, 9/14 에 법령 조회와 다음 상담 질문이 추가되었습니다.

**9/22 `02ffb4d` 에서 RAG 가 실제로 연결되었습니다.** 연결된 곳은 Backend 도 이 Agent 도 아니고, 팀장님 브랜치의 **루트 STT 서버**(`main.py` 의 `POST /api/v1/analyze`)입니다.

```text
음성 업로드 → STT → 아동 발화 텍스트(child_analysis_text) → 학대 유형 모델(detected)
→ detected 유형을 RAG abuse_type 으로 변환 → analyze_consultation_evidence(아동 발화, 유형)
→ 응답의 rag_analysis 로 반환      (RAG 가 실패하면 rag_analysis.error 에 담고 나머지 결과는 그대로)
```

- 이 경로는 Backend 의 세션 상태 기계를 타지 않습니다. **상담사 STT 검수(`STT_REVIEW_REQUIRED`) 전 텍스트**로 RAG 를 돌립니다.
- ⚠️ **아동 발화를 비식별 없이 OpenAI 로 보냅니다.** 검색 질의 임베딩(`rag/vector_store.py`, `OpenAIEmbeddings`), 체크리스트 판정(`rag/evidence_analyzer.py`, `[상담 원문]` 을 `ChatOpenAI` 로), 다음 상담 질문(`rag/checklist_builder.py`) 세 곳입니다. 9/18 회의 결정(외부 LLM 에는 로컬에서 비식별한 텍스트만)과 어긋납니다(4-7).

`rag/pipeline.py` 의 `analyze_consultation_evidence(text, abuse_type)` 가 전체를 묶습니다.

```text
상담 문장 + 학대 유형
→ 체크리스트 검색 → 상담 문장과 비교 (matched / needs_confirmation / excluded)   ← LLM
→ 국가법령정보센터 API 에서 관련 현행 조문
→ 다음 상담용 확인 질문 3~5개                                                 ← LLM
→ 상담사 참고자료 2~3개
```

`rag/README.md` §11 은 이 결과 JSON 을 **Backend / LangGraph Agent 에 연결하고 Frontend 에서 상담사에게 보여주는** 방향이었는데, 9/22 연결은 위처럼 **루트 STT 서버에서 detected 유형이 있으면 항상** 부르는 방식입니다. 이 문서의 4절은 RAG 를 **Agent 안에서 근거가 부족할 때만 부르는 재분석 재료**로 잡았습니다(4-1 표의 `rag_node` 입력). 세 방식이 서로 다르므로 어느 쪽으로 할지 팀장님 확인이 필요합니다(8절 5번).

| 방식 | RAG 를 부르는 곳 | 부르는 때 | 입력 |
| --- | --- | --- | --- |
| 9/22 연결 (`02ffb4d`) | 루트 STT 서버 `/api/v1/analyze` | detected 유형이 있으면 항상 | STT 검수 **전** 아동 발화 |
| `rag/README.md` §11 | Backend / Agent | 적혀 있지 않음 | STT 상담 텍스트 + 멀티라벨 모델의 `abuse_type` |
| 이 문서 4절 | Agent `rag_node` | 근거가 부족할 때만 | STT 확정 **후** Transcript |

아래 `search_evidence` 는 파이프라인 안에서 쓰이는 검색 함수입니다.

```python
# rag/retriever.py:30   (feature/rag 브랜치에만 있습니다 — 아래 주의 참조)
def search_evidence(
    query: str, *, top_k: int = TOP_K,
    source_type: str | None = None,
    abuse_type: str | None = None,
) -> list[dict[str, Any]]:
    """반환: [{"content": str, "metadata": dict}, ...]"""
    ...
```

**시그니처와 반환 모양은 계속 같습니다.** 다만 브랜치가 활발히 움직이고 있어(메타데이터 추론·청킹·필터 개선) `rag_node` 를 실제로 연결할 때 한 번 더 대조해야 합니다.

원본 PDF 는 `rag_data/` 에 두며 `.gitignore` 대상입니다. **각자 로컬에 준비해야 합니다.**

#### ⚠️ `rag/` 패키지는 아직 `feature/rag` 브랜치에만 있습니다

| 브랜치 | `rag/` |
| --- | --- |
| `feature/rag` | 있음 |
| `develop` | **없음** |
| `backend-agent` | **없음** |

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

### 2-5. LangGraph 의존성

`requirements*.txt` 전체에 `langgraph` 항목이 없었습니다. `backend-agent` 브랜치에서 `langgraph 1.2.11` 을 설치하고 `requirements-agent.txt` 로 고정합니다.

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
                     ├─ 비식별        ← 외부 LLM 호출 전 필수 (9/18 회의 결정, 4-7)
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
[그래프 안]  비식별 → 분석 → 위험요인 → 근거판정 → (RAG → 재분석) → 결과
```

그래프는 **`STT_CONFIRMED` 이후에 시작** 합니다. 어댑터가 호출되는 시점과 정확히 일치합니다.

---

## 4. 그래프 정의

### 4-1. 노드

| 노드 | 입력 | 반환(State 부분 갱신) | 담당 |
| --- | --- | --- | --- |
| `deidentify_node` | `transcript` | `deidentified` (지금은 항상 `False`, 4-7) | Agent · AI |
| `analysis_node` | `transcript` | `summary`, `summary_evidence` | AI |
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
    {"none": "report_node", "sufficient": "report_node", "insufficient": "rag_node"},
)
```

라우터는 **State 를 바꾸지 않고 목적지 이름만 돌려줍니다.** 노드는 State 부분 갱신을 `dict` 로 돌려주고, 라우터는 `str` 을 돌려준다는 점이 다릅니다.

라우터 안에서 State 를 고치면 **반영되지 않습니다**(아래에서 실행으로 확인). 갱신은 노드가 돌려준 `dict` 를 통해서만 이뤄지기 때문입니다. 라우터는 판단만 하고, 기록이 필요하면 노드에서 합니다.

#### 실행으로 확인했습니다 (`langgraph 1.2.11`)

최소 그래프를 만들어 세 가지를 검증했습니다.

```python
class S(TypedDict):
    log: Annotated[list[str], operator.add]   # reducer 있음
    n: Annotated[int, operator.add]
    plain: list[str]                          # reducer 없음

def a(s): return {"log": ["a"], "n": 1, "plain": ["A"]}
def b(s): return {"log": ["b"], "n": 1, "plain": ["B"]}

def router(s) -> str:
    s["log"].append("router-mutation")        # 라우터에서 State 변경 시도
    return "b" if s["n"] < 2 else "end"
```

실행 결과입니다.

```text
log   : ['a', 'b']     ← router-mutation 이 없다. 라우터 변경은 반영되지 않는다
n     : 2              ← reducer 가 1 + 1 을 누적했다
plain : ['B']          ← reducer 가 없으면 ['A'] 가 덮어써진다
```

| 문서의 주장 | 결과 |
| --- | --- |
| 라우터의 State 변경은 반영되지 않는다 | **확인** — `router-mutation` 이 로그에 없음 |
| reducer 가 있으면 누적된다 | **확인** — `['a','b']`, `n=2` |
| reducer 가 없으면 덮어쓴다 | **확인** — `['A']` 소실 |

따라서 4-3 의 reducer 구분(위험 필드는 교체, `rag_documents` 는 누적)은 **반드시 지켜야 합니다.** 틀리면 재분석이 이전 결과를 조용히 지웁니다.

### 4-2. 엣지

```text
START → deidentify_node → analysis_node → risk_node ─┬─[none]─────────→ report_node → END
        (외부 LLM 호출 전                             ├─[sufficient]───→ report_node
         비식별 자리, 4-7)                            │
                                                     └─[insufficient]─→ rag_node
                                                                           ↓
                                                                     reanalysis_node
                                                                           │
                                                          ┌────────────────┘
                                                          │  (같은 라우터를 다시 통과)
                                                          └─┬─[sufficient]───→ report_node
                                                            └─[insufficient]─→ rag_node
```

`risk_node` 와 `reanalysis_node` 뒤에 **같은 라우터**(`route_after_risk`)를 붙입니다. 세 갈래의 기준은 4-6 입니다. `none`(검출된 신호 없음)은 재분석 없이, 경고 없이 결과 작성으로 갑니다.

#### ⚠️ 팀장님 자료의 두 그림이 서로 다릅니다 — 확인 필요

**그림 1** 은 RAG 를 **양쪽 경로 모두**에 둡니다.

```text
근거 충분?
 ↙ YES              ↘ NO
RAG                 RAG 추가 검색
 ↓                   ↓
결과 생성  ←──────  재분석
```

**그림 2** 의 노드 연결은 RAG 를 **부족한 경우에만** 둡니다.

```text
근거 충분  →  report_node
근거 부족  →  rag_node → reanalysis_node
```

위 4-2 는 **그림 2** 를 따랐습니다. 다만 그림 1 의 구조도 말이 됩니다.

| 해석 | RAG 의 역할 |
| --- | --- |
| 그림 1 | **항상 조회.** 근거가 충분해도 지침·판례를 붙여 결과를 풍부하게 한다 |
| 그림 2 | **부족할 때만.** 판정을 보강하기 위한 되돌이 경로 |

그림 1 이 의도라면 `report_node` 앞에 `rag_node` 를 한 번 더 두면 됩니다. 다만 **근거가 충분한데도 매번 LLM·검색 비용이 듭니다.**

**어느 쪽인지 확인 부탁드립니다**(8절 5번). 판단이 오기 전까지는 비용이 적은 그림 2 로 만들고, 그림 1 이 맞으면 엣지 하나만 추가하면 됩니다.

### 4-3. State

여러 노드가 같은 키에 쓰는 항목은 **reducer** 를 지정해야 합니다. 지정하지 않으면 뒤에 쓴 값이 **앞의 값을 덮어씁니다.**

```python
import operator
from typing import Annotated, TypedDict

class AgentState(TypedDict):
    transcript: dict                                    # 입력. Transcript Contract
    deidentified: bool                                  # 비식별 완료 여부 (4-7)
    summary: dict
    summary_evidence: list[dict]                        # 요약 문장 ↔ 근거 발화
    risk_utterances: list[dict]
    abuse_signals: list[dict]
    risk_factors: list[dict]

    # 재분석을 돌 때마다 쌓여야 하므로 누적 reducer 를 쓴다.
    rag_documents: Annotated[list[dict], operator.add]
    warnings: Annotated[list[str], operator.add]
    retry_count: Annotated[int, operator.add]           # 노드가 1 을 돌려주면 +1
```

위험 필드 3종은 **재분석 결과로 교체**되는 값이므로 reducer 를 두지 않습니다. `deidentified` · `summary_evidence` 도 교체형입니다. `summary_evidence` 는 어댑터가 `PipelineAIAdapter` 와 같은 방식으로 `AIAnalysisBundle.summary_evidence` 에 옮깁니다(Contract 밖 부가 정보). `rag_documents` 는 검색할수록 쌓여야 하므로 누적입니다. 이 구분을 틀리면 재분석이 이전 근거를 지우거나, 반대로 중복이 무한히 쌓입니다.

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
> 규정합니다. `AgentState` 의 `rag_documents` · `retry_count` · `deidentified` 는 **중간 산물이므로
> DB 에 저장하지 않습니다.** 어댑터는 `AIAnalysisBundle` 에 담을 값만 추려서 돌려줍니다.
>
> 어댑터는 추릴 때 **근거 발화가 없는 위험 항목을 뺍니다**(`drop_ungrounded_risk_items`).
> 세 필드의 각 항목 중 `segment_id` · `segment_ids` 가 비었거나 Transcript 에 없는 번호를
> 하나라도 가리키면 제외하고 `warnings` 에 `"segment 근거가 없는 신호 N건을 제외했습니다."` 를 남깁니다.
> `abuse_signals` 중 `detected: false` 인 유형은 위험 신호가 아니므로 근거가 없어도 남깁니다(정상 상담마다 경고가 붙지 않게).
> 그래프 안의 판정(4-6)은 재분석 여부만 정할 뿐 항목을 거르지 않으므로, `05_RULES.md` §1
> "근거(`segment_id`) 없는 위험 신호 생성" 금지를 지키는 마지막 관문입니다.

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

# 노드 — 포기한 경우 사유를 남긴다. 검출 신호가 없는 "none" 은 경고하지 않는다
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

**단일 확신도 기준(`>= 0.7`)을 쓰면 안 됩니다.** 학대 유형별 임계값이 크게 다르고, **모델 버전마다 또 다릅니다.**

| 유형 | `develop` · `abuse_model/infer_abuse.py` (09-03 가중치) | `ai-modeling` 옛 판 · `ai/modeling/abuse/infer_abuse.py` (v4 09-07 가중치, 9/15 삭제) |
| --- | --- | --- |
| 신체학대 | 0.72 | 0.57 |
| 정서학대 | 0.39 | 0.54 |
| 성학대 | 0.53 | **0.19** |
| 방임 | **0.32** | 0.55 |

성학대가 0.53 ↔ 0.19, 방임이 0.32 ↔ 0.55 로 뒤집힙니다.

**2026-09-15 에 모델이 또 바뀌었습니다.** 이경진 님이 `ai-modeling` 에서 오른쪽 열의 `infer_abuse.py` 와 임계값 진단 코드(`test_abuse_probabilities.py`)를 지우셨습니다. 커밋 설명에 따르면 새 모델(`infer_abuse_v3_adapter.py`)로 대체한 것입니다(`0bf2c40`).

- 새 모델의 `predict_abuse` 는 확률을 버리고 **`detected` 만** 돌려줍니다. 새 모델 본체(`infer_abuse_qa_v3.py`)는 저장소에 올라와 있지 않아 **임계값은 확인하지 못했습니다**(`cea06ad` 기준).
- 세부유형 15종(`infer_subtype.py`)도 임계값이 0.19 ~ 0.94 로 제각각이고, 코드 주석에 잠정값(provisional)이라고 적혀 있습니다. 이쪽도 밖으로는 탐지 여부만 내보냅니다.

따라서 **Agent 는 임계값을 갖지 않습니다.** 모델이 계산한 `detected` 를 그대로 씁니다. 상수로 박아두면 모델이 바뀔 때마다 Agent 를 고쳐야 합니다. 근거 상세는 [PROPOSAL_risk_fields.md](./PROPOSAL_risk_fields.md) §7-2 와 §7-4 를 따릅니다.

```python
def evidence_verdict(state: AgentState) -> str:
    """근거 충족 여부만 판단한다. State 를 바꾸지 않는다."""
    detected = [s for s in state.get("abuse_signals") or [] if s.get("detected")]
    if not detected:
        return "none"             # 검출된 신호 없음 → 재분석 없이 결과로, 경고 없음
    if all(s.get("segment_ids") for s in detected):
        return "sufficient"       # 검출 신호가 모두 근거 발화에 연결됨
    return "insufficient"         # 근거 발화가 없는 검출 신호가 하나라도 있음
```

**처음 초안(9/11)은 검출 신호가 0개일 때도 `insufficient` 를 돌려줬습니다.** 신호가 없는 정상 상담까지 재분석을 `MAX_RETRY` 번 돌고 "근거가 부족" 경고가 붙는 오류였습니다. 신호가 없는 것은 근거가 부족한 것이 아니므로 `none` 으로 나눴습니다. 또 "연결된 신호가 1개 이상" 이던 기준을 **"검출 신호가 모두 연결"** 로 바꿨습니다. 연결 안 된 검출 신호가 섞여 있으면 그 신호는 근거가 없는 것이기 때문입니다.

`s["detected"]` 가 아니라 `s.get("detected")` 를 씁니다. 구조 합의 전이거나 AI 가 필드를 빠뜨린 경우 `KeyError` 로 그래프 전체가 죽는 것을 막습니다.

### 4-7. 외부 LLM 호출 전 비식별 필수 (9/18 회의 결정)

**외부 LLM 에는 로컬(Ollama)에서 비식별한 텍스트만 보냅니다.** 그래프에는 이 자리를 먼저 만들어 두었습니다.

```python
# agent/nodes.py
def deidentify_node(state) -> dict:        # 그래프 맨 앞 노드
    return {"deidentified": False}         # 비식별을 연결하기 전까지는 항상 False

def require_deidentified(state) -> None:   # 외부 LLM 을 부르는 노드가 호출 직전에 부른다
    if state.get("deidentified") is not True:
        raise DeidentificationRequiredError(...)   # 어댑터에서 AI_FAILED 로 바뀐다
```

- **지금 노드들은 LLM 을 부르지 않으므로 동작은 바뀌지 않습니다.** 원문도 그래프 밖으로 나가지 않습니다.
- `analysis_node` · `risk_node`(외부 LLM 단계) · `rag_node` · `reanalysis_node` 의 TODO 에 `require_deidentified(state)` 필수를 적었습니다. 값이 없거나 `True` 가 아니면 모두 막습니다.
- `deidentify_node` 에 실제 비식별을 연결한 뒤에만 `deidentified=True` 를 돌려줍니다.

#### 합칠 때 할 일

| 위치 | 사실 | 할 일 |
| --- | --- | --- |
| `ai-modeling` `ai/modeling/abuse/pii_masking.py` (`4433c3d`, 9/22) | `mask_pii(text)` — 정규식(주민등록번호·전화번호·이메일) + NER(`monologg/koelectra-base-v3-naver-ner`, 사람·기관·지역)으로 `[PERSON_01]` 같은 토큰으로 바꾼다. 토큰↔원문 대응표(`entity_map`)는 로컬에만 두고 `restore_pii` 로 되돌린다 | `deidentify_node` 에서 쓴다. `entity_map` 은 DB·로그·외부 LLM 으로 내보내지 않는다. **모듈을 import 하는 순간 NER 모델을 내려받아 올리므로**(파일 최상단 `from_pretrained`) 노드 안에서 늦게 import 하거나, 테스트에서 가짜로 바꿔야 한다 |
| `ai-modeling` `ai/modeling/abuse/llm_backend.py` (`c5a7fde`, 9/21) | `LLM_BACKEND` 기본값이 `"ollama"`(로컬 `qwen2.5:14b-instruct`, `http://localhost:11434/v1`). `"openai"` 로 바꾸면 **같은 호출부가 그대로 OpenAI 로 나간다** | `LLM_BACKEND` 값만 보고 비식별을 건너뛰지 않는다. 설정 하나로 같은 호출이 외부로 나가기 때문이다. 그래서 LLM 을 부르는 노드는 설정과 관계없이 `require_deidentified` 를 먼저 부르는 것을 기본으로 둔다 |
| `ai-modeling` `ai/modeling/abuse/infer_abuse_pipeline.py` | 2차 세부유형·요약·체크리스트는 `mask_pii` 를 거친다. 단 note 모드의 1차 보완 체크(`_screen_missed_major_types`, 호출 :180-185)는 **`mask_pii` 전에 원문을** LLM 에 보낸다 | `LLM_BACKEND=openai` 이면 원문이 외부로 나간다. 이경진 님께 확인(8절 8번) |
| `develop` `ai/services/summary_service.py` | `summarize_consultation` 이 Transcript 전체를 JSON 으로 바꿔(`build_transcript_input`, :97) **비식별 없이** OpenAI `client.responses.parse`(:145)로 보낸다. `AI_PROVIDER=pipeline` 이 이 경로를 쓴다 | `analysis_node` 에 이 경로를 그대로 붙이지 않는다. 비식별한 Transcript 를 넘기고 `require_deidentified` 를 먼저 부른다. `pipeline` 경로도 같은 원칙이 필요하다(이 PR 범위 밖, 팀 공유) |
| `feature/rag` `02ffb4d` (9/22) | 루트 STT 서버 `/api/v1/analyze` 가 아동 발화를 **비식별 없이** OpenAI 임베딩·`ChatOpenAI` 로 보낸다(2-4) | `rag_node` 로 옮길 때 비식별한 텍스트만 넘긴다. 루트 서버 경로를 유지할지는 팀장님 확인(8절 5·6번) |

---

## 5. 담당별 할 일

### 5-0. `TASKS.md` 에 Task 를 추가해야 합니다

`TASKS.md` 의 현재 MVP 표에 Agent·RAG 항목이 없습니다. 새 Task 추가 규칙에 따라 아래를 등록해 주십시오.

```text
| AI-03 | AI | RAG 문서 색인/검색 | C | TODO | - |
| BE-08 | Backend | LangGraph Agent Adapter | C | TODO | AI-02 |
```

담당 칸은 기존 표와 같이 **팀 문자**를 씁니다(`A` 팀 A / `B` 팀 B / `C` Backend). 두 항목 모두 Backend 가 맡으므로 `C` 입니다.

`BE-08` 이 `AI-02`(Summary/위험 발화 분석)에 의존한다는 점이 중요합니다. **`AI-02` 는 현재 담당자가 비어 있고 `TODO` 상태입니다.** 그래서 6-1 이 막혀 있습니다.

### 5-1. Agent / Backend (최민규)

```text
브랜치  backend-agent   (팀장님 지정)
PR      #10 → develop
```

처음에는 PR #6 이 머지되기 전이라 통합 브랜치에서 분기했습니다. PR #6 이 `develop` 에 머지되고(2026-09-11) 통합 브랜치를 정리하면서 PR #10 의 베이스를 `develop` 으로 옮겼습니다.

1. `requirements-agent.txt` 추가 — `langgraph` 의존성
2. `agent/` 패키지 신설 — `state.py`, `nodes.py`, `graph.py`
3. `backend/app/adapters/ai_adapter.py` 에 `LangGraphAIAdapter` 추가
4. `AI_PROVIDER` 에 `"langgraph"` 허용값 추가 (`backend/app/core/config.py:89`)
5. 루프 종료·에러 처리·타임아웃
6. 그래프 결과를 `AIAnalysisBundle` 로 변환 — `summary_evidence` 포함(4-3)
7. 근거 발화가 없는 위험 항목을 저장 전에 빼는 마지막 관문(4-4 끝)
8. 외부 LLM 호출 전 비식별 자리 — `deidentify_node` · `require_deidentified`(4-7)
9. 그래프 테스트를 `backend/tests/test_agent_graph.py` 로 옮김 — 최상위 `tests/` 에 있을 때는 CI 와 `scripts/check.sh` 가 한 번도 돌리지 않았습니다

#### 팀장님이 지정하신 담당 항목과의 대응

| 팀장님 자료 | 이 문서에서 | 상태 |
| --- | --- | --- |
| LangGraph | 4절 전체 | 신규 |
| Agent State 관리 | 4-3 `AgentState` (reducer 포함) | 신규 |
| 조건 분기 | 4-1 조건부 엣지 함수(라우터) · 4-6 판정 기준 | 신규 |
| Tool 연결 | 2-2 어댑터 패턴 — `STT_PROVIDER` / `AI_PROVIDER` | **이미 있음** |
| FastAPI | 2-1 세션 상태 기계 · 2-3 비동기 처리 | **이미 있음** |
| 각 AI API 통합 | 2-2 `PipelineAIAdapter` · 신규 `LangGraphAIAdapter` | 일부 신규 |
| DB 연결 | 3절 — 상태 저장 주체는 DB 하나로 유지 | **이미 있음** |
| Error 처리 | 2-1 `AIError` + `ErrorCode`, 4-5 루프 종료 | 일부 신규 |

**"이미 있음" 표시된 넷은 Backend 에 구현되어 있고 테스트로 검증됩니다.** 다시 만들지 않고 그대로 씁니다. 그래서 3절에서 LangGraph 를 어댑터 안에 두는 것입니다.

**기존 어댑터 계약을 바꾸지 않습니다.** `analyze(transcript_payload) -> AIAnalysisBundle` 을 그대로 만족시킵니다. 기존 `mock` 은 건드리지 않습니다. `pipeline` 은 오류 변환 함수만 `LangGraphAIAdapter` 와 함께 쓰도록 모듈 함수(`map_ai_error`)로 뺐고, 그 결과 알 수 없는 예외의 문구를 싣지 않게 되었습니다(2-1).

### 5-2. AI 모델 (이경진)

1. `risk_utterances` / `abuse_signals` / `risk_factors` 를 **실제로 채우기**
   — `develop` 기준 `ai/services/summary_service.py:215-222` 에서 빈 배열로 고정돼 있습니다.
     다만 **요약 함수를 고치자는 뜻이 아닙니다.** `ai-modeling` 판에는 요약 단계가
     위험 필드를 만들면 오류를 내는 가드가 이미 있습니다(`:148`). 요약과 위험분석을
     분리해 두신 설계이므로, **별도 단계**에서 채우는 방향으로 봅니다.
     자세한 내용은 [PROPOSAL_risk_fields.md](./PROPOSAL_risk_fields.md) §5-1 참조.
2. 각 필드 구조 확정 — [PROPOSAL_risk_fields.md](./PROPOSAL_risk_fields.md) §8 질문 답변
3. `abuse_model` 결과를 `abuse_signals` 로 넘기는 경로
   — 현재 최상위 `main.py` 에서만 쓰이고 Backend 로 전달되지 않습니다
4. `reanalysis_node` 용 함수 — RAG 문서를 받아 재판정하는 진입점
5. 비식별 연결 — `ai-modeling` 의 `pii_masking.mask_pii` 를 `deidentify_node` 에서 쓸 수 있게(4-7)

### 5-3. RAG (팀장님)

1. 임베딩 모델 확정 — **나중에 바꾸면 전체 재색인이 필요합니다**
2. `rag_data/` 원본 PDF 확보 (팀장님께 기존 수집본 확인)
3. 메타데이터 정확도 (`rag/metadata.py`) — 9/11 에 `category`·`abuse_type` 추론이 추가되었습니다
4. Agent 가 RAG 에 넘길 입력 규칙 — 상담 문장 범위, 학대 유형 표기(RAG 는 `physical` 등, 이경진 님 모델은 `신체학대` 등)
5. RAG 를 부를 곳 — 9/22 에 루트 STT 서버 `/api/v1/analyze` 에 연결하셨습니다(2-4). 이 경로는 아동 발화를 비식별 없이 OpenAI 로 보냅니다(4-7)

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

구조가 정해져도 AI 가 실제 값을 채우기 전에는 분기가 항상 한쪽으로만 흐릅니다. `AI_PROVIDER=mock` 이 새 구조의 예시 데이터를 반환하도록 먼저 수정하면, AI 작업과 병행해서 그래프를 개발할 수 있습니다.

### 6-3. PRD 상 RAG 는 Later 항목입니다 🟡

```text
01_PRD.md §7 Later
- 과거 중대사건 RAG
Must Have 가 안정적으로 동작하기 전에는 Later 기능을 우선 구현하지 않는다.
```

또한 PRD 의 RAG 는 **"과거 중대사건"**(내부 상담 기록 검색)이고, `feature/rag` 는 **지침·매뉴얼·체크리스트·판례 등 공개 문서와 현행 법령**입니다. 서로 다른 기능입니다.

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
5. **RAG 를 어디서, 언제 부를지** 확인 부탁드립니다(2-4, 4-2). 9/22 에 루트 STT 서버 `/api/v1/analyze` 에서 detected 유형이 있으면 항상 부르도록 연결하셨는데(`02ffb4d`), 이 문서는 Agent 의 `rag_node` 에서 근거가 부족할 때만 부르도록 잡았습니다. 보내주신 자료의 두 그림도 서로 다릅니다(첫 그림은 양쪽 경로 모두 RAG, 두 번째는 부족할 때만). 루트 서버 경로는 상담사 STT 검수 전 텍스트를 쓰고 Backend 세션 상태를 거치지 않습니다. 앞으로 어느 경로를 쓸지 정해 주시면 그에 맞추겠습니다. 답을 받기 전까지 Agent 는 비용이 적은 두 번째로 둡니다.
6. **9/22 연결 경로가 아동 발화를 비식별 없이 OpenAI 로 보냅니다**(2-4, 4-7). 검색 질의 임베딩·체크리스트 판정·다음 상담 질문 세 곳입니다. 9/18 회의 결정(외부 LLM 에는 로컬에서 비식별한 텍스트만)에 맞추려면 `ai-modeling` 의 `mask_pii` 를 거친 텍스트를 넘겨야 합니다. 이 경로를 유지하신다면 비식별을 언제 붙일지, Agent 로 옮긴다면 `deidentify_node` 뒤에 두면 되는지 확인 부탁드립니다.

**이경진 님**

7. 5-2 의 5개 항목 중 착수 가능한 것과 예상 시점을 알려주시면 순서를 맞추겠습니다.
8. **비식별 관련 두 가지**입니다(4-7). ① `pii_masking.mask_pii` 를 Agent 의 `deidentify_node` 에서 그대로 불러 써도 될까요? import 하는 순간 NER 모델을 올리는 구조라 Backend 테스트에서는 가짜로 바꿔 쓰려고 합니다. ② note 모드의 1차 보완 체크(`infer_abuse_pipeline._screen_missed_major_types`)는 `mask_pii` 전에 원문을 LLM 에 보냅니다. `LLM_BACKEND=openai` 로 바꾸면 원문이 외부로 나가는데, 이 단계도 비식별한 텍스트로 바꾸실 수 있을까요?

**다솔 님**

9. 5-4 의 두 가지(재분석 표시 / RAG 근거 노출)는 지금 정하지 않아도 되지만, 필요하다고 판단되면 Contract 변경이 되므로 미리 말씀해주세요.
