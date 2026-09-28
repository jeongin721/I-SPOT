import json
import csv
from pathlib import Path
from statistics import mean

SAMPLE_DIR = Path("test_sample")
OUTPUT_PATH = Path("gap_feature_table.csv")


def avg_confidence(segment):
    words = segment.get("words", [])
    values = [
        w.get("confidence")
        for w in words
        if isinstance(w.get("confidence"), (int, float))
    ]

    if not values:
        return None

    return mean(values)


def last_word_confidence(segment):
    words = segment.get("words", [])

    for word in reversed(words):
        conf = word.get("confidence")
        if isinstance(conf, (int, float)):
            return conf

    return None


def is_question(text):
    text = (text or "").strip()

    question_patterns = [
        "?",
        "까",
        "니",
        "어?",
        "야?",
        "있어?",
        "했어?",
        "했니?",
        "인가?",
    ]

    return any(
        text.endswith(pattern)
        for pattern in question_patterns
    )


rows = []

for path in sorted(SAMPLE_DIR.glob("*_stt.json")):

    file_id = path.stem.replace("_stt", "")

    with open(
        path,
        "r",
        encoding="utf-8",
    ) as f:
        data = json.load(f)

    segments = (
        data
        .get("stt_data", {})
        .get("segments", [])
    )

    segments = sorted(
        segments,
        key=lambda x: x.get("start_ms", 0)
    )

    for i in range(len(segments) - 1):

        prev = segments[i]
        curr = segments[i + 1]

        prev_end = prev.get("end_ms")
        curr_start = curr.get("start_ms")

        if not isinstance(prev_end, (int, float)):
            continue

        if not isinstance(curr_start, (int, float)):
            continue

        gap_ms = curr_start - prev_end

        if gap_ms <= 0:
            continue

        prev_text = (prev.get("text") or "").strip()
        next_text = (curr.get("text") or "").strip()

        prev_start = prev.get("start_ms", prev_end)
        next_end = curr.get("end_ms", curr_start)

        prev_duration_ms = max(
            0,
            prev_end - prev_start
        )

        next_duration_ms = max(
            0,
            next_end - curr_start
        )

        prev_speaker = prev.get("speaker")
        next_speaker = curr.get("speaker")

        row = {
            "file_id": file_id,

            "gap_index": i,

            "gap_start_ms": prev_end,
            "gap_end_ms": curr_start,
            "gap_ms": gap_ms,
            "gap_sec": round(
                gap_ms / 1000,
                3
            ),

            "prev_speaker": prev_speaker,
            "next_speaker": next_speaker,

            "speaker_change": (
                prev_speaker != next_speaker
            ),

            "prev_duration_sec": round(
                prev_duration_ms / 1000,
                3
            ),

            "next_duration_sec": round(
                next_duration_ms / 1000,
                3
            ),

            "prev_text_len": len(prev_text),
            "next_text_len": len(next_text),

            "prev_word_count": len(
                prev.get("words", [])
            ),

            "next_word_count": len(
                curr.get("words", [])
            ),

            "prev_avg_conf": avg_confidence(prev),
            "prev_last_conf": last_word_confidence(prev),

            "next_avg_conf": avg_confidence(curr),

            "prev_is_question": is_question(
                prev_text
            ),

            "next_is_question": is_question(
                next_text
            ),

            "prev_text": prev_text,
            "next_text": next_text,
        }

        rows.append(row)


rows.sort(
    key=lambda x: x["gap_ms"],
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


print("=" * 100)
print("GAP FEATURE TABLE 생성 완료")
print("=" * 100)
print("전체 gap 수:", len(rows))
print("저장:", OUTPUT_PATH)

print()
print("=" * 100)
print("1354의 270~290초 주변 gap")
print("=" * 100)

target_rows = [
    row
    for row in rows
    if (
        row["file_id"] == "1354"
        and row["gap_start_ms"] >= 268000
        and row["gap_end_ms"] <= 292000
    )
]

for row in sorted(
    target_rows,
    key=lambda x: x["gap_start_ms"]
):
    print()
    print(
        f"GAP: "
        f"{row['gap_start_ms']} "
        f"→ {row['gap_end_ms']} "
        f"({row['gap_sec']} sec)"
    )

    print(
        "speaker:",
        row["prev_speaker"],
        "→",
        row["next_speaker"],
    )

    print(
        "speaker_change:",
        row["speaker_change"]
    )

    print(
        "prev_avg_conf:",
        row["prev_avg_conf"]
    )

    print(
        "prev_last_conf:",
        row["prev_last_conf"]
    )

    print(
        "prev_is_question:",
        row["prev_is_question"]
    )

    print(
        "next_is_question:",
        row["next_is_question"]
    )

    print(
        "prev_text:",
        row["prev_text"]
    )

    print(
        "next_text:",
        row["next_text"]
    )


print()
print("=" * 100)
print("긴 gap 상위 20개")
print("=" * 100)

for row in rows[:20]:

    print(
        f"{row['file_id']} | "
        f"{row['gap_sec']:>7.3f}s | "
        f"{row['prev_speaker']} → "
        f"{row['next_speaker']} | "
        f"change={row['speaker_change']} | "
        f"prev_words={row['prev_word_count']:>2} | "
        f"prev_last_conf={row['prev_last_conf']} | "
        f"prev_Q={row['prev_is_question']} | "
        f"next_Q={row['next_is_question']}"
    )