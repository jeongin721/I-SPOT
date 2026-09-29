"""Evaluate ElevenLabs Pilot 100 with Deepgram's strict GT role-separation rules.

This is not a general diarization-accuracy metric.  It maps provider word
timestamps against COUNSELOR/CHILD ground-truth utterance timestamps and
applies the same purity, coverage, and status rules as the Deepgram evaluator.
"""

import csv
import json
import math
from collections import defaultdict
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
GT_JSONL = PROJECT_ROOT / "data_prep" / "evaluation" / "ground_truth" / "gt_2876.jsonl"
PILOT_CSV = PROJECT_ROOT / "data_prep" / "evaluation" / "deepgram" / "pilot_100.csv"
ELEVENLABS_DIR = PROJECT_ROOT / "data_prep" / "evaluation" / "elevenlabs" / "outputs"
OUTPUT_CSV = PROJECT_ROOT / "data_prep" / "evaluation" / "elevenlabs" / "gt_role_mapping_100.csv"

PURITY_THRESHOLD = 0.80
ROLE_COVERAGE_THRESHOLD = 0.80
EXPECTED_SAMPLE_COUNT = 100


def overlap_duration(a_start, a_end, b_start, b_end):
    start = max(a_start, b_start)
    end = min(a_end, b_end)
    return max(0.0, end - start)


