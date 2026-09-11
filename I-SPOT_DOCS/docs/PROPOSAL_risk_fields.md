# [제안] 위험 관련 필드 3종 구조 정의

> `02_ARCHITECTURE.md` §8 Contract 변경 규칙에 따른 제안서입니다.
> 확정 전이며, AI·Backend·Frontend 세 파트 합의가 필요합니다.
>
> 작성: mingyu · 2026-09-11

대상 필드 — `risk_utterances`, `abuse_signals`, `risk_factors`

---

## 1. 변경 이유

### 1-1. 같은 필드가 세 곳에서 서로 다르게 정의돼 있습니다

| 위치 | 정의 |
| --- | --- |
| `ai/schemas/analysis.py:40-42` | `List[Dict[str, Any]]` |
| `ai/services/summary_service.py:78-80` | `List[str]` |
| `ispotvscode/src/api/types.ts:282-284` | `RiskUtterance[]` / `string[]` |

지금은 **세 곳 모두 빈 배열**이라 충돌이 드러나지 않습니다. 값이 들어가는 순간 한 곳이 깨집니다.

`types.ts` 의 `RiskUtterance` 는 제가 추측으로 써둔 것입니다. 근거 없이 정한 것이므로 **채택하든 폐기하든 이번에 정리**되어야 합니다.

