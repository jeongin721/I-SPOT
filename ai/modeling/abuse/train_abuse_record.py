"""
규칙 기반 상담사 기록형 텍스트로 4개 학대 관련 신호를 Multi-label 분류하는 RoBERTa 학습 스크립트.
기존 A-only/QA 실험은 보존하고 record 전용 데이터셋으로 별도 학습·평가한다.
"""

import os
import random
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from sklearn.metrics import classification_report, f1_score
from torch.nn import BCEWithLogitsLoss
from torch.optim import AdamW
from torch.utils.data import DataLoader
from tqdm import tqdm
from transformers import AutoModelForSequenceClassification, AutoTokenizer

from ai.modeling.abuse.utils.Custom_utils import (
    KoreanTextDataset,
)


# ============================================================
# 설정
# ============================================================

class CFG:
    MODEL_ID = "klue/roberta-base"

    EPOCHS = 20
    BATCH_SIZE = 16
    LR = 2e-5

    MAX_LEN = 512
    THRESHOLD = 0.5

    EARLY_STOP = 5
    SEED = 69


LABEL_NAMES = [
    "신체학대",
    "정서학대",
    "성학대",
    "방임",
]

NUM_LABELS = len(LABEL_NAMES)


# ============================================================
# 프로젝트 경로
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[3]

DATASET_DIR = (
    PROJECT_ROOT
    / "ai"
    / "modeling"
    / "abuse"
    / "datasets"
)

TRAIN_PATH = (
    DATASET_DIR
    / "train_multilabel_record.csv"
)

VALID_PATH = (
    DATASET_DIR
    / "valid_multilabel_record.csv"
)

WEIGHT_DIR = (
    PROJECT_ROOT
    / "ai"
    / "modeling"
    / "abuse"
    / "weight"
)

WEIGHT_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

TODAY = datetime.now().strftime(
    "%Y-%m-%d"
)

BEST_MODEL_PATH = (
    WEIGHT_DIR
    / f"roberta_multilabel_record_{TODAY}.pth"
)


# ============================================================
# Seed 고정
# ============================================================

def seed_everything(seed: int) -> None:
    """재현성을 위해 Python/Numpy/PyTorch Seed를 고정한다."""

    random.seed(seed)

    os.environ[
        "PYTHONHASHSEED"
    ] = str(seed)

    np.random.seed(seed)

    torch.manual_seed(seed)

    torch.cuda.manual_seed(seed)

    torch.cuda.manual_seed_all(seed)

    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False


# ============================================================
# 라벨 문자열 → 벡터 변환
# ============================================================

def parse_label(label_text: str) -> list:
    """
    CSV의 '[1, 0, 1, 0]' 형태 문자열을
    float Multi-label 벡터로 변환한다.
    """

    label_text = (
        str(label_text)
        .replace("[", "")
        .replace("]", "")
    )

    return [
        float(value.strip())
        for value in label_text.split(",")
    ]


# ============================================================
# 데이터 로드
# ============================================================

def load_dataframe(
    path: Path,
) -> pd.DataFrame:
    """기록형 CSV를 학습용 DataFrame으로 준비한다."""

    dataframe = pd.read_csv(
        path
    )

    # --------------------------------------------------------
    # 기존 KoreanTextDataset이 audio_text 컬럼을 사용하므로
    # record 데이터의 text 컬럼을 그대로 매핑한다.
    # --------------------------------------------------------

    dataframe[
        "audio_text"
    ] = dataframe[
        "text"
    ]

    dataframe[
        "label"
    ] = dataframe[
        "label"
    ].apply(
        parse_label
    )

    return dataframe


# ============================================================
# Multi-label 평가
# ============================================================

def calculate_metrics(
    labels: np.ndarray,
    probabilities: np.ndarray,
) -> tuple:
    """Sigmoid 확률을 threshold 0.5로 이진화해 F1을 계산한다."""

    predictions = (
        probabilities
        >= CFG.THRESHOLD
    ).astype(int)

    micro_f1 = f1_score(
        labels,
        predictions,
        average="micro",
        zero_division=0,
    )

    macro_f1 = f1_score(
        labels,
        predictions,
        average="macro",
        zero_division=0,
    )

    return (
        predictions,
        micro_f1,
        macro_f1,
    )


