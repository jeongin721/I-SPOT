import csv
import json
from collections import defaultdict
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]

GT_JSONL = (
    PROJECT_ROOT
    / "data_prep"
    / "evaluation"
    / "ground_truth"
    / "gt_2876.jsonl"
)

PILOT_CSV = (
    PROJECT_ROOT
    / "data_prep"
    / "evaluation"
    / "deepgram"
    / "pilot_100.csv"
)

DG_DIR = (
    PROJECT_ROOT
    / "data_prep"
    / "evaluation"
    / "deepgram"
    / "outputs"
)

OUTPUT_CSV = (
    PROJECT_ROOT
    / "data_prep"
    / "evaluation"
    / "deepgram"
    / "gt_role_mapping_100.csv"
)


# ============================================================
# 평가 기준
# ============================================================

PURITY_THRESHOLD = 0.80
ROLE_COVERAGE_THRESHOLD = 0.80


# ============================================================
# interval overlap
# ============================================================

def overlap_duration(a_start, a_end, b_start, b_end):

    start = max(a_start, b_start)
    end = min(a_end, b_end)

    return max(0.0, end - start)


# ============================================================
# GT load
# ============================================================

def load_gt():

    result = {}

    with GT_JSONL.open(
        "r",
        encoding="utf-8"
    ) as f:

        for line in f:

            line = line.strip()

            if not line:
                continue

            row = json.loads(line)

            sample_id = str(
                row["sample_id"]
            ).strip()

            result[sample_id] = row

    return result


# ============================================================
# Pilot load
# ============================================================

def load_pilot_ids():

    with PILOT_CSV.open(
        "r",
        encoding="utf-8-sig",
        newline=""
    ) as f:

        return [
            row["sample_id"].strip()
            for row in csv.DictReader(f)
        ]


# ============================================================
# main
# ============================================================

