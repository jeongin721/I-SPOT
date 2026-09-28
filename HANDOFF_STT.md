# I-SPOT STT / Speaker Role Pipeline 인계 문서

## 1. 작업 범위

본 작업은 I-SPOT 서비스에서 상담 음성을 후단 AI 모델이 사용할 수 있는 형태로 변환하는 전처리 파이프라인을 담당함.

현재 흐름은 다음과 같음.

```text
Audio
  ↓
SelectiveFallbackSTTProvider
  ↓
Deepgram STT + Speaker Diarization
  │
  └─ 특정 누락 의심 구간
       ↓
     Whisper large-v3 Selective Fallback
  ↓
STTPostProcessor
  ↓
Runtime Speaker Role Mapping
  │
  ├─→ child_analysis_text
  │      ↓
  │   Abuse / Subtype / XAI 모델 입력
  │
  └─→ TranscriptBuilder
         ↓
     Full Transcript
         ↓
     Summary / Grounding / Evidence 입력
```

---

## 2. 주요 파일

### `main.py`

FastAPI 진입점

주요 처리 순서:

1. 오디오 업로드
2. STT 수행
3. STT 후처리
4. Runtime 화자 역할 판별
5. CHILD 분석 텍스트 생성
6. 팀 공용 Transcript 생성
7. 학대 유형 모델 호출

API:

```text
POST /api/v1/analyze
```

---

### `ispot_stt.py`

STT Provider를 담당

기본 STT:

```text
Deepgram Nova-2
```

사용 기능:

- Korean STT
- Speaker Diarization
- Punctuation
- Utterance segmentation
- Word-level timestamp
- Confidence

일부 STT 누락이 의심되는 특정 구간에 대해서만
Whisper large-v3 fallback을 수행함.

Whisper large-v3는 서버 실행 시 즉시 로드하지 않고,
실제 fallback이 필요한 순간에 lazy loading함.

---

### `ispot_postprocess.py`

Deepgram STT 결과 후처리를 담당

주요 기능:

- 연속된 동일 화자 segment 병합
- word-level 정보 보존
- 일부 잘못 잘린 질문형 화자 경계 보정
- confidence 재검증
- segment_id 생성
- 텍스트 공백 정리
- selective fallback 정보 보존

최종 STT segment는 다음과 같은 정보를 가짐.

```json
{
  "segment_id": "seg_001",
  "speaker": "SPEAKER_0",
  "start_ms": 1000,
  "end_ms": 3000,
  "text": "오늘 기분은 어때?",
  "confidence": 0.98
}
```

`words`, `is_low_confidence` 등의 내부 분석용 필드도
STT 결과에는 추가로 존재할 수 있음.

---

### `speaker_role_runtime.py`

Deepgram의 익명 speaker ID를 실제 상담 역할로 추론

예:

```text
SPEAKER_0
SPEAKER_1
```

↓

```text
COUNSELOR
CHILD
```

질문 비율, 짧은 답변 비율 등의 대화 특징을 이용함.

화자 역할을 충분히 확정할 수 없는 경우
억지로 CHILD를 지정하지 않고 `UNKNOWN`으로 처리함.

---

### `child_analysis_text.py`

확정된 CHILD의 발화만 모아 후단 학대 분석 모델에 전달할
`child_analysis_text`를 생성

기본 Deepgram CHILD 발화와 selective fallback으로 복구된
CHILD gap text를 시간순으로 결합함.

CHILD가 정확히 한 명으로 확정되지 않으면:

```text
status = UNRESOLVED_CHILD_SPEAKER
child_analysis_text = ""
```

로 반환

이 경우 학대 유형 분석을 실행하지 않음.

---

### `transcript_builder.py`

Runtime Speaker Role Mapping 결과를 이용하여
STT의 익명 speaker ID를 팀 공용 역할로 변환함.

예:

```text
SPEAKER_0 → COUNSELOR
SPEAKER_1 → CHILD
```

최종 출력:

```json
{
  "schema_version": "1.0",
  "segments": [
    {
      "segment_id": "seg_001",
      "speaker": "COUNSELOR",
      "start_ms": 1000,
      "end_ms": 3000,
      "text": "오늘 기분은 어때?",
      "confidence": 0.98
    }
  ]
}
```

허용 역할:

```text
COUNSELOR
CHILD
GUARDIAN
OTHER
UNKNOWN
```

원본 STT 데이터는 수정하지 않음.

따라서 API에서는 다음 두 데이터를 별도로 사용할 수 있음.

```text
stt_data
→ STT 내부 분석 / 디버깅용
→ SPEAKER_0, SPEAKER_1 유지

transcript
→ 팀 공용 후단 AI 입력용
→ COUNSELOR, CHILD, UNKNOWN 등으로 변환
```

---

### `test_transcript_builder.py`

`TranscriptBuilder`의 기본 contract를 독립적으로 검사

검사 항목:

- schema_version
- 필수 segment 필드
- 허용 speaker role
- SPEAKER_n 잔존 여부
- start/end timestamp
- confidence 범위
- segment_id

실행:

```bash
python test_transcript_builder.py
```

---

## 3. 후단 AI에서 사용할 출력

### A. `child_analysis_text`

학대 분석 계열 모델 입력에 사용

연결 대상:

```text
Abuse Detection
Subtype Detection
XAI / Abuse Explanation
```

즉, 전체 상담 내용을 그대로 학대 분석 모델에 넣는 것이 아니라
CHILD로 확정된 발화만 사용함.

---

### B. `transcript`

전체 상담 흐름이 필요한 기능에 사용함.

연결 대상:

```text
Consultation Summary
Grounding Validation
Evidence Linking
```

