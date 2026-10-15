"""
2차 Q+A 기반 subtype v2 후보 라벨의 품질을 점검한다.
Subtype별 자동 라벨 샘플과 대분류별 미매칭 사례를 출력·저장하여 오라벨과 패턴 누락을 검토한다.
"""

# ============================================================
# 1. Import
# ============================================================

from pathlib import Path
from typing import List

import pandas as pd
from tqdm import tqdm

from ai.modeling.abuse.subtype_label_config import (
    ALL_SUBTYPE_LABELS,
    SUBTYPE_DISPLAY_NAMES,
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

RESULT_DIR = (
    BASE_DIR
    / "ai"
    / "modeling"
    / "abuse"
    / "results"
)

TRAIN_INPUT = DATASET_DIR / "subtype_labeled_train_v2.csv"
VALID_INPUT = DATASET_DIR / "subtype_labeled_valid_v2.csv"

TRAIN_SAMPLE_OUTPUT = RESULT_DIR / "subtype_v2_label_samples_train.csv"
VALID_SAMPLE_OUTPUT = RESULT_DIR / "subtype_v2_label_samples_valid.csv"

TRAIN_UNMATCHED_OUTPUT = RESULT_DIR / "subtype_v2_unmatched_train.csv"
VALID_UNMATCHED_OUTPUT = RESULT_DIR / "subtype_v2_unmatched_valid.csv"


# ============================================================
# 3. 검사 설정
# ============================================================

DEFAULT_SAMPLE_COUNT = 10

# Q 문맥 사용으로 오라벨 가능성을 특히 확인할 subtype
FOCUS_SAMPLE_COUNT = {
    "sexual_exposure": 20,
    "sexual_molestation": 20,
    "sexual_intercourse": 20,
    "neglect_physical": 20,
}

# 미매칭 사례를 많이 확인할 대분류
UNMATCHED_SAMPLE_COUNT = {
    "신체학대": 10,
    "정서학대": 20,
    "성학대": 20,
    "방임": 20,
}


# ============================================================
# 4. 출력용 텍스트 정리
# ============================================================

def clean_display_text(value) -> str:
    """
    NaN 등을 빈 문자열로 바꾸고 콘솔 출력용 문자열로 정리한다.
    """

    if pd.isna(value):
        return ""

    return str(value).strip()


# ============================================================
# 5. subtype별 자동 라벨 샘플 수집
# ============================================================

def collect_subtype_samples(
    dataframe: pd.DataFrame,
    split: str,
) -> pd.DataFrame:
    """
    각 subtype이 1로 자동 라벨된 사례에서 검토용 샘플을 수집한다.

    무작위 추출 대신 고정 random_state를 사용해
    반복 실행 시 동일한 검수 샘플을 얻도록 한다.
    """

    rows: List[dict] = []

    print()
    print("=" * 80)
    print(f"{split.upper()} - SUBTYPE 자동 라벨 샘플")
    print("=" * 80)

    for subtype in tqdm(
        ALL_SUBTYPE_LABELS,
        desc=f"{split} subtype 샘플 수집",
    ):

        label_column = f"label_{subtype}"
        evidence_column = f"evidence_{subtype}"

        if label_column not in dataframe.columns:
            continue

        positives = dataframe[
            dataframe[label_column] == 1
        ].copy()

        total_positive = len(positives)

        display_name = SUBTYPE_DISPLAY_NAMES.get(
            subtype,
            subtype,
        )

        print()
        print("-" * 80)
        print(
            f"{subtype} / {display_name} "
            f"(전체 후보={total_positive})"
        )
        print("-" * 80)

        if total_positive == 0:
            print("후보 없음")
            continue

        sample_count = FOCUS_SAMPLE_COUNT.get(
            subtype,
            DEFAULT_SAMPLE_COUNT,
        )

        sample_count = min(
            sample_count,
            total_positive,
        )

        samples = positives.sample(
            n=sample_count,
            random_state=42,
        )

        for sample_number, (_, row) in enumerate(
            samples.iterrows(),
            start=1,
        ):

            qa_text = clean_display_text(
                row.get("qa_text", "")
            )

            evidence = clean_display_text(
                row.get(evidence_column, "")
            )

            case_id = clean_display_text(
                row.get("case_id", "")
            )

            major_section = clean_display_text(
                row.get("major_section", "")
            )

            print()
            print(
                f"[{sample_number}] "
                f"case={case_id} / "
                f"major={major_section}"
            )

            print("[Q+A]")
            print(qa_text)

            print("[자동 근거]")
            print(
                evidence
                if evidence
                else "(근거 없음)"
            )

            rows.append(
                {
                    "split": split,
                    "subtype": subtype,
                    "subtype_name": display_name,
                    "case_id": case_id,
                    "major_section": major_section,
                    "qa_text": qa_text,
                    "evidence": evidence,
                    "source_file": clean_display_text(
                        row.get(
                            "source_file",
                            "",
                        )
                    ),
                }
            )

    return pd.DataFrame(rows)


# ============================================================
# 6. 대분류 Positive인데 subtype이 없는 사례 수집
# ============================================================

def collect_unmatched_samples(
    dataframe: pd.DataFrame,
    split: str,
) -> pd.DataFrame:
    """
    AI-Hub 대분류 GT는 Positive지만 subtype 후보가 하나도
    생성되지 않은 사례를 대분류별로 수집한다.
    """

    rows: List[dict] = []

    print()
    print("=" * 80)
    print(f"{split.upper()} - POSITIVE MAJOR 미매칭 샘플")
    print("=" * 80)

    for major_name, sample_count in UNMATCHED_SAMPLE_COUNT.items():

        unmatched = dataframe[
            (dataframe["major_section"] == major_name)
            & (dataframe["major_positive"] == 1)
            & (dataframe["matched_subtype_count"] == 0)
        ].copy()

        total_unmatched = len(unmatched)

        print()
        print("#" * 80)
        print(
            f"{major_name} "
            f"(미매칭={total_unmatched})"
        )
        print("#" * 80)

        if total_unmatched == 0:
            print("미매칭 사례 없음")
            continue

        actual_sample_count = min(
            sample_count,
            total_unmatched,
        )

        samples = unmatched.sample(
            n=actual_sample_count,
            random_state=42,
        )

        for sample_number, (_, row) in enumerate(
            samples.iterrows(),
            start=1,
        ):

            qa_text = clean_display_text(
                row.get("qa_text", "")
            )

            case_id = clean_display_text(
                row.get("case_id", "")
            )

            print()
            print(
                f"[{sample_number}] "
                f"case={case_id}"
            )
            print(qa_text)

            rows.append(
                {
                    "split": split,
                    "major_section": major_name,
                    "case_id": case_id,
                    "qa_text": qa_text,
                    "review_reason": clean_display_text(
                        row.get(
                            "review_reason",
                            "",
                        )
                    ),
                    "source_file": clean_display_text(
                        row.get(
                            "source_file",
                            "",
                        )
                    ),
                }
            )

    return pd.DataFrame(rows)


# ============================================================
# 7. 전체 분포 요약
# ============================================================

def print_distribution(
    dataframe: pd.DataFrame,
    split: str,
):
    """
    subtype별 후보 수와 대분류별 미매칭 수를 간단히 출력한다.
    """

    print()
    print("=" * 80)
    print(f"{split.upper()} - 분포 요약")
    print("=" * 80)

    print()
    print("[Subtype 후보 수]")

    for subtype in ALL_SUBTYPE_LABELS:

        column = f"label_{subtype}"

        count = (
            int(dataframe[column].sum())
            if column in dataframe.columns
            else 0
        )

        print(
            f"{subtype:30s}: {count}"
        )

    print()
    print("[대분류별 Positive / 미매칭]")

    for major_name in [
        "신체학대",
        "정서학대",
        "성학대",
        "방임",
    ]:

        positive = dataframe[
            (dataframe["major_section"] == major_name)
            & (dataframe["major_positive"] == 1)
        ]

        unmatched = positive[
            positive["matched_subtype_count"] == 0
        ]

        coverage = (
            (
                len(positive) - len(unmatched)
            )
            / len(positive)
            * 100
            if len(positive) > 0
            else 0.0
        )

        print(
            f"{major_name:10s}: "
            f"positive={len(positive):4d} / "
            f"unmatched={len(unmatched):4d} / "
            f"coverage={coverage:6.2f}%"
        )


# ============================================================
# 8. Split 하나 분석
# ============================================================

def analyze_split(
    input_path: Path,
    sample_output: Path,
    unmatched_output: Path,
    split: str,
):
    """
    하나의 split에 대해 분포, 자동 라벨 샘플,
    미매칭 샘플을 분석한다.
    """

    print()
    print("=" * 80)
    print(f"{split.upper()} V2 LABEL ANALYSIS")
    print(f"입력: {input_path}")
    print("=" * 80)

    dataframe = pd.read_csv(
        input_path
    )

    print_distribution(
        dataframe,
        split,
    )

    subtype_samples = collect_subtype_samples(
        dataframe,
        split,
    )

    unmatched_samples = collect_unmatched_samples(
        dataframe,
        split,
    )

    # 결과 폴더 생성
    RESULT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    subtype_samples.to_csv(
        sample_output,
        index=False,
        encoding="utf-8-sig",
    )

    unmatched_samples.to_csv(
        unmatched_output,
        index=False,
        encoding="utf-8-sig",
    )

    print()
    print("=" * 80)
    print(f"{split.upper()} 분석 완료")
    print(f"자동 라벨 샘플: {sample_output}")
    print(f"미매칭 샘플   : {unmatched_output}")
    print("=" * 80)


# ============================================================
# 9. Main
# ============================================================

def main():

    analyze_split(
        input_path=TRAIN_INPUT,
        sample_output=TRAIN_SAMPLE_OUTPUT,
        unmatched_output=TRAIN_UNMATCHED_OUTPUT,
        split="train",
    )

    analyze_split(
        input_path=VALID_INPUT,
        sample_output=VALID_SAMPLE_OUTPUT,
        unmatched_output=VALID_UNMATCHED_OUTPUT,
        split="valid",
    )


if __name__ == "__main__":
    main()