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

## 코드 구조

```text
/
├─ backend/                  # FastAPI + PostgreSQL Backend (팀 C)
│  ├─ README.md              # 실행 방법 / 환경변수 / 테스트
│  └─ docs/
│     ├─ CODE_GUIDE.md       # 코드 읽는 순서 / 요청 흐름 (처음이면 여기부터)
│     └─ API_CONTRACT.md     # Frontend 연동용 API 상세
├─ ai/                       # LLM 분석 파이프라인 (팀 B)
│  └─ modeling/              # 학대/위기/상호작용 모델링 (ai-modeling)
├─ stt/                      # STT 파이프라인 (팀 A)
├─ docker-compose.yml        # Local 실행용 최소 구성 (PostgreSQL 등)
└─ I-SPOT_DOCS/              # 공통 기준 문서
```

Backend 를 실행하려면 `backend/README.md` 를 따른다.

```bash
docker compose up -d db
cd backend && pip install -r requirements-dev.txt
cp .env.example .env
alembic upgrade head
python -m scripts.seed_users --demo
uvicorn app.main:app --reload
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

## 로컬 개발 환경 설정

### 1) 환경 변수 복사
프로젝트 루트에 `.env` 파일을 생성한다.

```bash
copy .env.example .env
```

이는 로컬 개발 환경에서 API Key, provider, diarization 옵션을 코드에 직접 넣지 않고 외부 환경 변수로 관리하기 위해서다.

### 2) 필수 값 예시
```env
I_SPOT_STT_PROVIDER=mock
I_SPOT_SPEAKER_DIARIZATION_PROVIDER=mock
OPENAI_API_KEY=
PYANNOTE_AUTH_TOKEN=
```

- `mock`은 로컬 테스트용 기본값이며, API Key 없이도 동작한다.
- `whisper`로 변경하면 OpenAI Whisper를 사용한다.
- `pyannote`로 변경하면 실제 화자 분리 모델을 연결할 준비가 된다.
- 실제 개인정보를 테스트 데이터로 사용하지 않는다.

### 3) 로컬 실행
```bash
python -m pytest tests/test_stt_transcriber.py -q
```

이 명령은 현재 구현된 STT contract와 diarization 구조가 실제로 동작하는지 확인하는 검증 절차다.

### 4) STT 사용 예시
```python
from ispot_stt import Transcriber

transcriber = Transcriber(provider="mock")
result = transcriber.transcribe("sample.wav")
print(result)
```

이 코드는 backend에서 import 후 바로 음성 파일을 전사하는 기본 사용 흐름을 보여준다.

### 5) 화자 분리 구조
현재 구현은 다음 구조를 유지한다.

```python
Transcriber -> SpeakerDiarizer -> normalize_speaker_label()
```

- STT는 세그먼트별 텍스트/타임스탬프/신뢰도를 생성한다.
- 화자 분리는 각 segment에 `speaker` 값을 붙이는 역할을 한다.
- 화자 인식이 불확실하면 `UNKNOWN`을 유지한다.
- 이 구조는 `pyannote` 또는 다른 diarization provider로 교체 가능하다.
- 핵심 목적은 공통 Contract를 유지하면서 실제 diarization 엔진을 유연하게 교체하는 것이다.
