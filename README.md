# I-SPOT Project Guide

I-SPOT은 Backend, Frontend, AI 모델링, STT 파이프라인을 함께 개발하는 통합 저장소입니다. 이 문서는 저장소에 처음 들어온 팀원을 위한 공통 진입점입니다.

## 코드 구조

```text
I-SPOT/
├─ backend/                  # FastAPI + PostgreSQL Backend (팀 C)
│  ├─ README.md              # Backend 실행 방법 / 환경변수 / 테스트
│  └─ docs/                  # CODE_GUIDE, API_CONTRACT
├─ ispotvscode/              # Frontend (React/Vite)
├─ ai/                       # LLM 분석 파이프라인 및 모델링 코드 (팀 B)
│  └─ modeling/              # 학대 / 위기 / 상호작용 모델링
├─ stt/                      # STT 파이프라인 모듈 (팀 A)
├─ data_prep/                # GT 구축 및 STT Provider 평가 코드·산출물
├─ main.py                   # STT + 학대분석 단독 확인용 앱 — Backend 아님
├─ docker-compose.yml        # Local 실행용 최소 구성
└─ I-SPOT_DOCS/              # 공통 기획·아키텍처·개발 규칙 문서
```

### FastAPI 앱이 두 개다 — 포트가 겹친다

| 파일 | 무엇인가 | 포트 |
| --- | --- | --- |
| `backend/app/main.py` | **Backend 본체.** 사례·회차·전사·분석·요약 API | 8000 |
| `main.py` (최상위) | STT + 학대분석만 확인하는 단독 앱 | 8000 |

둘 다 8000 포트를 사용하므로 **동시에 실행할 수 없습니다.** 최상위 `main.py`를 실행한 상태에서 <http://localhost:8000/docs>를 열면 Backend가 아닌 `/api/v1/analyze`만 보입니다.

Backend 실행은 [backend/README.md](backend/README.md)를 따릅니다.

```bash
docker compose up -d db
cd backend && pip install -r requirements-dev.txt
cp .env.example .env
alembic upgrade head
python -m scripts.seed_users --demo
uvicorn app.main:app --reload
```

## AI/STT 파이프라인

STT 결과는 화자 분리와 역할 판별을 거쳐, 안전하게 확정된 아동(`CHILD`) 발화를 후단 분석에 전달하는 것을 목표로 합니다.

```text
음성 입력 → STT / 화자 분리 → 역할 판별 → CHILD 발화 추출 → 후단 분석
```

- 주요 역할은 `COUNSELOR`, `CHILD`, `UNKNOWN`입니다. 불확실한 화자는 `UNKNOWN`으로 유지합니다.
- 아동 화자를 안전하게 확정할 수 없으면 CHILD 대상 분석을 보류합니다. 원본 STT 결과를 억지로 역할로 단정하지 않습니다.
- STT 구현은 `stt/`에, AI 분석·모델링은 `ai/`에 분리되어 있습니다. Backend 연동과 API Contract는 `backend/` 문서를 기준으로 확인합니다.
- 평가·재현용 코드는 `data_prep/` 및 실험 경로에 두며, production 경로와 구분합니다.

### Provider 평가 현황

`data_prep/`은 GT 기반으로 STT Provider의 화자 분리와 역할 매핑을 평가하기 위한 코드와 산출물을 관리합니다.

- Deepgram과 ElevenLabs의 비교 평가는 진행 중입니다.
- Deepgram 100건 파일럿에서는 GT 기반 strict role-separation 평가의 `purity >= 80%`, `role coverage >= 80%` 기준으로 `ROLE_MAPPING_OK`가 77/100건입니다. 이는 일반적인 전사 정확도 77%를 의미하지 않습니다.
- ElevenLabs는 100건 API 처리를 완료했지만, 100건 전체 GT 평가는 아직 완료되지 않았습니다. 현재 18건 비교 결과는 전체 성능 지표로 해석하지 않습니다.

상세 평가 절차·스크립트·산출물은 `data_prep/`을 확인합니다.

## 문서 안내와 협업 규칙

작업을 시작할 때는 `README.md`에서 영역을 분류한 뒤, 해당 문서만 추가로 확인합니다.

- 요구사항/기능 범위: [01_PRD.md](I-SPOT_DOCS/docs/01_PRD.md)
- 시스템·데이터·AI 구조: [02_ARCHITECTURE.md](I-SPOT_DOCS/docs/02_ARCHITECTURE.md)
- 화면/User Flow: [03_UI_UX.md](I-SPOT_DOCS/docs/03_UI_UX.md)
- 코드·폴더·Git·테스트·배포: [04_DEVELOPMENT.md](I-SPOT_DOCS/docs/04_DEVELOPMENT.md)
- 안전·보안·변경 제약: [05_RULES.md](I-SPOT_DOCS/docs/05_RULES.md)
- 현재 작업·담당·진척도: [TASKS.md](I-SPOT_DOCS/TASKS.md)

문서 간 내용이 충돌하면 다음 우선순위를 따릅니다.

`최신 승인된 기획 내용 > 01_PRD.md > 02_ARCHITECTURE.md / 03_UI_UX.md > 04_DEVELOPMENT.md > TASKS.md`

`05_RULES.md`의 안전·보안·변경 금지 규칙은 항상 적용합니다.

공통 Contract와 구조는 우선 재사용합니다. 공통 구조 변경이 필요하면 바로 변경하지 말고 변경안을 먼저 제안합니다.

## 로컬 개발 환경

프로젝트 루트의 STT 관련 환경 변수는 로컬 `.env`에서 관리합니다. 실제 개인정보를 테스트 데이터로 사용하거나 API Key를 코드에 직접 기록하지 않습니다.

```env
I_SPOT_STT_PROVIDER=mock
I_SPOT_SPEAKER_DIARIZATION_PROVIDER=mock
OPENAI_API_KEY=
PYANNOTE_AUTH_TOKEN=
```

STT Contract 검증은 다음 명령으로 실행할 수 있습니다.

```bash
python -m pytest tests/test_stt_transcriber.py -q
```

Backend의 설치·실행·테스트는 별도 [backend/README.md](backend/README.md)를 기준으로 합니다.
