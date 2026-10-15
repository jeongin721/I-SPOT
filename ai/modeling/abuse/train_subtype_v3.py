"""
I-SPOT 2차 15개 세부유형 RoBERTa v3를 학습한다.
v2와 동일한 pos_weight 설정을 유지하고 최대 epoch를 25로 늘려 추가 학습 효과를 비교한다.
"""

# ============================================================
# 1. Import
# ============================================================

import json
import random
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
from torch import nn
from torch.optim import AdamW
from torch.utils.data import DataLoader, Dataset
from tqdm import tqdm
from transformers import AutoModelForSequenceClassification, AutoTokenizer


# ============================================================
# 2. 경로
# ============================================================

BASE_DIR = Path("/data/I-SPOT")

DATASET_DIR = BASE_DIR / "ai" / "modeling" / "abuse" / "datasets"
WEIGHT_DIR = BASE_DIR / "ai" / "modeling" / "abuse" / "weight"
RESULT_DIR = BASE_DIR / "ai" / "modeling" / "abuse" / "results"

TRAIN_PATH = DATASET_DIR / "subtype_train_v1.csv"
VALID_PATH = DATASET_DIR / "subtype_valid_v1.csv"

BEST_WEIGHT_PATH = WEIGHT_DIR / "roberta_subtype_v3_best.pth"
RESULT_PATH = RESULT_DIR / "roberta_subtype_v3_history.csv"
POS_WEIGHT_PATH = RESULT_DIR / "roberta_subtype_v3_pos_weight.csv"

# ============================================================
# 3. 15개 Active Label
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
# 4. Hyperparameters
# ============================================================

MODEL_NAME = "klue/roberta-base"

MAX_LENGTH = 256

TRAIN_BATCH_SIZE = 16
VALID_BATCH_SIZE = 32

LEARNING_RATE = 2e-5
WEIGHT_DECAY = 0.01

MAX_EPOCHS = 25
EARLY_STOPPING_PATIENCE = 3

THRESHOLD = 0.50

# raw pos_weight가 너무 커지는 것을 방지
MAX_POS_WEIGHT = 10.0

SEED = 42


# ============================================================
# 5. Seed
# ============================================================

def set_seed(seed: int) -> None:
    """재현성을 위해 random seed를 고정한다."""

    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)

    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)

    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False


# ============================================================
# 6. Dataset
# ============================================================

class SubtypeDataset(Dataset):
    """Q+A text와 15차원 multi-hot label을 반환한다."""

    def __init__(
        self,
        dataframe: pd.DataFrame,
        tokenizer,
        max_length: int,
    ):
        self.dataframe = dataframe.reset_index(drop=True)
        self.tokenizer = tokenizer
        self.max_length = max_length

    def __len__(self) -> int:
        return len(self.dataframe)

    def __getitem__(self, index: int) -> Dict[str, torch.Tensor]:

        row = self.dataframe.iloc[index]

        text = str(row["text"])
        label = json.loads(row["label"])

        if len(label) != NUM_LABELS:
            raise ValueError(
                f"Label 길이 오류: {len(label)} != {NUM_LABELS}"
            )

        encoded = self.tokenizer(
            text,
            truncation=True,
            padding="max_length",
            max_length=self.max_length,
            return_tensors="pt",
        )

        return {
            "input_ids": encoded["input_ids"].squeeze(0),
            "attention_mask": encoded["attention_mask"].squeeze(0),
            "labels": torch.tensor(
                label,
                dtype=torch.float32,
            ),
        }


# ============================================================
# 7. Label Matrix
# ============================================================

def get_label_matrix(df: pd.DataFrame) -> np.ndarray:
    """CSV label 문자열을 N x 15 NumPy 배열로 변환한다."""

    labels = []

    for value in df["label"]:
        label = json.loads(value)

        if len(label) != NUM_LABELS:
            raise ValueError(
                f"Label 길이 오류: {len(label)} != {NUM_LABELS}"
            )

        labels.append(label)

    return np.asarray(
        labels,
        dtype=np.float32,
    )


# ============================================================
# 8. pos_weight 계산
# ============================================================

