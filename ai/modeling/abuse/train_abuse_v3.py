## v3 = PosWeight 실험

"""
A-only Hard Augmentation v2 데이터에 PosWeight를 적용해 KLUE-RoBERTa 4-label 모델을 학습한다.

v2와 동일한 데이터·하이퍼파라미터를 유지하고 클래스 불균형 보정 효과를
Validation Micro/Macro/라벨별 F1로 비교하며 최적 모델을 저장한다.
"""

from pathlib import Path
from datetime import datetime
import ast
import random
import time

import numpy as np
import pandas as pd
import torch
from sklearn.metrics import classification_report, f1_score
from torch.nn import BCEWithLogitsLoss
from torch.optim import AdamW
from torch.utils.data import DataLoader, Dataset
from tqdm.auto import tqdm
from transformers import AutoModelForSequenceClassification, AutoTokenizer


# ============================================================
# 1. 기본 설정
# ============================================================

SEED = 69

MODEL_ID = "klue/roberta-base"

EPOCHS = 20
BATCH_SIZE = 16
LEARNING_RATE = 2e-5
MAX_LEN = 512

# Baseline과 동일하게 우선 0.5 사용
THRESHOLD = 0.5

# Validation Macro F1이 5 epoch 연속 개선되지 않으면 종료
EARLY_STOP_PATIENCE = 5

LABEL_NAMES = [
    "신체학대",
    "정서학대",
    "성학대",
    "방임",
]

NUM_LABELS = len(LABEL_NAMES)


# ============================================================
# 2. 경로 설정
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[3]

DATASET_DIR = (
    PROJECT_ROOT
    / "ai"
    / "modeling"
    / "abuse"
    / "datasets"
)

TRAIN_PATH = DATASET_DIR / "train_multilabel_v2.csv"

# Validation은 기존 360건 그대로 사용
VALID_PATH = DATASET_DIR / "valid_multilabel.csv"

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

DATE_STRING = datetime.now().strftime("%Y-%m-%d")

BEST_MODEL_PATH = (
    WEIGHT_DIR
    / f"roberta_multilabel_v3_posweight_{DATE_STRING}.pth"
)


# ============================================================
# 3. 재현성 설정
# ============================================================

def set_seed(seed):
    """
    Python, NumPy, PyTorch의 랜덤 시드를 고정한다.
    """

    random.seed(seed)
    np.random.seed(seed)

    torch.manual_seed(seed)

    if torch.cuda.is_available():
        torch.cuda.manual_seed(seed)
        torch.cuda.manual_seed_all(seed)

    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False


set_seed(SEED)


# ============================================================
# 4. Device 설정
# ============================================================

DEVICE = torch.device(
    "cuda" if torch.cuda.is_available() else "cpu"
)

print("=" * 70)
print("A-only Multi-label v3 PosWeight Training")
print("=" * 70)

print(f"Device      : {DEVICE}")

if torch.cuda.is_available():
    print(f"GPU         : {torch.cuda.get_device_name(0)}")

print(f"Model       : {MODEL_ID}")
print(f"Train CSV   : {TRAIN_PATH}")
print(f"Valid CSV   : {VALID_PATH}")
print(f"Best Weight : {BEST_MODEL_PATH}")


# ============================================================
# 5. Label 문자열 → Tensor 변환
# ============================================================

def parse_label(value):
    """
    CSV에 저장된 '[1, 0, 0, 0]' 형태의 문자열을
    float32 NumPy 배열로 변환한다.
    """

    if isinstance(value, str):
        value = ast.literal_eval(value)

    label = np.asarray(
        value,
        dtype=np.float32,
    )

    if label.shape != (NUM_LABELS,):
        raise ValueError(
            f"잘못된 label shape: {label.shape} / value={value}"
        )

    return label


# ============================================================
# 6. Dataset
# ============================================================

