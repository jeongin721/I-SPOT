import csv
import json
import difflib
import re
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
SAMPLE_DIR = BASE_DIR / "test_sample"

FILE_ID = "1354"

GT_PATH = SAMPLE_DIR / f"{FILE_ID}.json"
STT_PATH = SAMPLE_DIR / f"{FILE_ID}_stt.json"

ROLE_PATH = BASE_DIR / "speaker_role_mapping_results.csv"


def collect_gt_a(obj):
    texts = []

    if isinstance(obj, dict):

        if (
            obj.get("type") == "A"
            and obj.get("text")
        ):
            texts.append(
                str(obj["text"]).strip()
            )

        for value in obj.values():
            texts.extend(
                collect_gt_a(value)
            )

    elif isinstance(obj, list):

        for item in obj:
            texts.extend(
                collect_gt_a(item)
            )

    return texts


def get_a_speakers():

    speakers = []

    with open(
        ROLE_PATH,
        "r",
        encoding="utf-8-sig",
    ) as f:

        reader = csv.DictReader(f)

        for row in reader:

            if (
                row["file"] == FILE_ID
                and row["role"] == "A"
            ):
                speakers.append(
                    row["speaker"]
                )

    return speakers


def normalize(text):
    return re.sub(
        r"\s+",
        "",
        str(text),
    )


# ------------------------------------------------------------
# GT
# ------------------------------------------------------------

with open(
    GT_PATH,
    "r",
    encoding="utf-8",
) as f:
    gt_json = json.load(f)

gt_items = collect_gt_a(
    gt_json
)

gt_text = " ".join(
    gt_items
)


# ------------------------------------------------------------
# STT
# ------------------------------------------------------------

a_speakers = get_a_speakers()

with open(
    STT_PATH,
    "r",
    encoding="utf-8",
) as f:
    stt_json = json.load(f)

segments = (
    stt_json
    .get("stt_data", {})
    .get("segments", [])
)

stt_items = [
    str(seg.get("text", "")).strip()
    for seg in segments
    if (
        seg.get("speaker") in a_speakers
        and str(
            seg.get("text", "")
        ).strip()
    )
]

stt_text = " ".join(
    stt_items
)


print("=" * 80)
print("1354 A-text 상세 비교")
print("=" * 80)

print("A Speaker :", a_speakers)
print("GT 발화 수 :", len(gt_items))
print("STT 발화 수:", len(stt_items))
print("GT 길이    :", len(gt_text))
print("STT 길이   :", len(stt_text))


# ------------------------------------------------------------
# 빠진 GT 구간 탐색
# ------------------------------------------------------------

gt_norm = normalize(
    gt_text
)

stt_norm = normalize(
    stt_text
)

matcher = difflib.SequenceMatcher(
    None,
    gt_norm,
    stt_norm,
    autojunk=False,
)

missing_chunks = []

for tag, i1, i2, j1, j2 in matcher.get_opcodes():

    if tag in (
        "delete",
        "replace",
    ):

        gt_chunk = gt_norm[
            i1:i2
        ]

        stt_chunk = stt_norm[
            j1:j2
        ]

        if len(gt_chunk) >= 5:

            missing_chunks.append(
                (
                    len(gt_chunk),
                    tag,
                    gt_chunk,
                    stt_chunk,
                )
            )


missing_chunks.sort(
    reverse=True,
    key=lambda x: x[0],
)


print()
print("=" * 80)
print("GT에는 있지만 STT에서 누락/변경된 큰 구간 TOP 15")
print("=" * 80)

for rank, (
    size,
    tag,
    gt_chunk,
    stt_chunk,
) in enumerate(
    missing_chunks[:15],
    start=1,
):

    print()
    print(
        f"[TOP {rank}] "
        f"{tag} / {size}자"
    )

    print(
        "GT :",
        gt_chunk
    )

    print(
        "STT:",
        stt_chunk
        if stt_chunk
        else "(없음)"
    )