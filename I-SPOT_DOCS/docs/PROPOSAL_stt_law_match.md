# 제안 — STT 검수 임시 조문: 문장과 닮은 호에만 · 왜인지 보이기 · 저장하면 다시 (2026-11-09)

> 작성 2026-11-09 · 팀장 결정: **원문 수정 뒤 다시 스캔은 비동기, 검수 전 처리는 서버 로컬(외부 전송 없음)**.
> 상태: **구현(`feature/rag`)** — AI(`law_match`) · Backend(비동기 재스캔 · Contract) · 화면을 한 브랜치에 올렸다. 검토: 민규(Backend) · 경진(화면 · AI).
> 바탕: [PROPOSAL_stt_key_scan.md](PROPOSAL_stt_key_scan.md) §8(합의) · §9(정밀도 개선 — 줄 확률 · 되돌림 · 측정).

---

## 1. 왜

STT 검수 화면(원문 확정 전)은 1차 모델이 고른 아동 발화 아래에 **'임시' 관련 조문**을 보인다(11/03). 그 조문은 유형 → 아동복지법 제17조 호 **고정 표**라서
1. 관련 없는 발화("네, 없어요")에도 유형만 맞으면 조문이 붙었고(§9 에서 줄 확률 · 되돌림을 고쳐 줄였지만 1차 모델 하나의 판단),
2. **왜 그 조문인지** 상담원이 알 수 없었고,
3. 원문을 고쳐 저장해도 조문은 **저장 전 문장 기준** 그대로였다(지운 발화만 뺌).

팀장님 요구: 처음 STT 때 **실제 STT 된 문장과 맞는 법령**을 보이고, 검수 전에 먼저 제공하되 **수정되면 수정된 문장으로 다시** 제공할 것.

"문장과 맞는 법령"은 세 가지가 동시에 맞아야 한다 — **(a) 맞는 발화에만, (b) 맞는 호를, (c) 왜 그 조문인지 근거와 함께.** 상담 발화에 붙일 수 있는 조문은 사실상
아동복지법 제17조의 호(2 성 · 3 신체 · 5 정서 · 6 방임)뿐이고(상해 · 상습 · 벌칙은 '법 위반 확정'이라 05_RULES 상 못 붙임), 법률 문장과 아이 말은 어휘가 달라
직접 비교는 약하다. 그래서 **아이 말투의 행위 예시(앵커)** 를 다리로 쓴다.

## 2. 구조

```text
STT 발화
 → ① 1차 RoBERTa 줄 판정(§9)        유형 확률 ≥ 임계값인 줄만 '먼저 들어볼 곳'                         [게이트 (a)]
 → ② 로컬 문장 임베딩 매칭(law_match) 줄 ↔ 그 유형의 행위 예시(앵커) 코사인 유사도                          [(b) · (c)]
      · 앵커는 서버 시작 때 한 번 임베딩, 줄은 묶음으로 — 수백 줄도 1초 안. 외부 전송 없음
 → ③ 유사도 ≥ KEY_SCAN_LAW_MIN_SIMILARITY(기본 0.45) 인 유형에만 조문 + 닮은 예시 + 점수. 못 넘으면 조문 없이 발화만 남음   [정밀도 ↑]
 → ④ law_cache 의 아동복지법 제17조에서 호 본문 · 조문 링크(캐시만 읽음), 없으면 내장 문구 · 법령 전체 링크
저장(PATCH) → 새 version 은 직전 결과를 복사해 REFRESHING → 백그라운드에서 저장한 원문으로 ①~④ 다시 → DONE · FAILED → 화면 재조회
```

- ①과 ②는 **독립된 두 신호**다. 둘이 일치할 때만 조문이 붙으므로 오탐이 준다. 1차 모델(1,440건 학습)보다 ②가 유형을 더 잘 고르는 건 아니다 —
  ②의 가치는 **근거 발췌(왜)** 와 **둘째 의견**이다.
- 모델을 못 올리면(파일 없음 · torch 없음) 예전처럼 유형 조문을 근거 없이 붙이고(score null) **스캔은 실패하지 않는다.** `KEY_SCAN_LAW_MATCH=off` 로 끌 수 있다.

## 3. 바뀐 것

