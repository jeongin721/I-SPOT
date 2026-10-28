# [제안] 구간별 음성 참고 표시(voice_marks) 저장 · 조회

> `02_ARCHITECTURE.md` §8 Contract 변경 규칙과 `05_RULES.md` §5 에 따른 제안서입니다.
> 계산 모듈(`stt/voice_marks.py`)은 같은 PR 에 있고, **저장 · 조회 구조**가 이 제안의 대상입니다.
> 저장 방식 · 재분석 · 기준값 읽는 방식은 **2026-10-28 에 Backend(최민규 님)와 사전에 맞췄습니다(§7-0).**
> 같은 날 Backend 가 **조회 API 이름 · 응답 모양 · 행이 없을 때와 실패 때의 처리 · 행 쌓기**를 정했고, 이 문서에 반영했습니다(§7-0, §7-2).
> ffmpeg 는 시연 뒤에 정합니다. Frontend · 팀장님 · AI 질문은 아직 답이 없습니다(§8).
>
> 작성: 정담원 · 2026-10-28

대상 — `audio_features` 표의 새 행(`extractor = "stt.voice_marks"`), 새 조회 API `GET /api/v1/sessions/{session_id}/voice-marks`

> **모든 성능 숫자는 합성 음성으로 낸 것이며 실제 아동 음성으로 검증하지 않았습니다**(`05_RULES.md` §4).
> 이 표시는 상담사가 **다시 들어 볼 구간**을 알려 주는 참고 정보이며, 학대나 위험을 판정하지 않습니다.

---

## 1. 변경 이유

### 1-1. 화면의 '목소리 신호' 칸에 서버가 줄 값이 없습니다

STT 검수 화면에 '목소리 신호' 칸은 자리만 있고(`counselor-web/src/data/screens/sttReview.ts` 14행과 378행에 '목소리 신호 준비 중', `SttReview.jsx` 347행에 칸), 서버가 그 칸을 채울 값을 주지 않습니다.
상담사가 아동의 떨림 · 웅얼거림 · 작게 말하는 구간을 **구간 단위로 다시 들어 보려면** 구간별 값을 저장하고 조회하는 길이 필요합니다.

### 1-2. 기존 음성 지표는 화자별 · 회차 단위라서 구간에 붙일 수 없습니다

`audio_features` 표(`backend/app/models/audio_feature.py`, `features` JSON)는 있지만 쓰는 코드가 아직 없고,
기존 `ispot_audio_features.py` 가 만드는 값은 화자별 음높이 · 에너지 · 말 속도 · 쉼 · 응답 지연 같은 **회차 · 화자 단위** 집계입니다.
화면에 구간별 표시를 붙이려면 `segment_id` 와 연결된 **구간 단위** 결과가 따로 필요합니다.

### 1-3. 이 제안이 하지 않는 것

- 학대 여부나 위험도를 판정하지 않습니다. 0~1 점수나 "위험도" 같은 값을 만들지 않습니다(`05_RULES.md` §1).
- AI 분석 입력과 위험 신호 계산(`PROPOSAL_risk_fields.md`)에는 쓰지 않습니다. 쓸지는 별도 안건입니다(§5).
- 근거를 줄 수 없으면 억지로 만들지 않습니다. 분석하지 못한 구간은 `UNDETERMINED` 와 이유로 돌려줍니다(`05_RULES.md` §3).

### 1-4. 먼저 알려 드릴 한계 (합성 음성 기준)

| 항목 | 값 |
| --- | --- |
| 효과 없는 음성에서 하나 이상 표시가 붙은 아동 구간 | 55/555 (약 10%). 조건별 6.4~13.0% |
| 지표별 오표시 | 떨림 3.3%, 웅얼거림 2.3%, 작은 소리 4.9% |
| 효과 줄 중 표시된 비율(STT 구간이 매칭된 줄) | 떨림 20/75, 웅얼거림 9/15, 작은 소리 9/11 |
| 잡음이 가장 큰 조건 | 아동 구간 145개 중 53~54개만 분석됨 |

