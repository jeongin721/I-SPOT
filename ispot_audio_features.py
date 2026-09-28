from collections import defaultdict

import librosa
import numpy as np


def analyze_pause_features(
    stt_segments,
    min_pause_ms=300,
):
    """
    같은 화자의 '한 발화(turn) 내부'에서 발생하는
    pause만 계산한다.

    다른 화자가 말하고 있는 시간은
    pause에 포함하지 않는다.
    """

    speaker_stats = defaultdict(
        lambda: {
            "word_count": 0,
            "pauses": [],
            "turn_count": 0,
        }
    )

    # --------------------------------------------------------
    # 1. STT segment 하나를 하나의 발화 turn으로 처리
    # --------------------------------------------------------

    for segment in stt_segments:

        segment_speaker = segment.get(
            "speaker",
            "UNKNOWN",
        )

        words = segment.get(
            "words",
            [],
        )

        if not words:
            continue

        # ----------------------------------------------------
        # 2. 이 segment에서 해당 화자의 word만 사용
        # ----------------------------------------------------

        speaker_words = []

        for word in words:

            word_speaker = word.get(
                "speaker",
                segment_speaker,
            )

            start_ms = word.get("start_ms")
            end_ms = word.get("end_ms")

            if (
                word_speaker != segment_speaker
                or start_ms is None
                or end_ms is None
            ):
                continue

            speaker_words.append(
                {
                    "word": word.get(
                        "word",
                        "",
                    ),
                    "start_ms": start_ms,
                    "end_ms": end_ms,
                }
            )

        if not speaker_words:
            continue

        speaker_words.sort(
            key=lambda x: x["start_ms"]
        )

        stats = speaker_stats[
            segment_speaker
        ]

        stats["turn_count"] += 1

        stats["word_count"] += len(
            speaker_words
        )

        # ----------------------------------------------------
        # 3. 같은 turn 안에서만 단어 간 간격 계산
        # ----------------------------------------------------

        for i in range(
            1,
            len(speaker_words),
        ):

            previous_word = (
                speaker_words[i - 1]
            )

            current_word = (
                speaker_words[i]
            )

            pause_ms = (
                current_word["start_ms"]
                - previous_word["end_ms"]
            )

            if pause_ms >= min_pause_ms:
                stats["pauses"].append(
                    pause_ms
                )

    # --------------------------------------------------------
    # 4. 최종 통계
    # --------------------------------------------------------

    result = {}

    for speaker, stats in speaker_stats.items():

        pauses = stats["pauses"]

        if pauses:

            mean_pause_ms = (
                sum(pauses)
                / len(pauses)
            )

            max_pause_ms = max(
                pauses
            )

            total_pause_ms = sum(
                pauses
            )

        else:

            mean_pause_ms = 0
            max_pause_ms = 0
            total_pause_ms = 0

        result[speaker] = {

            "turn_count":
                stats["turn_count"],

            "word_count":
                stats["word_count"],

            "pause_count":
                len(pauses),

            "mean_pause_ms":
                round(
                    mean_pause_ms,
                    2,
                ),

            "max_pause_ms":
                max_pause_ms,

            "total_pause_ms":
                total_pause_ms,
        }

    return result

