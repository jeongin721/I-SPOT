# I-SPOT Project Guide

이 저장소의 문서는 AI와 팀원이 같은 기준으로 I-SPOT을 개발하기 위한 공통 기준이다.

## 문서 구조

```text
/
├─ README.md                 # 프로젝트 진입점
├─ docs/
│  ├─ 01_PRD.md              # 무엇을 왜 만드는가
│  ├─ 02_ARCHITECTURE.md     # 시스템/데이터/AI 구조
│  ├─ 03_UI_UX.md            # 화면 및 사용자 Flow
│  ├─ 04_DEVELOPMENT.md      # 구현 방법 및 협업 기준
│  └─ 05_RULES.md            # AI/개발 공통 제약
└─ TASKS.md                  # 현재 개발 진행 상태
```

## AI가 문서를 읽는 순서

처음에는 `README.md`만 읽고 작업을 분류한다.

### Flow 1 — 작업 분류
- 요구사항/기능 범위 → `docs/01_PRD.md`
- DB/API/AI/시스템 구조 → `docs/02_ARCHITECTURE.md`
- 화면/User Flow → `docs/03_UI_UX.md`
- 코드/폴더/Git/Test/배포 → `docs/04_DEVELOPMENT.md`
- 제약/금지/변경 원칙 → `docs/05_RULES.md`
- 현재 작업/담당/진척도 → `TASKS.md`

### Flow 2 — 필요한 문서만 추가 확인
현재 Task에 직접 관련된 문서만 읽고 구현한다.
모든 문서를 매번 다시 설명하거나 복사하지 않는다.

예:
- 백엔드 Case API 구현
  → `01_PRD.md`에서 요구사항 확인
  → `02_ARCHITECTURE.md`에서 DB/API Contract 확인
  → `04_DEVELOPMENT.md`에서 구현 규칙 확인
  → `05_RULES.md`에서 변경 금지사항 확인
  → `TASKS.md` 상태 갱신

- AI 위험 발화 분석
  → `01_PRD.md`
  → `02_ARCHITECTURE.md`
  → `05_RULES.md`
  → `TASKS.md`

## 문서 우선순위

충돌 시 아래 순서를 따른다.

`최신 승인된 기획 내용 > 01_PRD.md > 02_ARCHITECTURE.md / 03_UI_UX.md > 04_DEVELOPMENT.md > TASKS.md`

`05_RULES.md`의 안전·보안·변경 금지 규칙은 항상 적용한다.

## AI 기본 행동

1. 먼저 현재 Task의 목표를 한 문장으로 정의한다.
2. 필요한 문서만 확인한다.
3. 기존 Contract를 우선 재사용한다.
4. 필요하면 실제 코드/파일을 생성 또는 수정한다.
5. 공통 구조 변경이 필요하면 바로 바꾸지 않고 변경안을 제시한다.
6. 작업 후 `TASKS.md`에 반영할 내용을 제안한다.

AI의 첫 답변은 장황한 설계 설명이 아니라 아래만 보여준다.

```text
목표:
참조 문서:
수정/생성 파일:
의존 Task:
```

그 다음 실제 작업을 수행한다.

---

## 개발 환경 실행 (Getting Started)

MVP 스캐폴드는 FastAPI 백엔드 + PostgreSQL, Next.js 프론트엔드로 구성된다.

```text
backend/    FastAPI + SQLAlchemy 2.x + Pydantic (Case/Session API, /api/v1)
frontend/   Next.js + TypeScript + Tailwind (Case/Session 관리 UI)
```

### 1) Docker Compose (권장)

```bash
docker compose up --build
# Frontend: http://localhost:3000
# Backend:  http://localhost:8000  (docs: /docs, health: /health)
```

### 2) 로컬 실행 (Docker 없이)

PostgreSQL이 `127.0.0.1:5432`에 `ispot/ispot` 계정으로 준비되어 있어야 한다.

Backend:

```bash
cd backend
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
uvicorn app.main:app --reload --port 8000
pytest            # 테스트 실행
```

Frontend:

```bash
cd frontend
npm install
npm run dev       # http://localhost:3000
```

### Cloud Agent 환경

`.cursor/environment.json`이 `install`/`start`/`terminals`를 정의한다.
`install.sh`는 시스템 패키지·의존성을 설치하고, `start.sh`는 PostgreSQL을 기동하며,
`backend`/`frontend` 터미널이 개발 서버를 실행한다.

### 주요 API (`/api/v1`)

```text
GET  /health
GET  /cases
POST /cases
GET  /cases/{case_id}
GET  /cases/{case_id}/sessions
POST /cases/{case_id}/sessions
```

성공 응답은 `{"data": ...}`, 실패 응답은 `{"error": {"code","message"}}` 형식을 따른다.