- 떨림은 놓치는 경우가 많습니다. 한 녹음 안의 상대 비교라서 상담 내내 떨리는 아동은 표시되지 않을 수 있습니다.
- 표시 기준은 합성 음성으로 정한 잠정값이고, 작은 소리 기준(-2.5)은 같은 데이터로 골랐습니다.
- 표시가 없다고 문제가 없다는 뜻이 아니고, 표시가 있다고 문제가 있다는 뜻도 아닙니다.
- 자세한 내용은 `stt/voice_marks.md` §7 에 있습니다.

---

## 2. 영향 Contract

- `I-SPOT_DOCS/docs/02_ARCHITECTURE.md` §5 API 기준 — 핵심 Resource 에 `/sessions/{session_id}/voice-marks` 를 추가합니다. `audio_features` 표에는 추출기마다 행이 섞일 수 있어(기존 `ispot_audio_features` 행이 나중에 붙을 수 있음) 추출기마다 조회 창구를 따로 둡니다(Backend 결정).
- `backend/docs/API_CONTRACT.md` — 새 조회 API 절을 추가합니다(절 번호는 리뷰에서 정합니다).
- `backend/app/models/audio_feature.py` · `backend/app/schemas/` 의 `audio_feature` 스키마 — **표 구조 변경 없음.** `features` JSON 에 새 모양이 들어갑니다.
- 변경 **없음**: `02_ARCHITECTURE.md` §6 STT Contract(구간 6칸), §7 AI Output Contract, 기존 `ispot_audio_features` 행.

`schema_version` 은 새 모양 자체에 `"1.0"` 을 붙입니다(`audio_features.schema_version` 열). AI Output Contract 의 `schema_version` 은 건드리지 않습니다.

---

## 3. Backend 영향

**DB 마이그레이션은 필요 없습니다.** `audio_features` 는 `extractor` · `schema_version` · `features`(JSON) 를 이미 갖고 있고 유일 제약이 없어서, 새 행을 넣을 수 있습니다.

- STT 저장 직후 백그라운드 작업에서 `analyze_voice_marks(audio_path, segments)` 를 불러 결과를 새 행으로 저장합니다.
- 행에 `audio_file_id` · `transcript_id` · `transcript_version` 을 채우고, 한 오디오에 이 `extractor` 의 행이 여러 개일 수 있게 합니다(§7-0).
- 조회 API 를 추가합니다(§7-2). 상담사 화면의 구간 재생을 위한 음성 파일 API(`GET /sessions/{id}/audio/file`, Range 지원)는 Backend 가 따로 PR 로 올립니다.
- 의존성(scipy · librosa · numba · soundfile)을 `backend/requirements-stt.txt` 에 넣고, Docker 이미지에 `NUMBA_CACHE_DIR` 를 지정하고, 서버 시작 때 `warm_up()` 을 부릅니다.
- 처리 시간은 측정한 곳마다 다릅니다(담이 PC 오디오 1분당 약 1.3~1.6초, Backend PC 약 5초, 아동 구간 비율에 따라 다름). Backend 쪽 시간 제한(10분)을 넘기거나 예외가 나면 행을 남기지 않는 것이 아니라 `status: UNDETERMINED` · `reason: ANALYSIS_ERROR` 로 구간 전부를 채운 행을 저장하고, 회차 상태에는 영향을 주지 않습니다(Backend 결정, §7-0).
- m4a · mp4 · webm 은 ffmpeg 가 없으면 `DECODE_FAILED` 입니다. **이번에는 ffmpeg 를 넣지 않습니다.** 시연은 wav 업로드로 하고, 브라우저 녹음(webm)은 '분석 불가(형식)' 으로 보입니다. 다만 상담사 웹의 녹음 기능이 webm 이라 실제 사용에서는 녹음 회차 전부가 분석 불가가 됩니다. 시연 뒤에 ① 이미지에 ffmpeg 를 넣고 읽기 대체 경로를 두는 방법과 ② 업로드 때 Backend 가 wav 로 바꿔 저장하는 방법 중 하나를 팀에서 정합니다(§8).
- mp3 는 값이 조금 다를 수 있어 다음 PR 에서 읽는 방식을 고칩니다.

---

## 4. Frontend 영향

