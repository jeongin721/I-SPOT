"""Compare Deepgram and ElevenLabs CHILD CER on common Pilot 100 cohorts.

Outputs two distinct metrics:
* Oracle-window CER: uses GT CHILD time windows and ignores provider speakers.
* BOTH_OK CER: uses mapped CHILD speakers only where both providers passed the
  strict GT role-separation evaluation.
"""

import csv
import json
import math
import re
import statistics
from collections import Counter
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
GT_JSONL = PROJECT_ROOT / "data_prep" / "evaluation" / "ground_truth" / "gt_2876.jsonl"
PILOT_CSV = PROJECT_ROOT / "data_prep" / "evaluation" / "deepgram" / "pilot_100.csv"
DEEPGRAM_DIR = PROJECT_ROOT / "data_prep" / "evaluation" / "deepgram" / "outputs"
ELEVENLABS_DIR = PROJECT_ROOT / "data_prep" / "evaluation" / "elevenlabs" / "outputs"
DEEPGRAM_MAPPING_CSV = (
    PROJECT_ROOT / "data_prep" / "evaluation" / "deepgram" / "gt_role_mapping_100.csv"
)
ELEVENLABS_MAPPING_CSV = (
    PROJECT_ROOT / "data_prep" / "evaluation" / "elevenlabs" / "gt_role_mapping_100.csv"
)
COMPARISON_CSV = (
    PROJECT_ROOT
    / "data_prep"
    / "evaluation"
    / "comparison"
    / "deepgram_vs_elevenlabs_role_100.csv"
)
ORACLE_OUTPUT_CSV = (
    PROJECT_ROOT / "data_prep" / "evaluation" / "comparison" / "oracle_child_cer_100.csv"
)
BOTH_OK_OUTPUT_CSV = (
    PROJECT_ROOT / "data_prep" / "evaluation" / "comparison" / "both_ok_child_cer_76.csv"
)

EXPECTED_PILOT_COUNT = 100
EXPECTED_BOTH_OK_COUNT = 76


def levenshtein(a, b):
    if len(a) < len(b):
        a, b = b, a
    previous = list(range(len(b) + 1))
    for i, character_a in enumerate(a, start=1):
        current = [i]
        for j, character_b in enumerate(b, start=1):
            current.append(
                min(
                    current[j - 1] + 1,
                    previous[j] + 1,
                    previous[j - 1] + (character_a != character_b),
                )
            )
        previous = current
    return previous[-1]


def cer(reference, hypothesis):
    if not reference:
        return None
    return levenshtein(reference, hypothesis) / len(reference)


def normalize_with_spaces(text):
    return re.sub(r"\s+", " ", text or "").strip()


def normalize_without_spaces(text):
    return re.sub(r"\s+", "", normalize_with_spaces(text))


def overlap_duration(a_start, a_end, b_start, b_end):
    return max(0.0, min(a_end, b_end) - max(a_start, b_start))


def load_csv_by_id(path, expected_count):
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        rows = list(csv.DictReader(file))
    if len(rows) != expected_count:
        raise ValueError(f"Expected {expected_count} rows in {path}, found {len(rows)}")
    result = {}
    for row in rows:
        sample_id = row["sample_id"].strip()
        if not sample_id or sample_id in result:
            raise ValueError(f"Blank or duplicate sample_id in {path}: {sample_id!r}")
        result[sample_id] = row
    return result


def load_pilot_ids():
    rows = load_csv_by_id(PILOT_CSV, EXPECTED_PILOT_COUNT)
    return list(rows)