class AbuseDataset(Dataset):
    """
    audio_text와 4차원 Multi-label을 RoBERTa 입력으로 변환한다.
    """

    def __init__(
        self,
        dataframe,
        tokenizer,
        max_len,
    ):
        self.dataframe = dataframe.reset_index(drop=True)
        self.tokenizer = tokenizer
        self.max_len = max_len

    def __len__(self):
        return len(self.dataframe)

    def __getitem__(self, index):
        row = self.dataframe.iloc[index]

        text = str(row["audio_text"])
        label = parse_label(row["label"])

        encoding = self.tokenizer(
            text,
            max_length=self.max_len,
            padding="max_length",
            truncation=True,
            return_tensors="pt",
        )

        return {
            "input_ids": encoding["input_ids"].squeeze(0),
            "attention_mask": encoding["attention_mask"].squeeze(0),
            "labels": torch.tensor(
                label,
                dtype=torch.float32,
            ),
        }


# ============================================================
# 7. 데이터 로드
# ============================================================

if not TRAIN_PATH.exists():
    raise FileNotFoundError(
        f"Train CSV를 찾을 수 없습니다: {TRAIN_PATH}"
    )

if not VALID_PATH.exists():
    raise FileNotFoundError(
        f"Validation CSV를 찾을 수 없습니다: {VALID_PATH}"
    )

train_df = pd.read_csv(TRAIN_PATH)
valid_df = pd.read_csv(VALID_PATH)

print()
print("[Dataset]")
print(f"Train      : {len(train_df)}")
print(f"Validation : {len(valid_df)}")

if len(train_df) != 3041:
    print(
        f"WARNING: 예상 Train 크기 3041과 다릅니다. "
        f"현재={len(train_df)}"
    )

if len(valid_df) != 360:
    print(
        f"WARNING: 예상 Validation 크기 360과 다릅니다. "
        f"현재={len(valid_df)}"
    )


# ============================================================
# 8. Tokenizer / Dataset / DataLoader
# ============================================================

print()
print("Tokenizer 로딩 중...")

tokenizer = AutoTokenizer.from_pretrained(
    MODEL_ID
)

train_dataset = AbuseDataset(
    train_df,
    tokenizer,
    MAX_LEN,
)

valid_dataset = AbuseDataset(
    valid_df,
    tokenizer,
    MAX_LEN,
)

train_loader = DataLoader(
    train_dataset,
    batch_size=BATCH_SIZE,
    shuffle=True,
    num_workers=2,
    pin_memory=torch.cuda.is_available(),
)

valid_loader = DataLoader(
    valid_dataset,
    batch_size=BATCH_SIZE,
    shuffle=False,
    num_workers=2,
    pin_memory=torch.cuda.is_available(),
)


# ============================================================
# 9. 모델 생성
# ============================================================

print("Model 로딩 중...")

model = AutoModelForSequenceClassification.from_pretrained(
    MODEL_ID,
    num_labels=NUM_LABELS,
    problem_type="multi_label_classification",
)

model.to(DEVICE)


# ============================================================
# 10. Loss / Optimizer
# ============================================================

# ============================================================
# 10. Loss / Optimizer
# ============================================================

def calculate_pos_weight(dataframe):
    """
    현재 Train 데이터에서 라벨별 PosWeight를 자동 계산한다.

    공식:
        pos_weight = negative_count / positive_count

    양성 사례가 적은 라벨일수록 양성 오분류에 더 큰 loss를 부여한다.
    Validation 정보는 계산에 사용하지 않는다.
    """

    labels = np.stack(
        dataframe["label"]
        .apply(parse_label)
        .to_numpy()
    )

    positive_counts = labels.sum(axis=0)
    negative_counts = len(labels) - positive_counts

    if np.any(positive_counts == 0):
        raise ValueError(
            "양성 샘플이 0개인 라벨이 있어 PosWeight를 계산할 수 없습니다."
        )

    pos_weight = (
        negative_counts
        / positive_counts
    ).astype(np.float32)

    print()
    print("[Train Label Distribution / PosWeight]")

    for index, label_name in enumerate(LABEL_NAMES):
        print(
            f"{label_name:<8} "
            f"Positive={int(positive_counts[index]):>4} | "
            f"Negative={int(negative_counts[index]):>4} | "
            f"PosWeight={pos_weight[index]:.4f}"
        )

    return torch.tensor(
        pos_weight,
        dtype=torch.float32,
        device=DEVICE,
    )


