# Backend 코드 읽는 가이드 (Code Reading Guide)

이 문서는 **처음 이 코드를 보는 팀원**을 위한 길잡이다.
파일이 90개라 어디부터 봐야 할지 막막할 때 여기부터 읽으면 된다.

- 각 파일이 무슨 일을 하는지는 **파일 맨 위 주석**에 적혀 있다.
- 이 문서는 그 파일들이 **어떻게 맞물려 돌아가는지**를 설명한다.

관련 문서
- `backend/README.md` — 실행 방법 (setup)
- `backend/docs/API_CONTRACT.md` — API 명세 (Frontend 연동용)
- `I-SPOT_DOCS/docs/02_ARCHITECTURE.md` — 팀 공통 규격

---

## 1. 30초 요약

아동 상담을 **녹음 → 텍스트 변환(STT) → AI 요약 → 상담사 검수 → 승인**까지
처리하는 API 서버다.

```text
Frontend (Next.js)
   ↓  HTTP
FastAPI  ← 이 저장소
   ├─ PostgreSQL        상담 기록 저장
   ├─ Local Storage     음성 파일 저장
   ├─ STT Adapter       음성 → 텍스트   (팀 A)
   └─ AI Adapter        텍스트 → 요약   (팀 B)
```

핵심 원칙 하나만 기억하면 된다.
**AI는 판단하지 않고, 최종 결정은 항상 상담사가 한다.**
그래서 모든 AI 결과는 `DRAFT` 상태로 저장되고 상담사가 승인해야 확정된다.

---

## 2. 폴더 구조 (Layer)

요청은 항상 **위에서 아래로** 흐른다. 아래 계층이 위 계층을 호출하지 않는다.

| 폴더 | 역할 (Layer) | 무엇이 들어있나 |
|---|---|---|
| `app/api/v1/` | **Router** (Controller) | URL 정의. 로직 없이 service 호출만 한다 |
| `app/services/` | **Service** | 실제 비즈니스 로직. 코드의 대부분이 여기 있다 |
| `app/models/` | **Model** (Entity) | DB 테이블 정의 (SQLAlchemy) |
| `app/schemas/` | **Schema** (DTO) | 요청/응답 형식 검증 (Pydantic) |
| `app/adapters/` | **Adapter** | 외부 서비스(STT/AI) 연결. 갈아끼울 수 있게 분리 |
| `app/core/` | **Core** | 설정, DB 연결, 인증, 오류, 상태 규칙 등 공통 기반 |
| `alembic/` | **Migration** | DB 테이블 생성/변경 이력 |
| `tests/` | **Test** | pytest 130개 |

### 왜 Router 를 얇게 만들었나

`app/api/v1/analysis.py` 는 57줄인데 `app/services/analysis_service.py` 는 337줄이다.
Router 에 로직을 넣으면 테스트할 때 매번 HTTP 요청을 만들어야 하고,
같은 로직을 다른 곳에서 재사용할 수 없다.
그래서 **Router 는 "받아서 넘기기"만** 하고 판단은 전부 Service 가 한다.

---

## 3. 요청 하나가 지나가는 길

### 예시 A — 사례 목록 조회 (간단, 동기)

`GET /api/v1/cases`

```text
1. app/api/v1/cases.py      list_cases()
                            URL 과 query parameter 를 받는다
        ↓
2. app/core/deps.py         get_current_user()
                            토큰을 검사해 로그인한 사용자를 찾는다
                            → 없으면 401 UNAUTHORIZED
        ↓
3. app/services/case_service.py   list_cases()
                            상담사면 본인 담당 Case 만 조회하도록 조건 추가
                            (권한 검사는 여기서 한다)
        ↓
4. app/models/case.py       Case
                            DB 에서 실제 데이터를 읽는다
        ↓
5. app/schemas/case.py      CaseResponse
                            응답에 내보낼 필드만 골라낸다
        ↓
6. app/core/responses.py    DataResponse
                            {"data": {...}} 형태로 감싼다
```

### 예시 B — 음성 업로드 후 STT (복잡, 비동기)

STT 는 오래 걸리므로 **바로 응답하고 뒤에서 처리**한다.
Frontend 는 결과가 나올 때까지 주기적으로 물어본다(Polling).

**1단계: 음성 업로드** — `POST /sessions/{id}/audio`

```text
app/api/v1/audio.py         upload_audio()
        ↓
app/services/access.py      get_session_or_404()
                            내 담당 Session 이 맞는지 확인 → 아니면 403
        ↓
app/services/audio_service.py   upload_audio()
        ├─ 확장자 검사        .wav .mp3 .webm ...
        ├─ MIME 검사
        ├─ 파일 내용 검사      진짜 음성 파일인지 앞부분 바이트 확인
        ├─ core/storage.py    저장 (경로 조작 공격 차단, 용량 초과 시 중단)
        ├─ core/state_machine.py   CREATED → AUDIO_UPLOADED 로 바꿔도 되는지 확인
        └─ audit_service.py   "누가 언제 올렸는지" 이력 남김
```

