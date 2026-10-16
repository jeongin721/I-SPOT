# I-SPOT

아동 상담 음성을 분석하여 **아동 발화 추출 → 학대 유형 신호 탐지 → 공식 근거자료·현행 법령 기반 확인 체크리스트**를 제공하는 상담사 지원 AI 백엔드.

> ⚠️ I-SPOT은 상담사의 판단을 **보조**한다. 학대 여부, 법 위반 여부, 사례 처리 결정을 자동으로 확정하지 않으며 최종 판단은 상담사·전문가가 수행한다.

---

## 전체 흐름

```text
상담 음성 (wav/mp3/m4a/flac/ogg/aac)
  ↓
SelectiveFallbackSTTProvider   ── Deepgram STT + 화자 분리
  │                               └ 누락 의심 구간만 Whisper large-v3로 보완
  ↓
STTPostProcessor               ── 동일 화자 병합, 공백 정리, confidence 재검증
  ↓
RuntimeSpeakerRoleMapper       ── SPEAKER_n → COUNSELOR / CHILD / UNKNOWN
  ├─→ child_analysis_text  →  KLUE-RoBERTa 멀티라벨 (신체/정서/성/방임)
  │                              ↓ 감지된 라벨 → abuse_type (2개 이상이면 multiple)
  │                         RAG + 국가법령정보센터 API (rag/, law/)
  │                         → 근거 문장, 체크리스트 판정, 관련 조문,
  │                           다음 상담용 확인 질문, 참고자료 2~3개
  └─→ TranscriptBuilder    →  팀 공용 Transcript
```

- 아동 화자를 확정하지 못하면(`child_analysis_status != "OK"`) 학대 유형 분석과 RAG 분석을 모두 건너뛴다.
- threshold를 넘은 학대 유형이 없으면 RAG 분석을 건너뛴다.
- RAG 분석이 실패해도 요청은 실패하지 않는다. 오류는 `rag_analysis.error`로 반환되고 STT·학대 유형 결과는 그대로 응답된다.

## 저장소 구조

```text
main.py                    # FastAPI 서버 (POST /api/v1/analyze)
ispot_stt.py               # STT provider (Deepgram / Whisper / Selective Fallback / mock)
ispot_postprocess.py       # STT 후처리
speaker_role_runtime.py    # 런타임 화자 역할 추정 (GT 불필요)
child_analysis_text.py     # 아동 발화만 모은 분석 텍스트 생성
transcript_builder.py      # 팀 공용 Transcript 스키마 생성
abuse_model/infer_abuse.py # KLUE-RoBERTa 학대 유형 추론
ispot_analyzer.py          # (선택) Groq LLM 기반 위험도 분석
ispot_audio_features.py    # 음향 특징(pause, 발화속도, pitch, energy) 추출 — 실험용
rag/                       # 체크리스트 RAG + 동적 체크리스트 파이프라인 → rag/README.md
law/                       # 국가법령정보센터 Open API 클라이언트·파서·조문 랭킹
experiments/               # STT/화자분리/fallback 평가 스크립트 (서비스 경로 아님)
tests/                     # 단위 테스트
I-SPOT_DOCS/               # 기획·아키텍처·규칙·작업 현황 문서
HANDOFF_STT.md             # STT/화자 역할 파이프라인 인계 문서
```

## 시작하기

### 1. 설치

Python 3.12 기준.

```bash
python -m venv .venv
.venv\Scripts\activate           # macOS/Linux: source .venv/bin/activate

pip install -r requirements.txt
pip install -r requirements-rag.txt
```

`main.py`가 `rag.pipeline`을 import하므로 API 서버를 실행하려면 **두 파일 모두 설치해야 한다.**

선택 의존성 (requirements에 미포함):
- `librosa` — `ispot_audio_features.py` 사용 시
- `pyannote.audio` — pyannote 화자 분리 실험 시 (서비스 경로에서는 사용하지 않음)

### 2. 환경 변수

```bash
copy .env.example .env      # macOS/Linux: cp .env.example .env
```

| 변수 | 용도 | 필요한 경우 |
|---|---|---|
| `DEEPGRAM_API_KEY` | Deepgram STT | API 서버 실행 |
| `I_SPOT_STT_PROVIDER` | `Transcriber` 기본 provider (`deepgram`, `whisper`, `mock`) | `Transcriber` 직접 사용 |
| `OPENAI_API_KEY` | RAG 임베딩·근거 분석 | RAG 분석 (`/api/v1/analyze` 포함) |
| `LAW_API_OC` | 국가법령정보센터 승인 OC 값 | 관련 법령 조회 (없으면 `law_warning`만 남기고 계속 진행) |
| `RAG_*` | 데이터 경로, 모델, chunk/Top-K 설정 | RAG (기본값 있음) |
| `LAW_*` | 법령 API URL, 캐시 경로·유효시간, 대상 법령 | 법령 조회 (기본값 있음) |
| `GROQ_API_KEY` | `ispot_analyzer.py` | 선택 |
| `PYANNOTE_AUTH_TOKEN` | pyannote 실험 | 선택 |

실제 키는 `.env`에만 넣고 커밋하지 않는다.

### 3. 모델 가중치

학대 유형 모델 가중치는 저장소에 포함되지 않는다. 팀 공유 경로에서 받아 아래 위치에 둔다.

```text
abuse_model/weight/roberta_multilabel_2026-09-03.pth
```

