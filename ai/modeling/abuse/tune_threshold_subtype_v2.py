"""
I-SPOT 2차 RoBERTa v2의 15개 세부유형별 threshold를 Validation에서 튜닝한다.
Best weight는 변경하지 않고 0.50 baseline과 label별 F1 최적 threshold 성능을 비교한다.
"""

# ============================================================
# 1. Import
# ============================================================

import json
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
import torch
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    precision_recall_fscore_support,
)
from torch.utils.data import DataLoader, Dataset
from tqdm import tqdm
from transformers import (
    AutoModelForSequenceClassification,
    AutoTokenizer,
)


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

WEIGHT_DIR = (
    BASE_DIR
    / "ai"
    / "modeling"
    / "abuse"
    / "weight"
)

RESULT_DIR = (
    BASE_DIR
    / "ai"
    / "modeling"
    / "abuse"
    / "results"
)

VALID_PATH = (
    DATASET_DIR
    / "subtype_valid_v1.csv"
)

WEIGHT_PATH = (
    WEIGHT_DIR
    / "roberta_subtype_v2_best.pth"
)

THRESHOLD_RESULT_PATH = (
    RESULT_DIR
    / "threshold_tuning_subtype_v2.csv"
)

SUMMARY_RESULT_PATH = (
    RESULT_DIR
    / "threshold_tuning_subtype_v2_summary.csv"
)


# ============================================================
# 3. Label
# ============================================================

LABEL_NAMES = [
    "physical_direct",
    "physical_object",
    "physical_force",

    "emotional_verbal",
    "emotional_threat",
    "emotional_restriction",
    "emotional_discrimination",
    "emotional_dv_exposure",
    "emotional_cruelty",

    "sexual_exposure",
    "sexual_molestation",
    "sexual_intercourse",

    "neglect_physical",
    "neglect_education",
    "neglect_medical",
]

NUM_LABELS = len(LABEL_NAMES)


# ============================================================
# 4. 설정
# ============================================================

MODEL_NAME = "klue/roberta-base"

MAX_LENGTH = 256
BATCH_SIZE = 32

BASE_THRESHOLD = 0.50

THRESHOLD_MIN = 0.05
THRESHOLD_MAX = 0.95
THRESHOLD_STEP = 0.01


# ============================================================
# 5. Dataset
# ============================================================

class SubtypeDataset(Dataset):
    """Validation text와 15차원 정답 label을 반환한다."""

    def __init__(
        self,
        dataframe: pd.DataFrame,
        tokenizer,
    ):
        self.dataframe = dataframe.reset_index(
            drop=True
        )

        self.tokenizer = tokenizer

    def __len__(self) -> int:
        return len(self.dataframe)

    def __getitem__(
        self,
        index: int,
    ) -> Dict[str, torch.Tensor]:

        row = self.dataframe.iloc[index]

        text = str(
            row["text"]
        )

        labels = json.loads(
            row["label"]
        )

        if len(labels) != NUM_LABELS:
            raise ValueError(
                f"Label 길이 오류: "
                f"{len(labels)} != {NUM_LABELS}"
            )

        encoded = self.tokenizer(
            text,
            truncation=True,
            padding="max_length",
            max_length=MAX_LENGTH,
            return_tensors="pt",
        )

        return {
            "input_ids": (
                encoded["input_ids"]
                .squeeze(0)
            ),
            "attention_mask": (
                encoded["attention_mask"]
                .squeeze(0)
            ),
            "labels": torch.tensor(
                labels,
                dtype=torch.int64,
            ),
        }


# ============================================================
# 6. 모델 로드
# ============================================================

