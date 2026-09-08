"""
v3→v4에서 새로 추가된 핵심 세부유형 라벨만 간결하게 검수한다.
성학대·방임 중심 subtype의 신규 건수와 대표 Q+A 근거만 출력한다.
"""

# ============================================================
# 1. Import
# ============================================================

from pathlib import Path
from typing import Dict, List

import pandas as pd
from tqdm import tqdm

from ai.modeling.abuse.subtype_label_config import ALL_SUBTYPE_LABELS


# ============================================================
# 2. 경로 설정
# ============================================================

BASE_DIR = Path("/data/I-SPOT")

DATASET_DIR = (
    BASE_DIR
    / "ai"
    / "modeling"
    / "abuse"
    / "datasets"
)

RESULT_DIR = (
    BASE_DIR
    / "ai"
    / "modeling"
    / "abuse"
    / "results"
)

TRAIN_V3 = DATASET_DIR / "subtype_labeled_train_v3.csv"
TRAIN_V4 = DATASET_DIR / "subtype_labeled_train_v4.csv"

VALID_V3 = DATASET_DIR / "subtype_labeled_valid_v3.csv"
VALID_V4 = DATASET_DIR / "subtype_labeled_valid_v4.csv"


# ============================================================
# 3. 이번에 실제로 검수할 subtype만 지정
# ============================================================

FOCUS_SUBTYPES = [
    "sexual_exposure",
    "sexual_molestation",
    "sexual_simulated",
    "sexual_intercourse",
    "sexual_exploitation",
    "neglect_physical",
    "neglect_medical",
]

# subtype별 대표 사례 3개만 출력
SAMPLE_COUNT = 3


# ============================================================
# 4. Helper
# ============================================================

def clean_text(value) -> str:
    """NaN을 안전한 문자열로 변환한다."""

    if pd.isna(value):
        return ""

    return str(value).strip()


def normalize_binary(value) -> int:
    """CSV 라벨 값을 0/1 정수로 변환한다."""

    try:
        return int(float(value))

    except (TypeError, ValueError):
        return 0


# ============================================================
# 5. v3 / v4 정렬 확인
# ============================================================

def validate_alignment(
    v3: pd.DataFrame,
    v4: pd.DataFrame,
    split: str,
):
    """v3와 v4가 같은 원본 행 순서를 사용하는지 확인한다."""

    if len(v3) != len(v4):

        raise ValueError(
            f"{split}: 행 수 불일치 "
            f"v3={len(v3)}, v4={len(v4)}"
        )

    for column in [
        "case_id",
        "major_section",
        "qa_text",
    ]:

        if (
            column not in v3.columns
            or column not in v4.columns
        ):
            continue

        left = (
            v3[column]
            .fillna("")
            .astype(str)
            .str.strip()
        )

        right = (
            v4[column]
            .fillna("")
            .astype(str)
            .str.strip()
        )

        mismatch = left != right

        if mismatch.any():

            raise ValueError(
                f"{split}: {column} 정렬 불일치 "
                f"{int(mismatch.sum())}건"
            )


# ============================================================
# 6. v3=0 → v4=1 신규 라벨 추출
# ============================================================

def extract_new_labels(
    v3: pd.DataFrame,
    v4: pd.DataFrame,
    split: str,
) -> pd.DataFrame:

    rows: List[dict] = []

    for subtype in tqdm(
        ALL_SUBTYPE_LABELS,
        desc=f"{split} 신규 라벨 확인",
    ):

        label_column = f"label_{subtype}"
        evidence_column = f"evidence_{subtype}"

        if (
            label_column not in v3.columns
            or label_column not in v4.columns
        ):
            continue

        for index in range(len(v4)):

            old_label = normalize_binary(
                v3.iloc[index].get(
                    label_column,
                    0,
                )
            )

            new_label = normalize_binary(
                v4.iloc[index].get(
                    label_column,
                    0,
                )
            )

            if not (
                old_label == 0
                and new_label == 1
            ):
                continue

            row = v4.iloc[index]

            rows.append(
                {
                    "split": split,
                    "row_index": index,
                    "case_id": clean_text(
                        row.get(
                            "case_id",
                            "",
                        )
                    ),
                    "major_section": clean_text(
                        row.get(
                            "major_section",
                            "",
                        )
                    ),
                    "subtype": subtype,
                    "qa_text": clean_text(
                        row.get(
                            "qa_text",
                            "",
                        )
                    ),
                    "evidence": clean_text(
                        row.get(
                            evidence_column,
                            "",
                        )
                    ),
                    "review_reason": clean_text(
                        row.get(
                            "review_reason",
                            "",
                        )
                    ),
                }
            )

    return pd.DataFrame(rows)