- STT 검수 화면 '목소리 신호' 칸에 구간별 표시를 붙입니다. `flag` 가 `true` 인 지표를 **아이콘 + 글자**로 보여 줍니다(색만으로 구분하지 않음, `03_UI_UX.md` §5).
- 표시 기준값은 코드에 적지 않고 응답의 `thresholds` 를 읽습니다. 기준값이 바뀌어도 화면은 고치지 않습니다.
- `UNDETERMINED` 는 "탐지 없음"(`ANALYZED` 이면서 모든 `flag` 가 `false`)과 다르게 보여 주고, `reason` 은 사람 말로 바꿔 보여 줍니다(예: 구간이 너무 짧음).
- 권장 문구: "음성 참고 표시", "다시 들어 볼 구간", "상담사 검토 필요", "분석 불가(이유)". 쓰지 않는 문구: "학대 확정", "위험 확정", "AI 판정", "자동 결정".
- 조회가 `{"data": null}` 이면 '분석 전' 으로 보여 줍니다. 분석 실패 · 시간 초과는 `UNDETERMINED` 행이 오므로 '분석 불가(이유)' 로 보여 주고, 두 경우를 구분합니다.
- 응답의 `transcript_version` 으로 지금 보는 전사본과 결과가 맞는지 알 수 있습니다. 상담사가 시각을 고친 구간은 결과 안의 원래 `start_ms` · `end_ms` 로 알아챕니다.
- 구간 재생(다시 듣기)과 함께 쓰는 것을 전제로 합니다.
- 한계(§1-4)를 화면 안내문에 그대로 옮깁니다.

---

## 5. AI 영향

**없음.** AI Output Contract(agent · ai)는 변경하지 않고, 이 표시를 AI 분석 입력이나 위험 필드(`risk_utterances` · `abuse_signals` · `risk_factors`)에 쓰지 않습니다.
분석 입력에 넣는 것은 AI(이경진 님) 모듈 변경이 필요한 별도 안건이며, 이 제안의 범위 밖입니다.

---

## 6. Test 영향

- `tests/test_voice_marks.py` 22개: 합성 음성 · 표본율 · 구간 입력 오류 · 짧은 구간 · 아동 구간 부족 · mp3 읽기 · `warm_up()` 포함. 사용자 환경과 Backend 환경에서 모두 통과했습니다.
- 값 일치: 합성 믹스 50개와 저장된 STT 구간에서 이전 실험 코드와 1,053행 모두 최대 절대차 0.0.
- Backend 통합 시험 제안: 하준 s1 효과 파일(떨림 3곳 · 웅얼거림 1곳 · 작게 말하기 1곳)을 올려 구간별 결과가 저장 · 조회되는지 확인합니다. 정답 시각은 떨림 90.4~94.8초 / 145.1~149.7초 / 203.4~208.2초, 웅얼거림 117.5~125.4초, 작게 말하기 52.9~54.6초입니다. 저장해 둔 STT 구간으로는 떨림 3곳 중 1곳이 표시되고, 서버의 실제 STT 구간으로는 달라질 수 있습니다.
- Backend 쪽 시험(저장 · 조회 · 실패 격리 · 확정 때 재분석)은 Backend 연결 PR 에서 추가합니다.
- CI 는 `stt/` 와 루트 `tests/` 를 실행하지 않습니다. 추가할지는 §8 에서 묻습니다.

---

## 7. 변경안

### 7-0. 사전 합의 (2026-10-28, 정담원 · 최민규)

