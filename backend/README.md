# I-SPOT Backend

아동 상담 지원 시스템 I-SPOT 의 Backend API.
FastAPI + PostgreSQL + SQLAlchemy 2.x 기반이며, STT/AI Service 를 Adapter 로 연동한다.

관련 문서
- `I-SPOT_DOCS/docs/02_ARCHITECTURE.md` — 공통 Contract / 상태 정의
- `I-SPOT_DOCS/docs/04_DEVELOPMENT.md` — 개발 순서 / 테스트 기준
- `I-SPOT_DOCS/docs/05_RULES.md` — AI & Project 공통 규칙
- `backend/docs/API_CONTRACT.md` — **Frontend 연동용 API 상세**

---

## 1. 아키텍처

```text
Frontend
   ↓  (JSON / multipart)
FastAPI
   ├─ PostgreSQL          (Case / Session / Transcript / AIAnalysis / Summary / AuditLog)
   ├─ Local Audio Storage (storage/audio/{case_id}/{session_id}/)
   ├─ STT Adapter         → 팀 A transcribe(audio_path)
   └─ AI Adapter          → 팀 B run_analysis_pipeline(transcript)
```

Frontend 는 STT/LLM Provider 를 직접 호출하지 않는다. 모든 외부 호출은 Backend 를 경유한다.

---

## 2. 빠른 시작

### 2.1 PostgreSQL 실행

```bash
# repo root 에서
docker compose up -d db
```

Docker 없이 이미 설치된 PostgreSQL 을 쓰려면 `DATABASE_URL` 만 맞추면 된다.

### 2.2 의존성 설치

```bash
cd backend
python -m venv .venv
```

가상환경 활성화는 **터미널 종류에 따라 경로가 다르다.**

| 터미널 | 명령 |
|---|---|
| Git Bash (Windows) | `source .venv/Scripts/activate` |
| PowerShell (Windows) | `.venv\Scripts\Activate.ps1` |
| cmd (Windows) | `.venv\Scripts\activate.bat` |
| macOS / Linux | `source .venv/bin/activate` |

Windows 에서는 `bin/` 이 아니라 `Scripts/` 이므로,
Git Bash 에서 `source .venv/bin/activate` 를 쓰면 파일을 찾지 못한다.

```bash
pip install -r requirements-dev.txt
```

> Windows 에서 `python` 이 Microsoft Store 안내창을 띄우거나 아무 것도 출력하지 않으면
> PATH 가 Store 스텁(`WindowsApps\python.exe`)을 가리키는 것이다.
> 실제 설치 경로(예: `~/anaconda3/python.exe`)를 쓰거나 Store 앱 별칭을 끈다.

### 2.3 환경변수 설정

```bash
cp .env.example .env
```

`.env` 에서 최소 아래 두 값을 확인한다.

```env
DATABASE_URL=postgresql+psycopg://ispot:ispot@localhost:5432/ispot
JWT_SECRET_KEY=<32 byte 이상 임의 문자열>
```

`JWT_SECRET_KEY` 생성:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

### 2.4 DB Migration

```bash
alembic upgrade head
```

### 2.5 초기 계정 생성

자유 회원가입이 없으므로 첫 계정은 script 로 만든다.

```bash
# 개발용 데모 계정(관리자 + 상담사) 일괄 생성
python -m scripts.seed_users --demo

# 개별 생성
python -m scripts.seed_users --email admin@example.com --name 관리자 --role ADMIN
```

### 2.6 서버 실행

```bash
uvicorn app.main:app --reload
```

- API 문서: http://localhost:8000/docs
- Health check: http://localhost:8000/health

### 2.7 전체를 Docker 로 실행

```bash
# repo root
docker compose up -d
```

Backend 컨테이너는 시작 시 `alembic upgrade head` 를 먼저 실행한다.

---

## 3. 테스트

```bash
cd backend
pytest
```

테스트는 PostgreSQL 없이 SQLite + 임시 디렉터리로 동작하므로 별도 준비가 필요 없다.

포함 범위
- Case / Session CRUD
- Permission (상담사 사례 격리, 관리자 전체 접근)
- Validation / 없는 Case·Session
- Audio Upload (확장자 / MIME / 크기 / 빈 파일 / 손상 파일 / Path Traversal)
- STT Mock / STT Error / STT Timeout / STT Contract 위반
- AI Mock / AI Timeout / AI 실패 / AI 잘못된 출력 / 재시도
- Transcript 수정·확정, Summary 수정·승인, Audit log
- 전체 E2E Flow, Response Contract 유지

### 실행 중인 서버에 대한 Smoke Test

`pytest` 는 `TestClient` 를 사용하므로 BackgroundTask 가 즉시 끝난다.
실제 Polling 동작과 시연 환경을 확인하려면 서버를 띄운 뒤 아래를 실행한다.

```bash
uvicorn app.main:app --port 8000

# 다른 터미널에서
python -m scripts.smoke_api \
  --base-url http://localhost:8000 \
  --email admin@ispot.example.com \
  --password <seed 비밀번호>
```

로그인 → Case/Session 생성 → Audio 업로드 → STT → Transcript 수정·확정
→ AI 분석 → Summary 수정 → 승인 → 재조회까지 한 번에 확인한다.

