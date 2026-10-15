"""
최종 2차 세부유형 후보 데이터의 19개 라벨 분포를 확인한다.
Train/Valid 개수와 희소 라벨 경고만 간결하게 출력한다.
"""

# ============================================================
# 1. Import
# ============================================================

from pathlib import Path
from typing import Dict

import pandas as pd

from ai.modeling.abuse.subtype_label_config import ALL_SUBTYPE_LABELS


# ============================================================
# 2. 경로
# ============================================================

BASE_DIR = Path("/data/I-SPOT")

DATASET_DIR = (
    BASE_DIR
    / "ai"
    / "modeling"
    / "abuse"
    / "datasets"
)

TRAIN_PATH = (
    DATASET_DIR
    / "subtype_labeled_train_v4_refined.csv"
)

VALID_PATH = (
    DATASET_DIR
    / "subtype_labeled_valid_v4_refined.csv"
)


# ============================================================
# 3. 희소 라벨 기준
# ============================================================

# Train 10건 미만:
# 현재 상태로는 독립 label 학습이 매우 불안정할 가능성이 높음.
VERY_RARE_THRESHOLD = 10

# Train 30건 미만:
# 학습은 가능하더라도 성능 해석에 주의가 필요한 수준.
RARE_THRESHOLD = 30


# ============================================================
# 4. Helper
# ============================================================

def normalize_binary(series: pd.Series) -> pd.Series:
    """라벨 컬럼을 안전하게 0/1 정수형으로 변환한다."""

    return (
        pd.to_numeric(
            series,
            errors="coerce",
        )
        .fillna(0)
        .astype(int)
    )


# ============================================================
# 5. 라벨 분포 계산
# ============================================================

def get_label_counts(
    df: pd.DataFrame,
) -> Dict[str, int]:
    """19개 subtype별 positive 개수를 계산한다."""

    counts: Dict[str, int] = {}

    for subtype in ALL_SUBTYPE_LABELS:

        column = f"label_{subtype}"

        if column not in df.columns:
            raise ValueError(
                f"필수 라벨 컬럼 없음: {column}"
            )

        counts[subtype] = int(
            normalize_binary(
                df[column]
            ).sum()
        )

    return counts


# ============================================================
# 6. 상태 판정
# ============================================================

def get_status(
    train_count: int,
    valid_count: int,
) -> str:
    """라벨별 데이터 충분도를 간단히 표시한다."""

    if train_count == 0:
        return "❌ TRAIN 0"

    if valid_count == 0:
        return "⚠ VALID 0"

    if train_count < VERY_RARE_THRESHOLD:
        return "⚠ 매우 희소"

    if train_count < RARE_THRESHOLD:
        return "△ 희소"

    return "OK"


# ============================================================
# 7. 결과 출력
# ============================================================

def print_distribution(
    train_counts: Dict[str, int],
    valid_counts: Dict[str, int],
):
    """최종 19개 라벨 분포를 한 번에 출력한다."""

    print()
    print("=" * 85)
    print("FINAL SUBTYPE LABEL DISTRIBUTION")
    print("=" * 85)

    print(
        f"{'subtype':30s} "
        f"{'train':>7s} "
        f"{'valid':>7s} "
        f"{'status':>12s}"
    )

    print("-" * 85)

    for subtype in ALL_SUBTYPE_LABELS:

        train_count = train_counts[subtype]
        valid_count = valid_counts[subtype]

        status = get_status(
            train_count=train_count,
            valid_count=valid_count,
        )

        print(
            f"{subtype:30s} "
            f"{train_count:7d} "
            f"{valid_count:7d} "
            f"{status:>12s}"
        )


# ============================================================
# 8. 요약 경고
# ============================================================

def print_warning_summary(
    train_counts: Dict[str, int],
    valid_counts: Dict[str, int],
):
    """학습 전 반드시 볼 희소 라벨만 따로 요약한다."""

    train_zero = []
    valid_zero = []
    very_rare = []
    rare = []

    for subtype in ALL_SUBTYPE_LABELS:

        train_count = train_counts[subtype]
        valid_count = valid_counts[subtype]

        if train_count == 0:
            train_zero.append(subtype)

        if valid_count == 0:
            valid_zero.append(subtype)

        if (
            train_count > 0
            and train_count < VERY_RARE_THRESHOLD
        ):
            very_rare.append(subtype)

        elif (
            train_count >= VERY_RARE_THRESHOLD
            and train_count < RARE_THRESHOLD
        ):
            rare.append(subtype)

    print()
    print("=" * 85)
    print("학습 전 경고")
    print("=" * 85)

    print(
        "TRAIN 0 : "
        + (
            ", ".join(train_zero)
            if train_zero
            else "없음"
        )
    )

    print(
        "VALID 0 : "
        + (
            ", ".join(valid_zero)
            if valid_zero
            else "없음"
        )
    )

    print(
        "TRAIN 10건 미만 : "
        + (
            ", ".join(very_rare)
            if very_rare
            else "없음"
        )
    )

    print(
        "TRAIN 30건 미만 : "
        + (
            ", ".join(rare)
            if rare
            else "없음"
        )
    )


# ============================================================
# 9. 전체 데이터 요약
# ============================================================

def print_dataset_summary(
    train_df: pd.DataFrame,
    valid_df: pd.DataFrame,
):
    """데이터 행 수와 subtype 매칭 여부만 출력한다."""

    print()
    print("=" * 85)
    print("DATASET SUMMARY")
    print("=" * 85)

    print(
        f"Train rows : {len(train_df)}"
    )

    print(
        f"Valid rows : {len(valid_df)}"
    )

    if "major_positive" in train_df.columns:
        train_major_positive = int(
            normalize_binary(
                train_df["major_positive"]
            ).sum()
        )

        print(
            f"Train major positive : "
            f"{train_major_positive}"
        )

    if "major_positive" in valid_df.columns:
        valid_major_positive = int(
            normalize_binary(
                valid_df["major_positive"]
            ).sum()
        )

        print(
            f"Valid major positive : "
            f"{valid_major_positive}"
        )

    if "matched_subtype_count" in train_df.columns:

        train_matched = int(
            (
                pd.to_numeric(
                    train_df[
                        "matched_subtype_count"
                    ],
                    errors="coerce",
                )
                .fillna(0)
                > 0
            ).sum()
        )

        print(
            f"Train subtype matched rows : "
            f"{train_matched}"
        )

    if "matched_subtype_count" in valid_df.columns:

        valid_matched = int(
            (
                pd.to_numeric(
                    valid_df[
                        "matched_subtype_count"
                    ],
                    errors="coerce",
                )
                .fillna(0)
                > 0
            ).sum()
        )

        print(
            f"Valid subtype matched rows : "
            f"{valid_matched}"
        )


# ============================================================
# 10. Main
# ============================================================

def main():

    train_df = pd.read_csv(
        TRAIN_PATH
    )

    valid_df = pd.read_csv(
        VALID_PATH
    )

    train_counts = get_label_counts(
        train_df
    )

    valid_counts = get_label_counts(
        valid_df
    )

    print_dataset_summary(
        train_df=train_df,
        valid_df=valid_df,
    )

    print_distribution(
        train_counts=train_counts,
        valid_counts=valid_counts,
    )

    print_warning_summary(
        train_counts=train_counts,
        valid_counts=valid_counts,
    )


if __name__ == "__main__":
    main()