# ============================================================
# Train 1 Epoch
# ============================================================

def train_one_epoch(
    model,
    loader,
    optimizer,
    criterion,
    device,
) -> float:
    """한 Epoch 학습을 수행하고 평균 Loss를 반환한다."""

    model.train()

    running_loss = 0.0

    progress_bar = tqdm(
        loader,
        desc="Train",
        leave=False,
    )

    for batch in progress_bar:

        input_ids = batch[
            "ids"
        ].to(device)

        attention_mask = batch[
            "mask"
        ].to(device)

        token_type_ids = batch[
            "token_type_ids"
        ].to(device)

        labels = batch[
            "labels"
        ].float().to(device)

        optimizer.zero_grad()

        outputs = model(
            input_ids=input_ids,
            attention_mask=attention_mask,
            token_type_ids=token_type_ids,
        )

        logits = outputs.logits

        loss = criterion(
            logits,
            labels,
        )

        loss.backward()

        optimizer.step()

        running_loss += (
            loss.item()
        )

        progress_bar.set_postfix(
            loss=f"{loss.item():.4f}"
        )

    return (
        running_loss
        / len(loader)
    )


# ============================================================
# Validation
# ============================================================

def validate(
    model,
    loader,
    criterion,
    device,
) -> tuple:
    """Validation Loss와 Micro/Macro F1 계산용 결과를 반환한다."""

    model.eval()

    running_loss = 0.0

    all_probabilities = []
    all_labels = []

    progress_bar = tqdm(
        loader,
        desc="Valid",
        leave=False,
    )

    with torch.no_grad():

        for batch in progress_bar:

            input_ids = batch[
                "ids"
            ].to(device)

            attention_mask = batch[
                "mask"
            ].to(device)

            token_type_ids = batch[
                "token_type_ids"
            ].to(device)

            labels = batch[
                "labels"
            ].float().to(device)

            outputs = model(
                input_ids=input_ids,
                attention_mask=attention_mask,
                token_type_ids=token_type_ids,
            )

            logits = outputs.logits

            loss = criterion(
                logits,
                labels,
            )

            running_loss += (
                loss.item()
            )

            probabilities = torch.sigmoid(
                logits
            )

            all_probabilities.append(
                probabilities
                .cpu()
                .numpy()
            )

            all_labels.append(
                labels
                .cpu()
                .numpy()
            )

            progress_bar.set_postfix(
                loss=f"{loss.item():.4f}"
            )

    probabilities = np.concatenate(
        all_probabilities,
        axis=0,
    )

    labels = np.concatenate(
        all_labels,
        axis=0,
    )

    validation_loss = (
        running_loss
        / len(loader)
    )

    return (
        validation_loss,
        probabilities,
        labels,
    )


# ============================================================
# Main
# ============================================================