def calculate_pos_weight(
    train_df: pd.DataFrame,
) -> Tuple[torch.Tensor, pd.DataFrame]:
    """
    각 subtype별 pos_weight를 계산한다.

    raw = negative_count / positive_count
    final = min(raw, MAX_POS_WEIGHT)

    희소 라벨의 지나친 가중치 증가를 막기 위해 상한을 적용한다.
    """

    label_matrix = get_label_matrix(train_df)

    total = len(label_matrix)

    positive_count = label_matrix.sum(axis=0)
    negative_count = total - positive_count

    raw_weights = (
        negative_count
        / np.maximum(positive_count, 1.0)
    )

    clipped_weights = np.clip(
        raw_weights,
        a_min=1.0,
        a_max=MAX_POS_WEIGHT,
    )

    weight_df = pd.DataFrame(
        {
            "label": LABEL_NAMES,
            "positive": positive_count.astype(int),
            "negative": negative_count.astype(int),
            "raw_pos_weight": raw_weights,
            "final_pos_weight": clipped_weights,
        }
    )

    tensor = torch.tensor(
        clipped_weights,
        dtype=torch.float32,
    )

    return tensor, weight_df


# ============================================================
# 9. DataLoader
# ============================================================

def create_dataloaders(
    tokenizer,
) -> Tuple[
    DataLoader,
    DataLoader,
    pd.DataFrame,
]:
    """Train/Valid DataLoader와 Train DataFrame을 반환한다."""

    train_df = pd.read_csv(TRAIN_PATH)
    valid_df = pd.read_csv(VALID_PATH)

    print()
    print("=" * 70)
    print("DATASET")
    print("=" * 70)
    print(f"Train : {len(train_df)}")
    print(f"Valid : {len(valid_df)}")

    train_dataset = SubtypeDataset(
        train_df,
        tokenizer,
        MAX_LENGTH,
    )

    valid_dataset = SubtypeDataset(
        valid_df,
        tokenizer,
        MAX_LENGTH,
    )

    train_loader = DataLoader(
        train_dataset,
        batch_size=TRAIN_BATCH_SIZE,
        shuffle=True,
        num_workers=2,
        pin_memory=True,
    )

    valid_loader = DataLoader(
        valid_dataset,
        batch_size=VALID_BATCH_SIZE,
        shuffle=False,
        num_workers=2,
        pin_memory=True,
    )

    return train_loader, valid_loader, train_df


# ============================================================
# 10. Train
# ============================================================

def train_one_epoch(
    model,
    loader,
    optimizer,
    criterion,
    device,
    epoch,
) -> float:
    """한 epoch을 학습하고 평균 loss를 반환한다."""

    model.train()

    total_loss = 0.0

    progress = tqdm(
        loader,
        desc=f"Epoch {epoch} Train",
        leave=True,
    )

    for step, batch in enumerate(
        progress,
        start=1,
    ):
        input_ids = batch["input_ids"].to(
            device,
            non_blocking=True,
        )

        attention_mask = batch["attention_mask"].to(
            device,
            non_blocking=True,
        )

        labels = batch["labels"].to(
            device,
            non_blocking=True,
        )

        optimizer.zero_grad(set_to_none=True)

        outputs = model(
            input_ids=input_ids,
            attention_mask=attention_mask,
        )

        loss = criterion(
            outputs.logits,
            labels,
        )

        loss.backward()

        torch.nn.utils.clip_grad_norm_(
            model.parameters(),
            1.0,
        )

        optimizer.step()

        total_loss += loss.item()
        avg_loss = total_loss / step

        progress.set_postfix(
            loss=f"{loss.item():.4f}",
            avg=f"{avg_loss:.4f}",
        )

    return total_loss / len(loader)


# ============================================================
# 11. Validation
# ============================================================

@torch.no_grad()
def validate(
    model,
    loader,
    criterion,
    device,
    epoch,
):
    """Validation 예측과 loss를 계산한다."""

    model.eval()

    total_loss = 0.0

    all_labels: List[np.ndarray] = []
    all_predictions: List[np.ndarray] = []

    progress = tqdm(
        loader,
        desc=f"Epoch {epoch} Valid",
        leave=False,
    )

    for batch in progress:

        input_ids = batch["input_ids"].to(
            device,
            non_blocking=True,
        )

        attention_mask = batch["attention_mask"].to(
            device,
            non_blocking=True,
        )

        labels = batch["labels"].to(
            device,
            non_blocking=True,
        )

        outputs = model(
            input_ids=input_ids,
            attention_mask=attention_mask,
        )

        loss = criterion(
            outputs.logits,
            labels,
        )

        total_loss += loss.item()

        probabilities = torch.sigmoid(
            outputs.logits
        )

        predictions = (
            probabilities >= THRESHOLD
        ).int()

        all_labels.append(
            labels.cpu().numpy().astype(int)
        )

        all_predictions.append(
            predictions.cpu().numpy()
        )

    return (
        total_loss / len(loader),
        np.concatenate(all_labels),
        np.concatenate(all_predictions),
    )


