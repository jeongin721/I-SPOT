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

### 1-3. 화면 조회 기능 5개 중 4개가 동작하지 않습니다

`CasesView` 의 필터 4개와 정렬 1개 중, 이름·사례번호 검색을 뺀 **나머지 전부**가 이 필드에 의존합니다.

| 조회 기능 | 의존 필드 | 현재 결과 |
| --- | --- | --- |
| 이름·사례번호 검색 | `childName` `id` `guardian` | 정상 |
| 학대유형 필터 | `abuseTypes` | **항상 0건** |
| 위험도 필터 | `riskLevel` | **항상 0건** |
| 키워드 검색 | `keywords` | **항상 0건** |
| 위험도순 정렬 | `riskScore` | **무의미** (전부 동일값) |

화면은 `abuseTypes` `riskLevel` `riskScore` `keywords` 네 필드를 기대하지만, Contract 에는 이에 대응하는 값이 없습니다. `abuse_signals` 와 `risk_factors` 가 채워지면 여기서 파생할 수 있습니다.

이 때문에 Backend API 연결(PR #8)에서 기존 `CasesView` 를 **의도적으로 연결하지 않았습니다.** 지금 연결하면 고장난 것처럼 보입니다.

### 1-4. 학대 분류 모델은 이미 동작하는데 결과가 전달되지 않습니다

```text
경로 ①  Backend → ai_adapter → analysis_pipeline → LLM 요약만
                                                    risk_utterances = []

경로 ②  최상위 main.py → abuse_model/infer_abuse → 신체학대 0.72
                            ↑ 여기서 종료. Backend 로 전달 없음
```

정담원 님 파이프라인에서 학대 유형과 확신도가 이미 산출됩니다. 이경진 님이 15개 세부유형 모델도 추가하셨습니다. **연결 경로만 없는 상태**입니다.

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

- 학대유형·위험도·키워드 필터와 위험도순 정렬, **네 기능이 동작하게 됩니다**(1-3 참조)
- `types.ts` 의 `RiskUtterance` 를 확정안에 맞춰 교체합니다
- `abuse_signals` 표기 통일이 필요합니다 (아래 5절 참조)
- 화면이 쓰는 `abuseTypes` `riskLevel` `riskScore` `keywords` 를 Contract 값에서
  **어떻게 파생할지** 정해야 합니다. 예를 들어 `riskLevel` 은 `abuse_signals` 의
  `detected` 개수로 볼 수도, 최고 `confidence` 로 볼 수도 있습니다. 파생 규칙이
  화면마다 달라지지 않도록 `adapters.ts` 한 곳에 둡니다.

---

## 5. AI 영향

### 5-1. `summarize_consultation` 이 빈 배열 대신 값을 채워야 합니다

```python
# ai/services/summary_service.py:215-221  (현재)
return AIAnalysisOutput(
    summary=summary,
    risk_utterances=[],   # ← 하드코딩
    abuse_signals=[],
    risk_factors=[],
)
```

### 5-2. 학대 유형 표기가 네 곳에서 다릅니다

| 위치 | 표기 |
| --- | --- |
| `02_ARCHITECTURE.md` §7 | `PHYSICAL` `EMOTIONAL` `SEXUAL` `NEGLECT` |
| `abuse_model/infer_abuse.py` | `신체학대` `정서학대` `성학대` `방임` |
| `ai/modeling/abuse/train_subtype_v1.py` | `physical_direct` … `neglect_medical` (15종) |
| Frontend | `신체` `정서` `성` `방임` |

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

`abuse_model/infer_abuse.py` 가 이미 유형별로 이 값을 전부 산출합니다. **연결만으로 채울 수 있습니다.**

```python
# abuse_model/infer_abuse.py:153-163 이 돌려주는 형태
{
  "신체학대": {"probability": 0.72, "percentage": 72.0,
              "threshold": 0.72, "detected": True},
  ...
}
```

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
4. 세 필드를 채우는 작업의 **예상 시점**을 알려주시면 그에 맞춰 준비하겠습니다.

**팀장님**

5. `abuse_type` 을 영문 대문자 대분류로 통일하는 안에 동의하시는지요?
6. `evidence_check_node` 의 판정 기준을 위 초안으로 시작해도 될까요?

**다솔 님**

7. 화면에서 위 필드 외에 **추가로 필요한 항목**이 있으면 지금 말씀해주세요. 나중에 추가하면 AI·Backend·Frontend 를 모두 고쳐야 합니다.