def main() -> None:
    """Record 모델 전체 학습 및 평가를 수행한다."""

    # --------------------------------------------------------
    # 1. Seed
    # --------------------------------------------------------

    seed_everything(
        CFG.SEED
    )

    # --------------------------------------------------------
    # 2. Device
    # --------------------------------------------------------

    device = torch.device(
        "cuda"
        if torch.cuda.is_available()
        else "cpu"
    )

    print(
        f"Device: {device}"
    )

    if torch.cuda.is_available():
        print(
            "GPU:",
            torch.cuda.get_device_name(0),
        )

    # --------------------------------------------------------
    # 3. 데이터 로드
    # --------------------------------------------------------

    train_df = load_dataframe(
        TRAIN_PATH
    )

    valid_df = load_dataframe(
        VALID_PATH
    )

    print(
        f"Train samples: {len(train_df)}"
    )

    print(
        f"Valid samples: {len(valid_df)}"
    )

    # --------------------------------------------------------
    # 4. Tokenizer
    # --------------------------------------------------------

    tokenizer = AutoTokenizer.from_pretrained(
        CFG.MODEL_ID
    )

    # --------------------------------------------------------
    # 5. Dataset
    # --------------------------------------------------------

    train_dataset = KoreanTextDataset(
    train_df,
    tokenizer,
    CFG.MAX_LEN,
    with_labels=True,
    )

    valid_dataset = KoreanTextDataset(
        valid_df,
        tokenizer,
        CFG.MAX_LEN,
        with_labels=True,
    )

    # --------------------------------------------------------
    # 6. DataLoader
    # --------------------------------------------------------

    train_loader = DataLoader(
        train_dataset,
        batch_size=CFG.BATCH_SIZE,
        shuffle=True,
        num_workers=0,
    )

    valid_loader = DataLoader(
        valid_dataset,
        batch_size=CFG.BATCH_SIZE,
        shuffle=False,
        num_workers=0,
    )

    # --------------------------------------------------------
    # 7. Model
    # --------------------------------------------------------

    model = (
        AutoModelForSequenceClassification
        .from_pretrained(
            CFG.MODEL_ID,
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
    # 8. Loss / Optimizer
    # --------------------------------------------------------

    criterion = BCEWithLogitsLoss()

    optimizer = AdamW(
        model.parameters(),
        lr=CFG.LR,
    )

    # --------------------------------------------------------
    # 9. Early Stopping 설정
    # --------------------------------------------------------

    best_macro_f1 = -1.0
    best_micro_f1 = -1.0

    patience = 0

    # --------------------------------------------------------
    # 10. Training
    # --------------------------------------------------------

    for epoch in range(
        1,
        CFG.EPOCHS + 1,
    ):

        print(
            "\n"
            + "=" * 70
        )

        print(
            f"Epoch {epoch}/{CFG.EPOCHS}"
        )

        print(
            "=" * 70
        )

        train_loss = train_one_epoch(
            model=model,
            loader=train_loader,
            optimizer=optimizer,
            criterion=criterion,
            device=device,
        )

        (
            valid_loss,
            probabilities,
            labels,
        ) = validate(
            model=model,
            loader=valid_loader,
            criterion=criterion,
            device=device,
        )

        (
            predictions,
            micro_f1,
            macro_f1,
        ) = calculate_metrics(
            labels,
            probabilities,
        )

        print(
            f"Train Loss : {train_loss:.4f}"
        )

        print(
            f"Valid Loss : {valid_loss:.4f}"
        )

        print(
            f"Micro F1   : {micro_f1:.4f}"
        )

        print(
            f"Macro F1   : {macro_f1:.4f}"
        )

        # ----------------------------------------------------
        # Macro F1 기준 Best Model 저장
        # ----------------------------------------------------

        if macro_f1 > best_macro_f1:

            best_macro_f1 = macro_f1
            best_micro_f1 = micro_f1

            patience = 0

            torch.save(
                model.state_dict(),
                BEST_MODEL_PATH,
            )

            print(
                f"[BEST] 모델 저장: {BEST_MODEL_PATH}"
            )

        else:

            patience += 1

            print(
                f"Early Stop patience: "
                f"{patience}/{CFG.EARLY_STOP}"
            )

        # ----------------------------------------------------
        # Early Stopping
        # ----------------------------------------------------

        if patience >= CFG.EARLY_STOP:

            print(
                "\nEarly Stopping"
            )

            break

    # ========================================================
    # 11. Best Model 다시 로드
    # ========================================================

    print(
        "\nBest model loading..."
    )

    model.load_state_dict(
        torch.load(
            BEST_MODEL_PATH,
            map_location=device,
            weights_only=True,
        )
    )

    # ========================================================
    # 12. Best Model 최종 Validation
    # ========================================================

    (
        _,
        probabilities,
        labels,
    ) = validate(
        model=model,
        loader=valid_loader,
        criterion=criterion,
        device=device,
    )

    (
        predictions,
        micro_f1,
        macro_f1,
    ) = calculate_metrics(
        labels,
        probabilities,
    )

    # ========================================================
    # 13. 최종 결과
    # ========================================================

    print(
        "\n"
        + "=" * 70
    )

    print(
        "FINAL BEST RESULT"
    )

    print(
        "=" * 70
    )

    print(
        f"Best Validation Micro F1: "
        f"{micro_f1:.4f}"
    )

    print(
        f"Best Validation Macro F1: "
        f"{macro_f1:.4f}"
    )

    print(
        "\nPer-label classification report"
    )

    print(
        classification_report(
            labels,
            predictions,
            target_names=LABEL_NAMES,
            digits=4,
            zero_division=0,
        )
    )

    print(
        f"Best Model: {BEST_MODEL_PATH}"
    )


if __name__ == "__main__":
    main()