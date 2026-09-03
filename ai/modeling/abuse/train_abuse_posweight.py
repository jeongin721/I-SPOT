"""
기존 A-only 멀티라벨 학대 신호 모델에 pos_weight를 적용해 클래스 불균형 영향을 줄이는 실험용 학습 코드.
기존 베이스라인과 동일한 설정을 유지하고 BCEWithLogitsLoss의 가중치만 변경해 성능을 비교한다.
"""

import random
import warnings
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import torch.nn as nn

from sklearn.metrics import (
    classification_report,
    f1_score,
)

from torch.utils.data import DataLoader

from transformers import (
    AutoModelForSequenceClassification,
    AutoTokenizer,
)

from ai.modeling.abuse.utils.Custom_utils import (
    KoreanTextDataset,
    LABEL_NAMES,
)


# ============================================================
# 기본 설정
# ============================================================

warnings.filterwarnings("ignore")

CFG = {
    "EPOCHS": 20,
    "LEARNING_RATE": 2e-5,
    "BATCH_SIZE": 16,
    "SEED": 69,
    "MAX_LEN": 512,
    "EARLY_STOP": 5,
    "MODEL_ID": "klue/roberta-base",
    "THRESHOLD": 0.5,
}


# ============================================================
# 파일 경로 설정
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

TRAIN_DATA_PATH = (
    BASE_DIR
    / "datasets"
    / "train_multilabel.csv"
)

VALID_DATA_PATH = (
    BASE_DIR
    / "datasets"
    / "valid_multilabel.csv"
)

WEIGHT_DIR = (
    BASE_DIR
    / "weight"
)

WEIGHT_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

today = datetime.now().strftime(
    "%Y-%m-%d"
)

MODEL_SAVE_PATH = (
    WEIGHT_DIR
    / f"roberta_multilabel_posweight_{today}.pth"
)


# ============================================================
# 랜덤 시드 고정
# ============================================================

def seed_everything(seed: int):
    random.seed(seed)
    np.random.seed(seed)

    torch.manual_seed(seed)
    torch.cuda.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)

    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False


seed_everything(
    CFG["SEED"]
)


# ============================================================
# GPU 설정
# ============================================================

device = torch.device(
    "cuda"
    if torch.cuda.is_available()
    else "cpu"
)

print(
    "Device:",
    device,
)

if torch.cuda.is_available():
    print(
        "GPU:",
        torch.cuda.get_device_name(0),
    )


# ============================================================
# 데이터 로드
# ============================================================

print()
print(
    "===== DATA LOADING ====="
)

train_df = pd.read_csv(
    TRAIN_DATA_PATH
)

valid_df = pd.read_csv(
    VALID_DATA_PATH
)

print(
    "Train:",
    len(train_df),
)

print(
    "Valid:",
    len(valid_df),
)

print(
    "Labels:",
    LABEL_NAMES,
)


# ============================================================
# Tokenizer 생성
# ============================================================

tokenizer = AutoTokenizer.from_pretrained(
    CFG["MODEL_ID"]
)


# ============================================================
# Dataset 생성
# ============================================================

train_dataset = KoreanTextDataset(
    train_df,
    tokenizer,
    CFG["MAX_LEN"],
)

valid_dataset = KoreanTextDataset(
    valid_df,
    tokenizer,
    CFG["MAX_LEN"],
)


# ============================================================
# DataLoader 생성
# ============================================================

train_loader = DataLoader(
    train_dataset,
    batch_size=CFG["BATCH_SIZE"],
    shuffle=True,
)

valid_loader = DataLoader(
    valid_dataset,
    batch_size=CFG["BATCH_SIZE"],
    shuffle=False,
)


# ============================================================
# Multi-label RoBERTa 모델 생성
# ============================================================

model = AutoModelForSequenceClassification.from_pretrained(
    CFG["MODEL_ID"],
    num_labels=len(LABEL_NAMES),
    problem_type="multi_label_classification",
)

model.to(device)


# ============================================================
# pos_weight 설정
#
# 계산식:
#   음성 샘플 수 / 양성 샘플 수
#
# 기존 train 2876건 기준:
# 신체학대 579
# 정서학대 850
# 성학대   251
# 방임     459
# ============================================================

positive_counts = torch.tensor(
    [
        579,
        850,
        251,
        459,
    ],
    dtype=torch.float32,
)

negative_counts = (
    len(train_df)
    - positive_counts
)

pos_weight = (
    negative_counts
    / positive_counts
).to(device)

print()
print(
    "===== POS WEIGHT ====="
)

for label_name, weight in zip(
    LABEL_NAMES,
    pos_weight.detach().cpu().numpy(),
):
    print(
        f"{label_name}: "
        f"{weight:.4f}"
    )


# ============================================================
# Loss / Optimizer
#
# 양성 샘플이 적은 학대 유형에 더 높은 가중치를 주어
# 소수 클래스의 미탐을 줄이는 실험을 수행한다.
# ============================================================

criterion = nn.BCEWithLogitsLoss(
    pos_weight=pos_weight
)

optimizer = torch.optim.AdamW(
    model.parameters(),
    lr=CFG["LEARNING_RATE"],
)


