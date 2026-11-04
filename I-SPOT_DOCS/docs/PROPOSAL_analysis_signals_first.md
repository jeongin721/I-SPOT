# [제안] AI 분석 두 번 저장 — 학대 신호 확인(2단계)을 먼저 보이기

> `02_ARCHITECTURE.md` §8 Contract 변경 규칙과 `05_RULES.md` §5 에 따른 제안서입니다.
> AI 모듈 쪽은 이경진 님 PR #150(심각도 호출 순서) · #151(`on_signals_ready` 콜백)에 있고, 이 문서는 **Backend 저장 방식 · 분석 응답 · 화면**이 대상입니다.
> 큰 방향은 **2026-11-04 에 이경진 · 최민규가 먼저 맞췄습니다(§7-0).** §5(AI 영향)는 이경진 님이 썼습니다.
> 팀장님 · 다솔 님 확인을 받기 전이라 구현은 시작하지 않았습니다(§8).
>
> 작성: 최민규 · 2026-11-04

대상 — `ai_analyses` 표의 새 칸 둘, `GET /api/v1/sessions/{session_id}/analysis` 응답의 새 칸 둘, 회차가 `AI_REVIEW_REQUIRED` 로 넘어가는 **시점**, 새 409 규칙, 새 감사 종류 둘, 새 오류 코드 하나

> 회차 상태의 **종류**와 AI Output Contract 의 **모양**은 바꾸지 않습니다. 사람이 확인하는 지점(`AI_REVIEW_REQUIRED`)도 그대로 거칩니다.

---

## 1. 변경 이유

### 1-1. 원문을 확정한 뒤 학대 신호 확인 화면이 늦게 뜹니다

11/03 데모에서 "원문 확정 뒤 학대 신호 확인 화면이 늦게 뜬다" 는 이야기가 있었습니다.
감사 기록상 분석 시간은 녹음 5분 기준 56~79초였습니다(이경진 님 확인).

### 1-2. 2단계 화면이 쓰는 값은 절반 시간에 나오는데, 전부 끝나야 한 번에 저장합니다