> **인용 파일의 위치 주의** — `ispotvscode/` 는 이 문서가 있는 브랜치에 없습니다.
> `feat/api-integration` 브랜치(PR #8)에 있습니다. 확인하시려면 아래처럼 하세요.
>
> ```bash
> git show origin/feat/api-integration:ispotvscode/src/api/types.ts
> ```
>
> 마찬가지로 `rag/` 는 `feature/rag` 브랜치에만 있습니다.

### 1-2. LangGraph 의 근거 충족 판정을 구현할 수 없습니다

팀장님이 제안하신 Agent 구조에서 분기 판정이 이렇게 동작해야 합니다.

```text
근거 충분  →  report_node
근거 부족  →  rag_node  →  reanalysis_node
```

판정하려면 근거 하나하나의 **키를 읽어야** 합니다.

```python
s["detected"]        # 이 유형이 검출됐는가
s["segment_ids"]     # 근거 발화가 Transcript 에 연결돼 있는가
```

`risk_utterances` 와 `abuse_signals` 가 `List[Dict[str, Any]]` 로만 정의돼 있어 **이 키들이 존재한다는 보장이 없습니다.** 따라서 판정 함수를 작성할 수 없습니다.

> 실제 판정 초안은 §7-4 에 있습니다. 유형별 임계값이 0.32 ~ 0.72 로 다르므로
> `confidence >= 0.7` 같은 **단일 기준은 쓰면 안 됩니다**(§7-2 참조).

### 1-3. 화면 조회 기능 5개 중 4개가 Backend 연결 시 멈춥니다

**지금은 모두 정상 동작합니다.** `CasesView` 가 `src/data/cases.ts` 의 하드코딩된 목업을 쓰기 때문입니다. 목업에는 값이 들어 있습니다.

```ts
riskScore: 87, 82, 61, 91, 54, 31, 67, 78 ...
abuseTypes: ["신체", "정서"]
keywords: ["멍", "두려움", "회피", "수면장애"]
```

문제는 **이 목업을 Backend 응답으로 바꾸는 순간** 드러납니다. Contract 에 대응하는 값이 없어 네 기능이 빈 결과를 냅니다.

| 조회 기능 | 의존 필드 | 목업 (현재) | Backend 연결 후 |
| --- | --- | --- | --- |
| 이름·사례번호 검색 | `childName` `id` `guardian` | 정상 | **정상** |
| 학대유형 필터 | `abuseTypes` | 정상 | **항상 0건** |
| 위험도 필터 | `riskLevel` | 정상 | **항상 0건** |
| 키워드 검색 | `keywords` | 정상 | **항상 0건** |
| 위험도순 정렬 | `riskScore` | 정상 | **무의미** (값 없음) |

`abuse_signals` 와 `risk_factors` 가 채워지면 여기서 파생할 수 있습니다. 그래서 **PR #8 에서 기존 `CasesView` 를 의도적으로 연결하지 않았습니다.** 지금 연결하면 잘 되던 화면이 고장난 것처럼 보입니다.

#### 다만 이 필터들은 UI 명세에 없는 항목입니다

`03_UI_UX.md` §3 의 S02 Case List 명세는 다음까지입니다.

```text
담당 사례 · 사례 코드 · 최근 상담일 · 상태 · 검색 · 새 사례
```

**학대유형·위험도·키워드 필터는 명세에 없습니다.** 구현 과정에서 추가된 것으로 보입니다.

그리고 같은 문서 §6 에 이런 규칙이 있습니다.

> 새 데이터가 필요하면 **임의로 화면용 필드를 만들지 않는다.**
> `02_ARCHITECTURE.md` 의 API Contract 변경 필요 여부를 먼저 확인한다.

따라서 이 절은 **"필터가 고장났으니 고치자"** 가 아니라 **"화면이 먼저 만든 필드를 Contract 에 맞출지, 화면에서 뺄지 정하자"** 로 읽어 주십시오. 선택지는 둘입니다.

| 선택 | 내용 |
| --- | --- |
| Contract 에 반영 | 아래 변경안대로 정의하고 화면이 파생해 쓴다 |
| 명세대로 축소 | 필터를 명세 범위(상태·검색)로 되돌린다 |

Must Have 인 **"신체/정서/성/방임 관련 신호"** 와 **"근거 문장 제공"**(`01_PRD.md` §5)은 필터와 무관하게 어차피 필요하므로, 이 제안의 §7 자체는 어느 쪽을 택하든 유효합니다.

### 1-4. 학대 분류 모델은 이미 동작하는데 결과가 전달되지 않습니다

```text
경로 ①  Backend → ai_adapter → analysis_pipeline → LLM 요약만
                                                    risk_utterances = []

경로 ②  최상위 main.py → abuse_model/infer_abuse → 신체학대 0.72
                            ↑ 여기서 종료. Backend 로 전달 없음
```

정담원 님 파이프라인에서 학대 유형과 확신도가 이미 산출됩니다. 이경진 님이 15개 세부유형 모델도 추가하셨습니다.

다만 **배선만 하면 되는 것은 아닙니다.** 모델이 주는 것은 유형별 확률·임계값·검출여부뿐이고, 근거 발화(`segment_ids`)는 주지 않습니다. 자세한 내용은 §7-2 를 보십시오.

---

## 2. 영향 Contract

- `I-SPOT_DOCS/docs/02_ARCHITECTURE.md` §7 AI Output Contract
- `ai/schemas/analysis.py` — `AIAnalysisOutput`
- `ai/services/summary_service.py` — `SummaryLLMOutput`
- `backend/app/schemas/contracts.py` — `AIAnalysisResult`
- `ispotvscode/src/api/types.ts` — `AnalysisResult`, `RiskUtterance`

`schema_version` 은 `"1.0"` 을 유지합니다. 기존 필드명·개수는 바뀌지 않고 **빈 배열의 내부 구조만 정의**하기 때문입니다.

---

## 3. Backend 영향

**DB 마이그레이션은 필요 없습니다.** `ai_analyses.result` 가 JSON 컬럼이라 구조가 바뀌어도 스키마 변경이 없습니다.

```python
# backend/app/models/analysis.py:46
result: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONType, nullable=True)
```

필요한 작업은 다음과 같습니다.

- `contracts.py` 에 `RiskUtterance` / `AbuseSignal` / `RiskFactor` 모델 추가
- 필터·정렬을 위한 조회 경로 (JSON 내부 검색 또는 별도 컬럼 승격 검토)

### 검증을 강화할지는 별도 판단이 필요합니다

현재 `AIAnalysisResult` 는 **리스트·사전 형태인지만 확인하고 키는 전혀 검사하지 않습니다.**

```python
# backend/app/schemas/contracts.py:64-77
class AIAnalysisResult(BaseModel):
    """
    AI 담당의 Structured JSON Contract.

    9월에는 위험 관련 필드가 빈 배열일 수 있다.
    Backend 는 내용을 판단하지 않고 그대로 저장/전달한다.
    """

    schema_version: Literal["1.0"] = SCHEMA_VERSION
    summary: AISummaryBody = Field(default_factory=AISummaryBody)
    risk_utterances: List[Dict[str, Any]] = Field(default_factory=list)
    abuse_signals: List[Dict[str, Any]] = Field(default_factory=list)
    risk_factors: List[Dict[str, Any]] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
```

**"내용을 판단하지 않는다" 는 의도적인 설계**입니다. AI 출력이 바뀌어도 Backend 가 막지 않도록 일부러 느슨하게 둔 것입니다.

구조를 확정한 뒤에도 이 방침을 유지할지는 선택입니다.

| 방식 | 장점 | 단점 |
| --- | --- | --- |
| 현행 유지 (`Dict[str, Any]`) | AI 쪽 변경에 Backend 가 안 막힘 | 잘못된 값이 화면까지 감 |
| 모델로 검증 | 깨진 데이터를 조기 차단 | AI 가 필드 추가할 때마다 Backend 수정 |

**절충안** — `ConfigDict(extra="allow")` 로 정의하면 명시한 키는 검증하면서 추가 키는 통과시킵니다. `audio_feature` 스키마에서 이미 쓰고 있는 방식입니다.

마지막 조회 경로 항목은 **이번 제안 범위 밖**입니다. 구조가 정해진 뒤 성능을 보고 판단하겠습니다.

---

## 4. Frontend 영향

- 학대유형·위험도·키워드 필터와 위험도순 정렬 네 기능이 **목업을 떼고 Backend 에 붙여도 계속 동작합니다**(1-3 참조). 지금 연결하면 이 네 기능이 빈 결과를 냅니다.
- `types.ts` 의 `RiskUtterance` 를 확정안에 맞춰 교체합니다
- `abuse_signals` 표기 통일이 필요합니다 (아래 5절 참조)
- 화면이 쓰는 `abuseTypes` `riskLevel` `riskScore` `keywords` 를 Contract 값에서
  **어떻게 파생할지** 정해야 합니다. 예를 들어 `riskLevel` 은 `abuse_signals` 의
  `detected` 개수로 볼 수도, 최고 `confidence` 로 볼 수도 있습니다. 파생 규칙이
  화면마다 달라지지 않도록 `adapters.ts` 한 곳에 둡니다.

### ⚠️ 화면의 값 표기가 Contract 안과 다릅니다

`ispotvscode/src/data/cases.ts` 의 정의입니다.

```ts
export type RiskLevel = "high" | "mid" | "low";
export type AbuseType = "신체" | "정서" | "성" | "방임";
```

§7-3 에서 제안한 `severity` 는 `LOW | MEDIUM | HIGH` 인데 화면은 `low | mid | high` 를 씁니다. **대소문자도 다르고 중간값 이름도 다릅니다**(`MEDIUM` vs `mid`).

Contract 안은 대문자로 통일하고, 화면 값으로의 변환은 `adapters.ts` 에서 처리합니다. `guardian_type` 과 같은 방식입니다.

```ts
const SEVERITY_TO_RISK_LEVEL: Record<Severity, RiskLevel> = {
  HIGH: "high", MEDIUM: "mid", LOW: "low",
};
```

---

## 5. AI 영향

### 5-0. 이 작업은 `TASKS.md` 의 `AI-02` 이고, **담당자가 비어 있습니다**

```text
| AI-02 | AI | Summary/위험 발화 분석 | - | TODO | AI-01 |
| BE-04 | Backend | AI 결과 저장/조회 | C | REVIEW | AI-02 |
```

`AI-02` 는 담당 칸이 `-` 이고 상태가 `TODO` 입니다. **아무도 맡고 있지 않습니다.**

`BE-04`(Backend AI 결과 저장/조회)가 `AI-02` 에 의존하며 이미 `REVIEW` 상태이므로, **Backend 쪽은 받을 준비가 되어 있고 채울 사람만 없는 상태**입니다.

이 제안이 합의되면 `TASKS.md` 의 `AI-02` 에 담당자를 지정하고 `IN_PROGRESS` 로 옮겨 주십시오.

### 5-1. `summarize_consultation` 이 빈 배열 대신 값을 채워야 합니다

```python
# ai/services/summary_service.py:215-222  (현재)
return AIAnalysisOutput(
    schema_version="1.0",
    summary=summary,
    risk_utterances=[],   # ← 하드코딩
    abuse_signals=[],
    risk_factors=[],
    warnings=warnings,
)
```

### 5-2. 학대 유형 표기가 네 곳에서 다릅니다

| 위치 | 표기 |
| --- | --- |
| `02_ARCHITECTURE.md` §7 | `PHYSICAL` `EMOTIONAL` `SEXUAL` `NEGLECT` |
| `abuse_model/infer_abuse.py` | `신체학대` `정서학대` `성학대` `방임` |
| `ai/modeling/abuse/train_subtype_v1.py` | `physical_direct` … `neglect_medical` (15종) |
| `ispotvscode/src/data/cases.ts` | `신체` `정서` `성` `방임` |

세부유형 15종은 접두사가 대분류와 일치하므로 매핑이 자명합니다.

```text
physical_*   →  PHYSICAL
emotional_*  →  EMOTIONAL
sexual_*     →  SEXUAL
neglect_*    →  NEGLECT
```

**Contract 상 값은 영문 대문자 대분류로 통일**하고, 한글 표기는 화면에서 변환할 것을 제안합니다. 이미 `guardian_type` 을 같은 방식으로 처리하고 있습니다.

---

## 6. Test 영향

```python
# backend/tests/test_analysis.py:176-179
# 9월 범위에서는 위험 관련 항목이 빈 배열이다.
assert result["risk_utterances"] == []
assert result["abuse_signals"] == []
assert result["risk_factors"] == []
```

이 단정 3건을 구조 검증으로 교체합니다. `AI_CONTRACT_KEYS` 는 변경 없습니다.

Mock provider(`AI_PROVIDER=mock`)도 새 구조에 맞는 예시 데이터를 반환하도록 수정이 필요합니다. 그래야 AI 파이프라인 없이도 Frontend 개발이 가능합니다.

---

## 7. 변경안

### 기존 필드명과의 관계

이미 API 응답에 나가고 있는 `summary_evidence` 는 이런 모양입니다.

```jsonc
{ "key_point": "...", "segment_ids": ["seg_004"], "score": 0.75 }
```

아래 변경안은 **확신도를 `score` 가 아니라 `confidence` 로** 씁니다. 이름을 다르게 둔 이유는 의미가 다르기 때문입니다.

| 필드 | 의미 |
| --- | --- |
| `summary_evidence.score` | 요약 문장과 근거 발화의 **연결 강도** (팀 B `EvidenceLink` 유래) |
| 아래의 `confidence` | 분류 모델이 낸 **확률값** (`abuse_model` 의 `probability`) |

같은 이름을 쓰면 임계값 비교를 섞어 쓰기 쉬워 일부러 구분합니다. **다른 이름이 낫다고 보시면 말씀해 주세요.**

연결 대상이 하나면 `segment_id`, 여럿이면 `segment_ids` 로 둡니다. 발화 하나를 가리키는 `risk_utterances` 만 단수입니다.

### 7-1. `risk_utterances` — 위험 관련 발화

```jsonc
{
  "segment_id": "seg_047",              // 필수. Transcript 와 연결
  "text": "아빠가 막대기로 때렸어요",      // 필수
  "abuse_type": "PHYSICAL",             // 필수. 대분류 4종
  "abuse_subtype": "physical_object",   // 선택. 15종 세부유형
  "confidence": 0.91,                   // 필수. 0.0 ~ 1.0
  "reason": "도구를 사용한 체벌 진술"      // 필수. 상담사에게 보여줄 근거
}
```

`segment_id` 가 핵심입니다. `02_ARCHITECTURE.md` §7 의 *"근거가 있는 결과는 가능한 한 `segment_id` 로 STT 와 연결한다"* 를 따르며, 상담사가 **원본 음성을 직접 확인**할 수 있게 합니다.

### 7-2. `abuse_signals` — 학대 유형별 종합 신호

```jsonc
{
  "abuse_type": "PHYSICAL",             // 필수
  "confidence": 0.72,                   // 필수. 모델 원본 확률
  "threshold": 0.72,                    // 필수. 이 유형의 판정 기준선
  "detected": true,                     // 필수. confidence >= threshold
  "segment_ids": ["seg_047", "seg_052"],// 필수. 근거 발화 목록
  "subtypes": [                         // 선택
    { "name": "physical_object", "confidence": 0.68 }
  ]
}
```

`abuse_model/infer_abuse.py` 가 이 중 **세 필드를 이미 산출합니다.**

```python
# abuse_model/infer_abuse.py:153-163 이 돌려주는 형태
{
  "신체학대": {"probability": 0.72, "percentage": 72.0,
              "threshold": 0.72, "detected": True},
  ...
}
```

| 필드 | 모델이 주나 | 비고 |
| --- | --- | --- |
| `confidence` | ✅ | `probability` 를 그대로 |
| `threshold` | ✅ | 그대로 |
| `detected` | ✅ | 그대로 |
| `abuse_type` | ⚠️ | 한글 키(`신체학대`)라 **영문 대분류로 변환 필요** |
| `segment_ids` | ❌ | **모델이 주지 않습니다** |
| `subtypes` | ❌ | 별도 세부유형 모델 필요 |

`segment_ids` 가 문제입니다. `predict_abuse(text: str)` 는 **문자열 하나만 받습니다.** `child_analysis_text` 가 아동 발화를 이어 붙여 만든 텍스트라, 모델은 어느 segment 에서 나온 판정인지 알지 못합니다.

따라서 `segment_ids` 는 **텍스트를 만들 때 사용한 segment 목록을 별도로 보존해** 채워야 합니다. 단순 배선이 아니라 `child_analysis_text` 쪽 수정이 함께 필요합니다.

> `05_RULES.md` §3 은 **"근거 없는 위험 신호 생성"** 을 금지합니다. `segment_ids` 없이
> `abuse_signals` 만 채우면 이 규칙에 걸립니다. 판정과 근거는 함께 와야 합니다.

### ⚠️ `threshold` 를 반드시 함께 넘겨야 합니다

유형별 판정 기준선이 두 배 넘게 차이납니다.

| 유형 | threshold |
| --- | --- |
| 신체학대 | 0.72 |
| 정서학대 | 0.39 |
| 성학대 | 0.53 |
| 방임 | **0.32** |

`confidence` 만 넘기고 화면이나 Agent 가 `>= 0.7` 같은 **단일 기준으로 판단하면 방임을 전부 놓칩니다.** 0.5 짜리 방임 신호는 모델 기준으로는 이미 "검출" 인데 버려집니다.

`detected` 는 모델이 이미 계산한 값이므로 그대로 전달합니다.

### 7-3. `risk_factors` — 위험 요인

```jsonc
{
  "code": "RETALIATION_FEAR",           // 필수. 고정 코드
  "label": "보복 두려움",                 // 필수. 표시용
  "segment_ids": ["seg_012"],           // 필수
  "severity": "HIGH"                    // 필수. LOW | MEDIUM | HIGH
}
```

`code` 목록은 **이경진 님이 실제로 추출 가능한 범위**로 정해주시면 그에 맞추겠습니다.

### 7-4. 근거 충족 판정 기준 (초안)

단일 확신도 기준(`>= 0.7`)은 **쓸 수 없습니다.** 위에서 본 대로 유형별 기준선이 0.32 ~ 0.72 로 다르기 때문입니다. 모델이 계산한 `detected` 를 기준으로 삼습니다.

```python
def evidence_verdict(state) -> str:
    signals = [s for s in state["abuse_signals"] if s.get("detected")]
    linked = [s for s in signals if s.get("segment_ids")]

    sufficient = len(linked) >= 1
    return "sufficient" if sufficient else "insufficient"
```

이 함수는 LangGraph 의 **조건부 엣지 함수**로 쓰입니다. 노드가 아니므로 State 를 바꾸지 않고 목적지 이름만 돌려줍니다. 배치 방법은 [PLAN_langgraph_agent.md](./PLAN_langgraph_agent.md) §4-1 을 참고하세요.

판정 기준을 **"검출된 유형이 1건 이상이고, 그 근거 발화가 Transcript 에 연결돼 있을 것"** 으로 둡니다. 근거 없는 판정은 상담사가 확인할 수 없으므로 `segment_ids` 연결을 필수로 봅니다.

`>= 1` 은 초안입니다. 실제 출력을 보고 조정하되, **확신도 임계값을 Agent 쪽에서 다시 정하지는 않습니다.** 모델이 유형별로 튜닝한 값을 존중합니다.

**먼저 필요한 것은 `detected` 와 `segment_ids` 키의 존재 보장**입니다.

---

## 8. 확인 부탁드릴 사항

**이경진 님**

1. 위 세 구조에서 **실제로 산출 가능한 필드**는 어디까지인가요? 불가능한 항목은 빼겠습니다.
2. `risk_factors` 의 `code` 를 고정 목록으로 둘 수 있을까요? 가능한 코드 목록을 주시면 Backend·Frontend 가 맞추겠습니다.
3. `abuse_model` 결과를 `abuse_signals` 로 넘기는 경로를 만드실 예정인가요? 아니면 Backend 에서 별도로 호출할까요?
4. **`segment_ids` 를 어떻게 채울지**가 가장 어려운 지점으로 보입니다(§7-2). `predict_abuse(text: str)` 는 문자열만 받아서 어느 segment 의 판정인지 모릅니다. `child_analysis_text` 를 만들 때 쓴 segment 목록을 함께 남기는 방식이 가능할까요?
5. 세 필드를 채우는 작업의 **예상 시점**을 알려주시면 그에 맞춰 준비하겠습니다.

**팀장님**

6. `abuse_type` 을 영문 대문자 대분류로 통일하는 안에 동의하시는지요?
7. 근거 충족 판정(`evidence_verdict`, §7-4)을 위 초안으로 시작해도 될까요?

**다솔 님**

8. 화면에서 위 필드 외에 **추가로 필요한 항목**이 있으면 지금 말씀해주세요. 나중에 추가하면 AI·Backend·Frontend 를 모두 고쳐야 합니다.
9. `CasesView` 의 학대유형·위험도·키워드 필터는 `03_UI_UX.md` S02 명세에 없는 항목입니다(1-3). **유지하실 계획이면 Contract 에 반영**하고, 아니면 명세 범위로 줄이는 편이 낫습니다. 어느 쪽인지 알려주시면 그에 맞추겠습니다.
10. `03_UI_UX.md` §5 가 **"위험 확정" · "AI 판정"** 같은 표현을 금지합니다. `detected: true` 는 모델 내부 값이므로 화면에는 **"관련 신호"** · **"추가 확인 필요"** 로 표기해 주세요. 색상만으로 위험도를 표현하지 않는 규칙도 같은 절에 있습니다.
