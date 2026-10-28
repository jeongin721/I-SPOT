# 제안 — STT 검수 '1차 임시 핵심 발화' (원문 확정 전 1차 모델 스캔)

> 작성 2026-10-28 · 이경진(AI) · 검토 요청: 최민규(Backend)
> 상태: **제안(결정 전)**. 전사본 응답에 선택 칸이 하나 늘고 STT 작업 끝에 한 단계가 붙으므로 §7 질문에 답을 받은 뒤 구현합니다.

---

## 1. 왜

10/27 디자인(`counselor-design/screens/SttReview.dc.html`)의 STT 검수는 이렇게 흐릅니다.

1. 변환 진행 단계: 화자 구분 중 → 전사 중 → 신뢰도 계산 중 → **핵심 발화 고르는 중** → 완료
2. 끝나면 **"1차 임시 핵심 발화"** 보기(칩 `임시 · 검수 전`)로 먼저 열림 — 상담원이 중요한 곳부터 다시 듣고 고침
3. **전체 STT 보기** · **저신뢰 구간 보기** 단추로 전체 · 저신뢰로 바꿈

지금 앱은 원문 확정 **뒤에** AI 분석을 하므로, 검수할 때(확정 전)는 핵심 발화를 고른 값이 없습니다. 그래서 2 를 빼고 '전체 STT' 로 엽니다.

## 2. 이미 있는 것

`ai/modeling/abuse/infer_audio_session.py` 의 **`quick_risk_scan(stt_result)`** 가 정확히 이 용도로 만들어져 있습니다(2026-10-01, 주석 "2.4 '분석하기' 전 빠른 1차 스캔(검수 화면용)"). 아직 부르는 곳이 없습니다.

- 정식 분석과 **같은 chunk 분할**(`build_qa_chunks`, 500자)로 **1차 RoBERTa 분류기만** 돌립니다. LLM 보완 체크는 하지 않습니다.
- 반환은 `{segment_id: ["신체학대", …]}` 입니다.
- 서버 안 GPU 모델이라 **원문이 외부로 나가지 않고**, chunk 몇 개면 몇 초 안에 끝납니다(모델은 서버 시작 때 미리 올려 둠 — `start_ai_preload`).

## 3. 제안 — AI 쪽

`quick_risk_scan` 을 그대로 쓰되 두 가지만 다듬습니다.

1. **아동 발화만 표시**: 지금은 검출된 chunk 의 모든 줄(상담원 질문 포함)을 표시합니다. 핵심 발화 보기는 "다시 들어볼 아동 발화" 라 검출 chunk 안의 `CHILD` 발화만 남깁니다(화자 미확인 발화는 남김 — 저신뢰 보기와 겹쳐도 괜찮음).
2. **Contract 경계 모양**: 영문 유형 · 목록으로 바꿉니다.

```jsonc
"key_scan": {
  "status": "DONE",              // DONE | FAILED | SKIPPED(AI_PROVIDER 가 modeling 이 아님)
  "model": "roberta_abuse_qa_child_v3",
  "segments": [                  // 원문 순서. 없으면 빈 배열
    { "segment_id": "seg_014", "abuse_types": ["PHYSICAL"] }
  ]
}
```

- **판정이 아닙니다.** 화면 문구는 "먼저 들어볼 곳"·"임시 · 검수 전" 입니다(05_RULES §1). 원문 확정 뒤 정식 분석(2차 LLM 포함)은 지금과 같습니다.
- 유형 이름을 화면에 보일지는 §7 질문 3.

## 4. 제안 — Backend

