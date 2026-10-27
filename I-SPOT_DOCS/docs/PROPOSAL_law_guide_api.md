# [제안] 법령 · 매뉴얼 AI 질문 API (LawGuide 화면)

> `02_ARCHITECTURE.md` §8 Contract 변경 규칙에 따른 제안서입니다. **아직 확정 전입니다.**
> 화면은 `frontend261021` 브랜치 `counselor-design/screens/LawGuide.dc.html`(2026-10-27 판),
> AI 쪽은 PR #83(`feat/law-qa`, `fdfbf8f` 기준)의 `ai/modeling/abuse/legal_manual_qa_llm.py` 를 기준으로 썼습니다.
>
> 작성: 이경진 · 2026-10-27

---

## 1. 무엇을 붙이나

LawGuide 화면 위쪽의 **AI 질문 채팅**이 대상입니다. 디자인 README 의 'Backend 가 필요한 부분' 표가 요구하는 것과 같습니다.

> LawGuide · AI 질문 — 실제로는 매뉴얼 · 두 법령을 근거로 답하는 질의 API(답변 + 매뉴얼 쪽수 · 조문 근거 목록)와 법령 개정 반영 필요

| 디자인 요소 | 이 API 가 주는 값 |
| --- | --- |
| 답변 말풍선 | `answer` |
| 답변 아래 '근거' 버튼 — 조문 | `sources.laws[]` (법령명 · 조문 · 조문 본문 · 국가법령정보센터 링크) |
| 답변 아래 '근거' 버튼 — 매뉴얼 쪽수 | `sources.manual[]` (자료 이름 · 쪽수) |
| '매뉴얼과 법령에서 찾는 중' | 요청이 끝날 때까지 화면이 표시(아래 §3 동기 응답) |
| 'AI 답변은 참고용입니다…' 안내 | 화면 고정 문구 + 응답 `notice`(같은 뜻, §3) |
| 추천 질문 · 새 대화 | 화면에서 처리. 서버 값 없음(§6-3) |

화면 아래쪽 **업무 단계별 참고사항 · 주요 조문** 목록은 이번 범위가 아닙니다(§7 2단계).

---

## 2. 엔드포인트

### `POST /api/v1/law-guide/questions` → 200

상담 회차 · 사례와 묶이지 않는 독립 질의입니다. 로그인한 사용자(COUNSELOR · ADMIN)면 누구나 부를 수 있습니다.

**요청**

```json
{
  "question": "응급조치 기간은 얼마나 돼요?"
}
```

| 필드 | 규칙 |
| --- | --- |
| `question` | 필수. 앞뒤 공백 제거 뒤 1~500자. 넘으면 422 `VALIDATION_ERROR` |

- 한 번에 질문 하나만 받습니다(대화 맥락 없음). AI 모듈이 이전 대화를 받지 않아서입니다. '새 대화' 는 화면의 말풍선만 지웁니다.
- 대상 법령 · 매뉴얼 범위는 서버 설정(`LAW_TARGET_LAWS`, `manual/manifest.py`)을 따르고, 요청으로 바꾸지 않습니다.

**응답** (`DataResponse` 감싸기는 1.1 그대로)

```json
{
  "data": {
    "answer": "응급조치는 … 72시간을 넘을 수 없어요(아동학대범죄의 처벌 등에 관한 특례법 제12조). …",
    "sources": {
      "laws": [
        {
          "law_name": "아동학대범죄의 처벌 등에 관한 특례법",
          "article": "제12조",
          "title": "피해아동 등에 대한 응급조치",
          "content": "① 제11조제1항에 따라 현장에 출동하거나 …",
          "portal_url": "https://www.law.go.kr/LSW/lsInfoP.do?lsiSeq=…&joNo=0012&joBrNo=00"
        }
      ],
      "manual": [
        {
          "id": "ref3_risk_scale_1",
          "title": "참고자료3 아동학대 위험수준별 개입 사정 척도 1/2 — 위험요인 문항 1~21(0~3점)",
          "page": "350"
        }
      ]
    },
    "law_versions": [
      { "law_name": "아동복지법", "effective_date": "2026-10-02" },
      { "law_name": "아동학대범죄의 처벌 등에 관한 특례법", "effective_date": "2026-10-02" }
    ],
    "notice": "AI 답변은 참고용입니다. 최종 판단은 매뉴얼 원문과 법령을 확인해 주세요.",
    "model": "gpt-5.6-luna",
    "answered_at": "2026-10-27T03:12:45Z"
  }
}
```

