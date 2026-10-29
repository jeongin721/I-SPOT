# [제안] 화면별 업무 매뉴얼 근거를 분석 시점에 만들어 저장

> `05_RULES.md` §5 변경 규칙에 따른 제안서입니다.
> 확정 전이며, AI · Backend · Frontend 세 파트 합의가 필요합니다.
>
> 작성: feature/rag · 2026-10-16

대상 — `2026년 아동보호서비스 업무 매뉴얼`에서 찾은 근거를 상담사 화면 세 곳(추가 확인 · 질문, 상담 전 브리핑, 종결 검토)에 보여 주는 데이터

---

## 1. 변경 이유

### 1-1. 화면을 열 때 검색하면 3~5초를 기다려야 합니다

`rag.screen_manual.search_screen_manual()`은 맞는 근거만 남기려고 검색 후보를 LLM으로 한 번 더 확인합니다. 근거가 맞지 않으면 빈 목록을 돌려줍니다(`05_RULES.md` §3 "근거 부족 시 빈 결과 허용").

측정(2026-10-16, 같은 질문 3회 평균):

| 화면 | 벡터 검색만 | LLM 확인 포함 |
| --- | --- | --- |
| 추가 확인 · 질문 | 0.45초 | 2.9초 |
| 상담 전 브리핑 | 0.25초 | 5.2초 |
| 종결 검토 | 0.29초 | 5.0초 |
| 세 화면 하나씩 | | 10.4초 |
| 세 화면 동시에(`build_screen_references`) | | 6.1초 |

화면을 열 때마다 이 시간을 기다리게 할 수 없으므로, 분석할 때 미리 만들어 저장하고 화면은 저장된 값만 읽어야 합니다.

### 1-2. 지금 이 데이터를 저장할 곳이 없습니다

- `backend/`는 RAG(`rag/`)를 부르지 않습니다. 매뉴얼 근거는 최상위 `main.py`(단독 확인용 앱)의 `/api/v1/rag/analyze` 응답(`manual_screen_references`, STT 검수 후 Transcript 입력)에만 있습니다.
  - (2026-10-29 갱신) Backend 가 AI 분석 뒤 다음 상담 체크리스트를 만들 때 `manual_screen_references` 도 함께 받아 `followup_suggestions.result` 에 저장합니다(API_CONTRACT 18절). 화면별로 읽는 곳은 아직 없습니다.
- `AIAnalysis.result`(`AnalysisResult`)에는 매뉴얼 근거 필드가 없습니다. 필드를 더하면 AI Output Contract 변경입니다.

### 1-3. 화면마다 검색에 넣을 문장이 다릅니다

아동 발화(`child_analysis_text`)로 세 화면을 검색하면 추가 확인 · 질문만 결과가 나오고, 상담 전 브리핑 · 종결 검토는 0건입니다. 아이의 말에는 양육상황 점검이나 종결 판단에 관한 내용이 없기 때문입니다.

| 화면 | 검색에 넣을 문장(제안) | 만드는 때(제안) |
| --- | --- | --- |
| 추가 확인 · 질문 | 회차 아동 발화(`child_analysis_text`) | 회차 AI 분석이 끝날 때 |
| 상담 전 브리핑 | 지난 회차 요약 + 확인하지 못한 항목 | 회차 요약 승인 때(다음 회차 브리핑용) |
| 종결 검토 | 사례 전체 상담 요약 | 종결 검토 등록 때 |

---

## 2. 영향 문서

- `02_ARCHITECTURE.md` — AI 분석 결과 저장 구조, AI Output Contract
- `backend/docs/API_CONTRACT.md` — 분석 조회(8절) 또는 새 조회 API
- `03_UI_UX.md` — 세 화면의 근거 표시 영역
- `rag/README.md` §8-1 — 화면별 매뉴얼 검색(이미 반영)

## 3. Backend 영향

