"""
A-only baseline과 Hard Augmentation v2 모델을 동일한 Hard Test v1에서 비교한다.

전체/라벨별 F1과 샘플별 예측을 비교하여 보강 후 개선·악화된 사례를 확인한다.
"""

from pathlib import Path
import ast

import numpy as np
import pandas as pd
import torch
from sklearn.metrics import f1_score, classification_report
from tqdm.auto import tqdm
from transformers import AutoModelForSequenceClassification, AutoTokenizer


# ============================================================
# 1. 기본 설정
# ============================================================

MODEL_ID = "klue/roberta-base"
MAX_LEN = 512
THRESHOLD = 0.5

LABEL_NAMES = [
    "신체학대",
    "정서학대",
    "성학대",
    "방임",
]

NUM_LABELS = len(LABEL_NAMES)

DEVICE = torch.device(
    "cuda" if torch.cuda.is_available() else "cpu"
)


# ============================================================
# 2. 경로 설정
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[3]

DATA_PATH = (
    PROJECT_ROOT
    / "ai"
    / "modeling"
    / "abuse"
    / "datasets"
    / "hard_test_v1.csv"
)

BASELINE_WEIGHT = (
    PROJECT_ROOT
    / "ai"
    / "modeling"
    / "abuse"
    / "weight"
    / "roberta_multilabel_2026-09-03.pth"
)

V2_WEIGHT = (
    PROJECT_ROOT
    / "ai"
    / "modeling"
    / "abuse"
    / "weight"
    / "roberta_multilabel_v2_2026-09-07.pth"
)

RESULT_DIR = (
    PROJECT_ROOT
    / "ai"
    / "modeling"
    / "abuse"
    / "results"
)

RESULT_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

RESULT_PATH = (
    RESULT_DIR
    / "hard_test_v1_comparison.csv"
)


# ============================================================
# 3. Label 처리
# ============================================================

def parse_label(value):
    """CSV 문자열 label을 4차원 정수 배열로 변환한다."""

    if isinstance(value, str):
        value = ast.literal_eval(value)

    label = np.asarray(
        value,
        dtype=np.int64,
    )

    if label.shape != (NUM_LABELS,):
        raise ValueError(
            f"잘못된 label: {value}"
        )

    return label


def label_to_names(label):
    """4차원 label을 사람이 읽기 쉬운 이름으로 변환한다."""

    names = [
        name
        for name, value in zip(LABEL_NAMES, label)
        if value == 1
    ]

    return ", ".join(names) if names else "해당 없음"


# ============================================================
# 4. Checkpoint에서 state_dict 추출
# ============================================================

def get_state_dict(checkpoint):
    """
    저장 방식 차이를 고려하여 model_state_dict를 추출한다.

    checkpoint 자체가 state_dict인 기존 모델도 처리한다.
    """

    if (
        isinstance(checkpoint, dict)
        and "model_state_dict" in checkpoint
    ):
        return checkpoint["model_state_dict"]

    return checkpoint


# ============================================================
# 5. 모델 로드
# ============================================================

def load_model(weight_path):
    """지정된 checkpoint의 RoBERTa 멀티라벨 모델을 로드한다."""

    if not weight_path.exists():
        raise FileNotFoundError(
            f"Weight를 찾을 수 없습니다: {weight_path}"
        )

    model = AutoModelForSequenceClassification.from_pretrained(
        MODEL_ID,
        num_labels=NUM_LABELS,
        problem_type="multi_label_classification",
    )

    checkpoint = torch.load(
        weight_path,
        map_location=DEVICE,
    )

    state_dict = get_state_dict(checkpoint)

    model.load_state_dict(state_dict)

    model.to(DEVICE)
    model.eval()

    return model


# ============================================================
# 6. 전체 Hard Test 추론
# ============================================================

def predict_dataset(
    model,
    tokenizer,
    dataframe,
    description,
):
    """
    Hard Test 전체를 추론한다.

    비교 공정성을 위해 baseline/v2 모두 threshold 0.5를 사용한다.
    """

    probabilities = []

    for text in tqdm(
        dataframe["audio_text"].tolist(),
        desc=description,
    ):

        encoded = tokenizer(
            str(text),
            return_tensors="pt",
            truncation=True,
            padding=True,
            max_length=MAX_LEN,
        )

        encoded = {
            key: value.to(DEVICE)
            for key, value in encoded.items()
        }

        with torch.no_grad():
            output = model(**encoded)

            probability = torch.sigmoid(
                output.logits
            )[0].cpu().numpy()

        probabilities.append(probability)

    probabilities = np.asarray(probabilities)

    predictions = (
        probabilities >= THRESHOLD
    ).astype(int)

    return probabilities, predictions