def load_gt():
    result = {}
    with GT_JSONL.open("r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError(f"Invalid GT JSON on line {line_number}") from error
            sample_id = str(row["sample_id"]).strip()
            if sample_id in result:
                raise ValueError(f"Duplicate GT sample_id: {sample_id}")
            result[sample_id] = row
    return result


def as_interval(value_start, value_end, context):
    try:
        start = float(value_start)
        end = float(value_end)
    except (TypeError, ValueError) as error:
        raise ValueError(f"Non-numeric timestamp: {context}") from error
    if not math.isfinite(start) or not math.isfinite(end) or end < start:
        raise ValueError(f"Invalid timestamp interval: {context}")
    return start, end


def load_deepgram_words(path):
    try:
        with path.open("r", encoding="utf-8") as file:
            data = json.load(file)
    except json.JSONDecodeError as error:
        raise ValueError(f"Invalid Deepgram JSON: {path}") from error

    words = data.get("normalized", {}).get("words")
    if not isinstance(words, list):
        raise ValueError(f"Deepgram normalized.words is missing: {path}")

    result = []
    for index, word in enumerate(words):
        if not isinstance(word, dict):
            raise ValueError(f"Invalid Deepgram word object at {path}:{index}")
        if word.get("speaker") is None:
            raise ValueError(f"Missing Deepgram speaker at {path}:{index}")
        start, end = as_interval(word.get("start"), word.get("end"), f"{path}:{index}")
        result.append(
            {
                "speaker": str(word["speaker"]),
                "start": start,
                "end": end,
                "index": index,
                "text": word.get("punctuated_word") or word.get("word") or "",
            }
        )
    if not result:
        raise ValueError(f"No Deepgram normalized words: {path}")
    return result


def load_elevenlabs_words(path):
    try:
        with path.open("r", encoding="utf-8") as file:
            data = json.load(file)
    except json.JSONDecodeError as error:
        raise ValueError(f"Invalid ElevenLabs JSON: {path}") from error

    words = data.get("words")
    if not isinstance(words, list):
        raise ValueError(f"ElevenLabs words is missing: {path}")

    result = []
    for index, word in enumerate(words):
        if not isinstance(word, dict):
            raise ValueError(f"Invalid ElevenLabs word object at {path}:{index}")
        if word.get("type") != "word":
            continue
        if word.get("speaker_id") is None:
            raise ValueError(f"Missing ElevenLabs speaker_id at {path}:{index}")
        start, end = as_interval(word.get("start"), word.get("end"), f"{path}:{index}")
        result.append(
            {
                "speaker": str(word["speaker_id"]),
                "start": start,
                "end": end,
                "index": index,
                "text": word.get("text") or "",
            }
        )
    if not result:
        raise ValueError(f"No ElevenLabs type='word' entries: {path}")
    return result


def child_intervals(gt):
    intervals = []
    for index, utterance in enumerate(gt.get("utterances", [])):
        if utterance.get("role") != "CHILD":
            continue
        start, end = as_interval(
            utterance.get("start"), utterance.get("end"), f"GT utterance {index}"
        )
        intervals.append((start, end))
    if not intervals:
        raise ValueError(f"No CHILD GT utterances for sample_id {gt.get('sample_id')}")
    return intervals


def chronological_text(words):
    return " ".join(
        word["text"]
        for word in sorted(words, key=lambda word: (word["start"], word["end"], word["index"]))
        if word["text"]
    )


def oracle_child_text(words, intervals):
    selected = [
        word
        for word in words
        if any(overlap_duration(word["start"], word["end"], start, end) > 0 for start, end in intervals)
    ]
    return chronological_text(selected)


def mapped_child_text(words, child_speaker_ids):
    return chronological_text(
        [word for word in words if word["speaker"] in child_speaker_ids]
    )


def cer_fields(reference, hypothesis, prefix):
    reference_spaces = normalize_with_spaces(reference)
    hypothesis_spaces = normalize_with_spaces(hypothesis)
    reference_no_spaces = normalize_without_spaces(reference)
    hypothesis_no_spaces = normalize_without_spaces(hypothesis)
    if not reference_no_spaces:
        raise ValueError("Empty normalized GT CHILD reference")
    return {
        f"{prefix}_child_chars": len(hypothesis_spaces),
        f"{prefix}_cer_with_spaces": round(cer(reference_spaces, hypothesis_spaces), 6),
        f"{prefix}_cer_without_spaces": round(
            cer(reference_no_spaces, hypothesis_no_spaces), 6
        ),
        f"{prefix}_child_text": hypothesis,
    }


def parse_child_speaker_ids(value):
    return {speaker_id.strip() for speaker_id in value.split(",") if speaker_id.strip()}


def write_csv(path, fields, rows):
    if path.exists():
        raise FileExistsError(f"Refusing to overwrite existing result: {path}")
    with path.open("x", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def summarize(label, rows):
    print(f"[{label}] rows={len(rows)}")
    for provider in ("deepgram", "elevenlabs"):
        for variant in ("with_spaces", "without_spaces"):
            values = [float(row[f"{provider}_cer_{variant}"]) for row in rows]
            print(
                f"{provider}_{variant}: mean={statistics.mean(values):.6f}, "
                f"median={statistics.median(values):.6f}"
            )

    dg_values = [float(row["deepgram_cer_without_spaces"]) for row in rows]
    el_values = [float(row["elevenlabs_cer_without_spaces"]) for row in rows]
    print(f"deepgram_lower_no_space={sum(dg < el for dg, el in zip(dg_values, el_values))}")
    print(f"elevenlabs_lower_no_space={sum(el < dg for dg, el in zip(dg_values, el_values))}")
    print(f"ties_no_space={sum(dg == el for dg, el in zip(dg_values, el_values))}")
    for provider, values in (("deepgram", dg_values), ("elevenlabs", el_values)):
        bins = Counter(
            "0-10%" if value < 0.10 else "10-20%" if value < 0.20 else "20-50%" if value < 0.50 else "50%+"
            for value in values
        )
        print(f"{provider}_no_space_bins=" + ", ".join(
            f"{name}:{bins[name]}" for name in ("0-10%", "10-20%", "20-50%", "50%+")
        ))


def main():
    gt_map = load_gt()
    pilot_ids = load_pilot_ids()
    deepgram_mapping = load_csv_by_id(DEEPGRAM_MAPPING_CSV, EXPECTED_PILOT_COUNT)
    elevenlabs_mapping = load_csv_by_id(ELEVENLABS_MAPPING_CSV, EXPECTED_PILOT_COUNT)
    comparison = load_csv_by_id(COMPARISON_CSV, EXPECTED_PILOT_COUNT)

    if (
        set(pilot_ids) != set(deepgram_mapping)
        or set(pilot_ids) != set(elevenlabs_mapping)
        or set(pilot_ids) != set(comparison)
    ):
        raise ValueError("Pilot, role-mapping, and comparison sample_id sets differ")

    both_ok_ids = [
        sample_id
        for sample_id in pilot_ids
        if comparison[sample_id]["comparison_group"] == "BOTH_OK"
    ]
    if len(both_ok_ids) != EXPECTED_BOTH_OK_COUNT:
        raise ValueError(f"Expected {EXPECTED_BOTH_OK_COUNT} BOTH_OK rows, found {len(both_ok_ids)}")

    oracle_rows = []
    both_ok_rows = []
    for sample_id in pilot_ids:
        gt = gt_map.get(sample_id)
        if gt is None:
            raise ValueError(f"Missing GT sample_id: {sample_id}")
        reference = gt.get("child_text", "")
        intervals = child_intervals(gt)
        dg_path = DEEPGRAM_DIR / f"{sample_id}_deepgram.json"
        el_path = ELEVENLABS_DIR / f"{sample_id}_elevenlabs.json"
        if not dg_path.exists() or not el_path.exists():
            raise FileNotFoundError(f"Missing provider JSON for sample_id: {sample_id}")

        dg_words = load_deepgram_words(dg_path)
        el_words = load_elevenlabs_words(el_path)
        dg_oracle_text = oracle_child_text(dg_words, intervals)
        el_oracle_text = oracle_child_text(el_words, intervals)
        oracle_rows.append(
            {
                "sample_id": sample_id,
                "gt_child_chars": len(normalize_with_spaces(reference)),
                "gt_child_text": reference,
                **cer_fields(reference, dg_oracle_text, "deepgram"),
                **cer_fields(reference, el_oracle_text, "elevenlabs"),
            }
        )

        if sample_id in both_ok_ids:
            dg_child_ids = parse_child_speaker_ids(deepgram_mapping[sample_id]["child_speaker_ids"])
            el_child_ids = parse_child_speaker_ids(elevenlabs_mapping[sample_id]["child_speaker_ids"])
            if not dg_child_ids or not el_child_ids:
                raise ValueError(f"BOTH_OK sample without CHILD speaker ID: {sample_id}")
            both_ok_rows.append(
                {
                    "sample_id": sample_id,
                    "deepgram_child_speaker_ids": ",".join(sorted(dg_child_ids)),
                    "elevenlabs_child_speaker_ids": ",".join(sorted(el_child_ids)),
                    "gt_child_chars": len(normalize_with_spaces(reference)),
                    "gt_child_text": reference,
                    **cer_fields(reference, mapped_child_text(dg_words, dg_child_ids), "deepgram"),
                    **cer_fields(reference, mapped_child_text(el_words, el_child_ids), "elevenlabs"),
                }
            )

    if len(oracle_rows) != EXPECTED_PILOT_COUNT:
        raise RuntimeError("Oracle output row count validation failed")
    if len(both_ok_rows) != EXPECTED_BOTH_OK_COUNT:
        raise RuntimeError("BOTH_OK output row count validation failed")
    if len({row["sample_id"] for row in oracle_rows}) != len(oracle_rows):
        raise RuntimeError("Duplicate sample_id in Oracle output")
    if len({row["sample_id"] for row in both_ok_rows}) != len(both_ok_rows):
        raise RuntimeError("Duplicate sample_id in BOTH_OK output")

    common_fields = [
        "sample_id", "gt_child_chars", "deepgram_child_chars", "elevenlabs_child_chars",
        "deepgram_cer_with_spaces", "elevenlabs_cer_with_spaces",
        "deepgram_cer_without_spaces", "elevenlabs_cer_without_spaces",
        "gt_child_text", "deepgram_child_text", "elevenlabs_child_text",
    ]
    both_ok_fields = [
        "sample_id", "deepgram_child_speaker_ids", "elevenlabs_child_speaker_ids", *common_fields[1:]
    ]
    write_csv(ORACLE_OUTPUT_CSV, common_fields, oracle_rows)
    write_csv(BOTH_OK_OUTPUT_CSV, both_ok_fields, both_ok_rows)

    summarize("Oracle-window / common Pilot 100", oracle_rows)
    summarize("BOTH_OK role-conditioned / common 76", both_ok_rows)
    for label, rows in (("oracle", oracle_rows), ("both_ok", both_ok_rows)):
        print(
            f"{label}_deepgram_blank_hypotheses="
            f"{sum(not row['deepgram_child_text'] for row in rows)}"
        )
        print(
            f"{label}_elevenlabs_blank_hypotheses="
            f"{sum(not row['elevenlabs_child_text'] for row in rows)}"
        )
    print(f"Oracle output: {ORACLE_OUTPUT_CSV}")
    print(f"BOTH_OK output: {BOTH_OK_OUTPUT_CSV}")


if __name__ == "__main__":
    main()
