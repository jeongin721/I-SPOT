# stt/voice_marks 결과 형식 (v0.3 초안)

## 1. 무엇인가

아동 발화 구간에서 **떨림 / 웅얼거림 / 작은 소리**가 그 녹음 안에서 두드러지는 구간을 표시한다.
상담사가 해당 구간을 **다시 들어 보도록** 돕는 참고 표시이다.
학대 여부나 위험을 판정하지 않으며, 위험 신호도 아니다. 판단은 상담사가 한다.

- 신호 처리로 계산한다(모델 학습 없음). 계산 코드는 `stt/voice_marks.py` 이다.
- 표시 기준은 **합성 음성으로 정한 잠정값**이다. 실제 아동 음성으로 검증하지 않았다.

## 2. 함수

```python
from stt.voice_marks import analyze_voice_marks, warm_up

result = analyze_voice_marks(audio_path, segments)  # dict, JSON 으로 저장 가능 (NaN 없음)
```

- DB, 네트워크를 쓰지 않는 순수 함수이다.
- **예외를 던지지 않는다.** 읽을 수 없는 음성이면 모든 구간을 `UNDETERMINED` 로 돌려준다.
- `segments` 는 dict 목록이다. 각 항목: `segment_id`("seg_001"), `speaker`(COUNSELOR / CHILD / GUARDIAN / OTHER / UNKNOWN),
  `start_ms`, `end_ms`(정수, 밀리초).
- 결과의 `segments` 는 입력과 **같은 순서**이고, `segment_id` · `speaker` · `start_ms` · `end_ms` 를 **입력 그대로** 돌려준다.
- `speaker` 가 정확히 `"CHILD"` 인 구간만 분석한다. 그 밖의 값(UNKNOWN 포함)은 분석하지 않는다.
- `warm_up()` 은 서버 시작 때 한 번 부르면 첫 요청이 느려지는 것(numba 컴파일, 약 1~9초)을 피한다. 성공하면 `True`.

## 3. 출력 예시 (값은 예시)

```json
{
  "schema_version": "1.0",
  "analyzer": "stt.voice_marks",
  "analyzer_version": "0.1.0",
  "status": "ANALYZED",
  "reason": null,
  "reference": {
    "child_segments_total": 30,
    "child_segments_used": 28,
    "min_required": 8,
    "note": "z 는 이 녹음 안의 아동 구간끼리 비교한 상대값입니다."
  },
  "thresholds": {
    "tremor_z_above": 1.6066,
    "mumble_z_below": -1.619,
    "soft_z_below": -2.5,
    "basis": "합성 음성 기준 잠정값. 실제 아동 음성으로 검증되지 않음."
  },
  "segments": [
    {
      "segment_id": "seg_003", "speaker": "CHILD", "start_ms": 12000, "end_ms": 15200,
      "status": "ANALYZED", "reason": null,
      "tremor": {"value": 21.4, "unit": "cent", "z": 0.3, "flag": false},
      "mumble": {"value": 1850.0, "unit": "Hz", "z": -1.9, "flag": true},
      "soft":   {"value": -38.2, "unit": "LUFS", "z": -0.2, "flag": false},
      "flag_any": true
    },
    {
      "segment_id": "seg_001", "speaker": "COUNSELOR", "start_ms": 0, "end_ms": 4000,
      "status": "UNDETERMINED", "reason": "NOT_CHILD_SEGMENT",
      "tremor": null, "mumble": null, "soft": null, "flag_any": null
    }
  ]
}
```

## 4. 필드 규칙

- 필드 이름은 영어 snake_case, 상태값은 대문자이다.
- `status` 는 `ANALYZED` 또는 `UNDETERMINED` 두 가지뿐이다(최상위와 구간 모두).
- **"탐지 없음"** 은 `ANALYZED` 이면서 모든 `flag` 가 `false` 인 경우이다. `UNDETERMINED`(분석하지 못함)와 다르다.
- `flag_any`: 하나라도 `true` 면 `true`, 계산된 `flag` 가 모두 `false` 면 `false`, `UNDETERMINED` 구간은 `null`.
- 지표(`tremor`, `mumble`, `soft`)는 `value`(단위 `unit` 포함), `z`, `flag` 로 이루어진다. 0~1 점수나 "위험도" 같은 값은 만들지 않는다.
  - `tremor`: 음높이 변화(cent). 소리 나는 구간이 짧아 계산할 수 없으면 `value`, `z`, `flag` 가 모두 `null` 이고 구간은 `ANALYZED` 로 둔다.
  - `mumble`: 소리 나는 프레임의 스펙트럼 중심(Hz).
  - `soft`: K-weighting 한 활성 프레임 평균 에너지(LUFS 방식 값). 보통 음수이다.
