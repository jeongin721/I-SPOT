# [제안] 사례 단위 신호 이력 API — `GET /cases/{case_id}/signal-history`

> `02_ARCHITECTURE.md` §8 Contract 변경 규칙에 따른 제안서입니다.
> 상태: **합의 · 구현(2026-10-28)**. 이경진 님이 2026-10-27 제안한 모양을 바탕으로 최민규(Backend)가 정리 · 구현했습니다.
> 화면 연결은 API 가 main 에 들어간 뒤 이경진 님이 합니다.
>
> 작성: 최민규 · 2026-10-28

---

## 1. 변경 이유

10/27 디자인에 칸은 있는데 **여러 회차를 모아야 해서** 아직 '준비 중' 인 것이 있습니다(AI 새 생성 없이 계산만 하면 되는 값).

- 유형별 위험도 화면의 **회차별 추이**
- 사례 상세 상담 이력의 **회차 카드 '신호 —'** · **세부 신호 행렬(유형 × 회차)**

지금 창구(`GET /sessions/{id}/analysis` · `GET /sessions/{id}/risk-assessments`)는 회차 단위라, 화면이 회차마다 따로 부르면
요청이 **회차 수 × 2** 로 나갑니다(사례당 회차가 수십 개). 서버에서 한 번에 모아 주는 사례 단위 창구가 필요합니다.

## 2. 영향 Contract

- **API 추가 1개**(읽기 전용): `GET /api/v1/cases/{case_id}/signal-history`. 기존 창구 · DB · AI 출력 Contract 는 바뀌지 않습니다.

## 3. Backend 영향

- 새 파일 `app/schemas/signal_history.py` · `app/services/signal_history_service.py`, `app/api/v1/cases.py` 에 라우트 1개.
- 쿼리 3개(회차 목록 · 회차들의 분석 전부(최신 하나만 씀) · 회차들의 상담원 판단)로 한 번에 만듭니다. AI 를 새로 돌리지 않습니다.
- 값 규칙은 기존 창구와 **같습니다**: `detected` 는 8절 `abuse_signals[].detected`, `ai_level` 은 11절 `ai_level` 과 같은 규칙
  (`risk_assessment_service.ai_level_for`: 같은 유형 첫 항목의 1~5 정수만), `counselor_level` · `assessed_at` 은 11절.
- 권한 · 오류는 `GET /cases/{case_id}` 와 같습니다(담당 상담원 또는 관리자, `404 CASE_NOT_FOUND` · `403 FORBIDDEN`).

## 4. Frontend 영향

- `counselor-web/src/api/types.ts` 에 `SignalHistory` 타입, `endpoints.ts` 에 `cases.signalHistory(caseId)` 를 함께 넣었습니다(화면은 아직).
- 이경진 님이 붙일 것: 회차별 추이 · 상담 이력 회차 카드 신호 · 세부 신호 행렬, 누적 요약 출처 표시.
- 표현 규칙(05_RULES §1): `ai_level` · `detected` 는 **AI 제안**이고 판정이 아닙니다. 위험도 표시는 `counselor_level` 만 씁니다.

## 5. AI 영향

- 없음. 저장된 분석 결과만 읽습니다.

## 6. Test 영향

- `backend/tests/test_signal_history.py` 8개: 빈 사례 · 분석 전 회차 · 규칙(첫 항목 · 참/거짓 · 1~5 · 띄어쓰기 라벨 · 범위 밖) · 회차 순서 · 판단만 있는 회차 ·
  이상한 모양의 선택 필드 · 권한(403 · 관리자) · 404.

## 7. 변경안 (응답 모양)

```json
{
  "data": {
    "case_id": "…",
    "sessions": [
      {
        "session_id": "…",
        "session_number": 1,
        "consulted_at": "2026-10-20T10:00:00+09:00",
        "status": "APPROVED",
        "analysis_status": "COMPLETED",
        "types": [
          { "abuse_type": "PHYSICAL",  "detected": true,  "ai_level": 3,    "counselor_level": "HIGH", "assessed_at": "2026-10-21T09:12:00+09:00" },
          { "abuse_type": "EMOTIONAL", "detected": null,  "ai_level": null, "counselor_level": null,   "assessed_at": null },
          { "abuse_type": "SEXUAL",    "detected": null,  "ai_level": null, "counselor_level": null,   "assessed_at": null },
          { "abuse_type": "NEGLECT",   "detected": false, "ai_level": null, "counselor_level": null,   "assessed_at": null }
        ]
      },
      { "session_id": "…", "session_number": 2, "consulted_at": null, "status": "STT_REVIEW_REQUIRED", "analysis_status": null, "types": [] }
    ]
  }
}
```

- 회차는 **전부**, `session_number` 오름차순(분석 전 회차도 자리가 있어야 추이 그래프가 끊기지 않음). 목록 상한 없음.
- `analysis_status` 는 가장 최근 분석의 상태(`PROCESSING` · `COMPLETED` · `FAILED`), 요청한 적 없으면 `null`.
- `types` 는 늘 네 유형을 `PHYSICAL · EMOTIONAL · SEXUAL · NEGLECT` 순서로 — 단, 분석이 `COMPLETED` 도 아니고 상담원 판단도 없는 회차는 `[]`.
- 재분석하면 최신 분석 기준으로 바뀝니다. 상담원 판단에 저장된 `ai_level`(판단 당시 값)과는 다를 수 있습니다(11절).

## 8. 질문과 답 (이경진 님 2026-10-27 → 최민규 2026-10-28)

| # | 질문 | 답 |
| --- | --- | --- |
| 1 | 이 API 를 민규가 만들지, 경진이 백엔드까지 같이 올릴지 | Backend(Contract · 시험 · 문서)는 민규. 화면은 API 머지 뒤 경진 |
| 2 | 사례 단위 API vs 화면에서 회차별로 모아 부르기 | 사례 단위 API. 요청 수(회차 × 2)와 일관성 때문 |
| 3 | 상담 이력 '누적 요약'(기간별)을 승인된 회차의 요약 4칸 모음으로 채워도 되는지(AI 새 생성 없음). '주제 비중' 은 뺌 | 됨. 화면에 "승인된 회차 요약 모음(AI 생성 아님)" 처럼 출처를 적는다. 주제 비중은 이번에 뺌 |

## 9. 뒤로 미룬 것

- 기간 필터 · 페이지: 회차 수가 수백을 넘을 때 다시 봅니다(지금 사례당 수십 회차).
- 누적 요약은 기존 `GET /sessions/{id}/summary` 로 승인 회차만 모읍니다(새 API 없음). 회차가 많아지면 사례 단위 요약 창구를 따로 제안합니다.
