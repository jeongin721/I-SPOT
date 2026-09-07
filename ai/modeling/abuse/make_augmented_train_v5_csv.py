"""
A-only v4 학습 데이터와 최종 Hard Augmentation v3 데이터를 병합해 v5 학습 CSV를 생성한다.

기존 v4 데이터와 최종 문맥 오탐 보강 데이터를 합치고 중복·결측을 검사한 뒤
train_multilabel_v5.csv로 저장한다.
"""

# ============================================================
# 1. Import
# ============================================================

from pathlib import Path

import pandas as pd


# ============================================================
# 2. 경로 설정
# ============================================================

BASE_DIR = Path(__file__).resolve().parent
DATASET_DIR = BASE_DIR / "datasets"

BASE_TRAIN_PATH = (
    DATASET_DIR
    / "train_multilabel_v4.csv"
)

AUGMENTATION_PATH = (
    DATASET_DIR
    / "train_hard_augmentation_v3.csv"
)

OUTPUT_PATH = (
    DATASET_DIR
    / "train_multilabel_v5.csv"
)


# ============================================================
# 3. 입력 파일 존재 확인
# ============================================================

for path in [
    BASE_TRAIN_PATH,
    AUGMENTATION_PATH,
]:

    if not path.exists():
        raise FileNotFoundError(
            f"필요한 파일이 없습니다: {path}"
        )


# ============================================================
# 4. 데이터 로드
# ============================================================

base_df = pd.read_csv(
    BASE_TRAIN_PATH
)

augmentation_df = pd.read_csv(
    AUGMENTATION_PATH
)


print()
print("=" * 70)
print("A-only v5 Train 데이터 생성")
print("=" * 70)

print(
    f"기존 v4 Train : {len(base_df)}"
)

print(
    f"최종 보강 v3  : {len(augmentation_df)}"
)


# ============================================================
# 5. 필수 컬럼 검사
# ============================================================

required_columns = {
    "audio_text",
    "label",
}

for name, df in [
    ("v4 Train", base_df),
    ("Hard Augmentation v3", augmentation_df),
]:

    missing_columns = (
        required_columns
        - set(df.columns)
    )

    if missing_columns:
        raise ValueError(
            f"{name}에 필요한 컬럼이 없습니다: "
            f"{missing_columns}"
        )


# ============================================================
# 6. 학습용 컬럼 통일
# ============================================================

base_train_df = base_df[
    [
        "audio_text",
        "label",
    ]
].copy()

augmentation_train_df = augmentation_df[
    [
        "audio_text",
        "label",
    ]
].copy()


# ============================================================
# 7. 병합
# ============================================================

merged_df = pd.concat(
    [
        base_train_df,
        augmentation_train_df,
    ],
    ignore_index=True,
)

before_duplicate_removal = len(
    merged_df
)


# ============================================================
# 8. 결측치 검사
# ============================================================

missing_text = (
    merged_df["audio_text"]
    .isna()
    .sum()
)

missing_label = (
    merged_df["label"]
    .isna()
    .sum()
)

print()
print("===== 결측치 검사 =====")

print(
    f"audio_text : {missing_text}"
)

print(
    f"label      : {missing_label}"
)

if (
    missing_text > 0
    or missing_label > 0
):
    raise ValueError(
        "병합 데이터에 결측치가 존재합니다."
    )


# ============================================================
# 9. 완전히 동일한 데이터 중복 제거
# ============================================================

merged_df = merged_df.drop_duplicates(
    subset=[
        "audio_text",
        "label",
    ]
).reset_index(
    drop=True
)

after_duplicate_removal = len(
    merged_df
)


# ============================================================
# 10. 동일 문장 + 서로 다른 Label 충돌 검사
# ============================================================

label_conflicts = (
    merged_df
    .groupby("audio_text")["label"]
    .nunique()
)

label_conflicts = label_conflicts[
    label_conflicts > 1
]

print()
print("===== Label 충돌 검사 =====")

print(
    f"충돌 문장 수 : {len(label_conflicts)}"
)

if len(label_conflicts) > 0:

    print()
    print("[충돌 문장 예시]")

    conflict_texts = (
        label_conflicts
        .index
        .tolist()[:10]
    )

    print(
        merged_df[
            merged_df["audio_text"].isin(
                conflict_texts
            )
        ][
            [
                "audio_text",
                "label",
            ]
        ].to_string(
            index=False
        )
    )

    raise ValueError(
        "동일 문장에 서로 다른 Label이 존재합니다."
    )


# ============================================================
# 11. 데이터 셔플
# ============================================================

merged_df = merged_df.sample(
    frac=1.0,
    random_state=42,
).reset_index(
    drop=True
)


# ============================================================
# 12. 저장
# ============================================================

merged_df.to_csv(
    OUTPUT_PATH,
    index=False,
    encoding="utf-8-sig",
)


# ============================================================
# 13. 결과 출력
# ============================================================

print()
print("=" * 70)
print("A-only v5 Train 생성 완료")
print("=" * 70)

print(
    f"v4 Train             : "
    f"{len(base_train_df)}"
)

print(
    f"Hard Augmentation v3 : "
    f"{len(augmentation_train_df)}"
)

print(
    f"병합 직후            : "
    f"{before_duplicate_removal}"
)

print(
    f"중복 제거 후         : "
    f"{after_duplicate_removal}"
)

print(
    f"제거된 중복          : "
    f"{before_duplicate_removal - after_duplicate_removal}"
)

print()
print("===== Label Distribution =====")

print(
    merged_df[
        "label"
    ].value_counts()
)

print()
print(
    f"저장 경로: {OUTPUT_PATH}"
)

print()
print(
    "※ 생성 CSV는 Git에 커밋하지 않습니다."
)