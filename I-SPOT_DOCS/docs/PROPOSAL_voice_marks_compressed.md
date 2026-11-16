# [제안] voice_marks — 웹 녹음 창 · 파일 선택 업로드의 압축 음성(m4a · mp4 · webm) 읽기

> `02_ARCHITECTURE.md` §8 Contract 변경 규칙과 `05_RULES.md` §5 에 따른 제안서입니다.
> 바꾸는 곳은 계산 모듈(`stt/voice_marks.py`)과 이미지 패키지(`backend/requirements-stt.txt`)이고, **API 응답 모양 · 이유 값 · Backend · Frontend 코드는 바꾸지 않습니다.**
> 방식은 팀 결정 A안(voice_marks 안에서 PyAV 로 읽기)입니다.
>
> 작성: 정담원 · 2026-11-11

대상 — `stt/voice_marks.py`(읽는 부분), `backend/requirements-stt.txt`(`av==19.0.2` 추가), 시험 `tests/test_voice_marks.py`, 문서 `stt/voice_marks.md` · `backend/docs/API_CONTRACT.md` 16절 한 항목

> **모든 수치는 합성 음성과 시험 안에서 만든 신호로 낸 것이며, 실제 휴대폰 녹음 · 실제 아동 음성으로 확인하지 않았습니다**(`05_RULES.md` §4).
> 이 표시는 상담사가 다시 들어 볼 구간을 알려 주는 참고 정보이며, 학대나 위험을 판정하지 않습니다.

---

## 1. 변경 이유

### 1-1. 웹 녹음 창 · 파일 선택으로 올린 m4a · webm 회차는 목소리 신호가 전부 '분석 불가(DECODE_FAILED)' 입니다

- `stt/voice_marks.py` 는 음성을 `soundfile`(libsndfile)로만 엽니다(`_analyze` 의 `sf.info` · `sf.SoundFile`). libsndfile 은 m4a · mp4(AAC) · webm 을 읽지 못해, 녹음 전체가 `DECODE_FAILED` 가 됩니다.
- Backend 는 업로드 원본 경로를 그대로 넘깁니다(`backend/app/services/voice_marks_service.py:205-209`, `storage.resolve_stored_path(audio.path)`). 저장 때 변환도 없습니다(`backend/app/core/storage.py` `save_audio_chunks`).
- 녹음이 올라오는 경로는 세 가지입니다(데모 서버 브랜치 `deploy/case-tabs-1104` 끝 커밋 `3802817` 기준. **main 에 같은 변경이 들어갔는지는 확인하지 않았습니다**).
  - **상담사 앱(폰) 녹음**(`counselor-web/src/pages/AppRecord.jsx` → `src/data/useRecorder.ts`): 11/11 커밋 `3b43846` · `39662f1` 부터 MediaRecorder 를 쓰지 않고
    **항상 MP3(16 kHz 모노 32 kbps, `audio/mpeg` · `.mp3`)** 로 만들어 올립니다. MP3 는 지금 코드(soundfile)로도 읽히므로 **이 경로는 이 PR 의 대상이 아닙니다.**
  - **웹 녹음 창**(`src/components/RecordDialog.jsx` → `src/data/useAudioRecorder.ts`): MediaRecorder 의 **브라우저 기본 형식**(webm · m4a 등)입니다.
  - **파일 선택 업로드**(`src/pages/UploadModal.jsx` · `src/pages/AppUpload.jsx`): **고른 파일 그대로**입니다(폰 녹음 앱의 m4a 등).
- 그래서 **웹 녹음 창과 파일 선택 업로드로 m4a · webm 이 여전히 올라오고**, 그중 STT 까지 끝난 회차(m4a 등, §1-3)는 voice_marks 가 `DECODE_FAILED` 로 저장됩니다.
  이 PR 이 필요한 경우는 이 두 경로입니다. 문서에도 이미 "ffmpeg 가 없어 DECODE_FAILED, 시연 뒤 팀 결정"으로 적혀 있었습니다.

### 1-2. PyAV 로 읽으면 같은 계산이 됩니다 (작업 90 · 92, 합성 음성)

