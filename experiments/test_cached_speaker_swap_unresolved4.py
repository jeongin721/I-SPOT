from pathlib import Path
import json
import sys


# ============================================================
# 프로젝트 설정
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from abuse_model.infer_abuse import predict_abuse


FILE_IDS = [
    "1786",
    "5113",
    "2315",
    "5194",
]

LABELS = [
    "신체학대",
    "정서학대",
    "성학대",
    "방임",
]

CACHE_DIR = (
    PROJECT_ROOT
    / "results"
    / "pyannote_diarization_cache"
)

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

    words = list(unique.values())

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
# word → pyannote speaker
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

    # overlap이 없는 경우
    # 단어 중앙점에서 가장 가까운 화자 구간 선택

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
# 특정 speaker의 text 생성
# ============================================================

def build_speaker_text(
    words,
    diarization_segments,
    target_speaker,
):

    selected_words = []

    for word in words:

        speaker = assign_word_to_speaker(
            word,
            diarization_segments,
        )

        if speaker == target_speaker:

            selected_words.append(
                word["word"]
            )

    return " ".join(
        selected_words
    ).strip()


# ============================================================
# 결과 문자열
# ============================================================

def detection_string(
    prediction,
):

    values = []

    for label in LABELS:

        values.append(
            "T"
            if prediction[label]["detected"]
            else "F"
        )

    return " ".join(values)


def expected_string(
    expected,
):

    return " ".join(
        "T" if expected[label] else "F"
        for label in LABELS
    )


def count_matches(
    prediction,
    expected,
):

    return sum(
        prediction[label]["detected"]
        == expected[label]
        for label in LABELS
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 100)
    print("CACHED PYANNOTE SPEAKER SWAP TEST")
    print("=" * 100)

    all_results = []

    for file_id in FILE_IDS:

        print()
        print("=" * 100)
        print(f"FILE: {file_id}")
        print("=" * 100)

        cache_path = (
            CACHE_DIR
            / f"{file_id}.json"
        )

        stt_path = (
            PROJECT_ROOT
            / "test_sample"
            / f"{file_id}_stt.json"
        )

        if not cache_path.exists():

            print(
                f"[ERROR] cache 없음: "
                f"{cache_path}"
            )

            continue

        if not stt_path.exists():

            print(
                f"[ERROR] STT 없음: "
                f"{stt_path}"
            )

            continue

        # ----------------------------------------------------
        # 캐시 읽기
        # ----------------------------------------------------

        with open(
            cache_path,
            "r",
            encoding="utf-8",
        ) as f:

            cache = json.load(f)

        diarization_segments = (
            cache["segments"]
        )

        speakers = (
            cache["speakers"]
        )

        # ----------------------------------------------------
        # STT 읽기
        # ----------------------------------------------------

        with open(
            stt_path,
            "r",
            encoding="utf-8",
        ) as f:

            stt_data = json.load(f)

        words = collect_words(
            stt_data
        )

        expected = (
            GT_EXPECTED[file_id]
        )

        print(
            f"GT: "
            f"{expected_string(expected)}"
        )

        print(
            f"Deepgram words: "
            f"{len(words)}"
        )

        print(
            f"Cached speakers: "
            f"{speakers}"
        )

        file_results = []

        # ----------------------------------------------------
        # 각 speaker를 CHILD라고 가정
        # ----------------------------------------------------

        for speaker in speakers:

            child_text = build_speaker_text(
                words,
                diarization_segments,
                speaker,
            )

            prediction = predict_abuse(
                child_text
            )

            match_count = count_matches(
                prediction,
                expected,
            )

            print()
            print(
                f"[ASSUME CHILD = {speaker}]"
            )

            print(
                f"  text length: "
                f"{len(child_text)} chars"
            )

            for label in LABELS:

                info = prediction[label]

                mark = (
                    "OK"
                    if (
                        info["detected"]
                        == expected[label]
                    )
                    else "MISMATCH"
                )

                print(
                    f"  {label:<6} "
                    f"{info['percentage']:>6.2f}% "
                    f"pred="
                    f"{'T' if info['detected'] else 'F'} "
                    f"GT="
                    f"{'T' if expected[label] else 'F'} "
                    f"[{mark}]"
                )

            print(
                f"  => "
                f"{detection_string(prediction)} "
                f"| {match_count}/4"
            )

            file_results.append(
                {
                    "speaker": speaker,
                    "text_length":
                        len(child_text),
                    "prediction":
                        prediction,
                    "match_count":
                        match_count,
                }
            )

        all_results.append(
            {
                "file": file_id,
                "expected": expected,
                "speaker_results":
                    file_results,
            }
        )

    # ========================================================
    # COMPACT SUMMARY
    # ========================================================

    print()
    print()
    print("=" * 100)
    print("COMPACT SUMMARY")
    print("=" * 100)

    for result in all_results:

        file_id = result["file"]

        print()
        print(
            f"{file_id} | "
            f"GT="
            f"{expected_string(result['expected'])}"
        )

        for speaker_result in (
            result["speaker_results"]
        ):

            prediction = (
                speaker_result["prediction"]
            )

            print(
                f"  CHILD={speaker_result['speaker']} "
                f"| text="
                f"{speaker_result['text_length']} "
                f"| pred="
                f"{detection_string(prediction)} "
                f"| "
                f"{speaker_result['match_count']}/4"
            )

    print()
    print("=" * 100)

    # --------------------------------------------------------
    # 결과 저장
    # --------------------------------------------------------

    output_path = (
        PROJECT_ROOT
        / "results"
        / "cached_speaker_swap_unresolved4.json"
    )

    with open(
        output_path,
        "w",
        encoding="utf-8",
    ) as f:

        json.dump(
            all_results,
            f,
            ensure_ascii=False,
            indent=2,
        )

    print(
        f"Saved: {output_path}"
    )


if __name__ == "__main__":
    main()