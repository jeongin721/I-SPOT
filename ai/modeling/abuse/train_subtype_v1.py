"""
I-SPOT 2차 15개 세부유형 Multi-label RoBERTa baseline을 학습한다.
tqdm, Early Stopping, Best Weight 저장과 Micro/Macro/Per-label 평가를 수행한다.
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
# 2. 기본 설정
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

TRAIN_PATH = DATASET_DIR / "subtype_train_v1.csv"
VALID_PATH = DATASET_DIR / "subtype_valid_v1.csv"

BEST_WEIGHT_PATH = (
    WEIGHT_DIR
    / "roberta_subtype_v1_best.pth"
)

RESULT_PATH = (
    RESULT_DIR
    / "roberta_subtype_v1_history.csv"
)


# ============================================================
# 3. 학습할 15개 subtype
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

MAX_EPOCHS = 15
EARLY_STOPPING_PATIENCE = 3

THRESHOLD = 0.50

SEED = 42


# ============================================================
# 5. 재현성 설정
# ============================================================

def set_seed(seed: int) -> None:
    """Python, NumPy, PyTorch random seed를 고정한다."""

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
    """Q+A text와 15차원 Multi-hot label을 제공한다."""

    def __init__(
        self,
        dataframe: pd.DataFrame,
        tokenizer,
        max_length: int,
    ):
        self.dataframe = dataframe.reset_index(
            drop=True
        )

        self.tokenizer = tokenizer
        self.max_length = max_length

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

        label = json.loads(
            row["label"]
        )

        if len(label) != NUM_LABELS:
            raise ValueError(
                f"Label 길이 오류: "
                f"{len(label)} != {NUM_LABELS}"
            )

        encoded = self.tokenizer(
            text,
            truncation=True,
            padding="max_length",
            max_length=self.max_length,
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
                label,
                dtype=torch.float32,
            ),
        }


# ============================================================
# 7. DataLoader 생성
# ============================================================

def create_dataloaders(
    tokenizer,
) -> Tuple[DataLoader, DataLoader]:

    train_df = pd.read_csv(
        TRAIN_PATH
    )

    valid_df = pd.read_csv(
        VALID_PATH
    )

    print()
    print("=" * 70)
    print("DATASET")
    print("=" * 70)
    print(f"Train : {len(train_df)}")
    print(f"Valid : {len(valid_df)}")

    train_dataset = SubtypeDataset(
        dataframe=train_df,
        tokenizer=tokenizer,
        max_length=MAX_LENGTH,
    )

    valid_dataset = SubtypeDataset(
        dataframe=valid_df,
        tokenizer=tokenizer,
        max_length=MAX_LENGTH,
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

    return train_loader, valid_loader


# ============================================================
# 8. Train 1 Epoch
# ============================================================

def train_one_epoch(
    model,
    loader: DataLoader,
    optimizer,
    criterion,
    device: torch.device,
    epoch: int,
) -> float:

    model.train()

    total_loss = 0.0

    progress = tqdm(
        loader,
        desc=f"Epoch {epoch} Train",
        leave=True,
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

        labels = batch[
            "labels"
        ].to(
            device,
            non_blocking=True,
        )

        optimizer.zero_grad(
            set_to_none=True
        )

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
            max_norm=1.0,
        )

        optimizer.step()

        total_loss += loss.item()

        average_loss = (
            total_loss
            / max(
                1,
                progress.n,
            )
        )

        progress.set_postfix(
            loss=f"{loss.item():.4f}",
            avg=f"{average_loss:.4f}",
        )

    return total_loss / len(loader)


# ============================================================
# 9. Validation
# ============================================================

@torch.no_grad()
def validate(
    model,
    loader: DataLoader,
    criterion,
    device: torch.device,
    epoch: int,
):
    """Validation loss와 전체 예측/정답을 반환한다."""

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

        labels = batch[
            "labels"
        ].to(
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
            probabilities
            >= THRESHOLD
        ).int()

        all_labels.append(
            labels
            .cpu()
            .numpy()
            .astype(int)
        )

        all_predictions.append(
            predictions
            .cpu()
            .numpy()
        )

    y_true = np.concatenate(
        all_labels,
        axis=0,
    )

    y_pred = np.concatenate(
        all_predictions,
        axis=0,
    )

    valid_loss = (
        total_loss
        / len(loader)
    )

    return (
        valid_loss,
        y_true,
        y_pred,
    )


# ============================================================
# 10. Metric 계산
# ============================================================

def calculate_metrics(
    y_true: np.ndarray,
    y_pred: np.ndarray,
):
    """Micro/Macro/Exact 및 subtype별 P/R/F1을 계산한다."""

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
# 11. Per-label 결과 출력
# ============================================================

def print_per_label_metrics(
    metrics,
):
    """15개 subtype별 Precision / Recall / F1을 출력한다."""

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

    for index, label in enumerate(
        LABEL_NAMES
    ):

        print(
            f"{label:30s}"
            f"{metrics['precision'][index]:9.4f}"
            f"{metrics['recall'][index]:9.4f}"
            f"{metrics['f1'][index]:9.4f}"
            f"{int(metrics['support'][index]):10d}"
        )

    print("-" * 82)


# ============================================================
# 12. Best Model 저장
# ============================================================

def save_best_model(
    model,
    epoch: int,
    metrics,
):
    """가장 높은 Macro F1 모델을 저장한다."""

    WEIGHT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    torch.save(
        {
            "epoch": epoch,
            "model_state_dict": (
                model.state_dict()
            ),
            "model_name": MODEL_NAME,
            "label_names": LABEL_NAMES,
            "threshold": THRESHOLD,
            "macro_f1": metrics[
                "macro_f1"
            ],
            "micro_f1": metrics[
                "micro_f1"
            ],
        },
        BEST_WEIGHT_PATH,
    )


# ============================================================
# 13. Main
# ============================================================

def main():

    set_seed(
        SEED
    )

    # --------------------------------------------------------
    # Device
    # --------------------------------------------------------

    device = torch.device(
        "cuda"
        if torch.cuda.is_available()
        else "cpu"
    )

    print()
    print("=" * 70)
    print("I-SPOT SUBTYPE MODEL V1")
    print("=" * 70)

    print(
        f"Device       : {device}"
    )

    if torch.cuda.is_available():

        print(
            f"GPU          : "
            f"{torch.cuda.get_device_name(0)}"
        )

    print(
        f"Model        : {MODEL_NAME}"
    )

    print(
        f"Labels       : {NUM_LABELS}"
    )

    print(
        f"Threshold    : {THRESHOLD}"
    )

    # --------------------------------------------------------
    # Tokenizer / Model
    # --------------------------------------------------------

    tokenizer = AutoTokenizer.from_pretrained(
        MODEL_NAME
    )

    model = (
        AutoModelForSequenceClassification
        .from_pretrained(
            MODEL_NAME,
            num_labels=NUM_LABELS,
            problem_type=(
                "multi_label_classification"
            ),
        )
    )

    model.to(
        device
    )

    # --------------------------------------------------------
    # Data
    # --------------------------------------------------------

    train_loader, valid_loader = (
        create_dataloaders(
            tokenizer
        )
    )

    # --------------------------------------------------------
    # Loss
    #
    # 첫 baseline에서는 pos_weight를 넣지 않는다.
    # 먼저 원본 데이터 기준 성능을 확인한다.
    # --------------------------------------------------------

    criterion = nn.BCEWithLogitsLoss()

    # --------------------------------------------------------
    # Optimizer
    # --------------------------------------------------------

    optimizer = AdamW(
        model.parameters(),
        lr=LEARNING_RATE,
        weight_decay=WEIGHT_DECAY,
    )

    # --------------------------------------------------------
    # 학습 상태
    # --------------------------------------------------------

    best_macro_f1 = -1.0
    best_epoch = 0
    patience_count = 0

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
        print(
            f"EPOCH {epoch}/{MAX_EPOCHS}"
        )
        print("=" * 70)

        train_loss = train_one_epoch(
            model=model,
            loader=train_loader,
            optimizer=optimizer,
            criterion=criterion,
            device=device,
            epoch=epoch,
        )

        (
            valid_loss,
            y_true,
            y_pred,
        ) = validate(
            model=model,
            loader=valid_loader,
            criterion=criterion,
            device=device,
            epoch=epoch,
        )

        metrics = calculate_metrics(
            y_true=y_true,
            y_pred=y_pred,
        )

        # ----------------------------------------------------
        # Epoch 결과
        # ----------------------------------------------------

        print()
        print(
            f"Train Loss : "
            f"{train_loss:.4f}"
        )

        print(
            f"Valid Loss : "
            f"{valid_loss:.4f}"
        )

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

        print_per_label_metrics(
            metrics
        )

        # ----------------------------------------------------
        # History
        # ----------------------------------------------------

        history.append(
            {
                "epoch": epoch,
                "train_loss": train_loss,
                "valid_loss": valid_loss,
                "micro_f1": metrics[
                    "micro_f1"
                ],
                "macro_f1": metrics[
                    "macro_f1"
                ],
                "exact_match": metrics[
                    "exact_match"
                ],
            }
        )

        # ----------------------------------------------------
        # Best Macro F1
        # ----------------------------------------------------

        if (
            metrics["macro_f1"]
            > best_macro_f1
        ):

            best_macro_f1 = metrics[
                "macro_f1"
            ]

            best_epoch = epoch
            patience_count = 0

            save_best_model(
                model=model,
                epoch=epoch,
                metrics=metrics,
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
        # History 저장
        # ----------------------------------------------------

        RESULT_DIR.mkdir(
            parents=True,
            exist_ok=True,
        )

        pd.DataFrame(
            history
        ).to_csv(
            RESULT_PATH,
            index=False,
            encoding="utf-8-sig",
        )

        # ----------------------------------------------------
        # Early Stopping
        # ----------------------------------------------------

        if (
            patience_count
            >= EARLY_STOPPING_PATIENCE
        ):

            print()
            print(
                "Early Stopping 실행"
            )

            break

    # ========================================================
    # 완료
    # ========================================================

    print()
    print("=" * 70)
    print("TRAINING COMPLETE")
    print("=" * 70)

    print(
        f"Best Epoch    : {best_epoch}"
    )

    print(
        f"Best Macro F1 : "
        f"{best_macro_f1:.4f}"
    )

    print(
        f"Best Weight   : "
        f"{BEST_WEIGHT_PATH}"
    )

    print(
        f"History       : "
        f"{RESULT_PATH}"
    )


if __name__ == "__main__":
    main()