- PyAV(`av` 19.0.2) wheel 은 FFmpeg 라이브러리를 품고 있어 apt 설치 없이 m4a · webm 을 읽습니다(Windows wheel 에서 확인).
- 합성 음성(physical_hajun_s1 V0, 약 5분, 아동 30구간)을 AAC 128 kbps m4a · Opus 64 kbps webm 으로 바꿔 이 PR 의 모듈에 바로 넣었을 때, 구간 상태는 wav 와 모두 같았습니다(아래 1-4 의 한계 참고).

### 1-3. 이 제안이 하지 않는 것

- **새 이유 값 · 응답 필드 · DB 칸은 만들지 않습니다.** `DECODE_FAILED` 의 뜻("이 음성을 읽을 수 없음")도 그대로입니다. 읽을 수 있는 형식이 늘어날 뿐입니다.
- **STT 허용 목록은 이 PR 에서 고치지 않습니다.** `stt/ispot_stt.py:44` `SUPPORTED_AUDIO_EXTENSIONS = {.wav, .mp3, .m4a, .aac, .flac}` 에 .webm · .ogg · .mp4 가 없어, 그런 업로드는 STT 단계(`_normalize_audio_path`)에서 `InvalidAudioError` → 회차 `STT_FAILED` 가 되고 voice_marks 까지 오지 않습니다. 이것은 **별도 PR** 로 다룹니다(§8).
- 업로드 · 저장 때 wav 로 바꾸는 방식(B안)은 택하지 않았습니다(§7-3).

### 1-4. 먼저 알려 드릴 한계 (합성 음성 기준)

- **압축 손실로 기준값 근처 구간의 표시가 바뀔 수 있습니다.** 위 5분 합성 음성에서 m4a 는 1구간(웅얼거림 z −1.513 → −1.663, 기준 −1.619)의 표시가 바뀌었고 webm 은 바뀐 구간이 없었습니다. mp3 에서도 같은 종류의 차이가 이미 알려져 있습니다(`stt/voice_marks.md` 7절).
- **인코더 지연을 알리지 않는 m4a 는 약 23 ms 늦게 읽힙니다.** 고정값 보정은 넣지 않았습니다(§7-1). 지연을 알리는 파일(FFmpeg CLI 로 만든 m4a, Opus webm)은 디코더가 잘라 시각이 wav 와 0 샘플 차이로 맞았습니다.
- 낮은 비트레이트 AAC(32 kbps)는 고음이 깎여 웅얼거림 값(스펙트럴 중심)이 시험 신호에서 최대 약 20% 낮아졌습니다(같은 녹음 안 비교라 표시는 바뀌지 않았습니다).

## 2. 영향 Contract

| 항목 | 바뀌나 | 내용 |
|---|---|---|
| `GET /api/v1/sessions/{id}/voice-marks` 응답 모양 | 아니요 | 같은 `features` dict(`schema_version` "1.0", `analyzer_version` "0.1.0" 그대로) |
| `reason` 값 목록 | 아니요 | `DECODE_FAILED` · `AUDIO_TOO_LONG` 등 그대로. 새 값 없음 |
| wav · flac · ogg · mp3 결과 | 아니요 | soundfile 경로 코드는 바꾸지 않았고, 수정 전후 결과가 키 · 값까지 같음(§6, 50개 녹음) |
| m4a · mp4 · webm 결과 | **예** | `DECODE_FAILED` → 계산된 결과(`ANALYZED` 등) |
| 문서 | 예 | `API_CONTRACT.md` 16절의 ffmpeg 문구를 실제 동작으로 고침, `stt/voice_marks.md` 6 · 7절 |

`analyzer_version` 을 올리지 않은 이유: wav 결과가 한 글자도 바뀌지 않아야 한다는 조건 때문입니다. 압축 음성 결과를 구분해야 하면 저장 행의 `audio_file_id` → 파일 형식으로 알 수 있습니다. 버전을 올릴지는 §9 에서 여쭙니다.

## 3. Backend 영향

