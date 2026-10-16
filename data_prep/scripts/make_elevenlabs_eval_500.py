"""Create a reproducible, metadata-only ElevenLabs expansion cohort.

This script deliberately does not read provider outputs, role-mapping results,
or CER files, and it makes no API calls.  It excludes the original Pilot 100,
then selects 500 rows by proportional stratification on abuse label, risk
stage, and duration tertile.
"""

from __future__ import annotations

import argparse
import csv
import math
import random
import statistics
import zipfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[2]
GT_CSV = PROJECT_ROOT / "data_prep" / "evaluation" / "ground_truth" / "gt_2876.csv"
DURATION_CSV = PROJECT_ROOT / "data_prep" / "evaluation" / "ground_truth" / "audio_duration_2876.csv"
PILOT_100_CSV = PROJECT_ROOT / "data_prep" / "evaluation" / "deepgram" / "pilot_100.csv"
OUTPUT_CSV = PROJECT_ROOT / "data_prep" / "evaluation" / "elevenlabs_500" / "pilot_500.csv"

# Verified current dataset location.  A different installation can supply
# --ts-zip without changing this script.
DEFAULT_TS_ZIP = Path(
    r"C:\Users\USER\Desktop\헬스케어 4조\024.아동·청소년_상담_데이터"
    r"\3.개방데이터\1.데이터\Training\01.원천데이터\TS_in.zip"
)
SEED = 20260916
TARGET_COUNT = 500

