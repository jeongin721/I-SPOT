"""
AI-Hub 세부유형 후보 라벨링에서 review_required로 분류된 사례를 분석한다.
대분류별 미매칭 사례와 실제 아동 발화를 추출하여 세부유형 라벨링 규칙 개선에 사용한다.
"""

# ============================================================
# 1. Import
# ============================================================

import ast
from pathlib import Path
from typing import List

import pandas as pd
from tqdm import tqdm

from ai.modeling.abuse.subtype_label_config import (
    SUBTYPE_LABELS,
)


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

TRAIN_INPUT = DATASET_DIR / "subtype_labeled_train_v1.csv"
VALID_INPUT = DATASET_DIR / "subtype_labeled_valid_v1.csv"

TRAIN_OUTPUT = DATASET_DIR / "subtype_unmatched_train_v1.csv"
VALID_OUTPUT = DATASET_DIR / "subtype_unmatched_valid_v1.csv"


# ============================================================
# 3. 대분류 설정
# ============================================================

MAJOR_CONFIG = {
    "신체학대": {
        "major_column": "label_physical",
        "answer_column": "physical_answers",
    },
    "정서학대": {
        "major_column": "label_emotional",
        "answer_column": "emotional_answers",
    },
    "성학대": {
        "major_column": "label_sexual",
        "answer_column": "sexual_answers",
    },
    "방임": {
        "major_column": "label_neglect",
        "answer_column": "neglect_answers",
    },
}


# ============================================================
# 4. 문자열 리스트 복원
# ============================================================

def parse_answer_list(value) -> List[str]:
    """
    CSV에 문자열로 저장된 AI-Hub 답변 리스트를 복원한다.
    """

    if pd.isna(value):
        return []

    if isinstance(value, list):
        return [
            str(item).strip()
            for item in value
            if str(item).strip()
        ]

    try:
        parsed = ast.literal_eval(str(value))

        if isinstance(parsed, list):
            return [
                str(item).strip()
                for item in parsed
                if str(item).strip()
            ]

    except (ValueError, SyntaxError):
        pass

    text = str(value).strip()

    return [text] if text else []


# ============================================================
# 5. 해당 대분류의 subtype 탐지 여부
# ============================================================

def has_subtype_match(
    row: pd.Series,
    major_name: str,
) -> bool:
    """
    특정 대분류에 속하는 세부유형 중 하나라도
    현재 후보 라벨이 1인지 확인한다.
    """

    for subtype in SUBTYPE_LABELS[major_name]:

        column = f"label_{subtype}"

        if int(row.get(column, 0)) == 1:
            return True

    return False


# ============================================================
# 6. 미매칭 사례 추출
# ============================================================

def extract_unmatched_cases(
    dataframe: pd.DataFrame,
    split: str,
) -> pd.DataFrame:
    """
    대분류는 positive지만 해당 대분류의 세부유형이
    하나도 잡히지 않은 사례를 대분류별 한 행으로 추출한다.

    하나의 case가 여러 대분류에서 미매칭이면
    결과 CSV에 여러 행으로 존재할 수 있다.
    """

    rows = []

    review_dataframe = dataframe[
        dataframe["review_required"] == 1
    ]

    for _, row in tqdm(
        review_dataframe.iterrows(),
        total=len(review_dataframe),
        desc=f"{split} 미매칭 분석",
    ):

        for major_name, config in MAJOR_CONFIG.items():

            major_positive = int(
                row.get(
                    config["major_column"],
                    0,
                )
            )

            if major_positive != 1:
                continue

            # 이미 subtype이 잡힌 대분류는 제외
            if has_subtype_match(
                row,
                major_name,
            ):
                continue

            answers = parse_answer_list(
                row.get(
                    config["answer_column"],
                    "",
                )
            )

            rows.append(
                {
                    "case_id": row.get(
                        "case_id",
                        "",
                    ),

                    "split": split,

                    "major_label": major_name,

                    # 해당 대분류의 실제 AI-Hub 아동 답변
                    "answers": " || ".join(
                        answers
                    ),

                    "answer_count": len(
                        answers
                    ),

                    # 전체 A 발화도 비교용으로 보존
                    "all_child_text": row.get(
                        "all_child_text",
                        "",
                    ),

                    "source_file": row.get(
                        "source_file",
                        "",
                    ),
                }
            )

    return pd.DataFrame(rows)


# ============================================================
# 7. 유형별 실제 발화 샘플 출력
# ============================================================

def print_samples(
    dataframe: pd.DataFrame,
    sample_count: int = 10,
):
    """
    각 대분류에서 현재 세부유형 규칙이 놓친
    실제 AI-Hub 발화를 터미널에 일부 출력한다.
    """

    print()
    print("=" * 70)
    print("대분류별 미매칭 발화 샘플")
    print("=" * 70)

    for major_name in MAJOR_CONFIG:

        subset = dataframe[
            dataframe["major_label"]
            == major_name
        ]

        print()
        print(
            f"[{major_name}] "
            f"미매칭 {len(subset)}건"
        )

        if len(subset) == 0:
            continue

        # 재현 가능한 샘플
        sample = subset.sample(
            n=min(
                sample_count,
                len(subset),
            ),
            random_state=42,
        )

        for number, (_, row) in enumerate(
            sample.iterrows(),
            start=1,
        ):

            text = str(
                row["answers"]
            ).strip()

            if not text:
                text = "[학대여부 A 발화 없음]"

            print(
                f"{number:02d}. "
                f"{text[:500]}"
            )


# ============================================================
# 8. Split 분석
# ============================================================

def analyze_split(
    input_path: Path,
    output_path: Path,
    split: str,
):
    """
    한 split의 미매칭 사례를 분석하고 CSV로 저장한다.
    """

    print()
    print("=" * 70)
    print(f"{split.upper()} review 분석")
    print(f"입력: {input_path}")
    print("=" * 70)

    dataframe = pd.read_csv(
        input_path
    )

    unmatched = extract_unmatched_cases(
        dataframe,
        split,
    )

    unmatched.to_csv(
        output_path,
        index=False,
        encoding="utf-8-sig",
    )

    print()
    print(
        f"review_required 사례 수: "
        f"{int(dataframe['review_required'].sum())}"
    )

    print(
        f"미매칭 대분류 행 수: "
        f"{len(unmatched)}"
    )

    print()
    print("[대분류별 미매칭 수]")

    if len(unmatched) > 0:

        counts = (
            unmatched["major_label"]
            .value_counts()
        )

        for major_name in MAJOR_CONFIG:

            print(
                f"{major_name:10s}: "
                f"{int(counts.get(major_name, 0))}"
            )

    print_samples(
        unmatched,
        sample_count=10,
    )

    print()
    print(
        f"분석 CSV 저장: {output_path}"
    )


# ============================================================
# 9. Main
# ============================================================

def main():

    analyze_split(
        TRAIN_INPUT,
        TRAIN_OUTPUT,
        "train",
    )

    analyze_split(
        VALID_INPUT,
        VALID_OUTPUT,
        "valid",
    )


if __name__ == "__main__":
    main()