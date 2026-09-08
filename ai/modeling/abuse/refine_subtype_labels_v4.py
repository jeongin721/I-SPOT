"""
v4 세부유형 후보 라벨에서 검수로 확인된 명백한 오탐만 제거한다.
성적 착취·성적 노출·물리적 방임·의료적 방임의 고위험 규칙을 보수적으로 정제한다.
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

TRAIN_INPUT = DATASET_DIR / "subtype_labeled_train_v4.csv"
VALID_INPUT = DATASET_DIR / "subtype_labeled_valid_v4.csv"

TRAIN_OUTPUT = DATASET_DIR / "subtype_labeled_train_v4_refined.csv"
VALID_OUTPUT = DATASET_DIR / "subtype_labeled_valid_v4_refined.csv"


# ============================================================
# 3. Helper
# ============================================================

def clean_text(value) -> str:
    """NaN을 빈 문자열로 안전하게 변환한다."""

    if pd.isna(value):
        return ""

    return re.sub(
        r"\s+",
        " ",
        str(value),
    ).strip()


def normalize_binary(value) -> int:
    """CSV의 binary 값을 0/1로 변환한다."""

    try:
        return int(float(value))

    except (TypeError, ValueError):
        return 0


def get_child_evidence(evidence: str) -> str:
    """근거에서 CHILD 발화만 추출한다."""

    evidence = clean_text(evidence)

    match = re.search(
        r"\[CHILD\]\s*(.*)",
        evidence,
        flags=re.DOTALL,
    )

    if not match:
        return evidence

    return clean_text(
        match.group(1)
    )


# ============================================================
# 4. 명백한 부정 패턴
# ============================================================

NEGATIVE_PATTERNS = [
    r"굶은\s*적\s*없",
    r"그런\s*적\s*없",
    r"없었어요",
    r"없어요",
    r"아니요",
    r"아니오",
]


def contains_explicit_negative(text: str) -> bool:
    """명시적 부정 표현이 포함됐는지 확인한다."""

    text = clean_text(text)

    return any(
        re.search(pattern, text)
        for pattern in NEGATIVE_PATTERNS
    )


# ============================================================
# 5. sexual_exploitation 검증
# ============================================================

EXPLOITATION_POSITIVE_PATTERNS = [
    r"(돈|용돈|현금|대가).{0,20}"
    r"(받았|줬|주겠|준다|준다고)",

    r"(사진|영상|성행위|성관계).{0,20}"
    r"(돈|용돈|현금|대가).{0,15}"
    r"(받았|줬|주겠|준다|준다고)",

    r"(성매매|조건만남)",
]


EXPLOITATION_NEGATIVE_PATTERNS = [
    r"돈\s*(은|을)?\s*안\s*받",
    r"돈\s*얘기.{0,10}없",
    r"돈은\s*없",
    r"대가.{0,10}없",
]


def valid_sexual_exploitation(
    child_text: str,
) -> bool:
    """
    실제 금전·대가성 또는 성매매가 명시된 경우만 유지한다.
    '돈은 안 받았다' 같은 부정 사례는 제거한다.
    """

    for pattern in EXPLOITATION_NEGATIVE_PATTERNS:

        if re.search(
            pattern,
            child_text,
        ):
            return False

    return any(
        re.search(
            pattern,
            child_text,
        )
        for pattern in EXPLOITATION_POSITIVE_PATTERNS
    )


# ============================================================
# 6. neglect_medical 검증
# ============================================================

MEDICAL_POSITIVE_PATTERNS = [
    r"(병원).{0,15}"
    r"(안\s*데려|안\s*보내|못\s*가게|가지\s*말)",

    r"(아픈|다친|맞았|상처|멍).{0,25}"
    r"(병원).{0,15}"
    r"(안\s*갔|못\s*갔|안\s*보내|가지\s*말)",

    r"병원\s*갈\s*자격\s*없",

    r"병원을?\s*불신.{0,30}"
    r"(민간요법|치료)",

    r"민간요법으로\s*치료",
]


MEDICAL_FALSE_PATTERNS = [
    r"항상\s*병원에\s*데려",
    r"병원에\s*안\s*갔.{0,20}"
    r"(아픈\s*곳이\s*없|안\s*아팠)",

    r"안\s*데려갈\s*것\s*같",
]


def valid_neglect_medical(
    child_text: str,
) -> bool:
    """실제 의료 이용 거부/차단이 확인된 경우만 유지한다."""

    for pattern in MEDICAL_FALSE_PATTERNS:

        if re.search(
            pattern,
            child_text,
        ):
            return False

    return any(
        re.search(
            pattern,
            child_text,
        )
        for pattern in MEDICAL_POSITIVE_PATTERNS
    )


# ============================================================
# 7. neglect_physical 검증
# ============================================================

NEGLECT_PHYSICAL_POSITIVE_PATTERNS = [
    r"굶었",
    r"굶은\s*적\s*(있|많)",
    r"먹을\s*게\s*없",
    r"밥을?\s*(안\s*줘|안\s*챙겨|주지\s*않)",

    r"돌봐주는\s*어른.{0,15}없",
    r"돌봐주는\s*사람.{0,15}없",
    r"아무도\s*없",

    r"(더럽|냄새나).{0,15}옷",
    r"(작은|안\s*맞|맞지\s*않).{0,15}(옷|신발)",
]


NEGLECT_PHYSICAL_FALSE_PATTERNS = [
    r"굶은\s*적\s*없",
    r"굶지는\s*않",
    r"먹을\s*게\s*없지\s*않",
]


def valid_neglect_physical(
    child_text: str,
) -> bool:
    """
    식사·의복·기본 돌봄 결핍이 실제로 명시된 경우만 유지한다.
    """

    for pattern in NEGLECT_PHYSICAL_FALSE_PATTERNS:

        if re.search(
            pattern,
            child_text,
        ):
            return False

    return any(
        re.search(
            pattern,
            child_text,
        )
        for pattern in NEGLECT_PHYSICAL_POSITIVE_PATTERNS
    )


# ============================================================
# 8. sexual_exposure 검증
# ============================================================

EXPOSURE_POSITIVE_PATTERNS = [
    # 상대가 자신의 신체를 노출
    r"(아빠|아저씨|남자|할아버지|오빠).{0,20}"
    r"(옷을?\s*벗고|팬티를?\s*벗고|알몸|나체)",

    # 아동에게 노출 요구
    r"(몸|가슴|성기|소중한\s*부위|밑에).{0,20}"
    r"(보여\s*달라|보여달라|보라고)",

    # 아동의 옷을 벗기는 행위
    r"(제|내)\s*(옷|팬티|속옷).{0,10}"
    r"(벗겼|벗기려고|벗기길)",
]


EXPOSURE_FALSE_PATTERNS = [
    # 옷 안으로 손을 넣은 것만으로 exposure 처리하지 않는다.
    r"(옷|티|팬티|속옷)\s*안.{0,20}"
    r"(손\s*넣|만졌)",
]


def valid_sexual_exposure(
    child_text: str,
) -> bool:
    """명시적 노출 또는 노출 요구가 있을 때만 유지한다."""

    has_positive = any(
        re.search(
            pattern,
            child_text,
        )
        for pattern in EXPOSURE_POSITIVE_PATTERNS
    )

    if not has_positive:
        return False

    # positive가 따로 존재하지 않고 단순 옷 안 접촉뿐인 경우 제거
    only_touch_inside_clothes = any(
        re.search(
            pattern,
            child_text,
        )
        for pattern in EXPOSURE_FALSE_PATTERNS
    )

    if only_touch_inside_clothes:

        explicit_exposure = bool(
            re.search(
                r"(옷을?\s*벗고|팬티를?\s*벗고|"
                r"벗겼|벗기려고|"
                r"보여\s*달라|보여달라|알몸|나체)",
                child_text,
            )
        )

        if not explicit_exposure:
            return False

    return True


# ============================================================
# 9. 검증 함수 연결
# ============================================================

VALIDATORS = {
    "sexual_exploitation": valid_sexual_exploitation,
    "neglect_medical": valid_neglect_medical,
    "neglect_physical": valid_neglect_physical,
    "sexual_exposure": valid_sexual_exposure,
}


# ============================================================
# 10. 한 행 정제
# ============================================================

def refine_row(
    row: pd.Series,
    removed_counts: Dict[str, int],
) -> pd.Series:
    """
    검수 대상 4개 subtype만 재검증한다.
    다른 subtype 라벨은 그대로 유지한다.
    """

    result = row.copy()

    for subtype, validator in VALIDATORS.items():

        label_column = f"label_{subtype}"
        evidence_column = f"evidence_{subtype}"

        if normalize_binary(
            result.get(
                label_column,
                0,
            )
        ) != 1:
            continue

        evidence = clean_text(
            result.get(
                evidence_column,
                "",
            )
        )

        child_text = get_child_evidence(
            evidence
        )

        # 기존 라벨 중 근거가 비어 있으면
        # 자동 삭제하지 않고 그대로 둔다.
        if not child_text:
            continue

        if validator(child_text):
            continue

        result[label_column] = 0
        result[evidence_column] = ""

        removed_counts[subtype] += 1

    return result


# ============================================================
# 11. Split 처리
# ============================================================

def process_split(
    input_path: Path,
    output_path: Path,
    split: str,
):
    """v4 후보 라벨을 정제하고 별도 CSV로 저장한다."""

    print()
    print("=" * 70)
    print(f"{split.upper()} V4 REFINEMENT")
    print("=" * 70)

    df = pd.read_csv(
        input_path
    )

    removed_counts = {
        subtype: 0
        for subtype in VALIDATORS
    }

    rows = []

    for _, row in tqdm(
        df.iterrows(),
        total=len(df),
        desc=f"{split} v4 refine",
    ):

        rows.append(
            refine_row(
                row=row,
                removed_counts=removed_counts,
            )
        )

    result_df = pd.DataFrame(
        rows
    )

    # --------------------------------------------------------
    # matched_subtype_count 재계산
    # --------------------------------------------------------

    label_columns = [
        column
        for column in result_df.columns
        if column.startswith("label_")
    ]

    result_df[
        "matched_subtype_count"
    ] = (
        result_df[label_columns]
        .fillna(0)
        .astype(int)
        .sum(axis=1)
    )

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    result_df.to_csv(
        output_path,
        index=False,
        encoding="utf-8-sig",
    )

    # --------------------------------------------------------
    # 출력은 삭제 건수만
    # --------------------------------------------------------

    print()
    print("[제거된 후보 라벨]")

    total_removed = 0

    for subtype, count in removed_counts.items():

        print(
            f"{subtype:30s}: {count}"
        )

        total_removed += count

    print(
        f"\n총 제거 라벨: {total_removed}"
    )

    # 대분류 positive인데 subtype이 모두 사라진 행
    unmatched = int(
        (
            (result_df["major_positive"] == 1)
            & (
                result_df[
                    "matched_subtype_count"
                ]
                == 0
            )
        ).sum()
    )

    print(
        f"정제 후 대분류 Positive 미매칭: {unmatched}"
    )

    print(
        f"저장: {output_path}"
    )


# ============================================================
# 12. Main
# ============================================================

def main():

    process_split(
        input_path=TRAIN_INPUT,
        output_path=TRAIN_OUTPUT,
        split="train",
    )

    process_split(
        input_path=VALID_INPUT,
        output_path=VALID_OUTPUT,
        split="valid",
    )


if __name__ == "__main__":
    main()