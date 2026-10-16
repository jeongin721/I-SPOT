"""Create a one-to-one comparison of strict GT role-separation results."""

import csv
from collections import Counter
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEEPGRAM_CSV = (
    PROJECT_ROOT / "data_prep" / "evaluation" / "deepgram" / "gt_role_mapping_100.csv"
)
ELEVENLABS_CSV = (
    PROJECT_ROOT / "data_prep" / "evaluation" / "elevenlabs" / "gt_role_mapping_100.csv"
)
OUTPUT_CSV = (
    PROJECT_ROOT
    / "data_prep"
    / "evaluation"
    / "comparison"
    / "deepgram_vs_elevenlabs_role_100.csv"
)
EXPECTED_SAMPLE_COUNT = 100


def load_by_sample_id(path):
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        rows = list(csv.DictReader(file))

    if len(rows) != EXPECTED_SAMPLE_COUNT:
        raise ValueError(f"Expected {EXPECTED_SAMPLE_COUNT} rows in {path}, found {len(rows)}")

    result = {}
    for row in rows:
        sample_id = row["sample_id"].strip()
        if not sample_id:
            raise ValueError(f"Blank sample_id in {path}")
        if sample_id in result:
            raise ValueError(f"Duplicate sample_id {sample_id} in {path}")
        result[sample_id] = row
    return result


def comparison_group(deepgram_status, elevenlabs_status):
    deepgram_ok = deepgram_status == "ROLE_MAPPING_OK"
    elevenlabs_ok = elevenlabs_status == "ROLE_MAPPING_OK"
    if deepgram_ok and elevenlabs_ok:
        return "BOTH_OK"
    if elevenlabs_ok:
        return "ELEVENLABS_ONLY_OK"
    if deepgram_ok:
        return "DEEPGRAM_ONLY_OK"
    return "BOTH_FAILED"


def main():
    if OUTPUT_CSV.exists():
        raise FileExistsError(f"Refusing to overwrite existing result: {OUTPUT_CSV}")

    deepgram = load_by_sample_id(DEEPGRAM_CSV)
    elevenlabs = load_by_sample_id(ELEVENLABS_CSV)
    deepgram_ids = set(deepgram)
    elevenlabs_ids = set(elevenlabs)
    if deepgram_ids != elevenlabs_ids:
        raise ValueError(
            "Evaluator sample_id sets differ: "
            f"missing in ElevenLabs={sorted(deepgram_ids - elevenlabs_ids)}, "
            f"missing in Deepgram={sorted(elevenlabs_ids - deepgram_ids)}"
        )

    fields = [
        "sample_id",
        "comparison_group",
        "deepgram_status",
        "elevenlabs_status",
        "deepgram_child_coverage",
        "elevenlabs_child_coverage",
        "deepgram_counselor_coverage",
        "elevenlabs_counselor_coverage",
        "deepgram_speaker_count",
        "elevenlabs_speaker_count",
    ]
    rows = []
    for sample_id in sorted(deepgram_ids):
        dg = deepgram[sample_id]
        el = elevenlabs[sample_id]
        rows.append(
            {
                "sample_id": sample_id,
                "comparison_group": comparison_group(
                    dg["mapping_status"], el["mapping_status"]
                ),
                "deepgram_status": dg["mapping_status"],
                "elevenlabs_status": el["mapping_status"],
                "deepgram_child_coverage": dg["child_coverage"],
                "elevenlabs_child_coverage": el["child_coverage"],
                "deepgram_counselor_coverage": dg["counselor_coverage"],
                "elevenlabs_counselor_coverage": el["counselor_coverage"],
                "deepgram_speaker_count": dg["speaker_count"],
                "elevenlabs_speaker_count": el["speaker_count"],
            }
        )

    group_counts = Counter(row["comparison_group"] for row in rows)
    if len(rows) != EXPECTED_SAMPLE_COUNT or sum(group_counts.values()) != EXPECTED_SAMPLE_COUNT:
        raise RuntimeError("Comparison row count validation failed")

    with OUTPUT_CSV.open("x", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    print("I-SPOT GT-based strict role-separation comparison")
    for group in (
        "BOTH_OK",
        "ELEVENLABS_ONLY_OK",
        "DEEPGRAM_ONLY_OK",
        "BOTH_FAILED",
    ):
        print(f"{group}: {group_counts[group]}")
    print(f"Output: {OUTPUT_CSV}")


if __name__ == "__main__":
    main()