def analyze_response_latency(
    stt_segments,
    min_latency_ms=0,
    max_latency_ms=10000,
):
    """
    화자가 바뀌는 지점에서
    이전 화자의 발화 종료 시점과
    다음 화자의 발화 시작 시점 사이의 시간을 계산한다.

    예:
        SPEAKER_0 발화 종료: 10.0초
        SPEAKER_1 발화 시작: 11.2초

        response latency = 1.2초
    """

    # --------------------------------------------------------
    # 1. 유효한 segment만 시간순으로 정렬
    # --------------------------------------------------------

    segments = [
        segment
        for segment in stt_segments
        if (
            segment.get("start_ms") is not None
            and segment.get("end_ms") is not None
            and segment.get("speaker") is not None
        )
    ]

    segments.sort(
        key=lambda x: x["start_ms"]
    )

    speaker_latencies = defaultdict(list)

    # --------------------------------------------------------
    # 2. 연속된 segment 비교
    # --------------------------------------------------------

    for i in range(1, len(segments)):

        previous = segments[i - 1]
        current = segments[i]

        previous_speaker = previous["speaker"]
        current_speaker = current["speaker"]

        # 같은 화자면 response latency가 아님
        if previous_speaker == current_speaker:
            continue

        latency_ms = (
            current["start_ms"]
            - previous["end_ms"]
        )

        # 음수가 나오면 두 화자의 말이 겹친 것
        # response latency에서는 일단 제외
        if latency_ms < min_latency_ms:
            continue

        # 지나치게 긴 구간도 일단 제외
        if latency_ms > max_latency_ms:
            continue

        # "응답한 사람" 기준으로 저장
        speaker_latencies[
            current_speaker
        ].append(latency_ms)

    # --------------------------------------------------------
    # 3. 화자별 통계 계산
    # --------------------------------------------------------

    result = {}

    for speaker, latencies in speaker_latencies.items():

        if latencies:

            mean_latency_ms = (
                sum(latencies)
                / len(latencies)
            )

            max_latency_ms_value = max(
                latencies
            )

            min_latency_ms_value = min(
                latencies
            )

        else:

            mean_latency_ms = 0
            max_latency_ms_value = 0
            min_latency_ms_value = 0

        result[speaker] = {
            "response_count":
                len(latencies),

            "mean_response_latency_ms":
                round(
                    mean_latency_ms,
                    2,
                ),

            "min_response_latency_ms":
                min_latency_ms_value,

            "max_response_latency_ms":
                max_latency_ms_value,
        }

    return result


def analyze_speech_rate(stt_segments):
    """
    화자별 실제 발화 구간을 기준으로
    발화 속도를 계산한다.

    추출 특징:
        - turn_count
        - word_count
        - speaking_duration_ms
        - words_per_second
        - chars_per_second
    """

    speaker_stats = defaultdict(
        lambda: {
            "turn_count": 0,
            "word_count": 0,
            "char_count": 0,
            "speaking_duration_ms": 0,
        }
    )

    # --------------------------------------------------------
    # 1. 각 STT segment를 발화 Turn으로 처리
    # --------------------------------------------------------

    for segment in stt_segments:

        speaker = segment.get(
            "speaker",
            "UNKNOWN",
        )

        words = segment.get(
            "words",
            [],
        )

        if not words:
            continue

        # ----------------------------------------------------
        # 2. 현재 segment 화자의 word만 추출
        # ----------------------------------------------------

        speaker_words = []

        for word in words:

            word_speaker = word.get(
                "speaker",
                speaker,
            )

            start_ms = word.get("start_ms")
            end_ms = word.get("end_ms")

            if (
                word_speaker != speaker
                or start_ms is None
                or end_ms is None
            ):
                continue

            speaker_words.append(word)

        if not speaker_words:
            continue

        speaker_words.sort(
            key=lambda x: x["start_ms"]
        )

        # ----------------------------------------------------
        # 3. 이 Turn의 발화시간
        # ----------------------------------------------------

        turn_start_ms = (
            speaker_words[0]["start_ms"]
        )

        turn_end_ms = (
            speaker_words[-1]["end_ms"]
        )

        turn_duration_ms = max(
            0,
            turn_end_ms - turn_start_ms,
        )

        # ----------------------------------------------------
        # 4. 단어/문자 개수
        # ----------------------------------------------------

        word_count = len(
            speaker_words
        )

        char_count = sum(
            len(
                "".join(
                    str(
                        word.get(
                            "word",
                            "",
                        )
                    ).split()
                )
            )
            for word in speaker_words
        )

        # ----------------------------------------------------
        # 5. 화자별 누적
        # ----------------------------------------------------

        stats = speaker_stats[speaker]

        stats["turn_count"] += 1

        stats["word_count"] += (
            word_count
        )

        stats["char_count"] += (
            char_count
        )

        stats["speaking_duration_ms"] += (
            turn_duration_ms
        )

    # --------------------------------------------------------
    # 6. 최종 발화속도 계산
    # --------------------------------------------------------

    result = {}

    for speaker, stats in speaker_stats.items():

        duration_seconds = (
            stats["speaking_duration_ms"]
            / 1000
        )

        if duration_seconds > 0:

            words_per_second = (
                stats["word_count"]
                / duration_seconds
            )

            chars_per_second = (
                stats["char_count"]
                / duration_seconds
            )

        else:

            words_per_second = 0
            chars_per_second = 0

        result[speaker] = {
            "turn_count":
                stats["turn_count"],

            "word_count":
                stats["word_count"],

            "char_count":
                stats["char_count"],

            "speaking_duration_ms":
                stats["speaking_duration_ms"],

            "words_per_second":
                round(
                    words_per_second,
                    3,
                ),

            "chars_per_second":
                round(
                    chars_per_second,
                    3,
                ),
        }

    return result