- **코드 변경 없음.** `voice_marks_service.analyze_for_transcript` 가 넘기는 경로 · 구간 · 저장 방식 그대로입니다.
- 이미지: `backend/requirements-stt.txt` 에 `av==19.0.2` 한 줄(`WITH_STT=1` 이미지에만 들어감). apt 변경 없음. PyAV wheel 크기만큼 이미지가 커집니다(FFmpeg 라이브러리 포함).
- 시간 · 메모리(§6-3): 30분 m4a 를 읽는 동안 파일 전체를 배열로 들지 않고 아동 구간 부분만 남깁니다.
- `VOICE_MARKS_TIMEOUT_SECONDS`(600초)는 그대로 둡니다.
- **`deploy/case-tabs-1104`(발표용 데모 서버)에도 같은 변경이 필요합니다.** 이 브랜치는 main 보다 73커밋 앞서고 190커밋 뒤라 main 에 머지해도 데모 서버에는 들어가지 않습니다. `stt/voice_marks.py` · `requirements-stt.txt` 는 두 브랜치에서 같으므로 같은 변경을 그대로 얹을 수 있고, 이미지를 `WITH_STT=1` 로 다시 만들어야 PyAV 가 들어갑니다.

## 4. Frontend 영향

- **코드 변경 없음.** 웹 녹음 창으로 녹음했거나 파일 선택으로 올린 m4a 회차에서 '분석 불가(DECODE_FAILED)' 대신 구간별 표시가 나옵니다.
- 상담사 앱(폰) 녹음은 데모 서버 브랜치에서 이미 MP3 로 올라오므로(§1-1) 이 PR 로 달라지지 않습니다.
- webm · ogg 로 녹음되는 브라우저(Firefox 등)는 STT 단계에서 실패하므로(§1-3) 이 PR 만으로는 달라지지 않습니다.

## 5. AI 영향

- 없음. voice_marks 결과는 AI 분석 입력이 아닙니다.

## 6. Test 영향

### 6-1. `tests/test_voice_marks.py` (기존 22개 + 새 12개, 모두 통과)

- 기존 22개는 그대로 통과합니다.
- 새 시험(합성 신호만 사용, PyAV 가 없으면 건너뜀)
  - 기준에서 여유 있게 만든 합성 녹음(아동 12구간, 떨림 · 웅얼거림 · 작은 소리가 뚜렷한 구간 각 1개)을 PyAV 로 4가지로 만들어 wav 와 비교: (가) m4a AAC 128 kbps, (나) m4a AAC 32 kbps 조각형 mp4(MediaRecorder 비슷), (다) webm Opus 64 kbps, (라) mp4 AAC 96 kbps.
    - 구간 상태 · 이유 같음, 떨림 ≤ 2 cent, 작은 소리 ≤ 1 LUFS, 웅얼거림 ≤ 5%(32 kbps 는 30%), 기준에서 z 1 이상 떨어진 표시는 같음, 뚜렷한 구간 3개는 표시됨
  - soundfile 로 열리는 wav 에서는 PyAV 를 부르지 않음
  - PyAV import 실패를 흉내 내면 `DECODE_FAILED`(예외 없음)
  - 깨진 파일(moov 없는 mp4 앞부분, 의미 없는 바이트, 빈 파일)은 `DECODE_FAILED`(예외 없음)
  - 헤더에 길이가 없는 파일(흉내)도 풀면서 잰 시각으로 `AUDIO_TOO_LONG`(짧은 제한값), 헤더에 길이가 있으면 먼저 `AUDIO_TOO_LONG`
  - 끝 시각이 음성 길이를 크게 넘는 구간은 wav 와 같이 길이에 맞춰 잘라 계산하고, 음성 뒤에서 시작하는 구간은 `INVALID_TIME_RANGE`(큰 버퍼를 잡지 않음)

### 6-2. 결과가 바뀌지 않는지 (flow79 입력 50개)

- 작업 79 의 합성 녹음 50개(5편 × V0 · VF × 깨끗한 음성 · 잡음 4조건, 44.1 kHz wav)와 STT 구간으로 수정 전(main `ff100028c9`) · 후 모듈을 돌린 결과:
  **50개 모두 결과가 완전히 같았습니다(50/50).** 결과 dict 전체(`==`)와 키를 정렬한 JSON 문자열을 함께 비교했고, 다른 키 · 값은 하나도 없었습니다.
  - 비교한 구간 2,930개(그중 계산된 아동 구간 1,106개). 녹음 48개 `ANALYZED`, 2개 `UNDETERMINED` / `TOO_FEW_CHILD_SEGMENTS`(가장 시끄러운 N5 조건의 emotional_gunwoo_s1, V0 · VF) — 두 모듈이 같은 결과
  - 걸린 시간 합: 수정 전 436.5초, 수정 후 430.7초(같은 PC, 한 번씩)

