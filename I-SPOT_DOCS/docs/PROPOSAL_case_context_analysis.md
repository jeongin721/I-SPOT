# 제안 — AI 분석에 사례 정보 넘기기 · '조사 후 변화' 채우기

> 작성 2026-10-27 · 이경진(AI) · 검토: 최민규(Backend)
> 상태: **범위 확정(2026-10-28)**. §3 제안 A(`case_context`) + §5 제안 C('조사 후 변화')로 갑니다 — C 가 A 의
> `previous_session` 을 쓰므로 한 묶음입니다. **§4 제안 B(아동 특성 · 가정상황 AI 제안)는 보류**합니다: 화면에 있는 칸만
> 채우고, 아동 특성 · 가정상황은 상담사가 직접 보고 고르는 것이 더 정확하다는 판단(2026-10-27 경진 · 2026-10-28 민규 합의).
> §8 에 민규 님 답을 적었습니다. PR 1(Backend `case_context`)은 민규 님이 맡습니다.

---

## 1. 왜

- 새 사례 등록(서식 4 초기면접지)에서 고른 **아동 특성 · 가정상황**은 서버에 저장되고(`cases.intake_child_traits` · `intake_family_situations`),
  요약 · 일지 화면은 그것을 "초기면접" 줄에 단어로 보입니다. 상담원은 그 아래 "추가로 확인한 항목"을 서식 목록에서 직접 고릅니다.
- 그런데 **AI 분석은 녹취 원문만 봅니다.** `analysis_service` 가 어댑터에 넘기는 것은 Transcript 하나뿐이라
  (`payload = transcript_to_contract(transcript)`), AI 는 이 아동의 나이 · 초기면접에서 체크된 항목 · 지난 회차 요약을 모릅니다.
