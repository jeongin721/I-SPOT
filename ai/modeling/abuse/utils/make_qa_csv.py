## 상담 질문 & 아동 발화 함께 보기 

import json
from pathlib import Path

import pandas as pd

from ai.modeling.common.consultation_qa_preprocessor import (
    extract_qa_pairs,
)

from ai.modeling.common.consultation_preprocessor import (
    extract_multilabel,
)


# ============================================================
# 경로 설정
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[4]

TRAIN_JSON_DIR = (
    PROJECT_ROOT
    / "data"
    / "abuse"
    / "train"
    / "TL_out_data"
)

VALID_JSON_DIR = (
    PROJECT_ROOT
    / "data"
    / "abuse"
    / "valid"
    / "VL_out_data"
)

OUTPUT_DIR = (
    PROJECT_ROOT
    / "ai"
    / "modeling"
    / "abuse"
    / "datasets"
)

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


# ============================================================
# JSON 1개 처리
# ============================================================

def process_json(json_path: Path):
    with open(
        json_path,
        "r",
        encoding="utf-8",
    ) as f:
        data = json.load(f)

    label = extract_multilabel(data)

    qa_pairs = extract_qa_pairs(data)

    rows = []

    for pair_index, pair in enumerate(qa_pairs):

        text = pair["text"]

        if not text:
            continue

        rows.append(
            {
                "source_file": json_path.name,
                "pair_index": pair_index,
                "question": pair["question"],
                "answer": pair["answer"],
                "text": text,
                "label": label,
            }
        )

    return rows


# ============================================================
# 폴더 전체 처리
# ============================================================

def build_dataset(
    input_dir: Path,
    output_path: Path,
):

    json_files = sorted(
        input_dir.rglob("*.json")
    )

    all_rows = []

    print(
        f"\nJSON files: {len(json_files)}"
    )

    for index, json_path in enumerate(
        json_files,
        start=1,
    ):

        try:
            rows = process_json(
                json_path
            )

            all_rows.extend(rows)

        except Exception as e:

            print(
                f"[ERROR] {json_path.name}: {e}"
            )

        if index % 100 == 0:
            print(
                f"processed: "
                f"{index}/{len(json_files)}"
            )

    df = pd.DataFrame(
        all_rows
    )

    df.to_csv(
        output_path,
        index=False,
        encoding="utf-8-sig",
    )

    print()
    print("==============================")
    print("Dataset created")
    print("==============================")

    print(
        "Output:",
        output_path,
    )

    print(
        "Rows:",
        len(df),
    )

    print(
        "Unique cases:",
        df["source_file"].nunique()
        if not df.empty
        else 0,
    )

    return df


# ============================================================
# 실행
# ============================================================

if __name__ == "__main__":

    print(
        "===== TRAIN QA DATA ====="
    )

    train_df = build_dataset(
        TRAIN_JSON_DIR,
        OUTPUT_DIR
        / "train_multilabel_qa.csv",
    )

    print()
    print(
        "===== VALID QA DATA ====="
    )

    valid_df = build_dataset(
        VALID_JSON_DIR,
        OUTPUT_DIR
        / "valid_multilabel_qa.csv",
    )

    # ------------------------------------------
    # 생성 결과 일부 확인
    # ------------------------------------------

    print()
    print(
        "===== QA SAMPLE ====="
    )

    if not train_df.empty:

        for i in range(
            min(5, len(train_df))
        ):

            row = train_df.iloc[i]

            print()
            print(
                f"[Sample {i + 1}]"
            )
            print(
                "Q:",
                row["question"],
            )
            print(
                "A:",
                row["answer"],
            )
            print(
                "Text:",
                row["text"],
            )
            print(
                "Label:",
                row["label"],
            )