def main():

    gt_map = load_gt()
    pilot_ids = load_pilot_ids()

    results = []

    for sample_id in pilot_ids:

        gt = gt_map.get(sample_id)

        if gt is None:
            continue

        dg_path = (
            DG_DIR
            / f"{sample_id}_deepgram.json"
        )

        if not dg_path.exists():
            continue

        with dg_path.open(
            "r",
            encoding="utf-8"
        ) as f:

            dg = json.load(f)

        normalized = dg.get(
            "normalized",
            {}
        )

        words = normalized.get(
            "words",
            []
        )

        speaker_count = normalized.get(
            "speaker_count",
            0
        )

        # ----------------------------------------------------
        # GT utterance
        # ----------------------------------------------------

        gt_utts = []

        for utt in gt.get(
            "utterances",
            []
        ):

            role = utt.get("role")

            if role not in (
                "CHILD",
                "COUNSELOR"
            ):
                continue

            start = utt.get("start")
            end = utt.get("end")

            if start is None or end is None:
                continue

            gt_utts.append(
                {
                    "role": role,
                    "start": float(start),
                    "end": float(end),
                }
            )

        # ----------------------------------------------------
        # speaker별 GT role overlap 계산
        # ----------------------------------------------------

        speaker_stats = defaultdict(
            lambda: {
                "CHILD": 0.0,
                "COUNSELOR": 0.0,
                "word_count": 0,
            }
        )

        for word in words:

            speaker = word.get(
                "speaker"
            )

            start = word.get(
                "start"
            )

            end = word.get(
                "end"
            )

            if (
                speaker is None
                or start is None
                or end is None
            ):
                continue

            speaker = int(speaker)
            start = float(start)
            end = float(end)

            speaker_stats[
                speaker
            ]["word_count"] += 1

            for gt_utt in gt_utts:

                overlap = overlap_duration(
                    start,
                    end,
                    gt_utt["start"],
                    gt_utt["end"],
                )

                if overlap <= 0:
                    continue

                speaker_stats[
                    speaker
                ][gt_utt["role"]] += overlap

        # ----------------------------------------------------
        # 전체 CHILD / COUNSELOR overlap
        # ----------------------------------------------------

        total_child_overlap = sum(
            stat["CHILD"]
            for stat in speaker_stats.values()
        )

        total_counselor_overlap = sum(
            stat["COUNSELOR"]
            for stat in speaker_stats.values()
        )

        # ----------------------------------------------------
        # speaker role 분류
        # ----------------------------------------------------

        speaker_mapping = []

        child_speakers = []
        counselor_speakers = []
        mixed_speakers = []

        for speaker in sorted(
            speaker_stats.keys()
        ):

            stat = speaker_stats[
                speaker
            ]

            child_sec = stat["CHILD"]
            counselor_sec = stat[
                "COUNSELOR"
            ]

            total = (
                child_sec
                + counselor_sec
            )

            if total <= 0:

                role = "UNKNOWN"
                purity = 0.0

            else:

                dominant = max(
                    child_sec,
                    counselor_sec
                )

                purity = (
                    dominant
                    / total
                )

                if (
                    purity
                    < PURITY_THRESHOLD
                ):

                    role = "MIXED"

                elif (
                    child_sec
                    > counselor_sec
                ):

                    role = "CHILD"

                else:

                    role = "COUNSELOR"

            if role == "CHILD":
                child_speakers.append(
                    speaker
                )

            elif role == "COUNSELOR":
                counselor_speakers.append(
                    speaker
                )

            elif role == "MIXED":
                mixed_speakers.append(
                    speaker
                )

            speaker_mapping.append(
                {
                    "speaker":
                        speaker,

                    "role":
                        role,

                    "child_sec":
                        round(
                            child_sec,
                            4
                        ),

                    "counselor_sec":
                        round(
                            counselor_sec,
                            4
                        ),

                    "purity":
                        round(
                            purity,
                            4
                        ),

                    "word_count":
                        stat[
                            "word_count"
                        ],
                }
            )

        # ----------------------------------------------------
        # Role coverage
        # ----------------------------------------------------

        assigned_child_overlap = sum(
            speaker_stats[s][
                "CHILD"
            ]
            for s in child_speakers
        )

        assigned_counselor_overlap = sum(
            speaker_stats[s][
                "COUNSELOR"
            ]
            for s in counselor_speakers
        )

        if total_child_overlap > 0:

            child_coverage = (
                assigned_child_overlap
                / total_child_overlap
            )

        else:

            child_coverage = 0.0

        if (
            total_counselor_overlap
            > 0
        ):

            counselor_coverage = (
                assigned_counselor_overlap
                / total_counselor_overlap
            )

        else:

            counselor_coverage = 0.0

        # ----------------------------------------------------
        # 최종 status
        # ----------------------------------------------------

        child_ok = (
            len(child_speakers) > 0
            and
            child_coverage
            >= ROLE_COVERAGE_THRESHOLD
        )

        counselor_ok = (
            len(counselor_speakers) > 0
            and
            counselor_coverage
            >= ROLE_COVERAGE_THRESHOLD
        )

        if (
            child_ok
            and counselor_ok
        ):

            mapping_status = (
                "ROLE_MAPPING_OK"
            )

        elif speaker_count == 1:

            mapping_status = (
                "SINGLE_SPEAKER_COLLAPSE"
            )

        elif mixed_speakers:

            mapping_status = (
                "MIXED_SPEAKER_COLLAPSE"
            )

        elif (
            not child_speakers
            or not counselor_speakers
        ):

            mapping_status = (
                "ROLE_MISSING"
            )

        else:

            mapping_status = (
                "AMBIGUOUS"
            )

        # ----------------------------------------------------
        # 결과 저장
        # ----------------------------------------------------

        results.append(
            {
                "sample_id":
                    sample_id,

                "speaker_count":
                    speaker_count,

                "mapping_status":
                    mapping_status,

                "child_speaker_ids":
                    ",".join(
                        str(x)
                        for x
                        in child_speakers
                    ),

                "counselor_speaker_ids":
                    ",".join(
                        str(x)
                        for x
                        in counselor_speakers
                    ),

                "mixed_speaker_ids":
                    ",".join(
                        str(x)
                        for x
                        in mixed_speakers
                    ),

                "child_coverage":
                    round(
                        child_coverage,
                        4
                    ),

                "counselor_coverage":
                    round(
                        counselor_coverage,
                        4
                    ),

                "speaker_mapping_json":
                    json.dumps(
                        speaker_mapping,
                        ensure_ascii=False
                    ),
            }
        )

    # ========================================================
    # CSV 저장
    # ========================================================

    fields = [
        "sample_id",
        "speaker_count",
        "mapping_status",
        "child_speaker_ids",
        "counselor_speaker_ids",
        "mixed_speaker_ids",
        "child_coverage",
        "counselor_coverage",
        "speaker_mapping_json",
    ]

    with OUTPUT_CSV.open(
        "w",
        encoding="utf-8-sig",
        newline=""
    ) as f:

        writer = csv.DictWriter(
            f,
            fieldnames=fields
        )

        writer.writeheader()
        writer.writerows(results)

    # ========================================================
    # 요약
    # ========================================================

    status_counts = defaultdict(int)

    for row in results:

        status_counts[
            row["mapping_status"]
        ] += 1

    print("=" * 72)
    print(
        "I-SPOT STRICT GT-BASED "
        "DIARIZATION EVALUATION"
    )
    print("=" * 72)

    print(
        f"평가 샘플: "
        f"{len(results)}"
    )

    print()

    status_order = [
        "ROLE_MAPPING_OK",
        "SINGLE_SPEAKER_COLLAPSE",
        "MIXED_SPEAKER_COLLAPSE",
        "ROLE_MISSING",
        "AMBIGUOUS",
    ]

    for status in status_order:

        count = status_counts[
            status
        ]

        print(
            f"{status}: "
            f"{count}개 "
            f"({count / len(results) * 100:.2f}%)"
        )

    print()
    print(
        f"기준: "
        f"speaker purity >= "
        f"{PURITY_THRESHOLD:.0%}"
    )

    print(
        f"기준: "
        f"role coverage >= "
        f"{ROLE_COVERAGE_THRESHOLD:.0%}"
    )

    print()

    print(
        "[ROLE_MAPPING_OK 중 "
        "여러 CHILD speaker]"
    )

    for row in results:

        if (
            row["mapping_status"]
            == "ROLE_MAPPING_OK"
            and ","
            in row[
                "child_speaker_ids"
            ]
        ):

            print(
                f"  {row['sample_id']} | "
                f"child="
                f"{row['child_speaker_ids']} | "
                f"coverage="
                f"{row['child_coverage']}"
            )

    print()

    print(
        "[MIXED_SPEAKER_COLLAPSE]"
    )

    for row in results:

        if (
            row["mapping_status"]
            == "MIXED_SPEAKER_COLLAPSE"
        ):

            print(
                f"  {row['sample_id']} | "
                f"speakers="
                f"{row['speaker_count']} | "
                f"mixed="
                f"{row['mixed_speaker_ids']} | "
                f"child coverage="
                f"{row['child_coverage']} | "
                f"counselor coverage="
                f"{row['counselor_coverage']}"
            )

    print()

    print(
        "저장 완료:"
    )

    print(
        OUTPUT_CSV
    )


if __name__ == "__main__":
    main()