# ============================================================
# 7. 평가 출력
# ============================================================

def print_evaluation(
    title,
    y_true,
    y_pred,
):
    """Micro/Macro/라벨별 F1과 classification report를 출력한다."""

    micro = f1_score(
        y_true,
        y_pred,
        average="micro",
        zero_division=0,
    )

    macro = f1_score(
        y_true,
        y_pred,
        average="macro",
        zero_division=0,
    )

    per_label = f1_score(
        y_true,
        y_pred,
        average=None,
        zero_division=0,
    )

    exact_match = np.mean(
        np.all(
            y_true == y_pred,
            axis=1,
        )
    )

    print()
    print("=" * 70)
    print(title)
    print("=" * 70)

    print(f"Micro F1    : {micro:.4f}")
    print(f"Macro F1    : {macro:.4f}")
    print(f"Exact Match : {exact_match:.4f}")

    print()
    print("[Per-label F1]")

    for name, score in zip(
        LABEL_NAMES,
        per_label,
    ):
        print(
            f"{name:<6}: {score:.4f}"
        )

    print()
    print("[Classification Report]")

    print(
        classification_report(
            y_true,
            y_pred,
            target_names=LABEL_NAMES,
            digits=4,
            zero_division=0,
        )
    )

    return {
        "micro": micro,
        "macro": macro,
        "exact_match": exact_match,
        "per_label": per_label,
    }


# ============================================================
# 8. 데이터 로드
# ============================================================

print("=" * 70)
print("A-only Hard Test v1 Comparison")
print("=" * 70)

print(f"Device   : {DEVICE}")
print(f"Dataset  : {DATA_PATH}")
print(f"Baseline : {BASELINE_WEIGHT}")
print(f"v2       : {V2_WEIGHT}")

if not DATA_PATH.exists():
    raise FileNotFoundError(
        f"Hard Test를 찾을 수 없습니다: {DATA_PATH}"
    )

df = pd.read_csv(DATA_PATH)

y_true = np.stack(
    df["label"]
    .apply(parse_label)
    .to_numpy()
)

print()
print(f"Hard Test Samples : {len(df)}")


# ============================================================
# 9. Tokenizer / 모델 로드
# ============================================================

print()
print("Tokenizer 로딩 중...")

tokenizer = AutoTokenizer.from_pretrained(
    MODEL_ID
)

print("Baseline 모델 로딩 중...")

baseline_model = load_model(
    BASELINE_WEIGHT
)

print("v2 모델 로딩 중...")

v2_model = load_model(
    V2_WEIGHT
)


# ============================================================
# 10. Baseline 추론
# ============================================================

baseline_prob, baseline_pred = predict_dataset(
    model=baseline_model,
    tokenizer=tokenizer,
    dataframe=df,
    description="Baseline",
)


# ============================================================
# 11. v2 추론
# ============================================================

v2_prob, v2_pred = predict_dataset(
    model=v2_model,
    tokenizer=tokenizer,
    dataframe=df,
    description="A-only v2",
)


# ============================================================
# 12. 전체 평가
# ============================================================

baseline_score = print_evaluation(
    title="Baseline Hard Test",
    y_true=y_true,
    y_pred=baseline_pred,
)

v2_score = print_evaluation(
    title="A-only v2 Hard Test",
    y_true=y_true,
    y_pred=v2_pred,
)


# ============================================================
# 13. Baseline vs v2 요약
# ============================================================

print()
print("=" * 70)
print("Baseline vs A-only v2")
print("=" * 70)

print(
    f"Micro F1 : "
    f"{baseline_score['micro']:.4f}"
    f" → {v2_score['micro']:.4f}"
    f" ({v2_score['micro'] - baseline_score['micro']:+.4f})"
)

print(
    f"Macro F1 : "
    f"{baseline_score['macro']:.4f}"
    f" → {v2_score['macro']:.4f}"
    f" ({v2_score['macro'] - baseline_score['macro']:+.4f})"
)

print(
    f"Exact    : "
    f"{baseline_score['exact_match']:.4f}"
    f" → {v2_score['exact_match']:.4f}"
    f" ({v2_score['exact_match'] - baseline_score['exact_match']:+.4f})"
)