def analyze_pitch(audio_path):
    """
    원본 음성에서 Pitch(F0, 기본주파수)를 추출한다.

    현재 단계에서는 화자를 구분하지 않고
    전체 음성의 voiced frame만 대상으로 테스트한다.
    """

    # 음성 파일 로드
    y, sr = librosa.load(
        audio_path,
        sr=None,
        mono=True,
    )

    # Pitch(F0) 추출
    f0, voiced_flag, voiced_prob = librosa.pyin(
        y,
        fmin=librosa.note_to_hz("C2"),
        fmax=librosa.note_to_hz("C7"),
        sr=sr,
    )

    # 음성이 존재하는 frame만 사용
    valid_f0 = f0[
        ~np.isnan(f0)
    ]

    if len(valid_f0) == 0:
        return {
            "pitch_mean_hz": 0,
            "pitch_median_hz": 0,
            "pitch_std_hz": 0,
            "pitch_min_hz": 0,
            "pitch_max_hz": 0,
            "voiced_frame_count": 0,
        }

    return {
        "pitch_mean_hz": round(
            float(np.mean(valid_f0)),
            2,
        ),

        "pitch_median_hz": round(
            float(np.median(valid_f0)),
            2,
        ),

        "pitch_std_hz": round(
            float(np.std(valid_f0)),
            2,
        ),

        "pitch_min_hz": round(
            float(np.min(valid_f0)),
            2,
        ),

        "pitch_max_hz": round(
            float(np.max(valid_f0)),
            2,
        ),

        "voiced_frame_count": int(
            len(valid_f0)
        ),
    }

def analyze_pitch_by_speaker(
    audio_path,
    stt_segments,
):
    """
    원본 음성에서 F0(Pitch)를 추출한 뒤,
    Deepgram STT segment의 시간 정보를 이용해
    화자별 Pitch 특징을 계산한다.
    """

    # --------------------------------------------------------
    # 1. 음성 로드
    # --------------------------------------------------------

    y, sr = librosa.load(
        audio_path,
        sr=None,
        mono=True,
    )

    # --------------------------------------------------------
    # 2. 전체 음성의 F0 추출
    # --------------------------------------------------------

    f0, voiced_flag, voiced_prob = librosa.pyin(
        y,
        fmin=librosa.note_to_hz("C2"),
        fmax=librosa.note_to_hz("C7"),
        sr=sr,
    )

    # 각 F0 frame의 시간 계산
    frame_times = librosa.times_like(
        f0,
        sr=sr,
    )

    # 초 → ms
    frame_times_ms = (
        frame_times * 1000
    )

    # --------------------------------------------------------
    # 3. 화자별 F0 저장 공간
    # --------------------------------------------------------

    speaker_f0 = defaultdict(list)

    # --------------------------------------------------------
    # 4. STT segment 시간과 F0 frame 연결
    # --------------------------------------------------------

    for segment in stt_segments:

        speaker = segment.get(
            "speaker",
            "UNKNOWN",
        )

        start_ms = segment.get(
            "start_ms"
        )

        end_ms = segment.get(
            "end_ms"
        )

        if (
            start_ms is None
            or end_ms is None
        ):
            continue

        # 이 segment 시간 안에 들어오는 frame 찾기
        mask = (
            (frame_times_ms >= start_ms)
            & (frame_times_ms <= end_ms)
        )

        segment_f0 = f0[mask]

        # NaN = 무성음/피치 추정 불가 frame
        segment_f0 = segment_f0[
            ~np.isnan(segment_f0)
        ]

        if len(segment_f0) == 0:
            continue

        speaker_f0[speaker].extend(
            segment_f0.tolist()
        )

    # --------------------------------------------------------
    # 5. 화자별 통계
    # --------------------------------------------------------

    result = {}

    for speaker, values in speaker_f0.items():

        values = np.array(
            values,
            dtype=float,
        )

        result[speaker] = {

            "pitch_mean_hz": round(
                float(np.mean(values)),
                2,
            ),

            "pitch_median_hz": round(
                float(np.median(values)),
                2,
            ),

            "pitch_std_hz": round(
                float(np.std(values)),
                2,
            ),

            "pitch_min_hz": round(
                float(np.min(values)),
                2,
            ),

            "pitch_max_hz": round(
                float(np.max(values)),
                2,
            ),

            "voiced_frame_count": int(
                len(values)
            ),
        }

    return result