각 segment에는 speaker role과 timestamp가 포함되어 있으므로
상담사 질문과 아동 답변의 문맥 및 실제 근거 segment를 추적할 수 있음.

---

## 4. API 주요 응답

`POST /api/v1/analyze` 결과에는 현재 다음 데이터가 포함됨.

```text
status
file_name

stt_data

transcript

speaker_roles

child_speaker
child_analysis_status
child_analysis_text

abuse_prediction
```

핵심적으로 후단에서는 목적에 따라:

```text
child_analysis_text
```

또는:

```text
transcript
```

를 사용하면 됨

---

## 5. 안전 처리

### 화자가 정상적으로 분리된 경우

```text
Deepgram
SPEAKER_0 / SPEAKER_1
       ↓
Runtime Role Mapping
       ↓
COUNSELOR / CHILD
```

CHILD가 한 명으로 확정되면
`child_analysis_text`를 생성하고 후단 학대 분석을 수행

---

### Deepgram이 두 화자를 한 명으로 합친 경우

일부 상담에서는 실제로 상담사와 아동이 모두 존재하지만
Deepgram diarization 결과가 하나의 speaker로 collapse되는 사례가 확인되었음.

이 경우 현재 정책은:

```text
single speaker
     ↓
UNKNOWN
     ↓
UNRESOLVED_CHILD_SPEAKER
     ↓
child_analysis_text 생성 안 함
     ↓
학대 분석 실행 안 함
```

입니다.

안전성 때문에 SPEAKER_0을 임의로 CHILD로 지정하지 않음.

---

## 6. 실험했지만 현재 적용하지 않은 방법

### 정규식 기반 단일화자 복구

한 speaker transcript 내부의 질문/답변 패턴을 이용하여
상담사와 아동 발화를 다시 분리하는 방법을 실험했음.

하지만 상담사의 학대 screening 질문이 CHILD text에 포함되어
학대 유형 오탐을 발생시키는 사례가 확인되어 production에는 적용하지 않았음.

---

### Pyannote Speaker Diarization

Deepgram single-speaker collapse를 보완하기 위한
대체 diarization 방식으로 Pyannote를 실험했음.

일부 사례에서는 화자 분리가 개선되었지만:

- CPU 처리시간이 매우 김
- 일부 파일에서 두 speaker에 Q/A가 크게 혼합됨
- Runtime role 추론이 불안정한 사례 존재
- 소수 실패 사례에 맞춘 추가 튜닝은 과적합 위험 존재

등의 이유로 현재 production fallback에는 포함하지 않았음.

관련 코드는 `experiments/`에 연구/재현 목적으로 보존되어 있음.

---

## 7. Selective Whisper Fallback

Deepgram STT가 특정 발화를 통째로 누락하는 사례가 확인되어
전체 음성을 Whisper로 다시 처리하는 대신
누락이 의심되는 구간에만 Whisper large-v3를 적용.

fallback 결과 전체를 무조건 CHILD text에 넣지 않음.

CHILD 쪽 구간으로 판단된 경우에만
실제 gap 내부에서 복구된 `gap_text`를 사용

---

## 8. Regression Test

30개 평가 샘플을 대상으로 최종 API pipeline regression을 수행함

결과:

```text
전체 파일       : 30
API 성공        : 30/30
아동 화자 미확정 : 4
Fallback 발생   : 2개 파일
```

이 결과는 서비스 정확도(accuracy)를 의미하지 않음

새 Transcript 연결 이후에도 기존 API 파이프라인이 정상적으로
동작하는지 확인하기 위한 regression 결과

---

## 9. 알려진 한계

현재 가장 중요한 한계는 Speaker Diarization,

Deepgram이 실제 두 화자를 하나의 speaker로 합치는 경우
현재 시스템은 안전하게 UNKNOWN으로 보류.

따라서:

```text
API 성공
```

과

```text
모든 상담에서 CHILD 분석 가능
```

은 같은 의미가 아님.

아동 화자가 확정되지 않는 상담은 의도적으로 후단 학대 분석을
실행하지 않음.

---

## 10. Git에 포함하지 않는 파일

다음 항목은 로컬 전용이므로 Git에 포함하지 않음.

```text
.env
test_sample/
results/
model weight
local cache
```

특히 `.env`에는 API key가 포함될 수 있으므로
GitHub에 commit하지 않음.

필요한 API key 및 환경변수는 팀 환경에 맞게 별도로 설정.

---

## 11. 실행

프로젝트 환경 활성화 후 FastAPI 서버 실행:

```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

API endpoint:

```text
POST /api/v1/analyze
```

오디오 파일을 multipart/form-data의 `file` 필드로 전달.

지원 확장자:

```text
.wav
.mp3
.m4a
.flac
.ogg
.aac
```

---

## 12. 인계 시 핵심 연결 지점

후단 AI 담당자는 다음 두 출력만 우선 확인하면 됨.

```text
1. child_analysis_text
   → Abuse / Subtype / XAI

2. transcript
   → Summary / Grounding / Evidence
```

`stt_data`의 `SPEAKER_0`, `SPEAKER_1`을 직접 후단 AI에 사용하는 것보다
역할 변환이 완료된 `transcript`를 사용하는 것을 권장

---

## 13. 현재 상태 요약

```text
Audio Upload                         완료
Deepgram Korean STT                 완료
Deepgram Speaker Diarization        완료
STT Post-processing                 완료
Selective Whisper large-v3 Fallback 완료
Runtime Speaker Role Mapping        완료
CHILD Text Extraction               완료
Team Transcript Conversion          완료
FastAPI Integration                 완료
30-file Regression                  완료
```

현재 단계에서 STT 전처리 파이프라인의 핵심 구현 및
후단 AI 인계를 위한 출력 contract까지 연결된 상태.