- `z = (값 - 중앙값) / (Q3 - Q1)`. 한 녹음 안에서 지표마다 따로 계산한다(분석된 아동 구간 전체 기준, numpy 기본 백분위).
  지표별로 값이 있는 구간이 8개 미만이거나 `Q3 - Q1` 이 0 이하이면 그 지표의 `z` 와 `flag` 는 `null` 이다.
- `flag`(엄격한 부등호): `tremor` 는 `z > thresholds.tremor_z_above`, `mumble` 은 `z < thresholds.mumble_z_below`,
  `soft` 는 `z < thresholds.soft_z_below` 일 때 `true`.
- 세 지표의 `flag` 가 모두 `null` 이면 구간은 `UNDETERMINED`(`NO_REFERENCE`)이다.

## 5. reason 목록 (UNDETERMINED)

- `TOO_SHORT`: 구간이 1.0초 미만
- `NO_VOICED_FRAMES`: 소리 나는 프레임이 없음
- `NOT_CHILD_SEGMENT`: `speaker` 가 `CHILD` 가 아님
- `TOO_FEW_CHILD_SEGMENTS`: 분석된 아동 구간이 8개 미만이라 이 녹음 안의 비교를 만들 수 없음
- `NO_REFERENCE`: 값이 거의 같아 비교 기준을 만들 수 없음(`Q3 - Q1` 이 0 등)
- `INVALID_TIME_RANGE`: 시각이 잘못됨(시작 < 0, 끝 <= 시작, 시작이 음성 길이 밖, 정수가 아님). 끝이 음성 길이를 넘으면 길이에 맞춰 자른다.
  STT 결과에 시작 = 끝(길이 0)인 구간이 있으면 이 reason 이 된다(합성 음성 시험에서 잡음 조건 25건 확인).
- `DECODE_FAILED`: 음성 파일을 읽을 수 없음
- `AUDIO_TOO_LONG`: 음성이 60분을 넘음(`MAX_AUDIO_MINUTES`, 백엔드와 협의 전 잠정값)
- `ANALYSIS_ERROR`: 계산 중 예상하지 못한 오류(라이브러리가 없는 경우 포함)

녹음 전체가 불가능한 경우(`DECODE_FAILED`, `AUDIO_TOO_LONG`, `ANALYSIS_ERROR`)는 최상위 `status` 도 `UNDETERMINED` 이고
모든 구간의 `reason` 이 같다. `TOO_FEW_CHILD_SEGMENTS` 일 때는 분석 가능했던 아동 구간만 그 `reason` 을 갖고,
나머지 구간은 자기 `reason`(`NOT_CHILD_SEGMENT`, `TOO_SHORT` 등)을 유지한다.

## 6. 입력 처리

- 읽는 방식: `soundfile`(libsndfile). wav, flac, ogg, mp3 를 읽는다. **m4a, mp4, webm 은 읽지 못하고** `DECODE_FAILED` 이다(ffmpeg 가 필요).
- **mp3 는 값이 조금 다를 수 있다.** 구간마다 위치를 옮겨(seek) 읽는데 mp3 는 위치가 정확하지 않아, 같은 신호를 wav 로 읽을 때와 값이 달라질 수 있다.
  백엔드 시험(합성 음성 10분, 아동 130구간)에서 wav · flac · ogg 는 표시가 서로 같았고, mp3 는 4구간에 표시가 더 붙었으며 디코더 오류 줄이 stderr 에 나왔다. 다음 PR 에서 읽는 방식을 고칠 예정이다.
- 필요한 구간만 부분 읽기로 읽는다(파일 전체를 메모리에 올리지 않는다).
- 여러 채널은 평균해서 모노로 만들고, 실제 표본율에서 16 kHz 로 바꾼다.
- 시작 때 `warm_up()` 을 부르고, 서버 환경에 `NUMBA_CACHE_DIR`(쓰기 가능한 폴더)를 지정하면 numba 컴파일 결과를 재사용한다.
- 처리 시간(합성 음성, 한 PC, 코어 1개)은 측정한 곳마다 다르다.
  - 실험 PC: 오디오 1분당 약 1.3~1.6초.
  - 백엔드 PC(합성 음성 10분, 195구간 중 아동 130구간, 1프로세스): 약 50초, 즉 1분당 약 5초(`warm_up()` 첫 호출은 15초).
  - 시간은 아동 구간이 전체에서 차지하는 비율과 PC에 따라 달라진다. 서버(2 vCPU)에서의 시간은 측정하지 않았다.