### 6-3. 30분 m4a (합성 음성, Windows PC 1대)

- 파일: 같은 합성 음성(약 5분)을 6번 이어 1,800초로 자른 AAC 128 kbps m4a. 구간: 작업 79 의 STT 구간을 이어 붙여 350구간(아동 175).
- 결과: `ANALYZED`, 아동 151구간 계산.

| 측정 | 시간 | 최대 메모리 증가 (warm_up 뒤 기준) |
|---|---|---|
| 이 PR 의 전체 계산 | 46.2초 | +75.7 MB |
| 그중 이어 읽기 · 16 kHz 변환 · 구간 남기기만 | 4.2~4.4초 | +41 MB (남긴 구간 버퍼 33.2 MB) |
| (참고, 작업 90) 파일 전체를 한 float32 배열로 모으기 | 7.9~8.8초 | +362 MB |

- 첫 줄은 목소리 신호 분석 전체(디코딩 + 특징 계산 + 결과), 둘째 줄은 디코딩만 잰 값입니다. 같은 조건의 30분 wav 기준선은 재지 않았습니다(기준선 없음).
- 서버(2 vCPU)에서의 시간은 재지 않았습니다. 계산 시간의 대부분은 구간별 특징 계산(librosa pyin)일 것으로 봅니다(따로 재지는 않음).

### 6-4. Linux

- **미확인.** 작성 PC 에 Docker CLI(29.7.2)는 있지만 Docker 엔진이 켜져 있지 않아 `python:3.12-slim` 컨테이너 확인을 하지 못했습니다.
  머지 전에 다음으로 확인을 부탁드립니다(이미지 안 PyAV import 와 m4a 디코드):
  `docker run --rm python:3.12-slim sh -c "pip install -q av==19.0.2 && python -c 'import av; print(av.__version__, av.library_versions)'"`
- PyPI 에는 `av` 19.0.2 의 manylinux wheel(FFmpeg 포함)이 있는 것으로 알지만, 이번에 Linux 에서 내려받아 보지는 않았습니다.

## 7. 권장 변경안

### 7-1. 읽는 순서와 방식 (`stt/voice_marks.py`)

1. 지금처럼 `soundfile.info` 로 연다. **열리면 지금 코드 그대로**(구간마다 seek · 부분 읽기 · `resample_poly`).
2. `soundfile.info` 가 실패할 때만 PyAV 로 연다(`_analyze_pyav`). `import av` 실패 · 열기 실패 · 오디오 스트림 없음 · 디코드 예외는 모두 `DECODE_FAILED`.
3. PyAV 는 **처음부터 이어 읽기**(seek 없음). 디코더 프레임마다 채널을 유지한 채 16 kHz float32 로 바꾸고 채널 평균으로 모노를 만든 뒤, **계산할 아동 구간(1초 이상, 시각이 올바른 CHILD 구간)의 샘플만** 구간별 버퍼에 남깁니다(`_WindowCollector`). 파일 전체 배열은 만들지 않습니다.
4. 시각: 첫 프레임 시각(`pts · time_base`)을 스트림 `start_time` 기준으로 놓고 이어 붙입니다. 프레임 시각이 이어 붙인 위치보다 10 ms 넘게 앞서면 사이를 무음으로 둡니다. 0 보다 앞선 샘플은 버립니다. **고정값(23 ms 등) 보정은 넣지 않습니다.**
5. 길이: 헤더(스트림 · 컨테이너) 길이가 60분을 넘으면 읽기 전에 `AUDIO_TOO_LONG`. 헤더에 길이가 없으면 풀면서 잰 시각이 60분을 넘는 순간 멈추고 `AUDIO_TOO_LONG`.
6. 구간 계산 · z · 표시 · 결과 만들기는 soundfile 경로와 같은 함수를 씁니다(`_summarize`, 구간 거르는 순서와 이유 값도 같음).