def analyze_energy_by_speaker(
    audio_path,
    stt_segments,
):
    """
    원본 음성의 RMS Energy를 계산한 뒤,
    Deepgram STT segment 시간 정보를 이용해
    화자별 에너지 특징을 계산한다.
    """

    y, sr = librosa.load(
        audio_path,
        sr=None,
        mono=True,
    )

    rms = librosa.feature.rms(
        y=y
    )[0]

    frame_times = librosa.times_like(
        rms,
        sr=sr,
    )

    frame_times_ms = (
        frame_times * 1000
    )

    speaker_energy = defaultdict(list)

    for segment in stt_segments:

        speaker = segment.get(
            "speaker",
            "UNKNOWN",
        )

        start_ms = segment.get(
            "start_ms"
        )

        end_ms = segment.get(
            "end_ms"
        )

        if (
            start_ms is None
            or end_ms is None
        ):
            continue

        mask = (
            (frame_times_ms >= start_ms)
            & (frame_times_ms <= end_ms)
        )

        segment_rms = rms[mask]

        if len(segment_rms) == 0:
            continue

        speaker_energy[speaker].extend(
            segment_rms.tolist()
        )

    result = {}

    for speaker, values in speaker_energy.items():

        values = np.array(
            values,
            dtype=float,
        )

        result[speaker] = {
            "energy_mean": round(
                float(np.mean(values)),
                6,
            ),

            "energy_median": round(
                float(np.median(values)),
                6,
            ),

            "energy_std": round(
                float(np.std(values)),
                6,
            ),

            "energy_min": round(
                float(np.min(values)),
                6,
            ),

            "energy_max": round(
                float(np.max(values)),
                6,
            ),

            "frame_count": int(
                len(values)
            ),
        }

    return result