## 7. 한계 (화면과 문서에 그대로 알려야 함)

- **한 녹음 안에서의 상대 비교**이다. 상담 내내 떨리는 아동은 표시되지 않을 수 있다.
  거꾸로, 기준이 "그 녹음의 상위/하위 구간"이라서 **문제가 없는 녹음에서도 일부 구간이 표시된다.**
  구간들의 값이 거의 같으면 아주 작은 차이도 표시될 수 있다.
- **효과를 넣지 않은 합성 음성에서도 분석된 아동 구간의 약 10%(55/555)에 하나 이상 표시가 붙었다.**
  조건별로는 6.4~13.0%이다(잡음 5개 조건과 깨끗한 음성). 지표별로는 떨림 3.3%, 웅얼거림 2.3%, 작은 소리 4.9%이다.
  이 비율은 표시가 "문제가 있다"는 뜻이 아님을 보여 주므로 화면에서도 참고 표시로만 쓴다.
- 표시 기준(`thresholds`)은 합성 음성으로 정한 잠정값이다. 실제 아동 음성으로 검증하지 않았다.
  떨림과 웅얼거림 기준은 효과 없는 합성 음성의 z 백분위로, 작은 소리 기준(-2.5)은 같은 데이터에서
  오표시를 줄이도록 골랐다. 같은 데이터로 고르고 확인한 값이라 실제 성능보다 좋게 보일 수 있다.
- 효과를 넣은 합성 음성에서 STT 구간과 매칭된 효과 줄 중 표시된 비율은 떨림 20/75(27%), 웅얼거림 9/15(60%),
  작은 소리 9/11(82%)이다. 떨림은 놓치는 경우가 많다. 이 수치는 실제 현장 성능이 아니다.
- 합성 음성은 줄마다 음량을 맞춰 두었고 작은 소리 효과 줄의 z 가 매우 극단적이었다(-12 이하).
  그래서 실제 녹음에서 은근히 작은 목소리나 웅얼거림이 합성 음성만큼 잘 분리되기 어렵다.
- 잡음이 가장 큰 조건(N5)에서는 아동 구간 145개 중 53~54개만 분석되었고, 한 녹음은 전체가 `UNDETERMINED` 였다.
  분석 불가 구간이 많을 수 있으므로 화면에서 이유와 함께 보여 준다.
- 실험은 정답 턴과 겹치는 STT 구간을 하나로 합쳐서 쟀다. 여기서는 합치지 않은 STT 구간을 그대로 쓴다.
  비교 결과 단일 구간 턴 1,053개 중 10개(약 1%)에서 표시가 달랐고, 합치지 않은 쪽이 효과 줄을 조금 덜 잡았다.
- 분석은 STT 첫 버전의 시각 기준이다. 상담사가 `start_ms`, `end_ms` 를 고치면 표시는 갱신되지 않는다
  (결과에 원래 시각이 들어 있으므로 화면에서 달라진 것을 알아챌 수 있다).
- 표시가 없다고 해서 문제가 없다는 뜻이 아니고, 표시가 있다고 해서 문제가 있다는 뜻도 아니다.

## 8. 저장

기존 `audio_features` 표에 **새 행**으로 저장한다.

- `extractor = "stt.voice_marks"`, `schema_version = "1.0"`, `features` 에는 위 dict 전체를 그대로 넣는다.
- 기존 화자별 지표 행(`extractor = "ispot_audio_features"`, 구조 `{speaker: {...}}`)은 건드리지 않는다.
- 구간(`segment_id`)별 결과이므로 transcript 의 `segments` 안에는 넣지 않는다(API_CONTRACT §7).
- 조회 API 와 위 JSON 모양은 Contract 변경이므로 `05_RULES §5` 형식의 변경안으로 먼저 제안한다.

## 9. 화면 문구 권고

- 권장: "음성 참고 표시", "다시 들어 볼 구간", "상담사 검토 필요", "분석 불가(이유)".
- 쓰지 않는다: "학대 확정", "위험 확정", "AI 판정", "자동 결정"(03_UI_UX §5). 색만으로 구분하지 않고 아이콘이나 글자를 함께 쓴다.
- "분석 불가"의 이유는 `reason` 값을 사람 말로 바꿔 보여 준다.