| 항목 | 내용 |
| --- | --- |
| 저장 | `audio_features` 새 행. `extractor = "stt.voice_marks"`, `schema_version = "1.0"`, `features` = 함수가 돌려주는 dict 전체. 기존 행과 transcript 의 `segments` 는 건드리지 않는다 |
| 행 식별 | 행마다 `audio_file_id` · `transcript_id` · `transcript_version` 이 있다. 한 오디오에 이 `extractor` 행이 여러 개일 수 있다 |
| 다시 STT 할 때 | 행을 **쌓는다**(교체하지 않음). 조회는 가장 최근 행을 준다. 확정 때 재분석도 새 행이다 |
| 돌리는 시점 | STT 직후 1회. 이때 화자 역할이 정해지지 않아 아동 구간이 없으면 결과 전체가 `TOO_FEW_CHILD_SEGMENTS` 가 된다. 그래서 상담사가 원문을 확정할 때 확정본의 아동 구간(`segment_id` · `speaker` · `start_ms` · `end_ms`)이 STT 직후와 다르면 한 번 더 돌려 새 행으로 저장한다. 화면은 가장 최근 행을 쓴다. 함수 쪽 변경은 없다 |
| 기준값 | 화면은 응답의 `thresholds` 와 `flag` 만 쓰고 코드에 숫자를 적지 않는다 |
| 시간 제한 · 실패 | Backend 쪽에서 10분. 넘기거나 예외가 나면 `status: UNDETERMINED` · `reason: ANALYSIS_ERROR` 로 구간 전부를 채운 행을 저장한다(그래야 화면이 '분석 전' 과 '분석 불가(이유)' 를 구분한다). 회차 상태에는 영향이 없다. 60분을 넘는 음성은 함수가 `AUDIO_TOO_LONG` 으로 돌려준다 |
| 조회 창구 | `GET /api/v1/sessions/{session_id}/voice-marks`. 행이 없으면(아직 계산 전) `200` 에 `{"data": null}` 이다(계산 전은 정상 상태라 `404` 를 쓰지 않는다) |

### 7-1. `features` JSON (행 하나)

```jsonc
{
  "schema_version": "1.0",
  "analyzer": "stt.voice_marks",
  "analyzer_version": "0.1.0",
  "status": "ANALYZED",                 // ANALYZED | UNDETERMINED
  "reason": null,                       // UNDETERMINED 일 때 이유 코드
  "reference": { "child_segments_total": 30, "child_segments_used": 28, "min_required": 8,
                 "note": "z 는 이 녹음 안의 아동 구간끼리 비교한 상대값입니다." },
  "thresholds": { "tremor_z_above": 1.6066, "mumble_z_below": -1.619, "soft_z_below": -2.5,
                  "basis": "합성 음성 기준 잠정값. 실제 아동 음성으로 검증되지 않음." },
  "segments": [
    { "segment_id": "seg_003", "speaker": "CHILD", "start_ms": 12000, "end_ms": 15200,
      "status": "ANALYZED", "reason": null,
      "tremor": { "value": 21.4, "unit": "cent", "z": 0.3,  "flag": false },
      "mumble": { "value": 1850.0, "unit": "Hz", "z": -1.9, "flag": true },
      "soft":   { "value": -38.2, "unit": "LUFS", "z": -0.2, "flag": false },
      "flag_any": true },
    { "segment_id": "seg_001", "speaker": "COUNSELOR", "start_ms": 0, "end_ms": 4000,
      "status": "UNDETERMINED", "reason": "NOT_CHILD_SEGMENT",
      "tremor": null, "mumble": null, "soft": null, "flag_any": null }
  ]
}
```

필드 규칙(전체는 `stt/voice_marks.md`):

| 규칙 | 내용 |
| --- | --- |
| `segment_id` | 입력의 `segment_id` · `speaker` · `start_ms` · `end_ms` 를 그대로 돌려주고 순서도 같다. 구간별 결과는 transcript 의 `segments` 안에 넣지 않는다(§2) |
| 대상 | `speaker` 가 정확히 `"CHILD"` 인 구간만 분석한다 |
| `status` | 최상위 · 구간 모두 `ANALYZED` 또는 `UNDETERMINED` 두 가지뿐이다. "탐지 없음"은 `ANALYZED` 이면서 모든 `flag` 가 `false` 인 경우 |
| 지표 | `value`(단위 포함) · `z` · `flag`. 0~1 점수나 "위험도"는 없다 |
| `flag` | 엄격한 부등호. 떨림 `z > tremor_z_above`, 웅얼거림 `z < mumble_z_below`, 작은 소리 `z < soft_z_below` |
| `reason` | `TOO_SHORT` `NO_VOICED_FRAMES` `NOT_CHILD_SEGMENT` `TOO_FEW_CHILD_SEGMENTS` `NO_REFERENCE` `INVALID_TIME_RANGE` `DECODE_FAILED` `AUDIO_TOO_LONG` `ANALYSIS_ERROR` |
| 값 | NaN 대신 `null`. 값은 모두 영문 · 대문자 상태 · snake_case 키이다 |