| 필드 | 뜻 |
| --- | --- |
| `answer` | 답변 본문. 비어 있지 않습니다(빈 답은 실패로 봅니다, §4) |
| `sources.laws[]` | 답변이 근거로 쓴 조문. **실제 조문 목록과 대조해 통과한 것만** 옵니다(`_verify_cited_articles`, 법령명 + 조문번호가 둘 다 맞아야 함). 없으면 빈 배열 |
| `sources.manual[]` | 답변이 근거로 쓴 매뉴얼 자료. **이번 질문에 실제로 첨부한 페이지 중에서만** 옵니다(`_verify_manual_references`). 내용이 그 페이지에 있다는 보장은 아닙니다(§5-2). `page` 는 문자열이고 쪽수를 모르면 `"?"`(서식29 두 장) |
| `law_versions[]` | 답변에 쓴 법령의 시행일. 화면 아래 '개정 여부는 원문으로 확인' 안내 옆에 보일 수 있습니다 |
| `notice` | 참고용 안내 고정 문구. 화면이 이미 고정 문구를 갖고 있으면 쓰지 않아도 됩니다 |
| `model` | 답한 모델 이름(감사 · 문의용) |

### 왜 202 + Polling 이 아닌가 (1.4 예외)

1.4 는 'STT/AI 요청은 202 로 즉시 반환' 입니다. 이 API 는 예외로 **동기 200** 을 제안합니다.

- 결과를 붙일 회차가 없고, 서버에 저장하지도 않습니다(§5-3). Polling 하려면 질문 · 답변을 담을 표를 새로 만들어야 합니다.
- 한 번에 걸리는 시간이 분석(최대 180초)보다 훨씬 짧습니다. 서버 제한 시간은 `LAW_QA_TIMEOUT_SECONDS`(기본 60초)로 따로 둡니다.
- 채팅 화면은 '찾는 중' 을 보이고 응답을 기다리면 됩니다.

실제로 재 보니 60초를 자주 넘으면 202 + `GET /law-guide/questions/{id}` 로 바꿉니다. 이때는 질문 원문 저장 문제(§5-3)를 먼저 정해야 합니다.

---

## 3. 오류

| code | status | 언제 |
| --- | --- | --- |
| `VALIDATION_ERROR` | 422 | 질문이 비었거나 500자 초과 |
| `UNAUTHORIZED` · `PASSWORD_CHANGE_REQUIRED` 등 | 401 · 403 | 다른 API 와 같음 |
| `LAW_QA_DISABLED` (새) | 503 | `LAW_QA_PROVIDER=off` 이거나 운영 잠금(§5-1)에 걸림 |
| `LAW_SOURCE_UNAVAILABLE` (새) | 503 | 법령 캐시가 없고 국가법령정보센터 조회도 실패 |
| `AI_TIMEOUT` | 504 | `LAW_QA_TIMEOUT_SECONDS` 안에 답이 안 옴 |
| `AI_AUTH_ERROR` · `AI_QUOTA_ERROR` | 502 | OpenAI 키 · 한도 문제 |
| `AI_FAILED` · `AI_INVALID_OUTPUT` | 502 | 그 밖의 LLM 실패, JSON 이 아니거나 `answer` 가 빈 응답 |
| `RATE_LIMITED` (새) | 429 | 사용자당 호출 한도 초과(§5-4) |

- `AI_*` 코드는 지금 13절에서 'Session `error` 필드로 전달(status —)' 인데, 이 API 에서는 HTTP 응답 코드로도 씁니다. 13절 표에 이 API 용 줄을 따로 추가합니다.
- **오류 문구는 고정 문구만** 씁니다(`map_ai_error` 와 같은 원칙). 예외 문구에는 질문 원문 · OC 인증값 · 내부 경로가 섞일 수 있습니다.

