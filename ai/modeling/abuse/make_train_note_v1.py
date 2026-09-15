"""
LLM으로 생성한 상담일지 문체 CSV(counseling_note_train_v1.csv /
counseling_note_valid_v1.csv)를 note 전용 1차 모델 학습용
audio_text/label 형식으로 변환한다.
"""

import ast
import csv
import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

LABEL_NAMES = [
    "신체학대",
    "정서학대",
    "성학대",
    "방임",
]

SOURCE_FILES = {
    "train": BASE_DIR / "datasets" / "counseling_note_train_v1.csv",
    "valid": BASE_DIR / "datasets" / "counseling_note_valid_v1.csv",
}

OUTPUT_FILES = {
    "train": BASE_DIR / "datasets" / "train_note_v1.csv",
    "valid": BASE_DIR / "datasets" / "valid_note_v1.csv",
}

OUTPUT_COLUMNS = [
    "case_id",
    "audio_text",
    "label",
    "reference_abuse_label",
]


def build_multihot_label(
    reference_abuse_label: str,
):
    """
    reference_abuse_label 문자열을 4대 유형 멀티핫 라벨로 변환한다.

    "(해당 없음)"은 전부 0으로, 콤마/슬래시로 여러 유형이 나열된
    경우에는 해당하는 인덱스를 전부 1로 표시한다.
    """

    label = [0] * len(LABEL_NAMES)

    if not reference_abuse_label:
        return label

    parts = (
        reference_abuse_label
        .replace("/", ",")
        .split(",")
    )

    for part in parts:
        part = part.strip()

        if part in LABEL_NAMES:
            label[LABEL_NAMES.index(part)] = 1

    return label


def convert_split(
    split_name: str,
):
    source_path = SOURCE_FILES[split_name]
    output_path = OUTPUT_FILES[split_name]

    if not source_path.exists():
        print(
            f"[SKIP] {split_name}: "
            f"{source_path} 없음"
        )
        return

    with source_path.open(
        encoding="utf-8-sig",
    ) as f:
        rows = list(
            csv.DictReader(f)
        )

    output_rows = []

    label_counts = [0] * len(LABEL_NAMES)
    empty_note_count = 0

    for row in rows:
        note_text = (
            row.get(
                "counseling_note",
                "",
            )
            or ""
        ).strip()

        if not note_text:
            empty_note_count += 1
            continue

        label = build_multihot_label(
            row.get(
                "reference_abuse_label",
                "",
            )
        )

        for i, value in enumerate(label):
            label_counts[i] += value

        output_rows.append(
            {
                "case_id": row.get(
                    "case_id",
                    "",
                ),
                "audio_text": note_text,
                "label": json.dumps(label),
                "reference_abuse_label": row.get(
                    "reference_abuse_label",
                    "",
                ),
            }
        )

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with output_path.open(
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as f:
        writer = csv.DictWriter(
            f,
            fieldnames=OUTPUT_COLUMNS,
        )

        writer.writeheader()
        writer.writerows(output_rows)

    print(
        f"[{split_name.upper()}] "
        f"{len(output_rows)}건 저장 -> {output_path}"
    )

    if empty_note_count:
        print(
            f"  (counseling_note 비어있어 제외: "
            f"{empty_note_count}건)"
        )

    for name, count in zip(
        LABEL_NAMES,
        label_counts,
    ):
        print(
            f"  {name:<6}: {count}"
        )


if __name__ == "__main__":
    for split_name in ("train", "valid"):
        convert_split(split_name)
        print()