# ============================================================
# 12. Metrics
# ============================================================

def calculate_metrics(
    y_true: np.ndarray,
    y_pred: np.ndarray,
):
    """전체 및 subtype별 성능을 계산한다."""

    micro_f1 = f1_score(
        y_true,
        y_pred,
        average="micro",
        zero_division=0,
    )

    macro_f1 = f1_score(
        y_true,
        y_pred,
        average="macro",
        zero_division=0,
    )

    exact_match = accuracy_score(
        y_true,
        y_pred,
    )

    precision, recall, f1, support = (
        precision_recall_fscore_support(
            y_true,
            y_pred,
            average=None,
            zero_division=0,
        )
    )

    return {
        "micro_f1": micro_f1,
        "macro_f1": macro_f1,
        "exact_match": exact_match,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "support": support,
    }


# ============================================================
# 13. Per-label 출력
# ============================================================

def print_per_label_metrics(metrics) -> None:
    """15개 subtype의 P/R/F1/Support를 출력한다."""

    print()
    print("-" * 82)

    print(
        f"{'Subtype':30s}"
        f"{'P':>9s}"
        f"{'R':>9s}"
        f"{'F1':>9s}"
        f"{'Support':>10s}"
    )

    print("-" * 82)

    for i, label in enumerate(LABEL_NAMES):

        print(
            f"{label:30s}"
            f"{metrics['precision'][i]:9.4f}"
            f"{metrics['recall'][i]:9.4f}"
            f"{metrics['f1'][i]:9.4f}"
            f"{int(metrics['support'][i]):10d}"
        )

    print("-" * 82)


# ============================================================
# 14. Best Model 저장
# ============================================================

def save_best_model(
    model,
    epoch,
    metrics,
    pos_weight,
) -> None:
    """Validation Macro F1 기준 Best 모델을 저장한다."""

    WEIGHT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    torch.save(
        {
            "epoch": epoch,
            "model_state_dict": model.state_dict(),
            "model_name": MODEL_NAME,
            "label_names": LABEL_NAMES,
            "threshold": THRESHOLD,
            "pos_weight": pos_weight.cpu(),
            "max_pos_weight": MAX_POS_WEIGHT,
            "macro_f1": metrics["macro_f1"],
            "micro_f1": metrics["micro_f1"],
        },
        BEST_WEIGHT_PATH,
    )


# ============================================================
# 15. Main
# ============================================================

