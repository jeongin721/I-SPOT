from pathlib import Path
import json


# ============================================================
# 설정
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent

FILE_IDS = [
    "1786",
    "5113",
    "2315",
    "5194",
]

CACHE_DIR = (
    PROJECT_ROOT
    / "results"
    / "pyannote_diarization_cache"
)


# ============================================================
# GT 시간 변환
# ============================================================

def time_to_seconds(time_string: str) -> float:
    """
    예:
        00:03.593 -> 3.593
        01:12.500 -> 72.500
    """

    minutes, seconds = time_string.split(":")

    return (
        int(minutes) * 60
        + float(seconds)
    )


# ============================================================
# GT Q/A 구간 추출
# ============================================================

def extract_gt_segments(data):
    """
    AI-Hub JSON에서 audio 항목을 찾아
    Q/A 시간 구간을 추출한다.

    Q = 상담자
    A = 아동
    """

    segments = []

    def walk(obj):

        if isinstance(obj, dict):

            audio = obj.get("audio")

            if isinstance(audio, list):

                for item in audio:

                    if not isinstance(item, dict):
                        continue

                    role = item.get("type")

                    if role not in {"Q", "A"}:
                        continue

                    start = item.get("start")
                    end = item.get("end")
                    text = item.get("text", "")

                    if not start or not end:
                        continue

                    segments.append(
                        {
                            "role": role,
                            "start":
                                time_to_seconds(start),
                            "end":
                                time_to_seconds(end),
                            "text": text,
                        }
                    )

            for value in obj.values():
                walk(value)

        elif isinstance(obj, list):

            for item in obj:
                walk(item)

    walk(data)

    # 중복 제거
    unique = {}

    for segment in segments:

        key = (
            segment["role"],
            segment["start"],
            segment["end"],
            segment["text"],
        )

        unique[key] = segment

    segments = list(
        unique.values()
    )

    segments.sort(
        key=lambda x: (
            x["start"],
            x["end"],
        )
    )

    return segments


# ============================================================
# 시간 overlap
# ============================================================

def overlap_seconds(
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
# 파일 하나 평가
# ============================================================

def evaluate_file(file_id):

    gt_path = (
        PROJECT_ROOT
        / "test_sample"
        / f"{file_id}.json"
    )

    cache_path = (
        CACHE_DIR
        / f"{file_id}.json"
    )

    if not gt_path.exists():

        raise FileNotFoundError(
            f"GT 없음: {gt_path}"
        )

    if not cache_path.exists():

        raise FileNotFoundError(
            f"pyannote cache 없음: "
            f"{cache_path}"
        )

    # --------------------------------------------------------
    # GT
    # --------------------------------------------------------

    with open(
        gt_path,
        "r",
        encoding="utf-8",
    ) as f:

        gt_data = json.load(f)

    gt_segments = extract_gt_segments(
        gt_data
    )

    q_segments = [
        x
        for x in gt_segments
        if x["role"] == "Q"
    ]

    a_segments = [
        x
        for x in gt_segments
        if x["role"] == "A"
    ]

    # --------------------------------------------------------
    # pyannote cache
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # overlap
    # --------------------------------------------------------

    speaker_results = {}

    for speaker in speakers:

        predicted_segments = [
            x
            for x in diarization_segments
            if x["speaker"] == speaker
        ]

        q_overlap = 0.0
        a_overlap = 0.0

        speaker_total = 0.0

        for pred in predicted_segments:

            pred_start = (
                pred["start_sec"]
            )

            pred_end = (
                pred["end_sec"]
            )

            speaker_total += (
                pred_end
                - pred_start
            )

            for gt in q_segments:

                q_overlap += overlap_seconds(
                    pred_start,
                    pred_end,
                    gt["start"],
                    gt["end"],
                )

            for gt in a_segments:

                a_overlap += overlap_seconds(
                    pred_start,
                    pred_end,
                    gt["start"],
                    gt["end"],
                )

        qa_overlap = (
            q_overlap
            + a_overlap
        )

        if qa_overlap > 0:

            q_ratio = (
                q_overlap
                / qa_overlap
            )

            a_ratio = (
                a_overlap
                / qa_overlap
            )

        else:

            q_ratio = 0.0
            a_ratio = 0.0

        if q_overlap > a_overlap:

            gt_role = "COUNSELOR"

        elif a_overlap > q_overlap:

            gt_role = "CHILD"

        else:

            gt_role = "UNKNOWN"

        # purity:
        # 해당 speaker가 한 역할로 얼마나
        # 깨끗하게 구성되어 있는지
        purity = max(
            q_ratio,
            a_ratio,
        )

        speaker_results[speaker] = {
            "speaker_total":
                speaker_total,

            "q_overlap":
                q_overlap,

            "a_overlap":
                a_overlap,

            "q_ratio":
                q_ratio,

            "a_ratio":
                a_ratio,

            "purity":
                purity,

            "gt_role":
                gt_role,
        }

    return {
        "file": file_id,

        "gt_q_count":
            len(q_segments),

        "gt_a_count":
            len(a_segments),

        "speaker_results":
            speaker_results,
    }


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 100)
    print(
        "CACHED PYANNOTE vs GT "
        "- UNRESOLVED 4"
    )
    print("=" * 100)

    results = []

    for file_id in FILE_IDS:

        print()
        print("=" * 100)
        print(f"FILE: {file_id}")
        print("=" * 100)

        try:

            result = evaluate_file(
                file_id
            )

        except Exception as exc:

            print(
                f"[ERROR] "
                f"{type(exc).__name__}: "
                f"{exc}"
            )

            continue

        results.append(
            result
        )

        print(
            f"GT Q segments: "
            f"{result['gt_q_count']}"
        )

        print(
            f"GT A segments: "
            f"{result['gt_a_count']}"
        )

        print()

        for speaker, info in (
            result[
                "speaker_results"
            ].items()
        ):

            print(
                f"[{speaker}]"
            )

            print(
                f"  Q overlap : "
                f"{info['q_overlap']:.2f} sec"
            )

            print(
                f"  A overlap : "
                f"{info['a_overlap']:.2f} sec"
            )

            print(
                f"  Q ratio   : "
                f"{info['q_ratio'] * 100:.2f}%"
            )

            print(
                f"  A ratio   : "
                f"{info['a_ratio'] * 100:.2f}%"
            )

            print(
                f"  purity    : "
                f"{info['purity'] * 100:.2f}%"
            )

            print(
                f"  => GT role: "
                f"{info['gt_role']}"
            )

            print()

    # ========================================================
    # COMPACT SUMMARY
    # ========================================================

    print()
    print("=" * 100)
    print("COMPACT SUMMARY")
    print("=" * 100)

    for result in results:

        print()
        print(
            f"{result['file']}:"
        )

        for speaker, info in (
            result[
                "speaker_results"
            ].items()
        ):

            print(
                f"  {speaker} | "
                f"Q={info['q_ratio'] * 100:6.2f}% | "
                f"A={info['a_ratio'] * 100:6.2f}% | "
                f"purity={info['purity'] * 100:6.2f}% | "
                f"{info['gt_role']}"
            )

    # ========================================================
    # JSON 저장
    # ========================================================

    output_path = (
        PROJECT_ROOT
        / "results"
        / "cached_pyannote_gt_unresolved4.json"
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

    print()
    print("=" * 100)

    print(
        f"Saved: {output_path}"
    )


if __name__ == "__main__":
    main()