| 곳 | 내용 |
| --- | --- |
| AI `ai/modeling/abuse/law_match.py` (새) | 내장 앵커(호마다 아이 말투 행위 예시) + `KEY_SCAN_LAW_ANCHORS`(JSON, 서버에만 — 기관 매뉴얼 발췌는 저장소에 올리지 않음). 로컬 임베딩(기본 `jhgan/ko-sroberta-multitask`, transformers mean pooling, HF 캐시). `references_for(발화 글, 유형들)` → 조문 목록. 조문 본문 · 링크는 `law_cache`(캐시만). 서버 시작 때 미리 올림(`contract_adapter.preload_key_scan` ← Backend `ai_adapter.prepare`) |
| AI `contract_adapter.key_scan_as_contract` | `segments[].legal_references` 추가(유형당 최대 하나 — 닮은 예시 `excerpt` · 유사도 `score`) |
| Backend `key_scan_service` | `legal_references` 저장(모양 다듬기 — 모르는 유형 · 법령 이름 없는 항목 뺌, 발화당 8개 · 글자 수 상한). **PATCH 뒤 비동기 재스캔**: 새 version 은 직전 결과 복사 + `REFRESHING`(`started_at`), 응답 뒤 `BackgroundTasks` 로 저장한 원문을 다시 스캔(`KEY_SCAN_TIMEOUT_SECONDS`, 동시 실행 `KEY_SCAN_MAX_CONCURRENCY` 기본 1). 자리를 기다리는 사이 또 저장되면 앞 version 은 돌리지 않음(더는 최신이 아님). 실패면 저장 전 결과를 둔 `FAILED`. 제한 시간 + 60초를 넘긴 REFRESHING 은 조회 때 FAILED 마감(작업이 사라진 경우). `scanned_version` = segments 를 만든 원문 version |
| Contract (API_CONTRACT 7절) | `key_scan.status` 에 `REFRESHING`, `scanned_version` · `started_at`, `segments[].legal_references[{abuse_type, law_name, article, item_label, text, portal_url, excerpt, score}]` |
| 화면 `counselor-web` | 서버가 준 `legal_references` 만 보임(빈 배열이면 조문 없이 '먼저 들어볼 곳'만), 조문 아래 `닮은 예시 "…"`. 저장 뒤 REFRESHING 동안 GET 재조회(STT 처리 중 폴링 재사용) + 범례에 '다시 고르는 중 · 저장 전 결과' 안내. 그 칸이 없는 예전 결과는 고정 표 그대로 |
| 설정 | 루트 `.env.example`(AI): `KEY_SCAN_LAW_MATCH` · `KEY_SCAN_LAW_EMBED_MODEL` · `KEY_SCAN_LAW_EMBED_LOCAL_ONLY` · `KEY_SCAN_LAW_MIN_SIMILARITY` · `KEY_SCAN_LAW_ANCHORS`. Backend: `KEY_SCAN_MAX_CONCURRENCY` |

## 4. §8 합의(10/28)에서 바뀐 것 — 민규 님 · 경진 님 확인

| 항목 | 10/28 합의 | 11/09 |
| --- | --- | --- |
| 원문 수정 때 | 다시 스캔 안 함(지운 발화만 빼고 복사) | **비동기 재스캔**(REFRESHING → DONE · FAILED). 복사본은 그동안 보임 |
| 폴링 | 늘리지 않음 | REFRESHING 동안만 GET 재조회(STT 처리 중 폴링 코드 재사용, 새 API 없음) |
| 유형 표시(답 3) | 화면에 안 보임 → 11/03 임시 조문 | 조문 + **닮은 예시**(왜인지). 문구는 '임시 · 1차 모델' · '법 위반을 확정하지 않습니다' 그대로 |
| 원문 외부 전송 | 없음 | 없음(로컬 임베딩). 검수 전 외부 LLM 은 쓰지 않는다(팀장 결정) |

## 5. 05_RULES 와 문구

문장별 조문은 유형 칩보다 더 '판정'처럼 읽힌다. 그래서 (c) 닮은 예시를 반드시 같이 보이고, 임시 조문 칩에는 '임시 · 1차 모델' 표와 범례의 '법 위반을 확정하지 않습니다'를
유지한다. 조문은 금지행위(제17조 각 호)에 한정하고 상해 · 상습 · 벌칙은 붙이지 않는다.

## 6. 확인한 것 · 못 한 것

| 항목 | 결과 |
| --- | --- |
| `tests/test_law_match.py`(가짜 임베딩 — 규칙 · 설정 · 모델 없음 경로) | 통과 |
| `backend/tests/test_key_scan.py`(재스캔 · 실패 · 멈춤 · 연이은 저장 · 조문 저장) · `test_modeling_ai_adapter.py` · 전체 backend 시험 | 통과 |
| counselor-web `tsc --noEmit` · `vite build` | 통과 |
| **실제 임베딩 모델 · GPU** | 이 작업 환경에는 없어 돌리지 못했다. 서버에서 HF 캐시에 모델을 받은 뒤(`KEY_SCAN_LAW_EMBED_LOCAL_ONLY=1` 이면 내려받지 않음) 실제 녹취로 확인해야 한다 |
| 앵커 품질 | 내장 앵커는 일반적인 행위 예시다. 기관 매뉴얼의 유형별 예시를 `KEY_SCAN_LAW_ANCHORS` 로 더하면 좋아진다(서버에만 둠) |

## 7. 다음

| 단계 | 내용 |
| --- | --- |
| 측정 | §9 의 0단계 시트로 **유사도 게이트 τ(0.35 · 0.45 · 0.55)** 별 조문 정밀도 · 재현율 비교 — `experiments/key_scan_eval.py` 에 줄별 유사도 기록 · 게이트 행 추가(예정). 라벨 100~200줄 |
| 앵커 | 매뉴얼 유형별 행위 예시를 앵커로(서버 로컬) |
| 보류 | 검수 전 외부 LLM 검증(비식별 뒤 OpenAI) — 팀장 결정으로 지금은 하지 않음. 필요해지면 ②를 LLM 으로 바꿔 끼우는 자리만 남겨 둠 |