def main():

    set_seed(SEED)

    device = torch.device(
        "cuda"
        if torch.cuda.is_available()
        else "cpu"
    )

    print()
    print("=" * 70)
    print("I-SPOT SUBTYPE MODEL V3 - POS WEIGHT / 25 EPOCHS")
    print("=" * 70)

    print(f"Device         : {device}")

    if torch.cuda.is_available():
        print(
            f"GPU            : "
            f"{torch.cuda.get_device_name(0)}"
        )

    print(f"Model          : {MODEL_NAME}")
    print(f"Labels         : {NUM_LABELS}")
    print(f"Threshold      : {THRESHOLD}")
    print(f"Max Pos Weight : {MAX_POS_WEIGHT}")

    # --------------------------------------------------------
    # Tokenizer / Model
    # --------------------------------------------------------

    tokenizer = AutoTokenizer.from_pretrained(
        MODEL_NAME
    )

    model = AutoModelForSequenceClassification.from_pretrained(
        MODEL_NAME,
        num_labels=NUM_LABELS,
        problem_type="multi_label_classification",
    )

    model.to(device)

    # --------------------------------------------------------
    # Data
    # --------------------------------------------------------

    (
        train_loader,
        valid_loader,
        train_df,
    ) = create_dataloaders(tokenizer)

    # --------------------------------------------------------
    # pos_weight
    # --------------------------------------------------------

    pos_weight, weight_df = calculate_pos_weight(
        train_df
    )

    RESULT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    weight_df.to_csv(
        POS_WEIGHT_PATH,
        index=False,
        encoding="utf-8-sig",
    )

    print()
    print("=" * 70)
    print("POS WEIGHT")
    print("=" * 70)

    print(
        weight_df.to_string(
            index=False,
        )
    )

    # GPU로 이동
    pos_weight = pos_weight.to(device)

    # --------------------------------------------------------
    # Weighted BCE
    # --------------------------------------------------------

    criterion = nn.BCEWithLogitsLoss(
        pos_weight=pos_weight
    )

    optimizer = AdamW(
        model.parameters(),
        lr=LEARNING_RATE,
        weight_decay=WEIGHT_DECAY,
    )

    # --------------------------------------------------------
    # Training state
    # --------------------------------------------------------

    best_macro_f1 = -1.0
    best_epoch = 0
    patience_count = 0

    best_metrics = None
    history = []

    # ========================================================
    # Training Loop
    # ========================================================

    for epoch in range(
        1,
        MAX_EPOCHS + 1,
    ):

        print()
        print("=" * 70)
        print(f"EPOCH {epoch}/{MAX_EPOCHS}")
        print("=" * 70)

        train_loss = train_one_epoch(
            model,
            train_loader,
            optimizer,
            criterion,
            device,
            epoch,
        )

        valid_loss, y_true, y_pred = validate(
            model,
            valid_loader,
            criterion,
            device,
            epoch,
        )

        metrics = calculate_metrics(
            y_true,
            y_pred,
        )

        print()
        print(f"Train Loss : {train_loss:.4f}")
        print(f"Valid Loss : {valid_loss:.4f}")
        print(
            f"Micro F1   : "
            f"{metrics['micro_f1']:.4f}"
        )
        print(
            f"Macro F1   : "
            f"{metrics['macro_f1']:.4f}"
        )
        print(
            f"Exact Match: "
            f"{metrics['exact_match']:.4f}"
        )

        print_per_label_metrics(metrics)

        # ----------------------------------------------------
        # History
        # ----------------------------------------------------

        history.append(
            {
                "epoch": epoch,
                "train_loss": train_loss,
                "valid_loss": valid_loss,
                "micro_f1": metrics["micro_f1"],
                "macro_f1": metrics["macro_f1"],
                "exact_match": metrics[
                    "exact_match"
                ],
            }
        )

        pd.DataFrame(history).to_csv(
            RESULT_PATH,
            index=False,
            encoding="utf-8-sig",
        )

        # ----------------------------------------------------
        # Best Model
        # ----------------------------------------------------

        if metrics["macro_f1"] > best_macro_f1:

            best_macro_f1 = metrics[
                "macro_f1"
            ]

            best_epoch = epoch
            best_metrics = metrics
            patience_count = 0

            save_best_model(
                model,
                epoch,
                metrics,
                pos_weight,
            )

            print(
                f"\n★ Best Model 저장 "
                f"(Macro F1="
                f"{best_macro_f1:.4f})"
            )

        else:

            patience_count += 1

            print(
                f"\nEarly Stopping "
                f"{patience_count}/"
                f"{EARLY_STOPPING_PATIENCE}"
            )

        # ----------------------------------------------------
        # Early Stopping
        # ----------------------------------------------------

        if (
            patience_count
            >= EARLY_STOPPING_PATIENCE
        ):

            print()
            print("Early Stopping 실행")
            break

    # ========================================================
    # 최종 Best 결과
    # ========================================================

    print()
    print("=" * 70)
    print("TRAINING COMPLETE")
    print("=" * 70)

    print(f"Best Epoch    : {best_epoch}")
    print(
        f"Best Micro F1 : "
        f"{best_metrics['micro_f1']:.4f}"
    )
    print(
        f"Best Macro F1 : "
        f"{best_metrics['macro_f1']:.4f}"
    )
    print(
        f"Best Exact    : "
        f"{best_metrics['exact_match']:.4f}"
    )

    print_per_label_metrics(
        best_metrics
    )

    print(
        f"\nBest Weight : "
        f"{BEST_WEIGHT_PATH}"
    )

    print(
        f"History     : "
        f"{RESULT_PATH}"
    )

    print(
        f"Pos Weight  : "
        f"{POS_WEIGHT_PATH}"
    )


if __name__ == "__main__":
    main()