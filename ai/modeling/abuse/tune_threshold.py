from pathlib import Path

import numpy as np
import pandas as pd

from sklearn.metrics import f1_score


# ============================================================
# 설정
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

RESULT_PATH = (
    BASE_DIR
    / "results"
    / "validation_predictions.csv"
)

LABEL_NAMES = [
    "신체학대",
    "정서학대",
    "성학대",
    "방임",
]

THRESHOLD_CANDIDATES = np.arange(
    0.10,
    0.91,
    0.01,
)


# ============================================================
# Validation prediction 결과 로드
# ============================================================

df = pd.read_csv(RESULT_PATH)

print("Validation predictions:", df.shape)


# ============================================================
# 라벨별 최적 Threshold 탐색
# ============================================================

best_thresholds = {}
best_f1_scores = {}

print("\n======================================")
print("       PER-LABEL THRESHOLD TUNING")
print("======================================")

for label_name in LABEL_NAMES:

    y_true = df[f"{label_name}_true"].values
    y_prob = df[f"{label_name}_prob"].values

    best_threshold = 0.5
    best_f1 = -1.0

    for threshold in THRESHOLD_CANDIDATES:

        y_pred = (
            y_prob >= threshold
        ).astype(int)

        score = f1_score(
            y_true,
            y_pred,
            zero_division=0,
        )

        if score > best_f1:

            best_f1 = score
            best_threshold = threshold

    best_thresholds[label_name] = float(best_threshold)
    best_f1_scores[label_name] = float(best_f1)

    print(
        f"{label_name:<8} "
        f"threshold={best_threshold:.2f} "
        f"F1={best_f1:.4f}"
    )


# ============================================================
# 최적 Threshold 전체 적용
# ============================================================

y_true_all = []
y_pred_all = []

for label_name in LABEL_NAMES:

    y_true = df[f"{label_name}_true"].values
    y_prob = df[f"{label_name}_prob"].values

    threshold = best_thresholds[label_name]

    y_pred = (
        y_prob >= threshold
    ).astype(int)

    y_true_all.append(y_true)
    y_pred_all.append(y_pred)


y_true_all = np.stack(
    y_true_all,
    axis=1,
)

y_pred_all = np.stack(
    y_pred_all,
    axis=1,
)


# ============================================================
# 전체 성능
# ============================================================

micro_f1 = f1_score(
    y_true_all,
    y_pred_all,
    average="micro",
    zero_division=0,
)

macro_f1 = f1_score(
    y_true_all,
    y_pred_all,
    average="macro",
    zero_division=0,
)


print("\n======================================")
print("       TUNED THRESHOLD RESULT")
print("======================================")

print("Best Thresholds:")

for label_name in LABEL_NAMES:

    print(
        f"{label_name}: "
        f"{best_thresholds[label_name]:.2f}"
    )


print(f"\nMicro F1 : {micro_f1:.4f}")
print(f"Macro F1 : {macro_f1:.4f}")


# ============================================================
# 기존 Threshold 0.5와 비교
# ============================================================

baseline_preds = []

for label_name in LABEL_NAMES:

    y_prob = df[f"{label_name}_prob"].values

    pred = (
        y_prob >= 0.5
    ).astype(int)

    baseline_preds.append(pred)


baseline_preds = np.stack(
    baseline_preds,
    axis=1,
)

baseline_macro_f1 = f1_score(
    y_true_all,
    baseline_preds,
    average="macro",
    zero_division=0,
)

baseline_micro_f1 = f1_score(
    y_true_all,
    baseline_preds,
    average="micro",
    zero_division=0,
)


print("\n======================================")
print("              COMPARISON")
print("======================================")

print(
    f"Baseline 0.5 Macro F1 : "
    f"{baseline_macro_f1:.4f}"
)

print(
    f"Tuned Threshold Macro F1 : "
    f"{macro_f1:.4f}"
)

print(
    f"Improvement : "
    f"{macro_f1 - baseline_macro_f1:+.4f}"
)

print()

print(
    f"Baseline 0.5 Micro F1 : "
    f"{baseline_micro_f1:.4f}"
)

print(
    f"Tuned Threshold Micro F1 : "
    f"{micro_f1:.4f}"
)