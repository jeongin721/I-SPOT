# I-SPOT Backend

아동 상담 지원 시스템 I-SPOT 의 Backend API.
FastAPI + PostgreSQL + SQLAlchemy 2.x 기반이며, STT/AI Service 를 Adapter 로 연동한다.

관련 문서
- `backend/docs/CODE_GUIDE.md` — **처음 이 코드를 본다면 여기부터** (읽는 순서 / 요청 흐름 / 폴더 역할)
- `backend/docs/API_CONTRACT.md` — **Frontend 연동용 API 상세**
- `I-SPOT_DOCS/docs/02_ARCHITECTURE.md` — 공통 Contract / 상태 정의
- `I-SPOT_DOCS/docs/04_DEVELOPMENT.md` — 개발 순서 / 테스트 기준
- `I-SPOT_DOCS/docs/05_RULES.md` — AI & Project 공통 규칙

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

> **Frontend 개발자라면 [부록 A. Docker 없이 5분 만에 띄우기](#부록-a-docker-없이-5분-만에-띄우기)를 먼저 보세요.**
> 화면 연동 확인이 목적이면 PostgreSQL 도 Docker 도 필요 없습니다.

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

### 2.7 데모 데이터 생성 (선택)

Frontend 개발이나 시연을 하려면 **여러 상태의 상담 데이터**가 필요하다.
`2.6` 에서 서버를 띄운 상태로 다른 터미널에서 실행한다.

```bash
python -m scripts.seed_demo_data \
  --base-url http://localhost:8000 \
  --admin-email admin@ispot.example.com \
  --admin-password <seed 비밀번호>
```

아래 6개 상태의 사례가 생성된다. Frontend 는 각 상태에 대응하는 화면을 확인할 수 있다.

| 상태 | 화면 |
|---|---|
| `CREATED` | 녹음 시작 전 |
| `AUDIO_UPLOADED` | 업로드 완료, STT 대기 |
| `STT_REVIEW_REQUIRED` | STT 검수 화면 |
| `STT_CONFIRMED` | 원문 확정, AI 대기 |
| `AI_REVIEW_REQUIRED` | AI 요약 검수 화면 |
| `APPROVED` | 완료 (읽기 전용) |

마지막 사례는 다른 상담사에게 배정되므로 **권한 격리**도 확인할 수 있다.
관리자로 로그인하면 전체가 보이고, 해당 상담사로 로그인하면 1건만 보인다.

데이터는 전부 합성이다. 실제 아동 정보를 사용하지 않으며 학대 정황을 생성하지 않는다.
(`I-SPOT_DOCS/docs/05_RULES.md`)

실행할 때마다 사례가 새로 추가된다. 초기화하려면 DB 를 다시 만든다.

### 2.8 전체를 Docker 로 실행

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

### Push 전 로컬 검증

CI 와 같은 항목(Lint / Test / Migration 정합성)을 한 번에 확인한다.

```bash
./scripts/check.sh
```

개별로 실행할 수도 있다.

```bash
ruff check .    # PR 최소 조건 (04_DEVELOPMENT.md §4)
pytest
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
  scripts/
    seed_users.py        초기 계정 생성
    seed_demo_data.py    상태별 데모 상담 데이터 생성 (Frontend/시연용)
    smoke_api.py         실행 중인 서버에 대한 전체 Flow 확인
    check.sh             push 전 로컬 검증 (Lint/Test/Migration)
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

---

## 부록 A. Docker 없이 5분 만에 띄우기

**Frontend 화면을 실제 API 에 붙여볼 때** 쓰는 방법이다.
PostgreSQL·Docker 없이 SQLite 파일 하나로 동작한다.

> 이 방법은 **로컬 개발 전용**이다. 배포나 성능 확인에는 §2 의 PostgreSQL 을 쓴다.

### A.1 가상환경 + 의존성

```bash
cd backend
python -m venv .venv
source .venv/Scripts/activate      # Git Bash (Windows)
pip install -r requirements-dev.txt
```

활성화 명령은 터미널 종류에 따라 다르다. §2.2 표를 참고한다.

### A.2 .env 생성

`backend/.env` 로 저장한다. `JWT_SECRET_KEY` 는 아무 문자열이나 넣어도 로컬에서는 동작한다.

```bash
ENV=local
DEBUG=true
LOG_LEVEL=INFO

# PostgreSQL 대신 파일 하나를 쓴다. Docker 가 필요 없다.
DATABASE_URL=sqlite+pysqlite:///./dev.db
DB_ECHO=false

JWT_SECRET_KEY=local-dev-only-change-me-1234567890
ACCESS_TOKEN_EXPIRE_MINUTES=720

CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173

AUDIO_STORAGE_ROOT=../storage/audio
AUDIO_MAX_SIZE_MB=200
AUDIO_ALLOWED_EXTENSIONS=.wav,.mp3,.m4a,.mp4,.ogg,.flac,.webm

# 팀 A / 팀 B 산출물 없이도 전 과정이 동작한다.
STT_PROVIDER=mock
AI_PROVIDER=mock
```

### A.3 DB 생성 + 계정 + 데모 데이터

```bash
alembic upgrade head

# 관리자/상담사 계정 생성 — 출력되는 비밀번호를 적어둔다
PYTHONPATH=. python scripts/seed_users.py --demo

# 서버 실행 (아래 A.4) 후 다른 터미널에서
PYTHONPATH=. python scripts/seed_demo_data.py \
  --base-url http://127.0.0.1:8000 \
  --admin-email admin@ispot.example.com \
  --admin-password <위에서 출력된 비밀번호>
```

데모 데이터는 **상태별 사례 6건**을 만든다. 각 화면이 어떤 상태에서
어떻게 보여야 하는지 한 번에 확인할 수 있다.

```text
C-2026-0001  CREATED               음성 업로드 전
C-2026-0002  AUDIO_UPLOADED        STT 대기
C-2026-0003  STT_REVIEW_REQUIRED   원문 검수 필요
C-2026-0004  STT_CONFIRMED         AI 분석 대기
C-2026-0005  AI_REVIEW_REQUIRED    요약 검수 필요
C-2026-0006  APPROVED              완료
```

### A.4 서버 실행

```bash
uvicorn app.main:app --reload
```

- API 문서 — <http://127.0.0.1:8000/docs>
- 상태 확인 — <http://127.0.0.1:8000/health>

### A.5 Frontend 에서 붙이기

`ispotvscode` 의 vite 설정이 `/api/v1` 요청을 `127.0.0.1:8000` 으로 넘긴다.
Backend 를 켜둔 상태에서 프론트를 실행하면 CORS 설정 없이 바로 연결된다.

```bash
cd ispotvscode
npm install
npm run dev
```

연결 확인 페이지: <http://localhost:5173/api-demo>
로그인 → 사례 목록 → 회차 목록이 실제 API 로 동작한다.

### A.6 자주 겪는 문제

| 증상 | 원인과 해결 |
|---|---|
| `401 UNAUTHORIZED` (Swagger) | 페이지를 새로고침하면 Authorize 가 풀린다. 다시 로그인해 토큰을 넣는다 |
| 토큰을 넣었는데 `401` | 응답에서 토큰을 복사할 때 앞뒤 `"` 까지 복사한 경우다. 따옴표 안쪽만 넣는다 |
| `409 INVALID_SESSION_STATE` | 상태 순서를 건너뛴 요청이다. 오류 본문의 `expected_status` 를 확인한다 |
| `202` 를 받았는데 결과가 없다 | STT/AI 는 비동기다. 완료가 아니라 **접수**이므로 세션 상태를 polling 한다 |
| 화면 스타일이 사라짐 | vite 캐시 문제다. `rm -rf node_modules/.vite && npm run dev` |

### A.7 정리

DB 를 초기화하려면 서버를 끄고 파일만 지우면 된다.

```bash
rm backend/dev.db
alembic upgrade head
```
