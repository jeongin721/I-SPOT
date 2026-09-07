"""
기존 AI-Hub A-only Train 데이터와 Hard Augmentation 데이터를 병합해 A-only v2 학습셋을 생성한다.

Validation 데이터는 건드리지 않으며, 원본 Train과 보강 데이터의 중복/결측을 검사한 뒤 별도 CSV로 저장한다.
"""

from pathlib import Path

import pandas as pd


# ============================================================
# 1. 경로 설정
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[4]

DATASET_DIR = (
    PROJECT_ROOT
    / "ai"
    / "modeling"
    / "abuse"
    / "datasets"
)

ORIGINAL_TRAIN_PATH = DATASET_DIR / "train_multilabel.csv"

AUGMENTATION_PATH = (
    DATASET_DIR
    / "train_hard_augmentation_v1.csv"
)

OUTPUT_PATH = (
    DATASET_DIR
    / "train_multilabel_v2.csv"
)


# ============================================================
# 2. 데이터 불러오기
# ============================================================

original_df = pd.read_csv(ORIGINAL_TRAIN_PATH)
augmentation_df = pd.read_csv(AUGMENTATION_PATH)


print("=" * 70)
print("A-only v2 Train 데이터 생성")
print("=" * 70)

print(f"기존 Train : {len(original_df)}")
print(f"보강 데이터 : {len(augmentation_df)}")


# ============================================================
# 3. 필요한 컬럼 확인
# ============================================================

required_columns = {
    "audio_text",
    "label",
}

for name, df in [
    ("Original", original_df),
    ("Augmentation", augmentation_df),
]:
    missing = required_columns - set(df.columns)

    if missing:
        raise ValueError(
            f"{name} 데이터에 필요한 컬럼이 없습니다: {missing}"
        )


# ============================================================
# 4. 모델 학습에 필요한 컬럼만 통일
# ============================================================

original_train = original_df[
    ["audio_text", "label"]
].copy()

augmentation_train = augmentation_df[
    ["audio_text", "label"]
].copy()


# ============================================================
# 5. 병합
# ============================================================

merged_df = pd.concat(
    [
        original_train,
        augmentation_train,
    ],
    ignore_index=True,
)


# ============================================================
# 6. 결측치 검사
# ============================================================

missing_text = merged_df["audio_text"].isna().sum()
missing_label = merged_df["label"].isna().sum()

print()
print("[결측치]")
print(f"audio_text : {missing_text}")
print(f"label      : {missing_label}")

if missing_text > 0 or missing_label > 0:
    raise ValueError("병합 데이터에 결측치가 존재합니다.")


# ============================================================
# 7. 완전히 동일한 입력 문장 중복 확인
# ============================================================

duplicate_count = merged_df["audio_text"].duplicated().sum()

print()
print("[동일 문장 중복]")
print(f"중복 수 : {duplicate_count}")

# 원본 데이터에 동일 발화가 존재할 가능성이 있으므로
# 자동 제거하지 않고 개수만 확인한다.


# ============================================================
# 8. 데이터 순서 섞기
# ============================================================

merged_df = merged_df.sample(
    frac=1,
    random_state=69,
).reset_index(drop=True)


# ============================================================
# 9. 최종 CSV 저장
# ============================================================

merged_df.to_csv(
    OUTPUT_PATH,
    index=False,
    encoding="utf-8-sig",
)


# ============================================================
# 10. 결과 확인
# ============================================================

print()
print("=" * 70)
print("A-only v2 Train 생성 완료")
print("=" * 70)

print(f"기존 Train      : {len(original_train)}")
print(f"Hard Augmentation: {len(augmentation_train)}")
print(f"최종 Train      : {len(merged_df)}")

print()
print("[Label Distribution]")
print(merged_df["label"].value_counts())

print()
print(f"저장 경로: {OUTPUT_PATH}")