| 곳 | 제안 |
| --- | --- |
| 실행 시점 | `process_stt` 가 STT 결과를 저장한 **같은 작업 끝**에서 `quick_risk_scan` 을 부르고, 끝나면 `STT_REVIEW_REQUIRED` 로 넘깁니다(디자인의 '핵심 발화 고르는 중' 단계). `AI_PROVIDER != modeling` 이면 `SKIPPED` 로 바로 넘깁니다 |
| 실패 | 스캔이 실패하거나 시간(예: `KEY_SCAN_TIMEOUT_SECONDS` 30초)을 넘기면 **STT 는 성공으로 두고** `key_scan.status = FAILED`. 검수 화면은 '전체 STT' 로 엽니다 |
| 저장 | `transcripts.key_scan`(JSON, nullable) 한 칸. 기존 전사본은 null(= 스캔 안 함) |
| 원문 수정 | 수정은 새 version 을 만듭니다. segment_id 가 그대로 이어지므로 **직전 version 의 key_scan 을 새 version 에 복사**하고, 지워진 발화의 id 만 뺍니다(문장이 바뀐 발화를 다시 스캔하지는 않음 — 임시 표시라서) |
| 응답 | `TranscriptResponse.key_scan`(선택 칸, `child_handoff` 와 같은 방식). 없으면 null |
| 개인정보 | 원문이 서버 밖으로 나가지 않습니다(로컬 모델). 감사 기록은 필요 없다고 봅니다(조회 · 저장이 아니라 STT 작업의 일부) |

## 5. 화면 (counselor-web, STT 검수)

- `key_scan.segments` 가 있고 **원문 확정 전**이면 **"1차 임시 핵심 발화"** 보기로 엽니다. 칩은 `임시 · 검수 전`(디자인 `c-sand`), 줄은 그 발화들만 보입니다.
- 단추는 지금 그대로(**전체 STT 보기** · **저신뢰 구간 보기**) — 누르면 그 보기로 바뀝니다. 새 단추는 넣지 않습니다.
- `key_scan` 이 null · `FAILED` · `SKIPPED` 이거나 빈 배열이면 지금처럼 '전체 STT' 로 엽니다.
- 원문 확정 뒤에는 '전체 STT' 로 엽니다(정식 분석 결과가 따로 있음).
- 변환 진행 카드의 단계 문구는 서버가 단계를 주지 않아 지금처럼 하나로 둡니다.

## 6. 단계 (PR 단위)

| PR | 누가(제안) | 내용 | 확인 |
| --- | --- | --- | --- |
| 1 | AI(경진) | `quick_risk_scan` 아동 발화만 · Contract 모양 변환 함수(`key_scan_as_contract`) | 단위 시험(검출 chunk 의 상담원 줄 제외 · 화자 미확인 남김 · 빈 결과) |
| 2 | Backend(민규 님?) | `transcripts.key_scan` 열 · `process_stt` 끝에서 호출 · 시간 제한 · version 복사 · 응답 칸 · API_CONTRACT 7절 | backend 시험(가짜 모듈 · 실패해도 STT 성공 · 수정 시 복사) |
| 3 | 화면(경진) | STT 검수 기본 보기 '1차 임시 핵심 발화' | tsc + vite build, 데모 실제 녹취 |

## 7. 질문 (민규 님)

| # | 질문 |
| --- | --- |
| 1 | 스캔을 `process_stt` **같은 작업 끝**에서 돌릴까요(STT 완료가 몇 초 늦어짐), STT 를 먼저 끝내고 **별도 작업**으로 돌릴까요(화면이 한 번 더 조회해야 함)? |
| 2 | 저장을 `transcripts.key_scan` JSON 한 칸으로 할까요, segment 행(`transcript_segments.key_types`)에 둘까요? version 복사는 segment 행 쪽이 자연스럽지만 열이 하나 더 늡니다 |
| 3 | 핵심 발화 줄에 1차 유형 이름(신체 등)을 보일까요? 디자인 key 보기에는 유형 칩이 없고, 임시 값이 판정처럼 읽힐 수 있어 **안 보이는 쪽**을 제안합니다 |
| 4 | Backend PR 2 를 민규 님이 맡으실지, 제가 같이 올릴지 |
