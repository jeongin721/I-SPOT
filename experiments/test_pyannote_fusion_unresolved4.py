from pathlib import Path
import json
import re
import subprocess
import sys

from pyannote.audio import Pipeline


# ============================================================
# 프로젝트 경로 / import
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from abuse_model.infer_abuse import predict_abuse


# ============================================================
# 설정
# ============================================================

FILE_IDS = [
    "1786",
    "5113",
    "2315",
    "5194",
]

MODEL_NAME = "pyannote/speaker-diarization-community-1"


# GT A-text를 RoBERTa에 넣었을 때의 기존 기준 결과
GT_EXPECTED = {
    "1786": {
        "신체학대": False,
        "정서학대": True,
        "성학대": False,
        "방임": False,
    },
    "5113": {
        "신체학대": False,
        "정서학대": False,
        "성학대": False,
        "방임": True,
    },
    "2315": {
        "신체학대": False,
        "정서학대": False,
        "성학대": False,
        "방임": False,
    },
    "5194": {
        "신체학대": False,
        "정서학대": False,
        "성학대": False,
        "방임": False,
    },
}


# ============================================================
# 질문 판별
# ============================================================

QUESTION_ENDINGS = (
    "나요",
    "가요",
    "까요",
    "인가요",
    "있나요",
    "없나요",
    "했나요",
    "하나요",
    "해요",
    "예요",
    "이에요",
    "니",
)


def is_question(text: str) -> bool:

    text = text.strip()

    if not text:
        return False

    if text.endswith("?"):
        return True

    clean = re.sub(
        r"[.!~\s]+$",
        "",
        text,
    )

    return clean.endswith(
        QUESTION_ENDINGS
    )


# ============================================================
# MP3 → WAV
# ============================================================