### Lint / Migration 정합성

```bash
ruff check .    # PR 최소 조건 (04_DEVELOPMENT.md §4)
alembic check   # model 과 migration 이 어긋나면 실패한다
```

GitHub Actions(`.github/workflows/backend-ci.yml`)에서 lint, pytest,
PostgreSQL 대상 migration, secret/음성파일 커밋 검사를 자동 실행한다.

---

## 4. STT / AI Provider 교체

두 Service 는 `.env` 로 전환한다. Backend 코드 수정이 필요 없다.

### STT (팀 A)

```env
# 기본값: 합성 데이터를 반환하는 Mock
STT_PROVIDER=mock

# 실제 STT 연동
STT_PROVIDER=module
STT_MODULE=stt.transcribe_service
STT_FUNCTION=transcribe
```

`module` 모드는 repo root 를 `sys.path` 에 추가한 뒤
`STT_MODULE.STT_FUNCTION(audio_path: str)` 를 호출하고,
결과가 STT Contract 를 만족하는지 저장 전에 검증한다.

### AI (팀 B)

```env
AI_PROVIDER=mock

# 실제 AI Pipeline 연동
AI_PROVIDER=pipeline
OPENAI_API_KEY=...
OPENAI_MODEL=...
```

`pipeline` 모드는 `ai/services/analysis_pipeline.run_analysis_pipeline(transcript)` 를 호출한다.
팀 B 의 Service Exception 은 아래처럼 API 오류 코드로 변환된다.

| 팀 B Exception | API error code |
|---|---|
| `SummaryTimeoutError` | `AI_TIMEOUT` |
| `SummaryAuthenticationError` | `AI_AUTH_ERROR` |
| `SummaryQuotaError` | `AI_QUOTA_ERROR` |
| `SummaryConnectionError` | `AI_FAILED` |
| `SummaryOutputError` | `AI_INVALID_OUTPUT` |

---

## 5. Session 상태 흐름

```text
CREATED
 → AUDIO_UPLOADED
 → STT_PROCESSING
 → STT_REVIEW_REQUIRED
 → STT_CONFIRMED
 → AI_PROCESSING
 → AI_REVIEW_REQUIRED
 → APPROVED
```

실패 상태는 재시도 가능하다.

```text
STT_PROCESSING → STT_FAILED → (재시도) → STT_PROCESSING
AI_PROCESSING  → AI_FAILED  → (재시도) → AI_PROCESSING
```

실패 시 `session.error = {code, message}` 가 함께 반환되므로
Frontend 는 이 값으로 재시도 UI 를 노출할 수 있다.

상태 전이는 `app/core/state_machine.py` 에서 강제되며,
잘못된 순서로 호출하면 `409 INVALID_SESSION_STATE` 를 반환한다.

---

## 6. 프로젝트 구조

```text
backend/
  app/
    main.py              FastAPI app + 전역 예외 handler (Response Contract 보장)
    api/v1/              Router (auth, cases, sessions, audio, transcript, analysis, summary, documents)
    core/
      config.py          .env 기반 설정
      database.py        Engine / Session
      deps.py            인증·권한 Dependency
      enums.py           공통 Enum (상태 / speaker / role)
      errors.py          ErrorCode + APIError
      responses.py       {"data": ...} Envelope
      state_machine.py   Session 상태 전이 규칙
      storage.py         Local Audio Storage (Path Traversal 방지)
      concurrency.py     외부 호출 timeout
      logging.py         상담 원문 미출력 로깅
    models/              SQLAlchemy 2.x Model
    schemas/
      contracts.py       STT / AI 공통 Contract (팀 합의 구조)
      ...                요청·응답 Schema
    services/            비즈니스 로직 (router 는 얇게 유지)
    adapters/
      stt_adapter.py     STT Provider 추상화 + Mock
      ai_adapter.py      AI Pipeline 추상화 + Mock
  alembic/               Migration
  scripts/seed_users.py  초기 계정 생성
  tests/                 pytest
```

호출 경로는 항상 `router → service → adapter` 순서를 유지한다.

---

## 7. 보안 / 개인정보 처리

- 자유 회원가입 없음. 계정은 관리자 또는 seed script 로만 생성한다.
- 권한 검사는 Backend 에서 수행한다. 상담사는 담당 Case 만 조회·수정할 수 있다.
- 아동 실명 컬럼을 두지 않는다. `child_alias` 와 출생연도만 저장한다.
- 상담 원문을 일반 로그에 출력하지 않는다. 로그에는 식별자·개수만 남긴다.
- Audit log 에 상담 원문/요약 본문을 저장하지 않고 변경 필드명만 남긴다.
- API Key / Secret 은 `.env` 로만 주입한다.
- 음성 파일은 `storage/` 에 저장되며 `.gitignore` 로 커밋을 차단한다.

---

## 8. 9월 MVP 범위 밖

Kubernetes, Kafka, MSA, 복잡한 Queue Infrastructure, S3 필수화, RAG,
중대사건 DB, 사례관리 자동 추천은 이번 범위에서 다루지 않는다.

장시간 작업(STT/AI)은 FastAPI `BackgroundTasks` + Polling 으로 처리한다.