### 7-2. 조회 API (초안)

`02_ARCHITECTURE.md` §5 규칙(Base `/api/v1`, 성공은 `{"data": ...}`)을 따릅니다. 이름과 응답 모양은 Backend 가 정했습니다(2026-10-28).

```text
GET /api/v1/sessions/{session_id}/voice-marks
```

```jsonc
{
  "data": {
    "id": "...",
    "audio_file_id": "...",
    "transcript_id": "...",
    "transcript_version": 2,
    "extractor": "stt.voice_marks",
    "schema_version": "1.0",
    "created_at": "2026-10-28T10:00:00Z",
    "result": { /* §7-1 의 JSON 그대로 */ }
  }
}
```

- 가장 최근 행 하나를 돌려줍니다(재분석으로 행이 여러 개일 수 있음, §7-0).
- 행이 없으면 `200` 에 `{"data": null}` 입니다. 시간 초과나 실패는 행이 없는 것이 아니라 `UNDETERMINED` · `ANALYSIS_ERROR` 행입니다(§7-0).
- 결과(`result`)는 함수가 돌려준 dict 를 그대로 담고, 기존 규칙대로 `data` 로 감쌉니다.

### 7-3. 고려했지만 택하지 않은 안

| 안 | 이유 |
| --- | --- |
| 기존 `ispot_audio_features` 행의 `features` 에 합치기 | 기존 구조가 `{speaker: {...}}` 라 구간 배열과 섞이고, 읽는 쪽이 깨질 수 있음 |
| transcript 의 `segments` 에 칸 추가 | STT Contract 6칸(§6)을 바꾸는 일이라 영향이 크고, 구간별 값은 별도 행으로 충분함 |
| AI 분석 입력에 넣기 | AI 모듈 변경이 필요하고 근거 검증이 없어서 이번 범위 밖(§5) |

---

## 8. 확인 부탁드릴 사항

> **답변 기록 · 2026-10-28** — Backend(최민규 님)가 이 제안의 처음 질문 셋에 답했고 §7-0 · §7-2 에 반영했습니다:
> 행이 없을 때 `200` + `{"data": null}`(실패 · 시간 초과는 `UNDETERMINED` 행), 다시 STT 하면 행을 쌓고 가장 최근 행을 조회, 조회 창구 이름 `voice-marks`.

**팀 전체 (시연 뒤 결정)**

1. 브라우저 녹음(webm)을 분석하려면 ffmpeg 가 필요합니다. 시연 뒤에 ① 이미지에 ffmpeg 를 넣고 읽기 대체 경로를 두는 방법, ② 업로드 때 Backend 가 wav 로 바꿔 저장하는 방법 중 하나를 정해 주세요.

**다솔 님**

2. '목소리 신호' 칸에 구간별 아이콘 + 글자로 보여 주는 것으로 괜찮은지요? 떨림은 놓치는 경우가 많아서(§1-4) 가장 약하게 보일지, 뺄지도 같이 봐 주세요.
3. 권장 문구(§4)를 화면에 쓰는 것이 괜찮은지 봐 주세요.

**팀장님**

4. 떨림 표시 기준을 어디에 둘지 정해 주세요. 지금은 오표시를 약 3% 로 묶은 상태에서 떨림이 20/75 입니다. 오표시를 10% 까지 받으면 약 55%, 20% 까지 받으면 약 82% 를 잡았습니다(합성 음성 · 턴 단위, 표본이 작음). 기준값은 `thresholds` 로 바꿀 수 있어 코드 수정은 필요 없습니다. 상담사가 보는 후보 구간이 그만큼 늘어납니다.
5. 실제 상담사가 "떨린다 · 웅얼거린다"고 표시한 정답 데이터를 구할 수 있을까요? 없으면 실제 음성 성능은 알 수 없습니다.

**이경진 님**

6. 이 표시를 AI 분석 입력과 위험 필드에 쓰지 않는 것(§5)으로 두어도 되는지 확인 부탁드립니다.

**공통**

7. CI 가 `stt/` 와 루트 `tests/` 를 실행하지 않습니다. 추가할지 정해 주세요.