**2단계: STT 실행 요청** — `POST /sessions/{id}/transcript`

```text
app/api/v1/transcript.py    request_stt()
        ↓
app/services/transcript_service.py   request_stt()
                            상태를 STT_PROCESSING 으로 바꾸고
        ↓
        202 Accepted 즉시 응답  ← 여기서 사용자는 기다리지 않는다
        ↓
        BackgroundTasks 로 아래를 뒤에서 실행
```

**3단계: 백그라운드 처리**

```text
app/services/transcript_service.py   process_stt()
        ↓
app/adapters/stt_adapter.py   get_stt_adapter()
                            설정에 따라 mock 또는 실제 STT 선택
        ↓
app/core/concurrency.py     run_with_timeout()
                            정해진 시간 안에 안 끝나면 실패 처리
        ↓
      성공 → Transcript 저장, 상태 STT_REVIEW_REQUIRED
      실패 → 상태 STT_FAILED + 오류 코드 저장 (재시도 가능)
```

**4단계: Frontend 가 결과 확인** — `GET /sessions/{id}/transcript`

아직 처리 중이면 404 가 아니라 `transcript: null` 을 돌려준다.
Frontend 는 `session_status` 만 보고 판단하면 된다.

---

## 4. 처음 읽을 때 추천 순서

작은 파일부터 보면 전체 그림이 빨리 잡힌다.

| 순서 | 파일 | 줄 수 | 왜 먼저 보나 |
|---|---|---|---|
| 1 | `app/core/enums.py` | 114 | 상담 상태, 화자 종류 등 **용어 사전**. 여기부터 봐야 나머지가 읽힌다 |
| 2 | `app/core/state_machine.py` | 73 | 상태가 어떤 순서로 바뀌는지. 이 시스템의 뼈대 |
| 3 | `app/schemas/contracts.py` | 90 | 팀 A·B 와 주고받는 **공통 데이터 형식** |
| 4 | `app/models/session.py` | 133 | 가장 중심이 되는 테이블 |
| 5 | `app/api/v1/sessions.py` | 57 | 가장 단순한 Router. 계층 구조 감 잡기 |
| 6 | `app/services/access.py` | 70 | 권한 검사가 어떻게 되는지 |
| 7 | `app/main.py` | — | 앱 시작점. 오류 응답이 어떻게 통일되는지 |
| 8 | `app/services/transcript_service.py` | 526 | 가장 복잡한 로직. 위를 다 본 뒤에 |

시간이 없다면 **1 → 2 → 5** 만 봐도 구조는 파악된다.

### 테스트를 읽는 것도 좋은 방법이다

`tests/test_e2e_flow.py` (252줄) 는 로그인부터 승인까지 전체 흐름을
순서대로 실행한다. **이 파일 하나가 사용 설명서 역할**을 한다.

---

## 5. 알아야 할 핵심 개념 5가지

### (1) 응답은 항상 같은 모양이다 (Response Envelope)

성공하든 실패하든 형식이 고정되어 있어서 Frontend 가 처리하기 쉽다.

```json
성공: {"data": { ... }}
실패: {"error": {"code": "CASE_NOT_FOUND", "message": "사례를 찾을 수 없습니다."}}
```

`app/main.py` 에서 모든 예외를 가로채므로, 예상 못 한 오류가 나도
형식이 깨지지 않는다.

### (2) 상태 머신 (State Machine)

상담은 정해진 순서로만 진행된다. `app/core/state_machine.py` 가 강제한다.

```text
CREATED → AUDIO_UPLOADED → STT_PROCESSING → STT_REVIEW_REQUIRED
        → STT_CONFIRMED → AI_PROCESSING → AI_REVIEW_REQUIRED → APPROVED
```

순서를 건너뛰면 `409 INVALID_SESSION_STATE` 로 막힌다.
예를 들어 **음성도 안 올리고 AI 분석을 요청할 수 없다.**

실패하면 `STT_FAILED` / `AI_FAILED` 로 가고, 오류 내용이 저장되어
같은 요청을 다시 보내면 재시도된다.

### (3) 외부 서비스는 갈아끼울 수 있다 (Adapter Pattern)

STT 와 AI 는 팀 A·B 가 따로 만든다. 아직 안 붙어도 개발이 막히면 안 된다.
그래서 `.env` 설정만 바꾸면 가짜(mock)와 진짜를 전환할 수 있다.

