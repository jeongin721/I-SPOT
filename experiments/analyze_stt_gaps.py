import json
from pathlib import Path
import csv

SAMPLE_DIR = Path("test_sample")
OUTPUT_PATH = Path("stt_gap_analysis.csv")

rows = []

for path in sorted(SAMPLE_DIR.glob("*_stt.json")):

    file_id = path.stem.replace("_stt", "")

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    segments = data.get("stt_data", {}).get("segments", [])

    segments = sorted(
        segments,
        key=lambda x: x.get("start_ms", 0)
    )

    gaps = []

    for prev, curr in zip(segments, segments[1:]):

        prev_end = prev.get("end_ms")
        curr_start = curr.get("start_ms")

        if prev_end is None or curr_start is None:
            continue

        gap_ms = curr_start - prev_end

        if gap_ms > 0:
            gaps.append({
                "gap_ms": gap_ms,
                "prev_end_ms": prev_end,
                "next_start_ms": curr_start,
                "prev_speaker": prev.get("speaker"),
                "next_speaker": curr.get("speaker"),
                "prev_text": prev.get("text", ""),
                "next_text": curr.get("text", ""),
            })

    gaps.sort(
        key=lambda x: x["gap_ms"],
        reverse=True
    )

    max_gap = gaps[0] if gaps else None

    row = {
        "file_id": file_id,
        "segment_count": len(segments),
        "max_gap_ms": max_gap["gap_ms"] if max_gap else 0,
        "max_gap_sec": round(
            max_gap["gap_ms"] / 1000, 3
        ) if max_gap else 0,
        "gaps_over_3s": sum(
            g["gap_ms"] >= 3000 for g in gaps
        ),
        "gaps_over_5s": sum(
            g["gap_ms"] >= 5000 for g in gaps
        ),
        "gaps_over_7s": sum(
            g["gap_ms"] >= 7000 for g in gaps
        ),
        "prev_text": max_gap["prev_text"] if max_gap else "",
        "next_text": max_gap["next_text"] if max_gap else "",
    }

    rows.append(row)


rows.sort(
    key=lambda x: x["max_gap_ms"],
    reverse=True
)


with open(
    OUTPUT_PATH,
    "w",
    newline="",
    encoding="utf-8-sig",
) as f:

    writer = csv.DictWriter(
        f,
        fieldnames=rows[0].keys()
    )

    writer.writeheader()
    writer.writerows(rows)


print("=" * 80)
print("STT GAP 분석 결과")
print("=" * 80)

for row in rows:
    print(
        f"{row['file_id']:>4} | "
        f"max={row['max_gap_sec']:>7.3f}s | "
        f">3s={row['gaps_over_3s']:>3} | "
        f">5s={row['gaps_over_5s']:>3} | "
        f">7s={row['gaps_over_7s']:>3}"
    )

print()
print("저장:", OUTPUT_PATH)