> ✅ **2026-10-27 반영(§6-1).** 예전에는 `answer_*` 가 LLM 실패를 삼키고 `answer` 에 실패 문구를 넣어 성공처럼 돌려줬습니다.
> 이제 실패는 **예외로** 올라갑니다. adapter 는 예외 종류로 코드를 정하고 문구는 버립니다.
>
> | 예외 | 언제 | 코드(제안) |
> | --- | --- | --- |
> | `TimeoutError` | `deadline` 을 넘김(문구 고정) | `AI_TIMEOUT` |
> | `law_qa_llm.LawQAOutputError` | LLM 응답에 답변이 없음 | `AI_INVALID_OUTPUT` |
> | `law_qa_llm.LawQALLMError` | 그 밖의 LLM 호출 실패(OpenAI 인증 · 연결 등). 문구는 `"법령 질의 LLM 호출 실패(종류 이름)"` | `AI_FAILED` |
> | `law.client.LawApiError` | 법령 캐시가 없고 국가법령정보센터 조회도 실패 | `LAW_SOURCE_UNAVAILABLE`(503, 위 표와 같음) |
>
> 성공하면 `answer` 는 늘 비어 있지 않습니다. 세 `LawQA*` · `TimeoutError` 는 원인 예외를 체인에 남기지 않습니다(`from None`) —
> `_call_llm_with_retry` 가 감싼 문구에 OpenAI SDK 원문(요청 URL 등)이 실리기 때문입니다(2026-10-27 민규 교차검증).
> `AI_AUTH_ERROR` · `AI_QUOTA_ERROR` 로 나누려면 종류 이름이 필요한데, 재시도 함수가 `RuntimeError` 로 감싸 올려 지금은 구분되지 않습니다.

---

## 4. Backend 구성

기존 AI 분석과 같은 모양(adapter + provider 스위치)으로 둡니다.

```text
backend/app/
├─ api/v1/law_guide.py          # POST /law-guide/questions (router.py 에 include)
├─ schemas/law_guide.py         # LawGuideQuestionRequest · LawGuideAnswer · LawSource · ManualSource
├─ services/law_guide_service.py# 검증 · 사용자 호출 한도 · 동시 실행 제한 · 시간 제한 · 감사 기록
└─ adapters/law_qa_adapter.py   # Protocol + MockLawQAAdapter + ModelingLawQAAdapter + get_law_qa_adapter()
```

- **`LAW_QA_PROVIDER`**: `off | mock | modeling`, 기본 `mock`. `AI_PROVIDER` 와 따로 둡니다(분석은 mock 인데 법령 질의만 켜거나 그 반대가 가능하게).
  - `mock`: 고정 답변 + 고정 근거(조문 1개 · 매뉴얼 1장)를 돌려줍니다. 화면 개발 · backend CI 는 OpenAI 없이 이걸로 합니다.
  - `modeling`: `module_loader` 로 `ai.modeling.abuse.legal_manual_qa_llm.answer_legal_manual_question` 을 **처음 부를 때** 가져옵니다
    (분석 adapter 의 `_load_pipeline` 과 같이 지연 import, `export_llm_env` · `build_openai_client_and_model` 사용).
    `deadline` 은 `시작 + LAW_QA_TIMEOUT_SECONDS - AI_DEADLINE_MARGIN_SECONDS` 로 넘깁니다.
- **응답 변환**은 adapter 가 합니다. 모듈의 `cited_articles` 에서 `law_name · article · title · content · portal_url` 만 골라 옮기고(그 밖의 키는 버림),
  `manual_references` 는 모듈이 `{id, title, page}` 로 주므로(§6-2, 2026-10-27 반영) 그대로 옮깁니다.
- **동시 실행 제한**: 호출 하나가 큰 입력(§5-4)이라 서버 전체 동시 2건(`LAW_QA_MAX_CONCURRENCY`)으로 묶습니다. 자리가 없으면 잠깐 기다렸다가 시간 안에 못 들어가면 `AI_TIMEOUT`.
- 엔드포인트는 `def`(동기)로 두어 FastAPI 스레드풀에서 돕니다. 분석의 BackgroundTasks 와 섞지 않습니다.

---

## 5. 정해야 할 것 · 주의할 것