```env
STT_PROVIDER=mock       # 가짜 결과 반환. Backend 단독 실행 가능
AI_PROVIDER=mock

AI_PROVIDER=pipeline    # 팀 B 의 실제 AI 호출
```

Backend 코드는 한 줄도 안 바뀐다. `app/adapters/` 안에서만 달라진다.

### (4) 권한은 Backend 에서 막는다

Frontend 에서 메뉴를 숨기는 건 보안이 아니다. URL 을 직접 치면 뚫린다.
그래서 모든 조회·수정에서 서버가 다시 확인한다.

- 상담사(COUNSELOR) — **본인 담당 사례만** 접근 가능
- 관리자(ADMIN) — 전체 접근 가능
- 회원가입 기능은 **없다**. 계정은 관리자가 만든다

`app/services/access.py` 의 `get_session_or_404()` 를 거치지 않는
하위 리소스 조회는 없다.

### (5) 사람이 최종 결정한다 (Human-in-the-loop)

AI 결과는 절대 자동 확정되지 않는다.

```text
AI 생성 → 상담사 확인 → 수정 → 승인 → 저장
```

- AI 원본은 `AIAnalysis` 에 **그대로 보존**된다
- 상담사가 고치는 건 `ConsultationSummary` 라는 **사본**이다
- 상담사가 수정한 뒤 AI 를 다시 돌려도 **수정 내용을 덮어쓰지 않는다**
- 누가 언제 무엇을 바꿨는지 `AuditLog` 에 남는다

`abuse_confirmed` 같은 **확정 필드는 만들지 않는다.** 금지 사항이다.

---

## 6. 이걸 고치려면 어디를 보나

| 하고 싶은 일 | 봐야 할 파일 |
|---|---|
| API 주소나 파라미터 변경 | `app/api/v1/` |
| 비즈니스 로직 수정 | `app/services/` |
| DB 컬럼 추가 | `app/models/` → `alembic revision --autogenerate` |
| 요청/응답 필드 추가 | `app/schemas/` |
| 새 오류 코드 추가 | `app/core/errors.py` 의 `ErrorCode` |
| 상담 상태 순서 변경 | `app/core/enums.py` + `app/core/state_machine.py` |
| 실제 STT/AI 연결 | `.env` 의 `STT_PROVIDER` / `AI_PROVIDER` |
| 음성 파일 검증 규칙 | `app/services/audio_service.py` |
| 로그인/권한 정책 | `app/core/deps.py`, `app/services/access.py` |
| 환경변수 추가 | `app/core/config.py` + `.env.example` |

DB 컬럼을 바꿨다면 migration 을 잊지 말 것. 안 만들면 CI 가 잡아낸다.

---

## 7. 코드를 고치기 전에 알아둘 규칙

`I-SPOT_DOCS/docs/05_RULES.md` 에서 온 팀 공통 규칙이다.

**혼자 바꾸면 안 되는 것**
- API 응답 구조 (Frontend 가 깨진다)
- STT / AI 데이터 형식 (팀 A·B 와 합의 필요)
- DB 핵심 테이블의 의미

바꿔야 한다면 먼저 이유와 영향 범위를 팀에 공유한다.

**절대 하면 안 되는 것**
- 상담 원문을 로그에 출력 — 개인정보다. `app/core/logging.py` 참고
- API Key 를 코드에 적기 — `.env` 만 사용
- 아동 실명 저장 — `child_alias` 만 쓴다
- AI 가 학대 여부를 확정하는 필드 만들기

**고친 뒤에는**

```bash
./scripts/check.sh
```

lint, 테스트 130개, migration 정합성을 한 번에 확인한다.
여기서 통과하면 CI 도 통과한다.

---

## 8. 용어 정리

| 용어 | 뜻 |
|---|---|
| Case | 사례. 아동 한 명에 대한 상담 전체 |
| Session | 회기. 한 번의 상담 (Case 하나에 여러 개) |
| Transcript | 음성을 받아쓴 텍스트 전체 |
| Segment | 발화 한 덩어리 (누가, 언제, 무슨 말) |
| STT | Speech-to-Text. 음성을 텍스트로 |
| Confidence | STT 가 얼마나 확신하는지 (0~1). 낮으면 검수 필요 |
| Evidence | AI 요약의 근거가 된 실제 발화 |
| Adapter | 외부 서비스를 갈아끼울 수 있게 감싼 코드 |
| Envelope | 응답을 감싸는 고정된 겉포장 (`data` / `error`) |
| Audit Log | 누가 언제 무엇을 바꿨는지 남기는 기록 |
| Polling | 결과 나올 때까지 주기적으로 물어보는 방식 |