2단계(학대 신호 확인) 화면이 쓰는 값은 2차 세부유형 · 유형별 심각도 · 기록 초안의 위험 신호 발화 · 관련 조문 · 보호요인입니다.
가상 녹취 5분 기준으로 이 값은 약 22초에 모두 나오고, 분석 전체는 45~53초가 걸립니다(#151 실측, 이경진 님).

나머지 — 상담 요약 · 일지, 체크리스트, 원하는 변화, 서사 요약, 회차 간 변화, 확인 메모, 추가 질문, 주제 비중 — 는 3 · 4단계에서만 씁니다.
그런데 지금 서버는 모듈이 모든 결과를 돌려준 뒤 한 번에 저장해서(`backend/app/services/analysis_service.py` `_save_analysis_result`), 2단계가 3 · 4단계 초안을 기다립니다.

### 1-3. 이 제안이 하지 않는 것

- AI 판단 규칙 · 출력 필드의 뜻을 바꾸지 않습니다. 학대 여부를 확정하지 않는 원칙(`05_RULES.md` §1)은 그대로입니다.
- 회차 상태를 새로 만들지 않습니다(§7-3).
- 분석 전체에 걸리는 시간과 시간 제한(`AI_TIMEOUT_SECONDS`)은 그대로입니다. 2단계가 먼저 보일 뿐입니다.
- 3 · 4단계 초안만 따로 다시 만드는 기능은 이번에 넣지 않습니다(§3-7, §8).

---

## 2. 영향 Contract

- `backend/docs/API_CONTRACT.md`
  - §2 Session 상태 — `AI_REVIEW_REQUIRED` 로 넘어가는 **시점**을 '2단계 값이 저장됐을 때' 로 고칩니다(상태 종류 · 전이 표는 그대로).
  - §8 Analysis — `GET` 응답의 `analysis` 에 `drafts_status` · `drafts_error` 를 더하고, `POST`(재분석)에 409 조건 하나를 더합니다.
  - §9 Summary — `PATCH` · `approve` 에 409 조건 하나를 더합니다.
  - §18 Followup Questions · §18.1 Followup Checks — `PUT` 에 409 조건 하나를 더합니다.
  - §13 Error Code 목록 — `ANALYSIS_DRAFTS_PENDING`(409) 을 더합니다.
- DB — `ai_analyses` 에 칸 둘(§7-2), 마이그레이션 1개.
- 감사 종류(`AuditAction`) — `ANALYSIS_DRAFTS_COMPLETED` · `ANALYSIS_DRAFTS_FAILED` 를 더합니다.
- 변경 **없음**: `02_ARCHITECTURE.md` §7 AI Output Contract(콜백 결과도 같은 `AIAnalysisResult` 로 검증합니다), 회차 상태 종류와 전이 표(`backend/app/core/state_machine.py`), 위험도 판단(§11) · 일정 · 문서 API.

---

## 3. Backend 영향

### 3-1. 흐름

```
POST …/analysis → 회차 AI_PROCESSING · 분석 PROCESSING                       (지금과 같음)
   │
   ├─ [콜백 on_signals_ready] 첫 저장 ─────────────────────────────────────── 약 22초
   │     회차 AI_PROCESSING → AI_REVIEW_REQUIRED
   │     분석 PROCESSING → COMPLETED, drafts_status = PENDING
   │     result = 콜백 결과(2단계 칸이 채워지고 3 · 4단계 칸은 빈 값)
   │     Summary 는 만들지 않음 · 감사 ANALYSIS_COMPLETED(지금과 같은 detail)
   │
   └─ [모듈이 돌아옴] 둘째 저장 ──────────────────────────────────────────── 45~53초
         drafts_status PENDING → DONE
         result 의 3 · 4단계 칸 · summary.overview · summary.assessment · warnings 를 마지막 값으로
         Summary 초안 맞춤(_sync_summary_draft, 상담사가 고친 Summary 는 그대로)
         감사 ANALYSIS_DRAFTS_COMPLETED → 19절 다음 상담 체크리스트(지금 자리 그대로)
```

콜백이 불리지 않으면(콜백 전에 실패 · 콜백 인자를 받지 않는 예전 판 모듈 · 첫 저장이 실패) **지금과 똑같이** 끝에서 한 번에 저장하거나 `AI_FAILED` 로 마감합니다.

### 3-2. 저장마다 조건 — 모두 조건부 UPDATE 의 행 수로 판단

| 저장 | 조건 | 조건이 맞지 않으면 |
| --- | --- | --- |
| 첫 저장 | 회차 `AI_PROCESSING` · 분석 `PROCESSING`(지금 `_claim_finish` 그대로) | 버림 — 그 사이 멈춤 판정 · 새 분석 요청 · 회차 삭제가 있었음 |
| 둘째 저장 | 그 분석 id · `drafts_status = PENDING` | 버림 |
| 초안 실패 마감 | 그 분석 id · `drafts_status = PENDING` → `FAILED` | 버림 |
| 콜백 없이 끝남 | 지금 그대로(회차 `AI_PROCESSING` → `AI_REVIEW_REQUIRED` / `AI_FAILED`) | 지금 그대로 |

읽어 둔 값으로 판단하면 그 사이 바뀐 것을 놓쳐서, 지금 `_claim_finish` 처럼 `WHERE 상태 = …` 의 행 수로 판단합니다(SQLite · PostgreSQL 모두 원자적).

### 3-3. 둘째 저장이 쓰는 칸 · 쓰지 않는 칸

| 쓰는 칸(마지막 값으로) | 쓰지 않는 칸(첫 저장 값 그대로) |
| --- | --- |
| `summary.overview` · `summary.assessment` · `session_change_notes` · `followup_check_points` · `followup_questions` · `topic_tags` · `warnings` | `risk_utterances` · `abuse_signals` · `risk_factors` · `severity_ratings` · `protective_factors` · `summary.key_points` · `summary_evidence` |

- 2단계 칸을 다시 쓰지 않는 까닭: 상담사가 첫 저장 뒤 2단계를 보고 판단을 적기 시작했을 수 있습니다. 모듈은 마지막 반환값의 2단계 칸이 콜백 값과 같다고 하지만(#151), 서버가 그것에 기대지 않습니다.
- `warnings` 는 2단계 칸으로 보지 않고 마지막 값으로 바꿉니다. 콜백 때에는 상담 요약이 아직 없어 '상담 요약을 만들지 못했습니다' 경고가 붙기 때문입니다(§5 · §8 — 모듈에서도 빼 달라고 요청). 법령 데이터 경고처럼 2단계에서 생긴 경고는 마지막 값에도 있습니다.

### 3-4. 스레드와 DB 세션

- 콜백은 `run_with_timeout` 이 띄운 작업 스레드 안에서 불립니다. 첫 저장은 바깥 `process_analysis` 의 DB 세션을 쓰지 않고 **콜백 안에서 `SessionLocal` 을 따로 열어** 커밋합니다.
- 콜백에서 난 예외는 서버가 잡아 예외 종류만 로그에 남기고 모듈을 멈추지 않습니다(모듈은 콜백 예외를 잡지 않습니다). 첫 저장이 실패했으면 끝에서 지금처럼 한 번에 저장합니다.
- 바깥 스레드는 둘째 저장 전에 회차 · 분석을 다시 읽습니다(다른 DB 세션이 커밋했기 때문).

### 3-5. 실패 · 시간 초과 · 멈춤

- **첫 저장 뒤 모듈 예외 · 시간 초과**: `drafts_status = FAILED`, `drafts_error` 에 `AI_FAILED` / `AI_TIMEOUT` 과 고정 문구. 회차는 `AI_REVIEW_REQUIRED`, 2단계 결과는 그대로. 감사 `ANALYSIS_DRAFTS_FAILED`(detail 은 오류 코드만).
  지금 `_fail_analysis` 는 회차가 `AI_PROCESSING` 이 아니면 아무것도 하지 않아서, 고치지 않으면 `PENDING` 이 계속 남습니다.
- **멈춤(배포 · 재시작으로 작업이 사라짐)**: `session_service.expire_stale_processing` 이 `PENDING` 도 봅니다. 요청 시각(`ai_started_at`) + 준비 제한 + `AI_TIMEOUT_SECONDS` + 여유 시간이 지나면 `FAILED` 로 마감합니다. 지금처럼 분석 조회 · 재분석 요청 때 판정합니다.
- 시간 제한(`_job_deadline`)은 바꾸지 않습니다. 분석 전체가 지금 제한 안에 끝나야 합니다.

### 3-6. `PENDING` 동안 막는 것 · 받는 것

| 막음(409 `ANALYSIS_DRAFTS_PENDING`) | 받음 |
| --- | --- |
| 재분석 `POST …/analysis` | 위험도 판단 저장(§11 — 2단계에서 상담사가 쓰는 것) |
| Summary `PATCH` · `approve`(§9) | 모든 조회 |
| 추가 질문 `PUT`(§18) · 확인 사항 `PUT`(§18.1) | |

- Summary 를 첫 저장에서 만들지 않는 것과 같은 까닭입니다: 빈 Summary 를 상담사가 먼저 고치면(`is_edited`) 둘째 저장이 AI 초안을 넣지 못합니다.
- 추가 질문 · 확인 사항 저장은 지금 'AI 분석 중에는 받지 않는다' 를 회차 상태로 막는데(`followup_question_service.EDITABLE_STATUSES` 에 `AI_REVIEW_REQUIRED` 가 있음), 회차를 먼저 넘기면 `PENDING` 동안 열려 버려서 따로 막습니다.

### 3-7. 초안이 실패했을 때 다시 하기

- 이번에는 **지금 있는 재분석**(`POST …/analysis`, 2단계부터 전부 다시)으로 합니다. `FAILED` 는 막지 않습니다.
- 2단계 결과는 두고 3 · 4단계만 다시 만들려면 모듈에 새 진입점(2단계 결과를 받아 나머지만 돌리기)이 필요합니다 — 후속으로 둡니다(§8).

### 3-8. 그대로인 곳

- 앞 회차 결과를 읽는 곳 — 다음 회차 분석의 사례 정보(`case_context_service`)와 종결 요약(`closure_review_service`)은 **승인된** 회차 · 요약만, 상담 전 브리핑의 추가 질문 · 확인 사항은 **저장한** 목록만 읽습니다. `PENDING` 동안 승인과 저장을 막으므로 바꿀 것이 없습니다. 브리핑의 학대 신호 이력은 2단계 값이라 첫 저장 뒤 바로 보입니다.
- 처리 대기 업무(`task_service`)의 '분석 검토' 는 첫 저장 때 생깁니다(바라는 동작).

---

## 4. Frontend 영향

- 타입(`counselor-web/src/api/types.ts`): 분석 응답에 `drafts_status` · `drafts_error`, 오류 코드 `ANALYSIS_DRAFTS_PENDING`.
- 되풀이 조회(`data/useSessionAnalysis.ts`): 지금 '회차가 처리 중' 일 때만 `usePolling` 합니다. `drafts_status === "PENDING"` 일 때도 돌게 합니다(간격은 지금 `POLL_INTERVAL_MS` 2.5초 그대로).
- 2단계(`data/screens/signalReview.ts`): 바꾸지 않습니다.
- 3 · 4단계 — 지금 'AI_PROCESSING 이면 분석 중' 으로 판단하는 곳에서 `PENDING` 도 같이 다룹니다:
  - `PENDING` → "AI 초안을 만드는 중입니다. 잠시 뒤 저절로 보입니다."
  - `FAILED` → "AI 초안을 만들지 못했습니다." + 재분석 단추(2단계 결과도 다시 만들어진다는 안내)
  - 대상: 3단계 일지(`data/screens/noteWrite.ts`), 확인 메모 · 추가 질문(`data/screens/followupQ.ts`), 확인 사항(`data/screens/followupChecks.ts`), 요약 검토(`data/useSummaryReview.ts`)
- 회차 목록(`data/sessionRows.ts`): 상태 이름은 'AI 결과 검수 필요' 그대로입니다. 초안 진행을 목록에도 보일지는 §8 에서 여쭙니다.

---

## 5. AI 영향

> 작성: 이경진 · 2026-11-04. 코드는 #150(심각도 호출 순서) · #151(`on_signals_ready` 콜백)에 있습니다.

### 5-1. 진입점

```python
analyze_audio_session_as_contract(stt_result, ..., on_signals_ready=cb)   # ai/modeling/abuse/contract_adapter.py
cb(contract_dict, summary_evidence, model_name)                           # 반환값과 같은 튜플 모양
```

- `contract_dict` 는 `AIAnalysisResult` 로 그대로 검증됩니다(#151 시험).
- 기본값 `None` 이면 예전과 같습니다. 서버는 받지 않는 예전 판 모듈과도 맞게 `accepts_keyword` 로 넘깁니다.
- 안쪽 `infer_audio_session.analyze_audio_session(..., on_signals_ready=)` 은 날 결과(dict)를 넘기고, `contract_adapter` 가 계약 모양으로 바꿔 `cb` 를 부릅니다.

### 5-2. 부르는 시점 · 스레드

- **2차 세부유형 · 유형별 심각도 · 기록 초안(위험 신호 발화 · 관련 조문 · 아동 진술) · 보호요인이 모두 끝났을 때 한 번** 부릅니다.
- 분석을 부른 스레드(서버에서는 `run_with_timeout` 작업 스레드)에서 **동기로** 부릅니다. 3 · 4단계의 상담 요약 · 일지 · 체크리스트 · 원하는 변화 호출은 이미 다른 스레드에서 돌고 있어 콜백이 저장하는 동안에도 계속 갑니다. 다만 서사 요약 · 확인 메모 · 추가 질문 · 주제는 콜백이 돌아온 뒤 시작하므로, 콜백 안에서는 저장만 짧게 하는 것이 좋습니다.
- 2단계 값이 모이기 전에 어느 호출이든 실패하면 부르지 않고, 예전처럼 분석 예외로 끝납니다.

### 5-3. 넘기는 값

| 구분 | 칸 |
| --- | --- |
| 채워진 칸 | `risk_utterances` · `abuse_signals` · `risk_factors` · `severity_ratings` · `protective_factors` · `summary.key_points`(아동 진술) · `summary_evidence` · `warnings`(그때까지) |
| 빈 칸 | `summary.overview`(`""`) · `summary.assessment`(빈 칸들) · `session_change_notes` · `followup_check_points` · `followup_questions`(빈 목록) · `topic_tags`(`None`) |

- 콜백 뒤의 서사 요약 · 확인 메모 · 추가 질문은 2단계 값을 **읽기만** 합니다. 그래서 마지막 반환값의 2단계 칸 · `summary.key_points` · `summary_evidence` 는 콜백 값과 같습니다(§3-3 의 "둘째 저장은 3 · 4단계 칸만" 과 맞습니다).
- `warnings`: 콜백 때는 상담 요약을 아직 만들기 전이라 `agent/summary_converter.py` 가 붙이는 `OVERVIEW_EMPTY_WARNING`('상담 요약을 만들지 못했습니다…')을 **콜백 결과에서만 뺍니다**(#151 반영, 민규 리뷰). 법령 데이터 경고처럼 2단계에서 생긴 경고는 남고, 마지막 반환값의 `warnings` 는 지금 그대로입니다. 서버는 둘째 저장에서 `warnings` 를 마지막 값으로 바꿉니다.

### 5-4. 예외

- 콜백에서 난 예외는 모듈이 잡지 않습니다. 서버가 감쌉니다(§3-4).
- 콜백 뒤 3 · 4단계 호출이 실패하거나 마감을 넘기면 예전처럼 분석 예외로 끝납니다. 서버는 이 경로를 `drafts FAILED` 로 마감합니다(§3-5).

### 5-5. 호출 순서 (#150 · #151)

| 차례 | 호출 | 콜백 전 / 후 |
| --- | --- | --- |
| ① | 2차 세부유형 | 전 |
| ② | 유형별 심각도(#150 — ① 바로 뒤로 옮김, 2~5초 줄임) · 기록 초안 · 보호요인 · 상담 요약 · 일지 · 체크리스트 · 원하는 변화를 겹쳐 돌림 | 심각도 · 기록 초안 · 보호요인이 끝나면 **콜백** |
| ③ | 상담 요약 · 일지 · 체크리스트 · 원하는 변화 기다림 → 서사 요약 → 회차 간 변화(LLM 아님) → 확인 메모 · 추가 질문 · 주제 | 후 |

프롬프트 · 모델 · 출력 필드의 뜻은 바꾸지 않았습니다.

### 5-6. 실측 (가상 녹취 5분 · 40줄, ispot-gpu T4, 실제 모델 + 실제 OpenAI, 모델을 올린 뒤)

| | 2차 세부유형 끝 | 심각도 · 기록 초안 · 보호요인 끝 = **콜백** | 전체 |
| --- | --- | --- | --- |
| 1회 | 13.9초 | **22.3초** | 45.5초 |
| 2회 | 9.6초 | **22.5초** | 52.7초 |

- 서버가 콜백에서 저장하면 원문 확정 뒤 2단계 화면까지 약 22초 + 저장 · 화면 되풀이 조회(2.5초)가 될 것으로 봅니다. 지금 데모 감사 기록은 56~79초입니다(§1-1).
- OpenAI 응답 시간이 호출마다 10초 넘게 흔들려 합계는 회마다 다릅니다. 콜백 시점은 ① 2차 세부유형과 보호요인 호출이 좌우합니다.

### 5-7. §8 에 여쭤 주신 것

- **`OVERVIEW_EMPTY_WARNING` 빼기:** #151 에 반영했습니다(§5-3).
- **3 · 4단계만 다시 만드는 진입점:** 이번에는 **전체 재분석으로 충분하다**고 봅니다. 3 · 4단계 초안만 다시 만들려면 모듈이 저장된 2단계 값(기록 초안 · 보호요인 · 2차 결과)을 다시 받아 이어 돌리는 새 진입점이 필요한데, 지금 2단계 칸은 계약 모양만 저장돼 날 결과(마스킹 대조용 위치 · 2차 근거 원문 등)가 없어 그대로는 이어 붙일 수 없습니다. 실패가 잦으면 그때 날 결과 저장과 함께 따로 제안하겠습니다.

---

## 6. Test 영향

Backend(`backend/tests/`, SQLite · PostgreSQL 모두):

- 콜백 → 첫 저장: 회차 `AI_REVIEW_REQUIRED`, `drafts_status = PENDING`, 2단계 칸 저장, Summary 없음, 감사 `ANALYSIS_COMPLETED` 한 번
- 둘째 저장: `DONE`, 3 · 4단계 칸 · `warnings` 마지막 값, **모듈이 다른 2단계 값을 돌려줘도 2단계 칸은 첫 저장 값**, Summary 초안, 19절 체크리스트 한 번
- 콜백 전 실패 → 지금처럼 `AI_FAILED`
- 콜백 뒤 예외 · 시간 초과 → `drafts FAILED`, 회차 `AI_REVIEW_REQUIRED`, 2단계 그대로
- 콜백 안 첫 저장 실패(DB 오류) → 끝에서 한 번에 저장
- 멈춤: `PENDING` 이 기준 시간을 넘기면 `FAILED`
- `PENDING` 동안 409 다섯 곳 · 위험도 판단 저장은 받음
- `PENDING` 중 회차 삭제 · 재분석 요청 → 둘째 저장을 버림(오류 없음)
- 예전 판 모듈(콜백 인자 없음) → 지금과 같음
- 마이그레이션 올리기 · 내리기, `backend/docs/CODE_GUIDE.md` 시험 수 두 곳

Frontend: `tsc` · `vite build`, `PENDING` · `FAILED` 문구와 되풀이 조회를 브라우저로 확인.

AI: #150 · #151 의 시험(이경진 님).

PR 을 올릴 때 Codex 교차검증이 필요합니다(회차 상태 · 경합 · 계약이 함께 바뀜).

---

## 7. 변경안

### 7-0. 사전 합의 (2026-11-04, 이경진 · 최민규)

- 회차는 새 상태 없이 `AI_REVIEW_REQUIRED` 로 먼저 넘깁니다.
- `drafts_status` 는 응답에서 계산하지 않고 `ai_analyses` 칸으로 둡니다.
- AI 모듈 콜백은 이경진 님, Backend(`analysis_service` · 마이그레이션 · 계약)와 화면 API 계층은 최민규가 맡습니다.
- 지킬 점 9가지(§3-2 ~ §3-6 에 반영)는 그대로 따릅니다.
- 마이그레이션 부모는 머지 직전의 main head 에 맞춥니다(#137 · #140 이 먼저 들어갈 가능성이 높음).

### 7-1. 분석 응답 (`GET …/analysis`, 바뀐 칸만)

```json
{
  "data": {
    "session_id": "…",
    "session_status": "AI_REVIEW_REQUIRED",
    "analysis": {
      "status": "COMPLETED",
      "drafts_status": "PENDING",
      "drafts_error": null,
      "result": { "risk_utterances": ["…"], "summary": { "overview": "", "key_points": ["…"] }, "followup_questions": [] }
    }
  }
}
```

- `drafts_status`: `PENDING` · `DONE` · `FAILED`. 이 제안 전에 만든 분석은 `DONE`.
- `drafts_error`: `FAILED` 일 때만 `{ "code": "AI_TIMEOUT" | "AI_FAILED", "message": "<고정 문구>" }`, 아니면 `null`. 원인 예외 문구는 싣지 않습니다.
- `analysis.status` · `analysis.error` 는 지금 뜻 그대로(2단계까지의 성공 · 실패)입니다.

### 7-2. DB (`ai_analyses`)

| 칸 | 모양 | 기존 행 |
| --- | --- | --- |
| `drafts_status` | `String(20)`, NOT NULL | `DONE` |
| `drafts_error_code` | `String(50)`, NULL 허용 | `NULL` |

- 문구는 저장하지 않고 오류 코드로 고정 문구를 고릅니다. 마이그레이션을 내리면 두 칸을 지웁니다.

### 7-3. 고려했지만 택하지 않은 안

- **새 회차 상태(예: `AI_DRAFTING`)**: 회차 상태는 처리 대기 업무 · 회차 목록 · 계약의 상태 흐름에 두루 쓰여 고칠 곳이 훨씬 많고, `AI_REVIEW_REQUIRED`('사람이 확인할 차례')와 뜻이 겹칩니다.
- **`drafts_status` 를 응답에서 계산**: '만드는 중' 과 '작업이 사라짐' 을 가를 수 없고, 409 · 멈춤 마감을 조건부 UPDATE 로 할 수 없습니다.
- **분석 기록을 둘로 나눔(2단계 · 초안)**: 조회 · 근거 연결 · 재분석 · 화면이 모두 바뀝니다.
- **모듈 호출만 더 겹쳐 돌리기**: #150 이 그 방향이고 2~5초 줄었습니다. 2단계를 반 이상 당기려면 저장을 나눠야 합니다.

---

## 8. 확인 부탁드릴 사항

- ~~**이경진 님**: §5 를 고쳐 주세요. 콜백 `warnings` 의 `OVERVIEW_EMPTY_WARNING` 을 빼 주세요. 3 · 4단계만 다시 만드는 진입점이 필요할지 의견 부탁드립니다.~~ → 답함(§5-3 · §5-7, 2026-11-04)
- **다솔 님**: 3 · 4단계의 'AI 초안을 만드는 중' · '만들지 못함' 자리와 문구, 회차 목록에도 초안 진행을 보일지.
- **팀장님**: 2단계를 먼저 보이고 3 · 4단계 초안을 뒤에 채우는 흐름이 사람 확인 원칙(`05_RULES.md` §2)과 맞는지, 칸 · 오류 코드 · 감사 종류 이름.