def ensure_wav(file_id: str) -> Path:

    mp3_path = (
        PROJECT_ROOT
        / "test_sample"
        / f"{file_id}.mp3"
    )

    wav_path = (
        PROJECT_ROOT
        / "test_sample"
        / f"{file_id}_pyannote_16k.wav"
    )

    if wav_path.exists():

        print(
            f"    WAV already exists: "
            f"{wav_path.name}"
        )

        return wav_path

    if not mp3_path.exists():

        raise FileNotFoundError(
            f"MP3 없음: {mp3_path}"
        )

    print(
        f"    MP3 -> WAV: "
        f"{mp3_path.name}"
    )

    command = [
        "ffmpeg",
        "-y",
        "-i",
        str(mp3_path),
        "-ac",
        "1",
        "-ar",
        "16000",
        "-c:a",
        "pcm_s16le",
        str(wav_path),
    ]

    subprocess.run(
        command,
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    return wav_path


# ============================================================
# Deepgram word 추출
# ============================================================

def collect_words(obj):

    found = []

    def walk(value):

        if isinstance(value, dict):

            word = value.get("word")
            start_ms = value.get("start_ms")
            end_ms = value.get("end_ms")

            if (
                isinstance(word, str)
                and start_ms is not None
                and end_ms is not None
            ):

                try:

                    found.append(
                        {
                            "word": word.strip(),
                            "start_ms": float(start_ms),
                            "end_ms": float(end_ms),
                        }
                    )

                except (TypeError, ValueError):
                    pass

            for child in value.values():
                walk(child)

        elif isinstance(value, list):

            for child in value:
                walk(child)

    walk(obj)

    unique = {}

    for item in found:

        if not item["word"]:
            continue

        key = (
            item["word"],
            item["start_ms"],
            item["end_ms"],
        )

        unique[key] = item

    words = list(
        unique.values()
    )

    words.sort(
        key=lambda x: (
            x["start_ms"],
            x["end_ms"],
        )
    )

    return words


# ============================================================
# overlap
# ============================================================

def overlap_ms(
    start1,
    end1,
    start2,
    end2,
):

    return max(
        0.0,
        min(end1, end2)
        - max(start1, start2),
    )


# ============================================================
# Deepgram word → pyannote speaker
# ============================================================

def assign_word_to_speaker(
    word,
    diarization_segments,
):

    word_start = word["start_ms"]
    word_end = word["end_ms"]

    best_speaker = None
    best_overlap = 0.0

    for segment in diarization_segments:

        overlap = overlap_ms(
            word_start,
            word_end,
            segment["start_ms"],
            segment["end_ms"],
        )

        if overlap > best_overlap:

            best_overlap = overlap
            best_speaker = segment["speaker"]

    if best_speaker is not None:
        return best_speaker

    # overlap이 없는 경우 가장 가까운
    # pyannote 구간의 speaker 사용

    midpoint = (
        word_start
        + word_end
    ) / 2

    best_distance = None

    for segment in diarization_segments:

        if midpoint < segment["start_ms"]:

            distance = (
                segment["start_ms"]
                - midpoint
            )

        elif midpoint > segment["end_ms"]:

            distance = (
                midpoint
                - segment["end_ms"]
            )

        else:

            distance = 0.0

        if (
            best_distance is None
            or distance < best_distance
        ):

            best_distance = distance
            best_speaker = segment["speaker"]

    return best_speaker


# ============================================================
# word → utterance
# ============================================================

def build_utterances(
    assigned_words,
    max_gap_ms=1200,
):

    utterances = []

    current = None

    for word in assigned_words:

        speaker = word["speaker"]

        if speaker is None:
            continue

        if current is None:

            current = {
                "speaker": speaker,
                "start_ms": word["start_ms"],
                "end_ms": word["end_ms"],
                "words": [word["word"]],
            }

            continue

        gap = (
            word["start_ms"]
            - current["end_ms"]
        )

        same_speaker = (
            speaker
            == current["speaker"]
        )

        if (
            same_speaker
            and gap <= max_gap_ms
        ):

            current["words"].append(
                word["word"]
            )

            current["end_ms"] = (
                word["end_ms"]
            )

        else:

            current["text"] = " ".join(
                current["words"]
            ).strip()

            utterances.append(
                current
            )

            current = {
                "speaker": speaker,
                "start_ms": word["start_ms"],
                "end_ms": word["end_ms"],
                "words": [word["word"]],
            }

    if current is not None:

        current["text"] = " ".join(
            current["words"]
        ).strip()

        utterances.append(
            current
        )

    return utterances


# ============================================================
# GT 없이 역할 추론
# ============================================================

def infer_roles(
    utterances,
    speakers,
):

    stats = {}

    for speaker in speakers:

        items = [
            x
            for x in utterances
            if (
                x["speaker"] == speaker
                and x["text"]
            )
        ]

        question_count = sum(
            1
            for item in items
            if is_question(
                item["text"]
            )
        )

        total = len(items)

        ratio = (
            question_count / total
            if total
            else 0.0
        )

        stats[speaker] = {
            "utterance_count": total,
            "question_count": question_count,
            "question_ratio": ratio,
        }

    if len(speakers) != 2:

        return {}, stats

    ordered = sorted(
        speakers,
        key=lambda speaker:
        stats[speaker]["question_ratio"],
        reverse=True,
    )

    counselor = ordered[0]
    child = ordered[1]

    roles = {
        counselor: "COUNSELOR",
        child: "CHILD",
    }

    return roles, stats


# ============================================================
# RoBERTa 결과 정리
# ============================================================

def normalize_prediction(
    prediction,
):

    result = {}

    for label, info in prediction.items():

        result[label] = {
            "probability": float(
                info["probability"]
            ),
            "percentage": float(
                info["percentage"]
            ),
            "threshold": float(
                info["threshold"]
            ),
            "detected": bool(
                info["detected"]
            ),
        }

    return result


# ============================================================
# 파일 하나 분석
# ============================================================

def analyze_file(
    file_id,
    pipeline,
):

    print()
    print("=" * 100)
    print(f"FILE: {file_id}")
    print("=" * 100)

    stt_path = (
        PROJECT_ROOT
        / "test_sample"
        / f"{file_id}_stt.json"
    )

    if not stt_path.exists():

        raise FileNotFoundError(
            f"STT JSON 없음: {stt_path}"
        )

    # --------------------------------------------------------
    # WAV
    # --------------------------------------------------------

    wav_path = ensure_wav(
        file_id
    )

    # --------------------------------------------------------
    # Deepgram words
    # --------------------------------------------------------

    with open(
        stt_path,
        "r",
        encoding="utf-8",
    ) as f:

        stt_data = json.load(f)

    words = collect_words(
        stt_data
    )

    print(
        f"    Deepgram words: "
        f"{len(words)}"
    )

    if not words:

        raise RuntimeError(
            "Deepgram words 없음"
        )

    # --------------------------------------------------------
    # pyannote
    # --------------------------------------------------------

    print(
        "    pyannote diarization..."
    )

    output = pipeline(
        str(wav_path),
        num_speakers=2,
    )

    diarization_segments = []

    for turn, speaker in (
        output.speaker_diarization
    ):

        diarization_segments.append(
            {
                "speaker": str(speaker),
                "start_ms":
                    float(turn.start) * 1000,
                "end_ms":
                    float(turn.end) * 1000,
            }
        )

    speakers = sorted(
        set(
            item["speaker"]
            for item
            in diarization_segments
        )
    )

    print(
        f"    pyannote speakers: "
        f"{speakers}"
    )

    # --------------------------------------------------------
    # Fusion
    # --------------------------------------------------------

    assigned_words = []

    for word in words:

        speaker = (
            assign_word_to_speaker(
                word,
                diarization_segments,
            )
        )

        assigned_words.append(
            {
                **word,
                "speaker": speaker,
            }
        )

    assigned_count = sum(
        1
        for item in assigned_words
        if item["speaker"] is not None
    )

    utterances = build_utterances(
        assigned_words
    )

    print(
        f"    assigned words: "
        f"{assigned_count}/{len(words)}"
    )

    print(
        f"    fusion utterances: "
        f"{len(utterances)}"
    )

    # --------------------------------------------------------
    # Role
    # --------------------------------------------------------

    roles, stats = infer_roles(
        utterances,
        speakers,
    )

    for speaker in speakers:

        stat = stats[speaker]

        print(
            f"    {speaker}: "
            f"utterances="
            f"{stat['utterance_count']}, "
            f"questions="
            f"{stat['question_count']}, "
            f"q_ratio="
            f"{stat['question_ratio']:.3f}"
        )

    child_speakers = [
        speaker
        for speaker, role
        in roles.items()
        if role == "CHILD"
    ]

    counselor_speakers = [
        speaker
        for speaker, role
        in roles.items()
        if role == "COUNSELOR"
    ]

    if (
        len(child_speakers) != 1
        or len(counselor_speakers) != 1
    ):

        raise RuntimeError(
            "역할 추론 실패"
        )

    child_speaker = (
        child_speakers[0]
    )

    counselor_speaker = (
        counselor_speakers[0]
    )

    print(
        f"    => CHILD: "
        f"{child_speaker}"
    )

    print(
        f"    => COUNSELOR: "
        f"{counselor_speaker}"
    )

    # --------------------------------------------------------
    # Child text
    # --------------------------------------------------------

    child_utterances = [
        item
        for item in utterances
        if item["speaker"]
        == child_speaker
    ]

    child_text = " ".join(
        item["text"]
        for item
        in child_utterances
        if item["text"]
    ).strip()

    print(
        f"    child utterances: "
        f"{len(child_utterances)}"
    )

    print(
        f"    child text length: "
        f"{len(child_text)} chars"
    )

    if not child_text:

        raise RuntimeError(
            "CHILD text 없음"
        )

    # --------------------------------------------------------
    # RoBERTa
    # --------------------------------------------------------

    prediction = normalize_prediction(
        predict_abuse(
            child_text
        )
    )

    expected = (
        GT_EXPECTED[file_id]
    )

    matches = {}

    for label in expected:

        actual = (
            prediction[label]["detected"]
        )

        matches[label] = (
            actual
            == expected[label]
        )

    match_count = sum(
        matches.values()
    )

    print()
    print("    RoBERTa:")

    for label in expected:

        info = prediction[label]

        expected_value = (
            expected[label]
        )

        actual_value = (
            info["detected"]
        )

        match_mark = (
            "OK"
            if matches[label]
            else "MISMATCH"
        )

        print(
            f"      {label:<6} "
            f"{info['percentage']:>6.2f}% "
            f"pred={str(actual_value):<5} "
            f"GT={str(expected_value):<5} "
            f"[{match_mark}]"
        )

    print(
        f"    => label match: "
        f"{match_count}/4"
    )

    return {
        "file": file_id,
        "speakers": speakers,
        "roles": roles,
        "role_stats": stats,
        "child_speaker": child_speaker,
        "counselor_speaker":
            counselor_speaker,
        "deepgram_word_count":
            len(words),
        "assigned_word_count":
            assigned_count,
        "fusion_utterance_count":
            len(utterances),
        "child_utterance_count":
            len(child_utterances),
        "child_text_length":
            len(child_text),
        "prediction": prediction,
        "expected": expected,
        "matches": matches,
        "match_count": match_count,
    }


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 100)
    print(
        "PYANNOTE FUSION REGRESSION "
        "- UNRESOLVED 4"
    )
    print("=" * 100)

    print()
    print("[1] pyannote 모델 로드 중...")

    # 모델은 한 번만 로드해서
    # 네 파일에 재사용한다.
    pipeline = Pipeline.from_pretrained(
        MODEL_NAME
    )

    print("    모델 로드 완료")

    results = []

    for file_id in FILE_IDS:

        try:

            result = analyze_file(
                file_id,
                pipeline,
            )

            results.append(
                result
            )

        except Exception as exc:

            print()
            print(
                f"[ERROR] {file_id}: "
                f"{type(exc).__name__}: "
                f"{exc}"
            )

            results.append(
                {
                    "file": file_id,
                    "error":
                        f"{type(exc).__name__}: "
                        f"{exc}",
                }
            )

    # --------------------------------------------------------
    # 결과 저장
    # --------------------------------------------------------

    results_dir = (
        PROJECT_ROOT
        / "results"
    )

    results_dir.mkdir(
        exist_ok=True
    )

    output_path = (
        results_dir
        / "pyannote_fusion_unresolved4.json"
    )

    with open(
        output_path,
        "w",
        encoding="utf-8",
    ) as f:

        json.dump(
            results,
            f,
            ensure_ascii=False,
            indent=2,
        )

    # --------------------------------------------------------
    # 최종 요약
    # --------------------------------------------------------

    print()
    print()
    print("=" * 100)
    print("FINAL SUMMARY")
    print("=" * 100)

    total_labels = 0
    matched_labels = 0
    successful_files = 0

    for result in results:

        file_id = result["file"]

        if "error" in result:

            print(
                f"{file_id}: ERROR"
            )

            continue

        successful_files += 1

        total_labels += 4
        matched_labels += (
            result["match_count"]
        )

        prediction = (
            result["prediction"]
        )

        values = []

        for label in [
            "신체학대",
            "정서학대",
            "성학대",
            "방임",
        ]:

            detected = (
                prediction[label][
                    "detected"
                ]
            )

            values.append(
                "T"
                if detected
                else "F"
            )

        expected_values = []

        for label in [
            "신체학대",
            "정서학대",
            "성학대",
            "방임",
        ]:

            detected = (
                result["expected"][label]
            )

            expected_values.append(
                "T"
                if detected
                else "F"
            )

        print(
            f"{file_id}: "
            f"GT={' '.join(expected_values)} | "
            f"Fusion={' '.join(values)} | "
            f"{result['match_count']}/4"
        )

    print()
    print(
        f"Successful files: "
        f"{successful_files}/{len(FILE_IDS)}"
    )

    print(
        f"Label matches: "
        f"{matched_labels}/{total_labels}"
        if total_labels
        else
        "Label matches: N/A"
    )

    print()
    print(
        f"Saved: {output_path}"
    )

    print("=" * 100)

    print()
    print(
        "주의: 이 결과는 unresolved 4개 샘플에 대한 "
        "회귀 실험 결과이며 서비스 전체 정확도가 아닙니다."
    )


if __name__ == "__main__":
    main()