print()
print("[Per-label F1 변화]")

for i, name in enumerate(LABEL_NAMES):

    before = baseline_score["per_label"][i]
    after = v2_score["per_label"][i]

    print(
        f"{name:<6}: "
        f"{before:.4f} → {after:.4f} "
        f"({after - before:+.4f})"
    )


# ============================================================
# 14. 샘플별 결과 생성
# ============================================================

result_df = df.copy()

result_df["true_label_name"] = [
    label_to_names(x)
    for x in y_true
]

result_df["baseline_pred_name"] = [
    label_to_names(x)
    for x in baseline_pred
]

result_df["v2_pred_name"] = [
    label_to_names(x)
    for x in v2_pred
]

result_df["baseline_correct"] = [
    bool(np.array_equal(true, pred))
    for true, pred in zip(
        y_true,
        baseline_pred,
    )
]

result_df["v2_correct"] = [
    bool(np.array_equal(true, pred))
    for true, pred in zip(
        y_true,
        v2_pred,
    )
]


# ============================================================
# 15. 개선 / 악화 여부
# ============================================================

def compare_status(row):

    if (
        not row["baseline_correct"]
        and row["v2_correct"]
    ):
        return "IMPROVED"

    if (
        row["baseline_correct"]
        and not row["v2_correct"]
    ):
        return "WORSE"

    if (
        row["baseline_correct"]
        and row["v2_correct"]
    ):
        return "BOTH_CORRECT"

    return "BOTH_WRONG"


result_df["comparison"] = result_df.apply(
    compare_status,
    axis=1,
)


# ============================================================
# 16. 라벨별 확률 저장
# ============================================================

for i, name in enumerate(LABEL_NAMES):

    result_df[
        f"baseline_{name}_prob"
    ] = baseline_prob[:, i]

    result_df[
        f"v2_{name}_prob"
    ] = v2_prob[:, i]


# ============================================================
# 17. 개선/악화 사례 출력
# ============================================================

improved = result_df[
    result_df["comparison"] == "IMPROVED"
]

worse = result_df[
    result_df["comparison"] == "WORSE"
]

both_wrong = result_df[
    result_df["comparison"] == "BOTH_WRONG"
]

print()
print("=" * 70)
print("샘플 단위 변화")
print("=" * 70)

print(f"IMPROVED   : {len(improved)}")
print(f"WORSE      : {len(worse)}")
print(f"BOTH WRONG : {len(both_wrong)}")


if len(improved) > 0:

    print()
    print("[개선된 사례]")

    for _, row in improved.iterrows():

        print("-" * 70)

        print(
            f"{row['sample_id']} | "
            f"{row['scenario_type']}"
        )

        print(
            f"문장     : {row['audio_text']}"
        )

        print(
            f"정답     : {row['true_label_name']}"
        )

        print(
            f"Baseline : {row['baseline_pred_name']}"
        )

        print(
            f"v2       : {row['v2_pred_name']}"
        )


if len(worse) > 0:

    print()
    print("[악화된 사례]")

    for _, row in worse.iterrows():

        print("-" * 70)

        print(
            f"{row['sample_id']} | "
            f"{row['scenario_type']}"
        )

        print(
            f"문장     : {row['audio_text']}"
        )

        print(
            f"정답     : {row['true_label_name']}"
        )

        print(
            f"Baseline : {row['baseline_pred_name']}"
        )

        print(
            f"v2       : {row['v2_pred_name']}"
        )


if len(both_wrong) > 0:

    print()
    print("[두 모델 모두 틀린 사례]")

    for _, row in both_wrong.iterrows():

        print("-" * 70)

        print(
            f"{row['sample_id']} | "
            f"{row['scenario_type']}"
        )

        print(
            f"문장     : {row['audio_text']}"
        )

        print(
            f"정답     : {row['true_label_name']}"
        )

        print(
            f"Baseline : {row['baseline_pred_name']}"
        )

        print(
            f"v2       : {row['v2_pred_name']}"
        )


# ============================================================
# 18. CSV 저장
# ============================================================

result_df.to_csv(
    RESULT_PATH,
    index=False,
    encoding="utf-8-sig",
)

print()
print("=" * 70)
print("비교 완료")
print("=" * 70)

print(f"결과 CSV : {RESULT_PATH}")