### 7-2. 패키지

- `backend/requirements-stt.txt`: `av==19.0.2`(작업 90 에서 쓴 버전, FFmpeg 9.0.2 포함).

### 7-3. 고려했지만 택하지 않은 안

| 안 | 내용 | 택하지 않은 이유 |
|---|---|---|
| B안 | 업로드 · 저장 때 wav 로 바꾸기(Backend) | Backend · 저장 공간 · STT 입력이 같이 바뀜. 팀 결정은 A안 |
| apt 로 ffmpeg 설치 | 이미지에 ffmpeg 를 깔고 soundfile 대신 ffmpeg 프로세스로 읽기 | 이미지 apt 변경 · 프로세스 호출 관리가 필요. PyAV wheel 로 apt 없이 됨 |
| PyAV 로 파일 전체를 한 배열로 읽기 | 구현이 간단 | 30분 m4a 에서 메모리가 약 +362 MB(작업 90). 구간만 남기면 크게 줄어듦(§6-3) |
| 구간마다 seek | soundfile 경로와 같은 모양 | 압축 음성의 seek 는 키프레임 · 인코더 지연 때문에 시각이 흔들릴 수 있음. 이어 읽기는 시각이 디코더 기준으로 한 번에 정해짐 |
| AAC 23 ms 고정 보정 | 지연을 알리지 않는 m4a 를 맞춤 | 지연을 알리는 파일에서는 거꾸로 23 ms 어긋남. 파일이 알리는 대로 따름 |

## 8. 별도 PR 로 다룰 것

- **STT 허용 목록**: `stt/ispot_stt.py:44` 에 `.webm` · `.ogg` · `.mp4` 가 없어 Backend 는 받지만(`backend/app/core/config.py` `AUDIO_ALLOWED_EXTENSIONS`) STT 에서 `STT_FAILED` 가 됩니다. STT 공급자(ElevenLabs 등)가 이 형식을 받는지 확인한 뒤 목록을 넓히는 별도 PR 이 필요합니다.
- **`deploy/case-tabs-1104` 반영**: 이 PR 이 main 에 머지된 뒤, 데모 서버 브랜치에도 같은 변경을 얹고 이미지를 다시 만들어야 합니다(§3).

## 9. 확인 부탁드릴 사항

1. (Backend · 팀장님) `analyzer_version` 을 그대로 둘지(지금), 압축 음성 지원을 알리도록 올릴지
2. (Backend) 데모 서버 이미지 재빌드 시점 — `deploy/case-tabs-1104` 반영과 함께
3. (Frontend) 폰 앱 녹음 비트레이트: 데모 서버 브랜치의 폰 앱 녹음은 MP3 32 kbps(16 kHz 모노)입니다. 32 kbps 압축이 목소리 신호 값에 주는 영향은
   AAC 로만 시험했고(웅얼거림 값이 많이 낮아졌지만 같은 녹음 안 비교라 표시는 유지, §1-4) MP3 로는 시험하지 않았습니다(§10). 그대로 두어도 되는지
4. (팀) STT 허용 목록 별도 PR 담당

## 10. 확인하지 못한 것

- 실제 기기 · 브라우저(아이폰 Safari, Android Chrome, Firefox)에서 각 경로(폰 앱 녹음, 웹 녹음 창, 파일 선택)로 실제로 올라오는 형식
- 폰 앱이 MP3 로 바뀌기 전(11/11 커밋 `3b43846` 이전)에 폰에 저장해 둔 m4a · webm 녹음이 그 형식 그대로 올라가는지
- 32 kbps MP3 가 목소리 신호 값에 주는 영향(작업 92 의 32 kbps 시험은 AAC 로만 했음)
- 폰 앱 MP3 녹음 변경이 main 에도 들어갔는지(§1-1 은 데모 서버 브랜치 끝 `3802817` 기준)
- Linux(이미지 `python:3.12-slim`)에서의 PyAV 동작(§6-4), 실제 휴대폰 녹음 · 실제 아동 음성(모든 수치는 합성 음성 기준)