def load_gt():
    result = {}
    with GT_JSONL.open("r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError(f"Invalid GT JSON at line {line_number}") from error
            sample_id = str(row["sample_id"]).strip()
            if sample_id in result:
                raise ValueError(f"Duplicate GT sample_id: {sample_id}")
            result[sample_id] = row
    return result


def load_pilot_ids():
    with PILOT_CSV.open("r", encoding="utf-8-sig", newline="") as file:
        sample_ids = [row["sample_id"].strip() for row in csv.DictReader(file)]

    if len(sample_ids) != EXPECTED_SAMPLE_COUNT:
        raise ValueError(f"Expected {EXPECTED_SAMPLE_COUNT} pilot rows, found {len(sample_ids)}")
    if len(set(sample_ids)) != len(sample_ids):
        raise ValueError("pilot_100.csv contains duplicate sample_id values")
    return sample_ids


def get_gt_utterances(gt):
    utterances = []
    for utterance in gt.get("utterances", []):
        role = utterance.get("role")
        if role not in ("CHILD", "COUNSELOR"):
            continue

        start = utterance.get("start")
        end = utterance.get("end")
        if start is None or end is None:
            continue
        utterances.append({"role": role, "start": float(start), "end": float(end)})
    return utterances


def load_elevenlabs_words(path):
    try:
        with path.open("r", encoding="utf-8") as file:
            data = json.load(file)
    except json.JSONDecodeError as error:
        raise ValueError(f"Invalid ElevenLabs JSON: {path}") from error

    raw_words = data.get("words")
    if not isinstance(raw_words, list):
        raise ValueError(f"ElevenLabs JSON has no words list: {path}")

    words = []
    speaker_ids = set()
    for index, word in enumerate(raw_words):
        if not isinstance(word, dict):
            raise ValueError(f"Invalid words[{index}] object: {path}")
        if word.get("type") != "word":
            continue

        speaker = word.get("speaker_id")
        start = word.get("start")
        end = word.get("end")
        if speaker is None or start is None or end is None:
            raise ValueError(f"Missing speaker_id/start/end in words[{index}]: {path}")

        try:
            start = float(start)
            end = float(end)
        except (TypeError, ValueError) as error:
            raise ValueError(f"Non-numeric timestamp in words[{index}]: {path}") from error
        if not math.isfinite(start) or not math.isfinite(end) or end < start:
            raise ValueError(f"Invalid timestamp interval in words[{index}]: {path}")

        speaker = str(speaker)
        speaker_ids.add(speaker)
        words.append({"speaker": speaker, "start": start, "end": end})

    if not words:
        raise ValueError(f"No type='word' entries: {path}")
    return words, len(speaker_ids)


def evaluate(words, speaker_count, gt_utterances):
    """Keep this calculation aligned with evaluate_deepgram_role_mapping.py."""
    speaker_stats = defaultdict(
        lambda: {"CHILD": 0.0, "COUNSELOR": 0.0, "word_count": 0}
    )

    for word in words:
        speaker = word["speaker"]
        start = word["start"]
        end = word["end"]
        speaker_stats[speaker]["word_count"] += 1

        for gt_utterance in gt_utterances:
            overlap = overlap_duration(
                start, end, gt_utterance["start"], gt_utterance["end"]
            )
            if overlap > 0:
                speaker_stats[speaker][gt_utterance["role"]] += overlap

    total_child_overlap = sum(stat["CHILD"] for stat in speaker_stats.values())
    total_counselor_overlap = sum(
        stat["COUNSELOR"] for stat in speaker_stats.values()
    )

    speaker_mapping = []
    child_speakers = []
    counselor_speakers = []
    mixed_speakers = []

    for speaker in sorted(speaker_stats):
        stat = speaker_stats[speaker]
        child_sec = stat["CHILD"]
        counselor_sec = stat["COUNSELOR"]
        total = child_sec + counselor_sec

        if total <= 0:
            role = "UNKNOWN"
            purity = 0.0
        else:
            purity = max(child_sec, counselor_sec) / total
            if purity < PURITY_THRESHOLD:
                role = "MIXED"
            elif child_sec > counselor_sec:
                role = "CHILD"
            else:
                role = "COUNSELOR"

        if role == "CHILD":
            child_speakers.append(speaker)
        elif role == "COUNSELOR":
            counselor_speakers.append(speaker)
        elif role == "MIXED":
            mixed_speakers.append(speaker)

        speaker_mapping.append(
            {
                "speaker": speaker,
                "role": role,
                "child_sec": round(child_sec, 4),
                "counselor_sec": round(counselor_sec, 4),
                "purity": round(purity, 4),
                "word_count": stat["word_count"],
            }
        )

    assigned_child_overlap = sum(
        speaker_stats[speaker]["CHILD"] for speaker in child_speakers
    )
    assigned_counselor_overlap = sum(
        speaker_stats[speaker]["COUNSELOR"] for speaker in counselor_speakers
    )

    child_coverage = (
        assigned_child_overlap / total_child_overlap if total_child_overlap > 0 else 0.0
    )
    counselor_coverage = (
        assigned_counselor_overlap / total_counselor_overlap
        if total_counselor_overlap > 0
        else 0.0
    )

    child_ok = bool(child_speakers) and child_coverage >= ROLE_COVERAGE_THRESHOLD
    counselor_ok = bool(counselor_speakers) and (
        counselor_coverage >= ROLE_COVERAGE_THRESHOLD
    )

    if child_ok and counselor_ok:
        mapping_status = "ROLE_MAPPING_OK"
    elif speaker_count == 1:
        mapping_status = "SINGLE_SPEAKER_COLLAPSE"
    elif mixed_speakers:
        mapping_status = "MIXED_SPEAKER_COLLAPSE"
    elif not child_speakers or not counselor_speakers:
        mapping_status = "ROLE_MISSING"
    else:
        mapping_status = "AMBIGUOUS"

    return {
        "speaker_count": speaker_count,
        "mapping_status": mapping_status,
        "child_speaker_ids": ",".join(child_speakers),
        "counselor_speaker_ids": ",".join(counselor_speakers),
        "mixed_speaker_ids": ",".join(mixed_speakers),
        "child_coverage": round(child_coverage, 4),
        "counselor_coverage": round(counselor_coverage, 4),
        "speaker_mapping_json": json.dumps(speaker_mapping, ensure_ascii=False),
    }


def main():
    if OUTPUT_CSV.exists():
        raise FileExistsError(f"Refusing to overwrite existing result: {OUTPUT_CSV}")

    gt_map = load_gt()
    pilot_ids = load_pilot_ids()
    results = []

    for sample_id in pilot_ids:
        if sample_id not in gt_map:
            raise ValueError(f"Missing GT for pilot sample_id: {sample_id}")

        path = ELEVENLABS_DIR / f"{sample_id}_elevenlabs.json"
        if not path.exists():
            raise FileNotFoundError(f"Missing ElevenLabs output for pilot sample_id: {sample_id}")

        words, speaker_count = load_elevenlabs_words(path)
        result = evaluate(words, speaker_count, get_gt_utterances(gt_map[sample_id]))
        results.append({"sample_id": sample_id, **result})

    if len(results) != EXPECTED_SAMPLE_COUNT:
        raise RuntimeError(f"Expected {EXPECTED_SAMPLE_COUNT} results, got {len(results)}")
    if len({row["sample_id"] for row in results}) != len(results):
        raise RuntimeError("Duplicate sample_id in evaluation results")

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
    with OUTPUT_CSV.open("x", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        writer.writerows(results)

    status_counts = defaultdict(int)
    for result in results:
        status_counts[result["mapping_status"]] += 1

    print("I-SPOT STRICT GT-BASED ROLE-SEPARATION EVALUATION (ElevenLabs)")
    print(f"Evaluated samples: {len(results)}")
    for status in (
        "ROLE_MAPPING_OK",
        "SINGLE_SPEAKER_COLLAPSE",
        "MIXED_SPEAKER_COLLAPSE",
        "ROLE_MISSING",
        "AMBIGUOUS",
    ):
        count = status_counts[status]
        print(f"{status}: {count} ({count / len(results) * 100:.2f}%)")
    print(f"Output: {OUTPUT_CSV}")


if __name__ == "__main__":
    main()
