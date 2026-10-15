"""
v3→v4에서 새로 추가된 세부유형 후보만 보수적으로 정제한다.
v3에서 이미 존재하던 라벨은 절대 변경하지 않고, 검수에서 확인된 신규 오탐만 제거한다.
"""

# ============================================================
# 1. Import
# ============================================================

from pathlib import Path
import re
from typing import Dict

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

TRAIN_V3 = DATASET_DIR / "subtype_labeled_train_v3.csv"
TRAIN_V4 = DATASET_DIR / "subtype_labeled_train_v4.csv"

VALID_V3 = DATASET_DIR / "subtype_labeled_valid_v3.csv"
VALID_V4 = DATASET_DIR / "subtype_labeled_valid_v4.csv"

TRAIN_OUTPUT = (
    DATASET_DIR
    / "subtype_labeled_train_v4_refined.csv"
)

VALID_OUTPUT = (
    DATASET_DIR
    / "subtype_labeled_valid_v4_refined.csv"
)


# ============================================================
# 3. Helper
# ============================================================

def clean_text(value) -> str:
    """NaN을 빈 문자열로 변환하고 공백을 정리한다."""

    if pd.isna(value):
        return ""

    return re.sub(
        r"\s+",
        " ",
        str(value),
    ).strip()


def binary(value) -> int:
    """CSV 값을 0/1 정수로 변환한다."""

    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def get_child_text(evidence: str) -> str:
    """evidence에서 CHILD 발화만 가져온다."""

    evidence = clean_text(evidence)

    match = re.search(
        r"\[CHILD\]\s*(.*)",
        evidence,
        flags=re.DOTALL,
    )

    if match:
        return clean_text(match.group(1))

    return evidence


# ============================================================
# 4. 검수에서 실제로 확인된 오탐 규칙
# ============================================================

def remove_sexual_exploitation(text: str) -> bool:
    """
    성적 사진/영상은 있었지만 금전·대가가 명시적으로 부정된 경우 제거.
    """

    false_patterns = [
        r"돈\s*얘기.{0,10}없",
        r"돈\s*(은|을)?\s*안\s*받",
        r"돈은\s*없",
        r"대가.{0,10}없",
    ]

    return any(
        re.search(pattern, text)
        for pattern in false_patterns
    )


def remove_neglect_physical(text: str) -> bool:
    """
    실제로 굶지 않았다고 명시한 신규 후보만 제거.
    다른 물리적 방임 표현은 건드리지 않는다.
    """

    false_patterns = [
        r"굶은\s*적\s*(은\s*)?없",
        r"굶지는\s*않",
        r"굶지\s*않",
    ]

    return any(
        re.search(pattern, text)
        for pattern in false_patterns
    )


def remove_neglect_medical(text: str) -> bool:
    """
    의료 방임이 실제 발생하지 않았거나
    단순 추측인 신규 후보만 제거.
    """

    false_patterns = [
        # 실제로는 항상 병원에 갔음
        r"항상\s*병원에\s*데려",

        # 아프지 않아서 병원에 가지 않음
        r"(아픈\s*곳이\s*없|안\s*아팠).{0,20}"
        r"병원에\s*안\s*갔",

        r"병원에\s*안\s*갔.{0,20}"
        r"(아픈\s*곳이\s*없|안\s*아팠)",

        # 미래 추측일 뿐 실제 사건 아님
        r"안\s*데려갈\s*것\s*같",
        r"안\s*보내줄\s*것\s*같",
    ]

    return any(
        re.search(pattern, text)
        for pattern in false_patterns
    )


def remove_sexual_exposure(text: str) -> bool:
    """
    단순히 옷 안으로 손을 넣어 접촉한 것뿐이고
    실제 노출/탈의/노출요구가 없는 신규 후보만 제거.
    """

    inside_touch = bool(
        re.search(
            r"(옷|티|팬티|속옷)\s*"
            r"(안|속).{0,20}"
            r"(손\s*넣|만졌|만지고)",
            text,
        )
    )

    explicit_exposure = bool(
        re.search(
            r"(옷을?\s*벗고|"
            r"팬티를?\s*벗고|"
            r"옷을?\s*벗겼|"
            r"팬티를?\s*벗겼|"
            r"벗기려고|"
            r"알몸|나체|"
            r"보여\s*달라|보여달라|"
            r"보라고)",
            text,
        )
    )

    return (
        inside_touch
        and not explicit_exposure
    )