# ============================================================
# 학습 함수
# ============================================================

def train_one_epoch():
    model.train()

    total_loss = 0.0

    for batch in train_loader:

        # ----------------------------------------------------
        # Dataset 반환 key를 모델 입력 형식에 맞게 가져온다.
        # ----------------------------------------------------

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
        ].to(device).float()

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

        total_loss += loss.item()

    return (
        total_loss
        / len(train_loader)
    )


# ============================================================
# Validation 함수
# ============================================================

def validate():
    model.eval()

    total_loss = 0.0

    all_labels = []
    all_probabilities = []

    with torch.no_grad():

        for batch in valid_loader:

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
            ].to(device).float()

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

            total_loss += loss.item()

            probabilities = torch.sigmoid(
                logits
            )

            all_labels.append(
                labels.cpu().numpy()
            )

            all_probabilities.append(
                probabilities.cpu().numpy()
            )

    y_true = np.concatenate(
        all_labels,
        axis=0,
    )

    y_prob = np.concatenate(
        all_probabilities,
        axis=0,
    )

    y_pred = (
        y_prob
        >= CFG["THRESHOLD"]
    ).astype(int)

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

    per_label_f1 = f1_score(
        y_true,
        y_pred,
        average=None,
        zero_division=0,
    )

    validation_loss = (
        total_loss
        / len(valid_loader)
    )

    return (
        validation_loss,
        micro_f1,
        macro_f1,
        per_label_f1,
        y_true,
        y_pred,
    )


# ============================================================
# 모델 학습
#
# Validation Macro F1 기준으로 가장 좋은 모델을 저장한다.
# EARLY_STOP 횟수 동안 개선되지 않으면 학습을 종료한다.
# ============================================================

best_macro_f1 = -1.0
early_stop_count = 0

print()
print(
    "======================================"
)

print(
    "   A-ONLY POS-WEIGHT TRAINING"
)

print(
    "======================================"
)

print(
    "Input: 아동 답변(A) only"
)

print(
    "Threshold:",
    CFG["THRESHOLD"],
)

print(
    "Model save:",
    MODEL_SAVE_PATH,
)


for epoch in range(
    1,
    CFG["EPOCHS"] + 1,
):

    print()
    print(
        f"===== Epoch "
        f"{epoch}/{CFG['EPOCHS']} ====="
    )

    train_loss = train_one_epoch()

    (
        valid_loss,
        micro_f1,
        macro_f1,
        per_label_f1,
        y_true,
        y_pred,
    ) = validate()

    print(
        f"Train Loss          : "
        f"{train_loss:.4f}"
    )

    print(
        f"Validation Loss     : "
        f"{valid_loss:.4f}"
    )

    print(
        f"Validation Micro F1 : "
        f"{micro_f1:.4f}"
    )

    print(
        f"Validation Macro F1 : "
        f"{macro_f1:.4f}"
    )

    print()
    print(
        "===== Per-label F1 ====="
    )

    for label_name, score in zip(
        LABEL_NAMES,
        per_label_f1,
    ):
        print(
            f"{label_name}: "
            f"{score:.4f}"
        )

    # --------------------------------------------------------
    # 최고 Macro F1 모델 저장
    # --------------------------------------------------------

    if macro_f1 > best_macro_f1:

        best_macro_f1 = macro_f1
        early_stop_count = 0

        torch.save(
            model.state_dict(),
            MODEL_SAVE_PATH,
        )

        print()
        print(
            f"Best model saved "
            f"(Macro F1: "
            f"{best_macro_f1:.4f})"
        )

    else:

        early_stop_count += 1

        print()
        print(
            "Early stopping:",
            f"{early_stop_count}"
            f"/{CFG['EARLY_STOP']}",
        )

    # --------------------------------------------------------
    # Early stopping
    # --------------------------------------------------------

    if (
        early_stop_count
        >= CFG["EARLY_STOP"]
    ):

        print()
        print(
            "Early stopping triggered."
        )

        break


# ============================================================
# 최고 성능 모델 다시 로드
# ============================================================

print()
print(
    "======================================"
)

print(
    "   BEST POS-WEIGHT MODEL EVALUATION"
)

print(
    "======================================"
)

state_dict = torch.load(
    MODEL_SAVE_PATH,
    map_location=device,
)

model.load_state_dict(
    state_dict
)

(
    valid_loss,
    micro_f1,
    macro_f1,
    per_label_f1,
    y_true,
    y_pred,
) = validate()


# ============================================================
# 최종 평가 결과 출력
# ============================================================

print(
    f"Best Validation Micro F1: "
    f"{micro_f1:.4f}"
)

print(
    f"Best Validation Macro F1: "
    f"{macro_f1:.4f}"
)

print()
print(
    "===== Per-label F1 ====="
)

for label_name, score in zip(
    LABEL_NAMES,
    per_label_f1,
):
    print(
        f"{label_name}: "
        f"{score:.4f}"
    )

print()
print(
    "===== Classification Report ====="
)

print(
    classification_report(
        y_true,
        y_pred,
        target_names=LABEL_NAMES,
        zero_division=0,
    )
)

print()
print(
    "Best Model Path:"
)

print(
    MODEL_SAVE_PATH
)