def load_model(
    device: torch.device,
):
    """v2 Best checkpoint를 로드한다."""

    print(
        f"Weight: {WEIGHT_PATH}"
    )

    checkpoint = torch.load(
        WEIGHT_PATH,
        map_location=device,
    )

    checkpoint_labels = checkpoint.get(
        "label_names"
    )

    if (
        checkpoint_labels is not None
        and checkpoint_labels != LABEL_NAMES
    ):
        raise ValueError(
            "Checkpoint label 순서와 "
            "현재 LABEL_NAMES 순서가 다릅니다."
        )

    model_name = checkpoint.get(
        "model_name",
        MODEL_NAME,
    )

    tokenizer = (
        AutoTokenizer.from_pretrained(
            model_name
        )
    )

    model = (
        AutoModelForSequenceClassification
        .from_pretrained(
            model_name,
            num_labels=NUM_LABELS,
            problem_type=(
                "multi_label_classification"
            ),
        )
    )

    model.load_state_dict(
        checkpoint["model_state_dict"]
    )

    model.to(device)
    model.eval()

    print(
        f"Checkpoint Epoch: "
        f"{checkpoint.get('epoch', 'unknown')}"
    )

    print(
        f"Checkpoint Macro F1: "
        f"{checkpoint.get('macro_f1', 'unknown')}"
    )

    return tokenizer, model


# ============================================================
# 7. Validation 확률 추론
# ============================================================

@torch.no_grad()
def predict_validation(
    model,
    loader: DataLoader,
    device: torch.device,
) -> Tuple[np.ndarray, np.ndarray]:
    """Validation 전체의 sigmoid score와 정답을 반환한다."""

    all_probabilities: List[np.ndarray] = []
    all_labels: List[np.ndarray] = []

    progress = tqdm(
        loader,
        desc="Validation inference",
    )

    for batch in progress:

        input_ids = batch[
            "input_ids"
        ].to(
            device,
            non_blocking=True,
        )

        attention_mask = batch[
            "attention_mask"
        ].to(
            device,
            non_blocking=True,
        )

        outputs = model(
            input_ids=input_ids,
            attention_mask=attention_mask,
        )

        probabilities = torch.sigmoid(
            outputs.logits
        )

        all_probabilities.append(
            probabilities.cpu().numpy()
        )

        all_labels.append(
            batch["labels"].numpy()
        )

    return (
        np.concatenate(
            all_probabilities,
            axis=0,
        ),
        np.concatenate(
            all_labels,
            axis=0,
        ),
    )


# ============================================================
# 8. Threshold 후보
# ============================================================

def get_threshold_candidates() -> np.ndarray:
    """0.05~0.95 threshold 후보를 생성한다."""

    return np.round(
        np.arange(
            THRESHOLD_MIN,
            THRESHOLD_MAX
            + THRESHOLD_STEP,
            THRESHOLD_STEP,
        ),
        2,
    )


# ============================================================
# 9. Label별 Threshold 탐색
# ============================================================