- 매뉴얼 근거를 만드는 작업을 백그라운드에서 실행: 회차 분석(`analysis_service.process_analysis`) 끝, 요약 승인, 종결 검토 등록.
- 저장 위치(둘 중 하나, §7 질문 1):
  - (A) 새 테이블 `manual_references` — `session_id` 또는 `case_id`, `screen`, `references`(JSON), `source_version`(매뉴얼 판 · 색인 버전), `created_at`
  - (B) `AIAnalysis`에 JSON 컬럼 `manual_references` 추가 — 추가 확인 · 질문만 담을 수 있다(브리핑 · 종결은 만드는 때가 회차 분석과 다름)
- `rag/`를 Backend에서 부르려면 `requirements-rag.txt`와 벡터 DB 경로(`RAG_VECTOR_DB_DIR`)가 Backend 배포에 있어야 한다.
- LLM 실패 · 시간 초과 시 해당 화면만 빈 목록 + 오류로 저장하고 분석 자체는 실패시키지 않는다(`build_screen_references`가 화면별로 오류를 나눠 돌려준다).

## 4. Frontend 영향

- 세 화면은 저장된 근거만 읽는다. 화면을 열 때 검색 API를 부르지 않는다.
- 근거가 빈 목록이면 근거 영역을 표시하지 않는다.
- 항목 표시: `section`(예: "[서식 9] 아동 상황 점검표") + `item_no`(추가 확인 · 질문만) + `reason`. 쪽 번호는 보이지 않는다.

## 5. AI 영향

- 출력 형식(화면별 목록 한 건):

```json
{
  "type": "manual",
  "title": "[붙임1] 2026년 아동보호서비스 업무 매뉴얼.pdf",
  "section": "[서식 9] 아동 상황 점검표",
  "item_no": 12,
  "summary": "섭식 문제가 있다. (예) 지나치게 먹지 않아 …",
  "reason": "밥을 잘 안 먹는다는 내용이 있어 섭식 문제와 관련됩니다.",
  "organization": "보건복지부·아동권리보장원",
  "chunk_id": "…"
}
```

- `item_no` · `detail`은 추가 확인 · 질문에만, `similarity`는 상담 전 브리핑 · 종결 검토에만 있다.
- `reason`은 고른 이유를 한 문장으로 쓴 것으로, 판단 과정(chain-of-thought)이 아니다(`05_RULES.md` §3).
- 학대 여부 · 종결 여부를 판단하지 않는다. 확인할 항목과 기준만 보여 준다.

## 6. Test 영향

- `rag.screen_manual` 단위 테스트: 벡터 검색 · LLM을 가짜로 바꿔 빈 결과, 기준점 미만 후보 제거, 화면별 오류 분리 확인.
- Backend: 근거 생성 실패가 분석 상태(`AI_REVIEW_REQUIRED`)를 바꾸지 않는지 확인.
- 기준점(`SCREEN_MIN_SIMILARITY`: 브리핑 0.32, 종결 0.35)은 화면별 문장 7개로 정한 값이다. 실제 상담 문장이 쌓이면 다시 맞춘다.

## 7. 권장 변경안

1. 저장은 (A) 새 테이블로 한다. 화면마다 만드는 때와 단위(회차 · 사례)가 달라 `AIAnalysis`에 붙이기 어렵다.
2. 1단계: 추가 확인 · 질문만 회차 분석 끝에 만들어 저장한다(입력이 이미 있음).
3. 2단계: 상담 전 브리핑 · 종결 검토의 입력 문장(§1-3)을 정한 뒤 붙인다.

### 합의가 필요한 질문

1. 저장 위치 — (A) 새 테이블 / (B) `AIAnalysis` 컬럼
2. 상담 전 브리핑 · 종결 검토에 넣을 문장과 만드는 때(§1-3 표)
3. Backend 배포에 `rag/` 의존성과 벡터 DB를 넣을지, 별도 AI 서버에서 만들어 Backend에 넘길지