REMOVERS = {
    "sexual_exploitation": remove_sexual_exploitation,
    "neglect_physical": remove_neglect_physical,
    "neglect_medical": remove_neglect_medical,
    "sexual_exposure": remove_sexual_exposure,
}


# ============================================================
# 5. Split 정제
# ============================================================

def refine_split(
    v3_path: Path,
    v4_path: Path,
    output_path: Path,
    split: str,
):
    """
    v3=0, v4=1인 신규 라벨에 대해서만 오탐 제거 규칙을 적용한다.
    """

    v3 = pd.read_csv(v3_path)
    v4 = pd.read_csv(v4_path)

    if len(v3) != len(v4):
        raise ValueError(
            f"{split}: v3/v4 행 수 불일치"
        )

    result = v4.copy()

    removed_counts: Dict[str, int] = {
        subtype: 0
        for subtype in REMOVERS
    }

    new_counts: Dict[str, int] = {
        subtype: 0
        for subtype in REMOVERS
    }

    # ========================================================
    # 신규 라벨만 검사
    # ========================================================

    for index in tqdm(
        range(len(result)),
        desc=f"{split} 신규 v4 라벨 정제",
    ):

        for subtype, remover in REMOVERS.items():

            label_col = f"label_{subtype}"
            evidence_col = f"evidence_{subtype}"

            old_label = binary(
                v3.iloc[index].get(
                    label_col,
                    0,
                )
            )

            new_label = binary(
                v4.iloc[index].get(
                    label_col,
                    0,
                )
            )

            # ------------------------------------------------
            # 핵심:
            # v3에서 이미 1이었던 라벨은 절대 건드리지 않는다.
            # ------------------------------------------------

            if not (
                old_label == 0
                and new_label == 1
            ):
                continue

            new_counts[subtype] += 1

            evidence = clean_text(
                result.iloc[index].get(
                    evidence_col,
                    "",
                )
            )

            child_text = get_child_text(
                evidence
            )

            if remover(child_text):

                result.at[
                    index,
                    label_col,
                ] = 0

                result.at[
                    index,
                    evidence_col,
                ] = ""

                removed_counts[subtype] += 1

    # ========================================================
    # matched_subtype_count 재계산
    # ========================================================

    label_columns = [
        column
        for column in result.columns
        if column.startswith("label_")
    ]

    result[
        "matched_subtype_count"
    ] = (
        result[label_columns]
        .fillna(0)
        .astype(int)
        .sum(axis=1)
    )

    # ========================================================
    # 저장
    # ========================================================

    result.to_csv(
        output_path,
        index=False,
        encoding="utf-8-sig",
    )

    # ========================================================
    # 필요한 결과만 출력
    # ========================================================

    print()
    print("=" * 70)
    print(f"{split.upper()} V4 신규 라벨 정제")
    print("=" * 70)

    for subtype in REMOVERS:

        new_count = new_counts[subtype]
        removed = removed_counts[subtype]
        kept = new_count - removed

        print(
            f"{subtype:25s} "
            f"신규={new_count:3d} / "
            f"제거={removed:3d} / "
            f"유지={kept:3d}"
        )

    total_removed = sum(
        removed_counts.values()
    )

    unmatched = int(
        (
            (result["major_positive"] == 1)
            & (
                result[
                    "matched_subtype_count"
                ]
                == 0
            )
        ).sum()
    )

    matched = int(
        (
            (result["major_positive"] == 1)
            & (
                result[
                    "matched_subtype_count"
                ]
                > 0
            )
        ).sum()
    )

    positive = int(
        (
            result["major_positive"]
            == 1
        ).sum()
    )

    coverage = (
        matched / positive * 100
        if positive
        else 0
    )

    print()
    print(
        f"총 제거 신규 라벨 : {total_removed}"
    )
    print(
        f"Positive 미매칭   : {unmatched}"
    )
    print(
        f"Coverage           : {coverage:.2f}%"
    )
    print(
        f"저장               : {output_path}"
    )


# ============================================================
# 6. Main
# ============================================================

def main():

    refine_split(
        v3_path=TRAIN_V3,
        v4_path=TRAIN_V4,
        output_path=TRAIN_OUTPUT,
        split="train",
    )

    refine_split(
        v3_path=VALID_V3,
        v4_path=VALID_V4,
        output_path=VALID_OUTPUT,
        split="valid",
    )


if __name__ == "__main__":
    main()