# ============================================================
# 7. 전체 신규 라벨 개수만 요약
# ============================================================

def print_summary(
    new_labels: pd.DataFrame,
    split: str,
):
    """전체 subtype 변화량은 숫자만 간단히 출력한다."""

    print()
    print("=" * 70)
    print(f"{split.upper()} V3 → V4 신규 라벨 요약")
    print("=" * 70)

    print(
        f"전체 신규 subtype label: {len(new_labels)}"
    )

    print()

    for subtype in ALL_SUBTYPE_LABELS:

        count = int(
            (
                new_labels["subtype"]
                == subtype
            ).sum()
        )

        if count == 0:
            continue

        print(
            f"{subtype:30s}: {count}"
        )


# ============================================================
# 8. 핵심 subtype만 3개씩 출력
# ============================================================

def print_focus_samples(
    new_labels: pd.DataFrame,
    split: str,
):
    """
    실제 판단에 필요한 성학대/방임 subtype만
    대표 사례 3개씩 출력한다.
    """

    print()
    print("=" * 70)
    print(f"{split.upper()} 핵심 신규 라벨 검수")
    print("=" * 70)

    for subtype in FOCUS_SUBTYPES:

        subset = new_labels[
            new_labels["subtype"]
            == subtype
        ]

        count = len(subset)

        print()
        print("#" * 70)
        print(
            f"{subtype} | 신규 {count}건"
        )
        print("#" * 70)

        if count == 0:
            print("신규 사례 없음")
            continue

        sample_count = min(
            SAMPLE_COUNT,
            count,
        )

        samples = subset.sample(
            n=sample_count,
            random_state=42,
        )

        for number, (_, row) in enumerate(
            samples.iterrows(),
            start=1,
        ):

            print()
            print(
                f"[{number}] case={row['case_id']}"
            )

            print("[근거]")
            print(
                row["evidence"]
                or "(없음)"
            )

            # 전체 Q+A는 너무 길기 때문에
            # 근거가 비어 있을 때만 출력한다.
            if not row["evidence"]:

                print("[전체 Q+A]")
                print(
                    row["qa_text"]
                )

            if row["review_reason"]:

                print("[Review]")
                print(
                    row["review_reason"]
                )


# ============================================================
# 9. 검수 CSV 저장
# ============================================================

def save_review_csv(
    new_labels: pd.DataFrame,
    split: str,
):
    """필요하면 전체 신규 사례를 CSV에서 직접 확인할 수 있게 저장한다."""

    RESULT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    review_df = new_labels.copy()

    review_df["manual_judgment"] = ""
    review_df["manual_note"] = ""

    output_path = (
        RESULT_DIR
        / f"subtype_v4_new_labels_review_{split}.csv"
    )

    review_df.to_csv(
        output_path,
        index=False,
        encoding="utf-8-sig",
    )


# ============================================================
# 10. Split 실행
# ============================================================

def analyze_split(
    v3_path: Path,
    v4_path: Path,
    split: str,
):

    v3 = pd.read_csv(
        v3_path
    )

    v4 = pd.read_csv(
        v4_path
    )

    validate_alignment(
        v3=v3,
        v4=v4,
        split=split,
    )

    new_labels = extract_new_labels(
        v3=v3,
        v4=v4,
        split=split,
    )

    if len(new_labels) == 0:

        print(
            f"{split}: 신규 라벨 없음"
        )

        return

    print_summary(
        new_labels=new_labels,
        split=split,
    )

    print_focus_samples(
        new_labels=new_labels,
        split=split,
    )

    save_review_csv(
        new_labels=new_labels,
        split=split,
    )


# ============================================================
# 11. Main
# ============================================================

def main():

    analyze_split(
        v3_path=TRAIN_V3,
        v4_path=TRAIN_V4,
        split="train",
    )

    analyze_split(
        v3_path=VALID_V3,
        v4_path=VALID_V4,
        split="valid",
    )


if __name__ == "__main__":
    main()