# ------------------------------------------------------------
# PosWeight는 Train 데이터만 사용해 계산한다.
# Validation label은 가중치 계산에 절대 사용하지 않는다.
# ------------------------------------------------------------

POS_WEIGHT = calculate_pos_weight(
    train_df
)

criterion = BCEWithLogitsLoss(
    pos_weight=POS_WEIGHT
)

optimizer = AdamW(
    model.parameters(),
    lr=LEARNING_RATE,
)

optimizer = AdamW(
    model.parameters(),
    lr=LEARNING_RATE,
)


# ============================================================
# 11. Training 함수
# ============================================================

def train_one_epoch(
    model,
    loader,
    optimizer,
    criterion,
    device,
    epoch,
):
    """
    한 epoch 학습을 수행한다.
    tqdm에서 실시간 평균 loss를 표시한다.
    """

    model.train()

    total_loss = 0.0

    progress_bar = tqdm(
        loader,
        desc=f"Epoch {epoch:02d} Train",
        leave=True,
    )

    for step, batch in enumerate(progress_bar, start=1):

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

        logits = outputs.logits

        loss = criterion(
            logits,
            labels,
        )

        loss.backward()

        optimizer.step()

        total_loss += loss.item()

        average_loss = total_loss / step

        progress_bar.set_postfix(
            loss=f"{average_loss:.4f}"
        )

    return total_loss / len(loader)


# ============================================================
# 12. Validation 함수
# ============================================================

def evaluate(
    model,
    loader,
    criterion,
    device,
    threshold=0.5,
):
    """
    Validation Loss와 Micro/Macro/라벨별 F1을 계산한다.
    """

    model.eval()

    total_loss = 0.0

    all_labels = []
    all_predictions = []
    all_probabilities = []

    progress_bar = tqdm(
        loader,
        desc="Validation",
        leave=False,
    )

    with torch.no_grad():

        for batch in progress_bar:

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

            logits = outputs.logits

            loss = criterion(
                logits,
                labels,
            )

            total_loss += loss.item()

            probabilities = torch.sigmoid(logits)

            predictions = (
                probabilities >= threshold
            ).int()

            all_labels.append(
                labels.cpu().numpy()
            )

            all_predictions.append(
                predictions.cpu().numpy()
            )

            all_probabilities.append(
                probabilities.cpu().numpy()
            )

    y_true = np.concatenate(
        all_labels,
        axis=0,
    )

    y_pred = np.concatenate(
        all_predictions,
        axis=0,
    )

    y_prob = np.concatenate(
        all_probabilities,
        axis=0,
    )

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

    average_loss = (
        total_loss / len(loader)
    )

    return {
        "loss": average_loss,
        "micro_f1": micro_f1,
        "macro_f1": macro_f1,
        "per_label_f1": per_label_f1,
        "y_true": y_true,
        "y_pred": y_pred,
        "y_prob": y_prob,
    }


# ============================================================
# 13. 학습 시작
# ============================================================

best_macro_f1 = -1.0
best_epoch = 0
early_stop_count = 0

training_start_time = time.time()

print()
print("=" * 70)
print("Training Start")
print("=" * 70)