OUTPUT_FIELDS = [
    "sample_id",
    "abuse_label",
    "risk_stage",
    "gender",
    "age",
    "grade",
    "subject_type",
    "tension_level",
    "behavior_characteristic",
    "interaction_characteristic",
    "duration_seconds",
    "duration_hms",
    "duration_bucket",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def percentile(sorted_values: list[float], fraction: float) -> float:
    position = (len(sorted_values) - 1) * fraction
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return sorted_values[lower]
    return sorted_values[lower] + (sorted_values[upper] - sorted_values[lower]) * (position - lower)


def duration_bucket(value: float, lower_cut: float, upper_cut: float) -> str:
    if value <= lower_cut:
        return "short"
    if value <= upper_cut:
        return "medium"
    return "long"


def proportional_allocation(counts: dict[tuple[str, str, str], int], total: int) -> dict[tuple[str, str, str], int]:
    population = sum(counts.values())
    raw = {key: total * count / population for key, count in counts.items()}
    allocation = {key: math.floor(value) for key, value in raw.items()}
    remaining = total - sum(allocation.values())
    for key in sorted(counts, key=lambda item: (raw[item] - allocation[item], item), reverse=True)[:remaining]:
        allocation[key] += 1
    return allocation


def zip_sample_ids(path: Path) -> set[str]:
    with zipfile.ZipFile(path, "r") as archive:
        return {Path(name).stem for name in archive.namelist() if name.lower().endswith(".mp3")}


def percentage(count: int, total: int) -> float:
    return round(100 * count / total, 2) if total else 0.0


def print_distribution(title: str, rows: Iterable[dict[str, str]], full_rows: list[dict[str, str]], field: str) -> None:
    sample_rows = list(rows)
    sample_counts = Counter(row[field] for row in sample_rows)
    full_counts = Counter(row[field] for row in full_rows)
    print(f"\n[{title}: {field}]")
    print("value,full_count,full_pct,sample_count,sample_pct,diff_pp")
    for value in sorted(set(full_counts) | set(sample_counts)):
        full_pct = percentage(full_counts[value], len(full_rows))
        sample_pct = percentage(sample_counts[value], len(sample_rows))
        print(
            f"{value},{full_counts[value]},{full_pct:.2f},"
            f"{sample_counts[value]},{sample_pct:.2f},{sample_pct - full_pct:.2f}"
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ts-zip", type=Path, default=DEFAULT_TS_ZIP)
    parser.add_argument("--output", type=Path, default=OUTPUT_CSV)
    args = parser.parse_args()

    for path in (GT_CSV, DURATION_CSV, PILOT_100_CSV, args.ts_zip):
        if not path.exists():
            raise FileNotFoundError(path)

    gt_rows = read_csv(GT_CSV)
    duration_rows = read_csv(DURATION_CSV)
    pilot_rows = read_csv(PILOT_100_CSV)
    if len(gt_rows) != 2876 or len(duration_rows) != 2876 or len(pilot_rows) != 100:
        raise ValueError("Expected GT=2876, duration=2876, Pilot 100=100 rows.")

    gt_by_id = {row["sample_id"]: row for row in gt_rows}
    duration_by_id = {row["sample_id"]: row for row in duration_rows}
    pilot_ids = {row["sample_id"] for row in pilot_rows}
    if len(gt_by_id) != len(gt_rows) or len(duration_by_id) != len(duration_rows) or len(pilot_ids) != 100:
        raise ValueError("Duplicate sample_id found in source data.")
    if not pilot_ids <= set(gt_by_id) or not pilot_ids <= set(duration_by_id):
        raise ValueError("Pilot 100 is not a subset of GT and duration metadata.")

    candidates = []
    for sample_id, gt in gt_by_id.items():
        if sample_id in pilot_ids:
            continue
        duration = duration_by_id.get(sample_id)
        if duration is None:
            continue
        candidates.append({**gt, **duration, "duration_seconds": float(duration["duration_seconds"])})
    if len(candidates) != 2776:
        raise ValueError(f"Expected 2776 non-Pilot candidates, found {len(candidates)}.")

    values = sorted(row["duration_seconds"] for row in candidates)
    lower_cut = percentile(values, 1 / 3)
    upper_cut = percentile(values, 2 / 3)
    for row in candidates:
        row["duration_bucket"] = duration_bucket(row["duration_seconds"], lower_cut, upper_cut)

    grouped: dict[tuple[str, str, str], list[dict[str, str]]] = defaultdict(list)
    for row in candidates:
        grouped[(row["abuse_label"], row["risk_stage"], row["duration_bucket"])].append(row)
    counts = {key: len(rows) for key, rows in grouped.items()}
    allocation = proportional_allocation(counts, TARGET_COUNT)

    rng = random.Random(SEED)
    selected: list[dict[str, str]] = []
    for key in sorted(grouped):
        rows = sorted(grouped[key], key=lambda row: row["sample_id"])
        quota = allocation[key]
        selected.extend(rng.sample(rows, quota))
    selected.sort(key=lambda row: row["sample_id"])

    selected_ids = {row["sample_id"] for row in selected}
    if len(selected) != TARGET_COUNT or len(selected_ids) != TARGET_COUNT or selected_ids & pilot_ids:
        raise ValueError("Selection validation failed before output.")

    audio_ids = zip_sample_ids(args.ts_zip)
    missing_audio = selected_ids - audio_ids
    if missing_audio:
        raise FileNotFoundError(f"Selected IDs missing from audio ZIP: {sorted(missing_audio)}")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.output.exists():
        raise FileExistsError(f"Refusing to overwrite existing output: {args.output}")
    with args.output.open("x", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_FIELDS)
        writer.writeheader()
        for row in selected:
            writer.writerow({field: row.get(field, "") for field in OUTPUT_FIELDS})

    selected_duration = [row["duration_seconds"] for row in selected]
    print("I-SPOT ElevenLabs expansion cohort")
    print(f"seed={SEED}")
    print(f"output={args.output}")
    print(f"candidate_count={len(candidates)}")
    print(f"selected_count={len(selected)}")
    print(f"unique_sample_id_count={len(selected_ids)}")
    print(f"pilot_100_overlap={len(selected_ids & pilot_ids)}")
    print(f"gt_present={sum(sample_id in gt_by_id for sample_id in selected_ids)}/{TARGET_COUNT}")
    print(f"audio_present={sum(sample_id in audio_ids for sample_id in selected_ids)}/{TARGET_COUNT}")
    print(f"duration_tertiles_seconds={lower_cut:.3f},{upper_cut:.3f}")
    print(
        "duration_summary_seconds="
        f"min:{min(selected_duration):.3f},max:{max(selected_duration):.3f},"
        f"mean:{statistics.mean(selected_duration):.3f},median:{statistics.median(selected_duration):.3f}"
    )
    print(f"total_duration_seconds={sum(selected_duration):.3f}")
    for field in (
        "abuse_label",
        "risk_stage",
        "gender",
        "age",
        "grade",
        "subject_type",
        "tension_level",
        "duration_bucket",
    ):
        print_distribution("full_2876_vs_sample_500", selected, gt_rows if field != "duration_bucket" else candidates, field)


if __name__ == "__main__":
    main()