def tune_thresholds(
    y_true: np.ndarray,
    probabilities: np.ndarray,
):
    """
    각 label에 대해 F1이 가장 높은 threshold를 찾는다.

    F1이 동일한 threshold가 여러 개면
    0.50에 더 가까운 값을 우선 선택한다.
    """

    candidates = (
        get_threshold_candidates()
    )

    tuned_thresholds = []
    result_rows = []

    for label_index, label_name in enumerate(
        LABEL_NAMES
    ):

        true_label = y_true[
            :,
            label_index,
        ]

        probability = probabilities[
            :,
            label_index,
        ]

        best_threshold = BASE_THRESHOLD
        best_f1 = -1.0
        best_precision = 0.0
        best_recall = 0.0

        for threshold in candidates:

            prediction = (
                probability >= threshold
            ).astype(int)

            precision, recall, f1, _ = (
                precision_recall_fscore_support(
                    true_label,
                    prediction,
                    average="binary",
                    zero_division=0,
                )
            )

            # ------------------------------------------------
            # 더 높은 F1이면 교체
            # ------------------------------------------------

            if f1 > best_f1 + 1e-12:

                best_threshold = float(
                    threshold
                )

                best_f1 = float(f1)
                best_precision = float(
                    precision
                )
                best_recall = float(
                    recall
                )

            # ------------------------------------------------
            # F1 동일하면 0.50에 가까운 threshold 선택
            # ------------------------------------------------

            elif abs(
                f1 - best_f1
            ) <= 1e-12:

                current_distance = abs(
                    float(threshold)
                    - BASE_THRESHOLD
                )

                best_distance = abs(
                    best_threshold
                    - BASE_THRESHOLD
                )

                if (
                    current_distance
                    < best_distance
                ):

                    best_threshold = float(
                        threshold
                    )

                    best_precision = float(
                        precision
                    )

                    best_recall = float(
                        recall
                    )

        # ----------------------------------------------------
        # 기존 0.50 성능
        # ----------------------------------------------------

        base_prediction = (
            probability
            >= BASE_THRESHOLD
        ).astype(int)

        (
            base_precision,
            base_recall,
            base_f1,
            _,
        ) = precision_recall_fscore_support(
            true_label,
            base_prediction,
            average="binary",
            zero_division=0,
        )

        support = int(
            true_label.sum()
        )

        tuned_thresholds.append(
            best_threshold
        )

        result_rows.append(
            {
                "label": label_name,
                "support": support,

                "base_threshold": (
                    BASE_THRESHOLD
                ),
                "base_precision": float(
                    base_precision
                ),
                "base_recall": float(
                    base_recall
                ),
                "base_f1": float(
                    base_f1
                ),

                "tuned_threshold": (
                    best_threshold
                ),
                "tuned_precision": (
                    best_precision
                ),
                "tuned_recall": (
                    best_recall
                ),
                "tuned_f1": best_f1,

                "f1_change": (
                    best_f1
                    - float(base_f1)
                ),
            }
        )

    return (
        np.asarray(
            tuned_thresholds,
            dtype=np.float32,
        ),
        pd.DataFrame(
            result_rows
        ),
    )


# ============================================================
# 10. 전체 Metric
# ============================================================

def calculate_overall_metrics(
    y_true: np.ndarray,
    y_pred: np.ndarray,
) -> Dict[str, float]:
    """Micro/Macro F1과 Exact Match를 계산한다."""

    return {
        "micro_f1": f1_score(
            y_true,
            y_pred,
            average="micro",
            zero_division=0,
        ),
        "macro_f1": f1_score(
            y_true,
            y_pred,
            average="macro",
            zero_division=0,
        ),
        "exact_match": accuracy_score(
            y_true,
            y_pred,
        ),
    }


# ============================================================
# 11. Per-label 출력
# ============================================================

def print_threshold_result(
    result_df: pd.DataFrame,
) -> None:
    """15개 label의 threshold 변경 결과를 출력한다."""

    print()
    print("-" * 106)

    print(
        f"{'Subtype':30s}"
        f"{'Sup':>6s}"
        f"{'BaseT':>8s}"
        f"{'BaseF1':>9s}"
        f"{'TuneT':>8s}"
        f"{'TuneP':>9s}"
        f"{'TuneR':>9s}"
        f"{'TuneF1':>9s}"
        f"{'ΔF1':>9s}"
    )

    print("-" * 106)

    for _, row in result_df.iterrows():

        print(
            f"{row['label']:30s}"
            f"{int(row['support']):6d}"
            f"{row['base_threshold']:8.2f}"
            f"{row['base_f1']:9.4f}"
            f"{row['tuned_threshold']:8.2f}"
            f"{row['tuned_precision']:9.4f}"
            f"{row['tuned_recall']:9.4f}"
            f"{row['tuned_f1']:9.4f}"
            f"{row['f1_change']:9.4f}"
        )

    print("-" * 106)


# ============================================================
# 12. Main
# ============================================================