### 5-1. 개인정보 · 운영 잠금

- 질문은 상담사가 직접 쓰는 글이라 아동 이름 같은 실제 사례 내용이 섞일 수 있습니다. 모듈이 `mask_for_outbound` 로 가린 뒤 OpenAI 로 보내고 답에서 되돌립니다(Tier 1 이름 인식).
- 그런데 **사례와 묶이지 않아 등록 실명 대조(Tier 2)는 원래 돌 수 없습니다.** `AI_PROVIDER=modeling` 운영 잠금(config `_block_modeling_in_production`)과 같은 위험이 그대로 있습니다.
- 제안: `ENV=production` 에서 `LAW_QA_PROVIDER=modeling` 은 `LAW_QA_ALLOW_IN_PRODUCTION=true` 를 함께 적어야만 뜨게 합니다(분석과 같은 방식, 잠금 문구도 같은 결).
  화면 입력칸에는 '아동 · 가족 실명은 쓰지 마세요' 안내를 둡니다.
- 현직자 인터뷰의 미해결 질문(기관 방화벽이 외부 AI 를 막음 — 온프레미스 LLM 필요 여부)은 이 API 에도 그대로 해당합니다. 지금 설계는 OpenAI 를 전제로 합니다.

### 5-2. 매뉴얼 근거의 한계 · 범위 차이 (중요)

- 매뉴얼 원본이 사진이라, `sources.manual[]` 은 '첨부한 페이지를 가리켰다' 까지만 보장합니다. 화면에서 매뉴얼 근거는 조문 근거와 구분해(예: '참고 자료') 보이는 게 좋겠습니다.
- **디자인과 지금 AI 범위가 다릅니다.** 디자인은 '2026 아동학대 대응 업무 매뉴얼(1권), 전체 494쪽' 의 2~4장(신고접수 p.36 · 응급조치 p.196 · 즉각분리 p.246 · 신변안전 p.291 …)을 근거로 답하는 모습입니다.
  지금 AI 가 가진 매뉴얼은 촬영본 10장(서식 · 척도, p.312~351)뿐입니다. 디자인 목차에서는 서식이 '5장, p.354~' 인데 manifest 는 '6장' 으로 적혀 있어, **같은 책 · 같은 판인지 확인이 필요합니다.**
- 그래서 디자인의 추천 질문 9개 중 법령 조문으로 답할 수 있는 것(응급조치 기간 · 신고자 보호 · 금지행위 · 임시조치 종류 · 조사 방해 처벌 등)은 조문 근거로 답하지만,
  매뉴얼 절차가 핵심인 것(사례판단 기한 · 종결 절차 · 신변안전 수칙)은 '제공된 자료 안에서는 확인되지 않습니다' 로 답할 가능성이 큽니다.
  **추천 질문을 지금 범위에 맞게 바꾸거나, 매뉴얼 2~4장을 먼저 넣어야 합니다**(§6-3).

### 5-3. 저장 · 감사 기록

- 1차는 질문 · 답변을 **DB 에 저장하지 않습니다.** 사례와 묶이지 않은 자유 입력에 개인정보가 섞일 수 있어서입니다. 대화 기록은 화면 상태로만 둡니다(새로고침하면 사라짐).
- 감사 기록(`audit_service.record`)에는 새 `AuditAction.LAW_QA` 로 **사용자 · 시각 · 성공/실패 코드 · 걸린 시간만** 남기고 질문 원문은 남기지 않습니다.
- 로그도 같은 원칙입니다(`core/logging.install_safe_exception_text`).

### 5-4. 비용 · 시간

- 호출마다 두 법령 전문(약 9.8만 자)이 들어가고, 매뉴얼 이미지가 최대 3장 붙습니다. 분석 1회와 비슷하거나 큰 입력이 **질문 한 번마다** 나갑니다.
- 그래서 사용자당 분당 호출 한도(`LAW_QA_RATE_LIMIT_PER_MINUTE`, 기본 6)를 둡니다. 1차는 서버 메모리 기준(서버 1대 전제)으로 충분합니다.
- 프롬프트는 법령 전문을 앞에, 질문마다 바뀌는 매뉴얼 부분을 뒤에 둔 지금 순서를 유지합니다(앞부분이 같으면 제공자 쪽 프롬프트 캐시를 탈 여지가 있음 — 실제 효과는 재 봐야 함).
- 데모 서버의 `OPENAI_API_KEY` 는 아직 개인 키입니다. 이 API 를 데모에 켜면 비용이 그 키로 나갑니다.

