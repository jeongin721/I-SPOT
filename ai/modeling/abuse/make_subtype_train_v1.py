"""
v4_refined 후보 라벨에서 2차 RoBERTa용 15-label 학습 CSV를 생성한다.
미매칭 positive는 제외하고, major negative와 신뢰 가능한 subtype positive만 학습에 사용한다.
"""

# ============================================================
# 1. Import
# ============================================================

import json
from pathlib import Path
from typing import Dict, List

import pandas as pd
from tqdm import tqdm


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

TRAIN_INPUT = (
    DATASET_DIR
    / "subtype_labeled_train_v4_refined.csv"
)

VALID_INPUT = (
    DATASET_DIR
    / "subtype_labeled_valid_v4_refined.csv"
)

TRAIN_OUTPUT = (
    DATASET_DIR
    / "subtype_train_v1.csv"
)

VALID_OUTPUT = (
    DATASET_DIR
    / "subtype_valid_v1.csv"
)


# ============================================================
# 3. 이번 baseline에서 실제 학습할 15개 subtype
# ============================================================

TRAIN_SUBTYPES = [
    # --------------------------------------------------------
    # 신체학대
    # --------------------------------------------------------
    "physical_direct",
    "physical_object",
    "physical_force",

    # --------------------------------------------------------
    # 정서학대
    # --------------------------------------------------------
    "emotional_verbal",
    "emotional_threat",
    "emotional_restriction",
    "emotional_discrimination",
    "emotional_dv_exposure",
    "emotional_cruelty",

    # --------------------------------------------------------
    # 성학대
    # --------------------------------------------------------
    "sexual_exposure",
    "sexual_molestation",
    "sexual_intercourse",

    # --------------------------------------------------------
    # 방임
    # --------------------------------------------------------
    "neglect_physical",
    "neglect_education",
    "neglect_medical",
]


# ============================================================
# 4. 데이터 부족으로 이번 학습에서만 제외할 4개
# ============================================================

EXCLUDED_RARE_SUBTYPES = [
    "physical_harmful",
    "sexual_simulated",
    "sexual_exploitation",
    "neglect_abandonment",
]


# ============================================================
# 5. Helper
# ============================================================

def binary(value) -> int:
    """CSV 값을 안전하게 0/1 정수로 변환한다."""

    try:
        return int(float(value))

    except (TypeError, ValueError):
        return 0


def clean_text(value) -> str:
    """NaN 및 불필요한 공백을 정리한다."""

    if pd.isna(value):
        return ""

    return " ".join(
        str(value).split()
    )


def get_label_vector(
    row: pd.Series,
) -> List[int]:
    """한 행을 15차원 multi-hot label vector로 변환한다."""

    return [
        binary(
            row.get(
                f"label_{subtype}",
                0,
            )
        )
        for subtype in TRAIN_SUBTYPES
    ]


def has_excluded_rare_label(
    row: pd.Series,
) -> bool:
    """이번 학습에서 제외한 희소 subtype이 존재하는지 확인한다."""

    return any(
        binary(
            row.get(
                f"label_{subtype}",
                0,
            )
        )
        == 1
        for subtype in EXCLUDED_RARE_SUBTYPES
    )


# ============================================================
# 6. 입력 컬럼 검증
# ============================================================

def validate_columns(
    df: pd.DataFrame,
):
    """학습 데이터 생성에 필요한 컬럼이 존재하는지 확인한다."""

    required_columns = [
        "qa_text",
        "major_positive",
    ]

    required_columns += [
        f"label_{subtype}"
        for subtype in TRAIN_SUBTYPES
    ]

    required_columns += [
        f"label_{subtype}"
        for subtype in EXCLUDED_RARE_SUBTYPES
    ]

    missing_columns = [
        column
        for column in required_columns
        if column not in df.columns
    ]

    if missing_columns:

        raise ValueError(
            "필수 컬럼 누락: "
            + ", ".join(missing_columns)
        )


# ============================================================
# 7. 한 Split 학습 데이터 생성
# ============================================================