def main():

    device = torch.device(
        "cuda"
        if torch.cuda.is_available()
        else "cpu"
    )

    print()
    print("=" * 70)
    print("I-SPOT SUBTYPE V2 THRESHOLD TUNING")
    print("=" * 70)

    print(
        f"Device : {device}"
    )

    if torch.cuda.is_available():

        print(
            f"GPU    : "
            f"{torch.cuda.get_device_name(0)}"
        )

    # --------------------------------------------------------
    # Model
    # --------------------------------------------------------

    tokenizer, model = load_model(
        device
    )

    # --------------------------------------------------------
    # Validation Data
    # --------------------------------------------------------

    valid_df = pd.read_csv(
        VALID_PATH
    )

    dataset = SubtypeDataset(
        valid_df,
        tokenizer,
    )

    loader = DataLoader(
        dataset,
        batch_size=BATCH_SIZE,
        shuffle=False,
        num_workers=2,
        pin_memory=True,
    )

    print(
        f"Valid  : {len(dataset)}"
    )

    # --------------------------------------------------------
    # 전체 Validation score 추론
    # --------------------------------------------------------

    probabilities, y_true = (
        predict_validation(
            model,
            loader,
            device,
        )
    )

    # --------------------------------------------------------
    # Baseline 0.50
    # --------------------------------------------------------

    base_prediction = (
        probabilities
        >= BASE_THRESHOLD
    ).astype(int)

    base_metrics = (
        calculate_overall_metrics(
            y_true,
            base_prediction,
        )
    )

    # --------------------------------------------------------
    # Threshold Tuning
    # --------------------------------------------------------

    (
        tuned_thresholds,
        result_df,
    ) = tune_thresholds(
        y_true,
        probabilities,
    )

    tuned_prediction = (
        probabilities
        >= tuned_thresholds.reshape(
            1,
            -1,
        )
    ).astype(int)

    tuned_metrics = (
        calculate_overall_metrics(
            y_true,
            tuned_prediction,
        )
    )

    # --------------------------------------------------------
    # 결과 출력
    # --------------------------------------------------------

    print_threshold_result(
        result_df
    )

    print()
    print("=" * 70)
    print("OVERALL COMPARISON")
    print("=" * 70)

    print(
        f"{'Metric':20s}"
        f"{'Base 0.50':>15s}"
        f"{'Tuned':>15s}"
        f"{'Change':>15s}"
    )

    print("-" * 65)

    for metric_name in [
        "micro_f1",
        "macro_f1",
        "exact_match",
    ]:

        base_value = base_metrics[
            metric_name
        ]

        tuned_value = tuned_metrics[
            metric_name
        ]

        print(
            f"{metric_name:20s}"
            f"{base_value:15.4f}"
            f"{tuned_value:15.4f}"
            f"{tuned_value - base_value:15.4f}"
        )

    # --------------------------------------------------------
    # 최종 threshold 출력
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("TUNED THRESHOLDS")
    print("=" * 70)

    for label, threshold in zip(
        LABEL_NAMES,
        tuned_thresholds,
    ):

        print(
            f"{label:30s}: "
            f"{threshold:.2f}"
        )

    # --------------------------------------------------------
    # CSV 저장
    # --------------------------------------------------------

    RESULT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    result_df.to_csv(
        THRESHOLD_RESULT_PATH,
        index=False,
        encoding="utf-8-sig",
    )

    summary_df = pd.DataFrame(
        [
            {
                "setting": "base_0.50",
                **base_metrics,
            },
            {
                "setting": "tuned",
                **tuned_metrics,
            },
        ]
    )

    summary_df.to_csv(
        SUMMARY_RESULT_PATH,
        index=False,
        encoding="utf-8-sig",
    )

    print()
    print(
        f"상세 결과: "
        f"{THRESHOLD_RESULT_PATH}"
    )

    print(
        f"비교 결과: "
        f"{SUMMARY_RESULT_PATH}"
    )

    print()
    print(
        "주의: 동일 Validation 데이터에서 "
        "threshold를 선택했으므로 최종 독립 Test 성능이 아니라 "
        "threshold tuning 결과로 해석해야 합니다."
    )


if __name__ == "__main__":
    main()