for epoch in range(1, EPOCHS + 1):

    epoch_start_time = time.time()

    print()
    print(f"[Epoch {epoch}/{EPOCHS}]")

    train_loss = train_one_epoch(
        model=model,
        loader=train_loader,
        optimizer=optimizer,
        criterion=criterion,
        device=DEVICE,
        epoch=epoch,
    )

    result = evaluate(
        model=model,
        loader=valid_loader,
        criterion=criterion,
        device=DEVICE,
        threshold=THRESHOLD,
    )

    epoch_minutes = (
        time.time() - epoch_start_time
    ) / 60

    print(
        f"Train Loss : {train_loss:.4f}"
    )

    print(
        f"Valid Loss : {result['loss']:.4f}"
    )

    print(
        f"Micro F1   : {result['micro_f1']:.4f}"
    )

    print(
        f"Macro F1   : {result['macro_f1']:.4f}"
    )

    print("Per-label F1:")

    for label_name, score in zip(
        LABEL_NAMES,
        result["per_label_f1"],
    ):
        print(
            f"  {label_name:<6}: {score:.4f}"
        )

    print(
        f"Epoch Time : {epoch_minutes:.2f} min"
    )


    # ========================================================
    # Best Model 저장
    # ========================================================

    if result["macro_f1"] > best_macro_f1:

        best_macro_f1 = result["macro_f1"]
        best_epoch = epoch
        early_stop_count = 0

        checkpoint = {
            "model_state_dict": model.state_dict(),
            "model_id": MODEL_ID,
            "num_labels": NUM_LABELS,
            "label_names": LABEL_NAMES,
            "threshold": THRESHOLD,
            "epoch": epoch,
            "macro_f1": result["macro_f1"],
            "micro_f1": result["micro_f1"],
            "train_size": len(train_df),
            "valid_size": len(valid_df),
            "seed": SEED,
        }

        torch.save(
            checkpoint,
            BEST_MODEL_PATH,
        )

        print(
            f"★ Best Model 저장 "
            f"(Macro F1={best_macro_f1:.4f})"
        )

    else:

        early_stop_count += 1

        print(
            f"개선 없음 "
            f"({early_stop_count}/{EARLY_STOP_PATIENCE})"
        )


    # ========================================================
    # Early Stopping
    # ========================================================

    if early_stop_count >= EARLY_STOP_PATIENCE:

        print()
        print(
            f"Early Stopping: "
            f"{EARLY_STOP_PATIENCE} epoch 연속 "
            f"Macro F1 개선 없음"
        )

        break


# ============================================================
# 14. Best Model 다시 로드
# ============================================================

print()
print("=" * 70)
print("Best Model Evaluation")
print("=" * 70)

checkpoint = torch.load(
    BEST_MODEL_PATH,
    map_location=DEVICE,
)

model.load_state_dict(
    checkpoint["model_state_dict"]
)

best_result = evaluate(
    model=model,
    loader=valid_loader,
    criterion=criterion,
    device=DEVICE,
    threshold=THRESHOLD,
)


# ============================================================
# 15. 최종 평가 출력
# ============================================================

total_minutes = (
    time.time() - training_start_time
) / 60

print()
print("=" * 70)
print("A-only v2 Final Result")
print("=" * 70)

print(f"Best Epoch : {best_epoch}")
print(f"Threshold  : {THRESHOLD:.2f}")

print(
    f"Micro F1   : "
    f"{best_result['micro_f1']:.4f}"
)

print(
    f"Macro F1   : "
    f"{best_result['macro_f1']:.4f}"
)

print()
print("[Per-label F1]")

for label_name, score in zip(
    LABEL_NAMES,
    best_result["per_label_f1"],
):
    print(
        f"{label_name:<6}: {score:.4f}"
    )


# ============================================================
# 16. Classification Report
# ============================================================

print()
print("[Classification Report]")

print(
    classification_report(
        best_result["y_true"],
        best_result["y_pred"],
        target_names=LABEL_NAMES,
        zero_division=0,
        digits=4,
    )
)


# ============================================================
# 17. Baseline 비교용 출력
# ============================================================

BASELINE_MACRO_F1 = 0.8575
BASELINE_MICRO_F1 = 0.8540

macro_diff = (
    best_result["macro_f1"]
    - BASELINE_MACRO_F1
)

micro_diff = (
    best_result["micro_f1"]
    - BASELINE_MICRO_F1
)

print()
print("=" * 70)
print("Baseline vs A-only v2")
print("=" * 70)

print(
    f"Baseline Micro F1 : "
    f"{BASELINE_MICRO_F1:.4f}"
)

print(
    f"v2 Micro F1       : "
    f"{best_result['micro_f1']:.4f}"
)

print(
    f"Difference        : "
    f"{micro_diff:+.4f}"
)

print()

print(
    f"Baseline Macro F1 : "
    f"{BASELINE_MACRO_F1:.4f}"
)

print(
    f"v2 Macro F1       : "
    f"{best_result['macro_f1']:.4f}"
)

print(
    f"Difference        : "
    f"{macro_diff:+.4f}"
)

print()
print(f"Best Weight : {BEST_MODEL_PATH}")
print(f"Total Time  : {total_minutes:.2f} min")