### 5-5. 배포

지금 이미지에는 이 기능에 필요한 것이 빠져 있습니다.

| 필요한 것 | 지금 | 할 일 |
| --- | --- | --- |
| `law/` · `manual/` 패키지 | `backend/Dockerfile` 이 `ai/ · agent/ · stt/` 만 COPY | `COPY law/ /law/`, `COPY manual/ /manual/` 추가 |
| 매뉴얼 이미지(`사례관리_업무/`) | git 에 없음(저작권 · 용량) | 가중치처럼 서버에 두고 읽기 전용으로 붙임(`-v …:/사례관리_업무:ro` 또는 `MANUAL_IMAGE_DIR`) |
| 법령 캐시 | 컨테이너 안에서는 `/law_cache`(재시작하면 사라짐) | 쓰기 가능한 볼륨 + `LAW_CACHE_DIR` 지정 |
| `LAW_API_OC` | 서버 `backend.env` 에 없음 | 추가 |
| 국가법령정보센터 접속 | 확인 안 함 | 데모 서버에서 `www.law.go.kr` 나가는 연결 확인 |

캐시는 24시간(`LAW_CACHE_MAX_AGE_HOURS`)마다 다시 받습니다. 첫 질문이 늦어지지 않게 서버 시작 때 한 번 받아 두는 것(`start_ai_preload` 와 같은 자리)을 권합니다.

---

## 6. 먼저 필요한 AI 모듈 수정 (PR #83 쪽)

1. ✅ (2026-10-27) **실패를 성공처럼 돌려주지 않기** — 예외를 그대로 던지고, 빈 답변은 `LawQAOutputError`(고정 문구). `answer` 에 예외 문구를 넣지 않습니다(§3 표).
2. ✅ (2026-10-27) **`manual_references` 에 id · page 같이 주기** — `{id, title, page}`(`manual.manifest.ManualPage` 값). 쪽수를 모르면 `page` 가 `"?"`.
3. **추천 질문 · 범위** — §5-2 의 범위 차이를 정한 뒤, 화면 추천 질문을 지금 자료로 답할 수 있는 것으로 고르거나 매뉴얼 페이지를 추가합니다.

---

## 7. 단계

| 단계 | 내용 |
| --- | --- |
| 1 | §6 모듈 수정 → `POST /law-guide/questions`(mock · modeling) → backend 시험(mock adapter, 가짜 모듈) → API_CONTRACT 새 절 · 13절 오류 표 |
| 1 | counselor-web: `useLawGuide` 훅(질문 보내기 · 찾는 중 · 오류 말풍선), 근거 버튼(조문은 펼쳐서 본문 + 원문 링크, 매뉴얼은 '자료 이름 · p.쪽수') |
| 2 | 아래쪽 '주요 조문' 을 법령 캐시에서 내려주기(`GET /law-guide/articles?law=…&article=…`) — 디자인 README 의 '법령 개정 반영' |
| 2 | 질문 · 답변 저장(즐겨찾기 · 기관 공유)이 필요하면 §5-3 을 다시 정함 |

---

## 8. 질문

| # | 누구에게 | 질문 |
| --- | --- | --- |
| 1 | Backend(최민규) | 동기 200(§2 1.4 예외)으로 가도 될까요, 처음부터 202 + Polling 으로 갈까요? |
| 2 | Backend · 팀장님 | 운영 잠금(§5-1)을 분석과 같은 방식으로 둘까요? |
| 3 | 팀장님 · Frontend(다솔 님) | 매뉴얼 범위 차이(§5-2) — 추천 질문을 바꿀까요, 매뉴얼 2~4장을 먼저 넣을까요? 촬영본이 디자인과 같은 책 · 판인가요? |
| 4 | Backend | 사용자당 호출 한도 · 동시 실행 제한 기본값(분당 6회 · 2건)이 괜찮을까요? |