def build_training_data(
    input_path: Path,
    output_path: Path,
    split: str,
) -> Dict[str, int]:
    """
    학습 포함 규칙

    1. major_positive == 0
       -> 정상 negative로 포함

    2. major_positive == 1 + 15-label 중 하나 이상 positive
       -> positive로 포함

    3. major_positive == 1 + 15-label 모두 0
       -> subtype 미확정이므로 제외

    4. 희소 4개만 positive인 경우
       -> 절대 negative로 바꾸지 않고 제외
    """

    df = pd.read_csv(
        input_path
    )

    validate_columns(
        df
    )

    output_rows = []

    stats = {
        "input_rows": len(df),
        "included_positive": 0,
        "included_negative": 0,
        "excluded_unmatched_positive": 0,
        "excluded_rare_only_positive": 0,
        "excluded_empty_text": 0,
    }

    # ========================================================
    # 행 단위 처리
    # ========================================================

    for _, row in tqdm(
        df.iterrows(),
        total=len(df),
        desc=f"{split} 학습 데이터 생성",
    ):

        text = clean_text(
            row.get(
                "qa_text",
                "",
            )
        )

        if not text:

            stats[
                "excluded_empty_text"
            ] += 1

            continue

        major_positive = binary(
            row.get(
                "major_positive",
                0,
            )
        )

        label_vector = get_label_vector(
            row
        )

        train_positive = (
            sum(label_vector) > 0
        )

        rare_positive = (
            has_excluded_rare_label(
                row
            )
        )

        # ----------------------------------------------------
        # 대분류 Positive
        # ----------------------------------------------------

        if major_positive == 1:

            if train_positive:

                stats[
                    "included_positive"
                ] += 1

            else:

                if rare_positive:

                    stats[
                        "excluded_rare_only_positive"
                    ] += 1

                else:

                    stats[
                        "excluded_unmatched_positive"
                    ] += 1

                continue

        # ----------------------------------------------------
        # 대분류 Negative
        # ----------------------------------------------------

        else:

            # major negative인데 subtype positive가 존재하면
            # 데이터 모순이므로 학습에서 제외한다.
            if (
                train_positive
                or rare_positive
            ):

                continue

            stats[
                "included_negative"
            ] += 1

        # ----------------------------------------------------
        # 최종 학습 행
        # ----------------------------------------------------

        output_rows.append(
            {
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
                "text": text,
                "label": json.dumps(
                    label_vector,
                    ensure_ascii=False,
                ),
            }
        )

    # ========================================================
    # DataFrame 생성
    # ========================================================

    output_df = pd.DataFrame(
        output_rows
    )

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_df.to_csv(
        output_path,
        index=False,
        encoding="utf-8-sig",
    )

    stats[
        "output_rows"
    ] = len(output_df)

    return stats


# ============================================================
# 8. 생성 결과 라벨 분포 확인
# ============================================================

def analyze_output(
    output_path: Path,
    split: str,
):
    """생성된 CSV의 15개 positive 라벨 개수를 확인한다."""

    df = pd.read_csv(
        output_path
    )

    counts = {
        subtype: 0
        for subtype in TRAIN_SUBTYPES
    }

    multi_label_rows = 0

    for label_text in df["label"]:

        labels = json.loads(
            label_text
        )

        if sum(labels) > 1:
            multi_label_rows += 1

        for index, value in enumerate(
            labels
        ):

            if value == 1:

                subtype = TRAIN_SUBTYPES[
                    index
                ]

                counts[subtype] += 1

    print()
    print("-" * 70)
    print(f"{split.upper()} 15-LABEL DISTRIBUTION")
    print("-" * 70)

    for subtype in TRAIN_SUBTYPES:

        print(
            f"{subtype:30s}: "
            f"{counts[subtype]}"
        )

    print(
        f"\nMulti-label rows: {multi_label_rows}"
    )


# ============================================================
# 9. 통계 출력
# ============================================================

def print_stats(
    stats: Dict[str, int],
    split: str,
):
    """필요한 생성 통계만 간단히 출력한다."""

    print()
    print("=" * 70)
    print(f"{split.upper()} TRAINING DATA")
    print("=" * 70)

    print(
        f"입력 행                : "
        f"{stats['input_rows']}"
    )

    print(
        f"Positive 포함          : "
        f"{stats['included_positive']}"
    )

    print(
        f"Negative 포함          : "
        f"{stats['included_negative']}"
    )

    print(
        f"미매칭 Positive 제외   : "
        f"{stats['excluded_unmatched_positive']}"
    )

    print(
        f"희소 subtype-only 제외 : "
        f"{stats['excluded_rare_only_positive']}"
    )

    print(
        f"빈 텍스트 제외         : "
        f"{stats['excluded_empty_text']}"
    )

    print(
        f"최종 학습 행           : "
        f"{stats['output_rows']}"
    )


# ============================================================
# 10. Main
# ============================================================

def main():

    # --------------------------------------------------------
    # Train
    # --------------------------------------------------------

    train_stats = build_training_data(
        input_path=TRAIN_INPUT,
        output_path=TRAIN_OUTPUT,
        split="train",
    )

    print_stats(
        stats=train_stats,
        split="train",
    )

    analyze_output(
        output_path=TRAIN_OUTPUT,
        split="train",
    )

    # --------------------------------------------------------
    # Validation
    # --------------------------------------------------------

    valid_stats = build_training_data(
        input_path=VALID_INPUT,
        output_path=VALID_OUTPUT,
        split="valid",
    )

    print_stats(
        stats=valid_stats,
        split="valid",
    )

    analyze_output(
        output_path=VALID_OUTPUT,
        split="valid",
    )

    # --------------------------------------------------------
    # 완료
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("2차 RoBERTa 학습 데이터 생성 완료")
    print("=" * 70)

    print(
        f"Train: {TRAIN_OUTPUT}"
    )

    print(
        f"Valid: {VALID_OUTPUT}"
    )

    print()
    print(
        "Label order:"
    )

    for index, subtype in enumerate(
        TRAIN_SUBTYPES
    ):

        print(
            f"{index:2d}: {subtype}"
        )


if __name__ == "__main__":
    main()