def extract_audio_features(
    audio_path,
    stt_segments,
):
    """
    상담 음성에서 화자별 Paralinguistic Feature를
    통합 추출한다.

    포함 특징:
        1. Within-turn Pause
        2. Response Latency
        3. Speech Rate
        4. Pitch (F0)
        5. RMS Energy
    """

    # --------------------------------------------------------
    # 1. 각 특징 추출
    # --------------------------------------------------------

    pause_features = analyze_pause_features(
        stt_segments
    )

    response_features = analyze_response_latency(
        stt_segments
    )

    speech_rate_features = analyze_speech_rate(
        stt_segments
    )

    pitch_features = analyze_pitch_by_speaker(
        audio_path,
        stt_segments,
    )

    energy_features = analyze_energy_by_speaker(
        audio_path,
        stt_segments,
    )

    # --------------------------------------------------------
    # 2. 등장한 모든 speaker 수집
    # --------------------------------------------------------

    speakers = set()

    for feature_dict in (
        pause_features,
        response_features,
        speech_rate_features,
        pitch_features,
        energy_features,
    ):
        speakers.update(
            feature_dict.keys()
        )

    # --------------------------------------------------------
    # 3. 화자별 하나의 Feature Vector로 통합
    # --------------------------------------------------------

    result = {}

    for speaker in sorted(speakers):

        pause = pause_features.get(
            speaker,
            {}
        )

        response = response_features.get(
            speaker,
            {}
        )

        speech_rate = speech_rate_features.get(
            speaker,
            {}
        )

        pitch = pitch_features.get(
            speaker,
            {}
        )

        energy = energy_features.get(
            speaker,
            {}
        )

        result[speaker] = {

            # ---------------- Pause ----------------

            "turn_count":
                pause.get("turn_count", 0),

            "word_count":
                pause.get("word_count", 0),

            "pause_count":
                pause.get("pause_count", 0),

            "mean_pause_ms":
                pause.get("mean_pause_ms", 0),

            "max_pause_ms":
                pause.get("max_pause_ms", 0),

            "total_pause_ms":
                pause.get("total_pause_ms", 0),

            # ------------ Response Latency ---------

            "response_count":
                response.get("response_count", 0),

            "mean_response_latency_ms":
                response.get(
                    "mean_response_latency_ms",
                    0,
                ),

            "min_response_latency_ms":
                response.get(
                    "min_response_latency_ms",
                    0,
                ),

            "max_response_latency_ms":
                response.get(
                    "max_response_latency_ms",
                    0,
                ),

            # --------------- Speech Rate -----------

            "char_count":
                speech_rate.get("char_count", 0),

            "speaking_duration_ms":
                speech_rate.get(
                    "speaking_duration_ms",
                    0,
                ),

            "words_per_second":
                speech_rate.get(
                    "words_per_second",
                    0,
                ),

            "chars_per_second":
                speech_rate.get(
                    "chars_per_second",
                    0,
                ),

            # ---------------- Pitch ----------------

            "pitch_mean_hz":
                pitch.get("pitch_mean_hz", 0),

            "pitch_median_hz":
                pitch.get(
                    "pitch_median_hz",
                    0,
                ),

            "pitch_std_hz":
                pitch.get("pitch_std_hz", 0),

            "pitch_min_hz":
                pitch.get("pitch_min_hz", 0),

            "pitch_max_hz":
                pitch.get("pitch_max_hz", 0),

            "pitch_voiced_frame_count":
                pitch.get(
                    "voiced_frame_count",
                    0,
                ),

            # ---------------- Energy ---------------

            "energy_mean":
                energy.get("energy_mean", 0),

            "energy_median":
                energy.get(
                    "energy_median",
                    0,
                ),

            "energy_std":
                energy.get("energy_std", 0),

            "energy_min":
                energy.get("energy_min", 0),

            "energy_max":
                energy.get("energy_max", 0),

            "energy_frame_count":
                energy.get("frame_count", 0),
        }

    return result


if __name__ == "__main__":
    import json
    from pathlib import Path

    # 테스트 파일
    test_path = Path("test_sample/0002_stt.json")
    audio_path = Path("test_sample/0002.mp3")

    # STT JSON 로드
    with open(
        test_path,
        "r",
        encoding="utf-8",
    ) as f:
        data = json.load(f)

    stt_segments = (
        data
        .get("stt_data", {})
        .get("segments", [])
    )

    # --------------------------------------------------------
    # 통합 음성 특징 추출
    # --------------------------------------------------------

    combined_features = extract_audio_features(
        audio_path,
        stt_segments,
    )

    # --------------------------------------------------------
    # 결과 출력
    # --------------------------------------------------------

    print()
    print("=" * 60)
    print("Combined Audio Feature Vector")
    print("=" * 60)

    print(
        json.dumps(
            combined_features,
            ensure_ascii=False,
            indent=2,
        )
    )

    print("=" * 60)  