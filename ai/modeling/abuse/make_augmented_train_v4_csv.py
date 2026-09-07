"""
A-only v4 학습용 데이터셋을 생성한다.

기존 v2 학습 CSV와 2차 Hard Augmentation CSV를 병합하고,
중복을 제거한 뒤 v4 학습용 CSV로 저장한다.
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
    / "train_multilabel_v2.csv"
)

AUGMENTATION_PATH = (
    DATASET_DIR
    / "train_hard_augmentation_v2.csv"
)

OUTPUT_PATH = (
    DATASET_DIR
    / "train_multilabel_v4.csv"
)


# ============================================================
# 3. 파일 존재 여부 확인
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


# ============================================================
# 5. 필요한 컬럼 확인
# ============================================================

required_columns = {
    "audio_text",
    "label",
}

for name, df in [
    ("기존 v2 데이터", base_df),
    ("2차 보강 데이터", augmentation_df),
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
# 6. 학습에 필요한 컬럼만 사용
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
# 8. 중복 제거
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
# 9. 셔플
# ============================================================

merged_df = merged_df.sample(
    frac=1.0,
    random_state=42,
).reset_index(
    drop=True
)


# ============================================================
# 10. 저장
# ============================================================

merged_df.to_csv(
    OUTPUT_PATH,
    index=False,
    encoding="utf-8-sig",
)


# ============================================================
# 11. 결과 출력
# ============================================================

print()
print("=" * 70)
print("A-only v4 학습 데이터 병합 완료")
print("=" * 70)

print(
    f"\nv2 기존 학습 데이터 : "
    f"{len(base_train_df)}"
)

print(
    f"2차 보강 데이터      : "
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
    f"\n저장 위치 : {OUTPUT_PATH}"
)

print()
print(
    "===== label 분포 ====="
)

print(
    merged_df[
        "label"
    ].value_counts()
)

print()
print(
    "※ 생성 CSV는 Git에 커밋하지 않습니다."
)