- 그래서 상담 요약 4칸 중 **"(안전관련) 조사 후 변화된 사항"**(`summary.assessment.safety_changes`, #86)이 늘 빈 칸입니다 —
  이전 회차를 몰라 비교할 수 없습니다.
- (보류) 10/21 · 10/27 디자인(`NoteWrite.dc.html`)에는 **아동 특성 · 가정상황 AI 제안**(예: `'불안': '01:36 "무서웠어요"'`)도 있지만,
  상담사가 직접 보고 고르는 쪽이 정확하다고 보고 이번 범위에서 뺍니다(§4).

## 2. 지금 코드

| 곳 | 지금 |
| --- | --- |
| `backend/app/services/analysis_service.py` | `_analyze(adapter, payload, time_limit)` — Transcript 만 넘김 |
| `backend/app/adapters/ai_adapter.py` `ModelingAIAdapter.analyze` | `analyze_audio_session_as_contract(stt_result=…, deadline=…)`. `case_id` 는 안 넘김 |
| `ai/modeling/abuse/contract_adapter.py` | docstring "아직 못 채운 것": case_id 를 안 받아 Privacy Gateway Tier 2 · 회차 비교를 못 씀 |
| `ai/modeling/abuse/infer_audio_session.py` | `case_id` 가 있으면 **모듈 쪽 로컬 저장소**(`case_store`)에서 이전 회차를 찾는데, 서버 DB 와 따로라 서버 경로에서는 비어 있음 |
| `backend/app/core/intake.py` ↔ `counselor-web/src/data/screens/intakeItems.ts` | 서식 4 항목 목록(아동 특성 · 가정상황). 서로 같아야 함(`test_case_intake.py`) |
| `counselor-web/src/data/screens/noteWrite.ts` | 초기면접 단어 + 추가 고르기. AI 제안은 "Backend 에 없어 보이지 않는다" |

## 3. 제안 A — 분석 입력에 `case_context` 추가 (Backend → AI)

`analysis_service` 가 회차의 사례에서 아래만 골라 어댑터에 넘깁니다. 어댑터는 `time_limit_seconds` 처럼 **받는 판에만**
키워드로 넘깁니다(`analyze(payload, case_context=…)`, `accepts_keyword(adapter.analyze, "case_context")`) — mock · pipeline ·
langgraph 어댑터는 그대로 둡니다. **STT Contract(Transcript payload)는 바꾸지 않습니다**(§8 답 1).

```jsonc
"case_context": {
  "child_age_band": "만 10~13세",         // child_birth_year 로 계산한 나이를 나이대로만(§8 답 4). 없으면 null
  "child_gender": "F",                   // 사례 값 그대로. 없으면 null
  "guardian_type": "FATHER",             // GuardianType enum. 없으면 null
  "intake_child_traits": ["불안", "우울"],          // 서식 4 목록 안의 단어만(이미 서버가 검증)
  "intake_family_situations": ["부부 및 가족갈등"],
  "previous_session": {                  // 같은 사례에서 이 회차 직전의 '승인 완료' 회차만(§8 답 3). 없으면 null
    "session_label": "7회차",
    "consulted_on": "2026-10-20",
    "assessment": {                      // 그 회차 요약 4칸의 상담원 확정 문장(text 만)
      "safety_changes": "…", "strengths_resources": "…", "safety_risks": "…", "desired_changes": "…"
    }
  }
}
```

**넘기지 않는 것**: `child_alias`(아동 가명) · `case_number` · `title` · `notes` · `guardian_note` · 상담원 정보.
자유 글이라 이름이 섞일 수 있거나, 분석에 필요 없는 값입니다.

**나이대**: `만 0~5세` · `만 6~9세` · `만 10~13세` · `만 14~17세` · `만 18세 이상`(연도 기준 계산). 정확한 나이는 넘기지 않습니다 —
OpenAI 로 나가는 값은 최소로(현직자 인터뷰의 "서버 마스킹" 요구).

**개인정보**: 위 값은 OpenAI 로 나갑니다. 나이대 · 성별 · 보호자 유형 · 서식 항목은 식별 정보가 아니지만,
`previous_session.assessment` 문장은 상담원이 쓴 글이라 이름이 섞일 수 있어 **원문과 같은 `mask_for_outbound` 를 거쳐** 보냅니다.

## 4. 제안 B — 새 선택 필드 `intake_suggestions` (AI → Backend → 화면) · **보류(2026-10-28)**

> 화면에 있는 칸만 채우고, 아동 특성 · 가정상황은 상담사가 직접 보고 고르는 것이 더 정확하다는 판단으로 보류합니다.
> 아래는 다시 꺼낼 때를 위한 기록입니다. 참고: `ai/modeling/abuse/checklist_llm.py` 가 서식 4 · 6 체크리스트 초안(항목별 원문 근거
> 발췌)을 이미 만들고 있어, 다시 꺼낸다면 새 LLM 대신 그 결과를 쓰는 쪽이 낫습니다(항목 이름 띄어쓰기 · 근거를 segment_id 로 바꾸기 필요).

AI 가 이번 회차 녹취에서 **서식 4 항목에 해당하는 근거**를 찾아 제안합니다. 판정이 아니라 "이 발화를 보고 이 항목을 확인해 볼 만하다" 는 제안입니다.

```jsonc
"intake_suggestions": {
  "child_traits": [
    { "item": "불안", "segment_ids": ["seg_014"], "reason": "무서웠다고 반복해서 말함" }
  ],
  "family_situations": [
    { "item": "부부 및 가족갈등", "segment_ids": ["seg_031"], "reason": "부모가 자주 싸운다고 말함" }
  ]
}
```

규칙(모두 AI 쪽 `contract_adapter` 경계와 Backend 관문 두 곳에서 지킴)

- `item` 은 **서식 4 목록의 단어 그대로**. 목록 밖 · `특성없음` · `기타` 는 버립니다(Backend 는 `core/intake.py` 로 다시 거름).
- **초기면접에 이미 있는 항목은 제안하지 않습니다**(`case_context` 로 앎). 이번 회차에서 새로 보인 것만.
- `segment_ids` 가 실제 발화에 없거나 비면 그 항목을 버립니다(`followup_check_llm._clean_points` 와 같은 검증, 목록 · bool 타입 검사 포함).
- 근거는 **아동 발화 우선**. 가정상황은 보호자 발화도 근거가 될 수 있어 §8 질문 2로 정합니다. 상담원 발화는 근거로 쓰지 않습니다.
- 항목마다 1개 · 최대 5개씩. 없으면 빈 목록.
- LLM 은 새 단계 하나(`intake_suggestion_llm.py`)로, 지금 병렬로 도는 보호요인 · 원하는 변화와 **같은 마스킹 축어록 · 같은 병렬 묶음**에 넣어 분석 시간이 늘지 않게 합니다.

Backend 저장: `AIAnalysis.result` 에 그대로 둡니다(새 열 없음). 선택 필드라 없던 결과도 그대로 읽힙니다.

## 5. 제안 C — "조사 후 변화된 사항" 채우기

`previous_session.assessment` 가 있으면 AI 가 **지난 회차 확정 문장과 이번 녹취를 비교**해 달라진 점만 씁니다
(`summary.assessment.safety_changes.text` · 근거 `segment_ids`). 없으면 지금처럼 빈 칸(상담원 작성).
지난 회차 문장은 근거 번호가 없으므로 "지난 회차: … → 이번: …(01:08 아동)" 처럼 이번 회차 근거만 겁니다.
이 단계도 A 의 마스킹을 거친 입력만 씁니다.

## 6. 화면 (counselor-web, 요약 · 일지)

- '조사 후 변화된 사항' 칸은 지금 화면 그대로입니다(#86 의 4칸). AI 초안 문장 · 근거가 채워지기만 합니다.
- (보류) 아동 특성 · 가정상황 AI 제안 표시는 §4 와 함께 보류합니다.
- 같이 고칠 것(작은 버그): 사례 정보를 못 받으면 "초기면접 항목을 불러오는 중…" 이 끝나지 않고 고르기 단추도 잠깁니다
  (`noteWrite.ts` 의 `intakeWaiting = !info && !caseDetail.error` — 받을 사례가 없을 때도 '받는 중' 으로 봄).
  `caseDetail.loading` 으로 가르고, 사례가 없으면 "연결된 사례 정보가 없어 초기면접 항목이 없습니다" + 고르기 열기.

## 7. 단계 (PR 단위)

| PR | 내용 | 확인 |
| --- | --- | --- |
| 1 | **(민규)** Backend: `case_context` 만들기(나이대 · 직전 승인 회차) · 받는 어댑터에만 넘기기 · `ModelingAIAdapter` → `analyze_audio_session_as_contract(case_context=…)` | backend 시험(가짜 모듈이 받은 값 · 안 넘기는 키 · 직전 승인 회차 고르기) |
| 2 | **(경진)** AI: `case_context` 받기 · 마스킹 · 조사 후 변화 비교 → `summary.assessment.safety_changes` · Contract 문서 | 마스킹 · 비교 단위 시험, backend `test_modeling_ai_adapter`, 데모에서 2회차 이상 사례 |
| 3 | **(경진)** 화면: "불러오는 중" 버그 | tsc + vite build |

PR 1 은 출력이 바뀌지 않아 먼저 넣어도 안전합니다(받는 쪽이 아직 안 씀).

## 8. 질문과 답 (민규 님, 2026-10-28)

| # | 질문 | 답 |
| --- | --- | --- |
| 1 | `case_context` 를 `analyze(payload, case_context=…)` 키워드로(받는 어댑터만) 넘길까요, Transcript payload 안에 넣을까요? | **키워드로, 받는 어댑터에만.** STT Contract 는 그대로 |
| 2 | 가정상황 제안의 근거로 보호자 발화도 허용할까요? | B 보류라 지금 답 불필요 |
| 3 | `previous_session` 을 직전 **승인 완료** 회차만 할까요? | **직전 승인 완료 회차만**(상담원이 확정한 문장만 AI 에 보냄) |
| 4 | 나이 vs 나이대? | **나이대만**("만 10~13세"). OpenAI 로 나가는 값은 최소로 |
| 5 | `intake_suggestions` 채택 기록을 따로 저장할까요? | B 보류라 지금 답 불필요 |