`main.py`는 import 시점에 이 파일을 로드하므로 **파일이 없으면 서버가 시작되지 않는다.**

### 4. RAG 벡터 DB

`rag_data/` 아래에 원문 PDF를 두고 `python -m rag.indexer`로 벡터 DB(`rag_storage/chroma`)를 생성한다. 벡터 DB가 없어도 서버는 시작되지만 `rag_analysis`가 비거나 오류로 반환된다.

## API 서버 실행

```bash
python main.py
# 또는
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

- Health check: `GET /`
- Swagger UI: http://localhost:8000/docs

### `POST /api/v1/analyze`

```bash
curl -X POST http://localhost:8000/api/v1/analyze -F "file=@sample.wav"
```

응답 주요 필드:

| 필드 | 설명 |
|---|---|
| `stt_data` | 후처리된 STT 결과 (segments, words, confidence) |
| `transcript` | 역할(COUNSELOR/CHILD/…)이 붙은 팀 공용 Transcript |
| `speaker_roles` | `SPEAKER_n` → 역할 매핑 |
| `child_speaker` | 아동으로 판정된 화자 ID |
| `child_analysis_status` | `OK`가 아니면 학대 유형 분석 생략 |
| `child_analysis_text` | 아동 발화만 모은 분석용 텍스트 |
| `abuse_prediction` | 라벨별 확률·threshold 판정 (분석 생략 시 `null`) |
| `rag_analysis` | 근거 문장, 체크리스트 판정, 관련 법령, 다음 상담 체크리스트, 참고자료, 매뉴얼·서식(`manual_references`), 판례(`precedents`) (생략 시 `null`, 실패 시 `{"error": ...}`) |

`rag_analysis`의 상세 스키마는 [rag/README.md](rag/README.md#8-주요-json-출력)를 참고한다.

오류: 지원하지 않는 확장자·빈 파일 `400`, STT 엔진 오류 `502`, 그 외 처리 오류 `500`.

### STT 모듈 직접 사용

```python
from ispot_stt import Transcriber

transcriber = Transcriber(provider="mock")   # API Key 없이 동작하는 로컬 테스트용
result = transcriber.transcribe("sample.wav")
```

`provider`를 생략하면 `I_SPOT_STT_PROVIDER` 값을 사용한다. 화자 인식이 불확실한 segment는 `UNKNOWN`으로 유지된다.

## RAG · 법령 파이프라인 (CLI)

API 서버를 거치지 않고 상담 문장만으로 RAG 분석을 실행하거나 디버깅할 때 사용한다.

```bash
# 1) rag_data/ 아래 원문 PDF로 벡터 DB 생성
python -m rag.indexer

# 2) 상담 문장 분석 (체크리스트 RAG + 현행 법령 + 다음 상담 질문)
python -m rag.pipeline "상담 문장" --abuse-type emotional
python -m rag.pipeline "상담 문장" --abuse-type emotional --json        # 백엔드 연동용
python -m rag.pipeline "상담 문장" --abuse-type emotional --skip-law    # 법령 API 없이

# 3) 법령 API 단독 테스트
python -m law.query "아동복지법" --abuse-type emotional --text "상담 문장" --refresh
```

`--abuse-type`: `physical`, `emotional`, `sexual`, `neglect`, `multiple`.
출력 스키마와 상태값(`matched` / `needs_confirmation` / `excluded`)은 [rag/README.md](rag/README.md)에 정리되어 있다.

## 테스트

```bash
python -m pytest tests/ -q
```

`experiments/` 아래 스크립트는 로컬 평가 데이터(`test_sample/`, gitignore)를 전제로 하는 실험·평가용이며 CI 테스트가 아니다. 결과는 `results/`에 저장된다.

## 커밋하지 않는 파일

`.env`, `abuse_model/weight/`, `test_sample/`, `results/`, `rag_data/`, `rag_storage/`, `law_cache/` — 모두 `.gitignore`에 등록되어 있다. 실제 아동·상담 개인정보는 테스트 데이터로 사용하지 않는다.

## 문서

| 문서 | 내용 |
|---|---|
| [I-SPOT_DOCS/README.md](I-SPOT_DOCS/README.md) | 문서 읽는 순서, 우선순위, AI 작업 규칙 |
| [I-SPOT_DOCS/docs/01_PRD.md](I-SPOT_DOCS/docs/01_PRD.md) | 서비스 정의, 요구사항 |
| [I-SPOT_DOCS/docs/02_ARCHITECTURE.md](I-SPOT_DOCS/docs/02_ARCHITECTURE.md) | 시스템·데이터·AI 구조 |
| [I-SPOT_DOCS/docs/03_UI_UX.md](I-SPOT_DOCS/docs/03_UI_UX.md) | 화면, 사용자 Flow |
| [I-SPOT_DOCS/docs/04_DEVELOPMENT.md](I-SPOT_DOCS/docs/04_DEVELOPMENT.md) | 코드·Git·테스트·배포 규칙 |
| [I-SPOT_DOCS/docs/05_RULES.md](I-SPOT_DOCS/docs/05_RULES.md) | 안전·보안·변경 금지 규칙 (항상 적용) |
| [I-SPOT_DOCS/TASKS.md](I-SPOT_DOCS/TASKS.md) | 현재 작업 현황 |
| [HANDOFF_STT.md](HANDOFF_STT.md) | STT·화자 역할 파이프라인 상세 및 실험 기록 |
| [rag/README.md](rag/README.md) | RAG V2 · 법령 연동 상세 |
