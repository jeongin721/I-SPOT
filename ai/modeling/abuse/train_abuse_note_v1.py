"""
상담일지(note) 문체 텍스트로 4대 학대유형 멀티라벨 모델을 학습한다.

기존 roberta_abuse_qa_child_v3는 [COUNSELOR]/[CHILD] 태깅된 Q+A 텍스트로만
학습되어 있어, 태깅 없는 3인칭 서술형 상담일지 문체에는 일반화가 안 됐다.
이 스크립트는 별도 모델로 note 문체 전용 데이터만 학습한다
(기존 qa/child_only 모델은 건드리지 않는다).
"""

# ============================================================
# 1. Import
# ============================================================

import ast
import json
import random
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import torch.nn as nn

from sklearn.metrics import f1_score, precision_score, recall_score
from torch.utils.data import Dataset, DataLoader
from tqdm import tqdm
from transformers import (
    AutoModelForSequenceClassification,
    AutoTokenizer,
    get_linear_schedule_with_warmup,
)


# ============================================================
# 2. 기본 설정
# ============================================================

SEED = 42

MODEL_NAME = "klue/roberta-base"

BASE_DIR = Path("/data/I-SPOT/ai/modeling/abuse")

TRAIN_PATH = (
    BASE_DIR
    / "datasets/train_note_v1.csv"
)

VALID_PATH = (
    BASE_DIR
    / "datasets/valid_note_v1.csv"
)

WEIGHT_DIR = BASE_DIR / "weight"
RESULT_DIR = BASE_DIR / "results"

BEST_MODEL_PATH = (
    WEIGHT_DIR
    / "roberta_abuse_note_v1_best.pth"
)

RESULT_PATH = (
    RESULT_DIR
    / "abuse_note_v1_result.json"
)

MAX_LENGTH = 512
BATCH_SIZE = 8

EPOCHS = 15

LEARNING_RATE = 2e-5
WEIGHT_DECAY = 0.01
WARMUP_RATIO = 0.1

PATIENCE = 3

THRESHOLD = 0.5

NUM_LABELS = 4

LABEL_NAMES = [
    "신체학대",
    "정서학대",
    "성학대",
    "방임",
]


# ============================================================
# 3. Seed
# ============================================================

def set_seed(seed):
    random.seed(seed)
    np.random.seed(seed)

    torch.manual_seed(seed)

    if torch.cuda.is_available():
        torch.cuda.manual_seed(seed)
        torch.cuda.manual_seed_all(seed)


set_seed(SEED)


# ============================================================
# 4. Device
# ============================================================

DEVICE = torch.device(
    "cuda" if torch.cuda.is_available() else "cpu"
)

print("=" * 70)
print("DEVICE")
print("=" * 70)

print(f"Device : {DEVICE}")

if torch.cuda.is_available():
    print(
        f"GPU    : "
        f"{torch.cuda.get_device_name(0)}"
    )

print()


# ============================================================
# 5. 데이터 로드
# ============================================================

print("=" * 70)
print("DATA LOAD")
print("=" * 70)

train_df = pd.read_csv(TRAIN_PATH)
valid_df = pd.read_csv(VALID_PATH)

print(f"TRAIN : {len(train_df):,}")
print(f"VALID : {len(valid_df):,}")
print()


# ============================================================
# 6. Label 파싱
# ============================================================

def parse_label(value):
    """
    CSV에 문자열로 저장된 멀티라벨을
    [0, 1, 0, 0] 형태의 float list로 변환한다.
    """

    if isinstance(value, str):
        value = ast.literal_eval(value)

    label = np.asarray(
        value,
        dtype=np.float32,
    )

    if label.shape != (NUM_LABELS,):
        raise ValueError(
            f"잘못된 label 형태: {value}"
        )

    return label


train_df["parsed_label"] = (
    train_df["label"].apply(parse_label)
)

valid_df["parsed_label"] = (
    valid_df["label"].apply(parse_label)
)


# ============================================================
# 7. 데이터 기본 검증
# ============================================================

required_columns = [
    "audio_text",
    "label",
]

for column in required_columns:

    if column not in train_df.columns:
        raise ValueError(
            f"TRAIN에 {column} 컬럼이 없습니다."
        )

    if column not in valid_df.columns:
        raise ValueError(
            f"VALID에 {column} 컬럼이 없습니다."
        )


print("=" * 70)
print("LABEL DISTRIBUTION")
print("=" * 70)

train_labels = np.stack(
    train_df["parsed_label"].values
)

valid_labels = np.stack(
    valid_df["parsed_label"].values
)

for i, label_name in enumerate(LABEL_NAMES):

    train_positive = int(
        train_labels[:, i].sum()
    )

    valid_positive = int(
        valid_labels[:, i].sum()
    )

    print(
        f"{label_name:<6} | "
        f"TRAIN + {train_positive:>5,} | "
        f"VALID + {valid_positive:>4,}"
    )

print()


# ============================================================
# 8. Tokenizer
# ============================================================

print("=" * 70)
print("TOKENIZER LOAD")
print("=" * 70)

tokenizer = AutoTokenizer.from_pretrained(
    MODEL_NAME
)

print(f"Tokenizer: {MODEL_NAME}")
print()


# ============================================================
# 9. Dataset
# ============================================================

class AbuseDataset(Dataset):

    def __init__(
        self,
        dataframe,
        tokenizer,
        max_length,
    ):
        self.df = dataframe.reset_index(
            drop=True
        )

        self.tokenizer = tokenizer
        self.max_length = max_length

    def __len__(self):
        return len(self.df)

    def __getitem__(self, index):

        row = self.df.iloc[index]

        text = str(
            row["audio_text"]
        )

        encoded = self.tokenizer(
            text,
            truncation=True,
            padding="max_length",
            max_length=self.max_length,
            return_tensors="pt",
        )

        labels = torch.tensor(
            row["parsed_label"],
            dtype=torch.float,
        )

        return {
            "input_ids":
                encoded["input_ids"].squeeze(0),

            "attention_mask":
                encoded["attention_mask"].squeeze(0),

            "labels":
                labels,
        }


train_dataset = AbuseDataset(
    train_df,
    tokenizer,
    MAX_LENGTH,
)

valid_dataset = AbuseDataset(
    valid_df,
    tokenizer,
    MAX_LENGTH,
)


# ============================================================
# 10. DataLoader
# ============================================================

train_loader = DataLoader(
    train_dataset,
    batch_size=BATCH_SIZE,
    shuffle=True,
    num_workers=2,
    pin_memory=True,
)

valid_loader = DataLoader(
    valid_dataset,
    batch_size=BATCH_SIZE,
    shuffle=False,
    num_workers=2,
    pin_memory=True,
)


# ============================================================
# 11. Pos Weight
# ============================================================

positive_counts = train_labels.sum(
    axis=0
)

negative_counts = (
    len(train_labels)
    - positive_counts
)

pos_weight = (
    negative_counts
    / np.maximum(
        positive_counts,
        1,
    )
)

pos_weight_tensor = torch.tensor(
    pos_weight,
    dtype=torch.float,
).to(DEVICE)


print("=" * 70)
print("POS WEIGHT")
print("=" * 70)

for label_name, weight in zip(
    LABEL_NAMES,
    pos_weight,
):
    print(
        f"{label_name:<6}: "
        f"{weight:.4f}"
    )

print()


# ============================================================
# 12. Model
# ============================================================

print("=" * 70)
print("MODEL LOAD")
print("=" * 70)

model = (
    AutoModelForSequenceClassification
    .from_pretrained(
        MODEL_NAME,
        num_labels=NUM_LABELS,
        problem_type="multi_label_classification",
    )
)

model.to(DEVICE)

print(f"Model: {MODEL_NAME}")
print()


# ============================================================
# 13. Loss / Optimizer / Scheduler
# ============================================================

criterion = nn.BCEWithLogitsLoss(
    pos_weight=pos_weight_tensor
)

optimizer = torch.optim.AdamW(
    model.parameters(),
    lr=LEARNING_RATE,
    weight_decay=WEIGHT_DECAY,
)

total_steps = (
    len(train_loader)
    * EPOCHS
)

warmup_steps = int(
    total_steps
    * WARMUP_RATIO
)

scheduler = get_linear_schedule_with_warmup(
    optimizer,
    num_warmup_steps=warmup_steps,
    num_training_steps=total_steps,
)


# ============================================================
# 14. Train
# ============================================================

def train_one_epoch(
    model,
    loader,
    optimizer,
    scheduler,
    criterion,
):

    model.train()

    total_loss = 0.0

    progress = tqdm(
        loader,
        desc="TRAIN",
        leave=False,
    )

    for batch in progress:

        optimizer.zero_grad()

        input_ids = (
            batch["input_ids"]
            .to(DEVICE)
        )

        attention_mask = (
            batch["attention_mask"]
            .to(DEVICE)
        )

        labels = (
            batch["labels"]
            .to(DEVICE)
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
        scheduler.step()

        total_loss += loss.item()

        progress.set_postfix(
            loss=f"{loss.item():.4f}"
        )

    return total_loss / len(loader)


# ============================================================
# 15. Validation
# ============================================================

def validate(
    model,
    loader,
    criterion,
):

    model.eval()

    total_loss = 0.0

    all_probs = []
    all_labels = []

    with torch.no_grad():

        progress = tqdm(
            loader,
            desc="VALID",
            leave=False,
        )

        for batch in progress:

            input_ids = (
                batch["input_ids"]
                .to(DEVICE)
            )

            attention_mask = (
                batch["attention_mask"]
                .to(DEVICE)
            )

            labels = (
                batch["labels"]
                .to(DEVICE)
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

            probs = torch.sigmoid(
                outputs.logits
            )

            all_probs.append(
                probs.cpu().numpy()
            )

            all_labels.append(
                labels.cpu().numpy()
            )

    probs = np.concatenate(
        all_probs,
        axis=0,
    )

    labels = np.concatenate(
        all_labels,
        axis=0,
    )

    preds = (
        probs >= THRESHOLD
    ).astype(int)

    labels = labels.astype(int)

    micro_f1 = f1_score(
        labels,
        preds,
        average="micro",
        zero_division=0,
    )

    macro_f1 = f1_score(
        labels,
        preds,
        average="macro",
        zero_division=0,
    )

    per_label_f1 = f1_score(
        labels,
        preds,
        average=None,
        zero_division=0,
    )

    macro_precision = precision_score(
        labels,
        preds,
        average="macro",
        zero_division=0,
    )

    macro_recall = recall_score(
        labels,
        preds,
        average="macro",
        zero_division=0,
    )

    per_label_precision = precision_score(
        labels,
        preds,
        average=None,
        zero_division=0,
    )

    per_label_recall = recall_score(
        labels,
        preds,
        average=None,
        zero_division=0,
    )

    exact_match = (
        preds == labels
    ).all(axis=1).mean()

    return {
        "loss":
            total_loss / len(loader),

        "micro_f1":
            float(micro_f1),

        "macro_f1":
            float(macro_f1),

        "macro_precision":
            float(macro_precision),

        "macro_recall":
            float(macro_recall),

        "exact_match":
            float(exact_match),

        "per_label_f1": {
            LABEL_NAMES[i]:
                float(per_label_f1[i])

            for i in range(
                NUM_LABELS
            )
        },

        "per_label_precision": {
            LABEL_NAMES[i]:
                float(per_label_precision[i])

            for i in range(
                NUM_LABELS
            )
        },

        "per_label_recall": {
            LABEL_NAMES[i]:
                float(per_label_recall[i])

            for i in range(
                NUM_LABELS
            )
        },

        # 유형별 threshold 튜닝에 쓰는 원본 확률/정답값 (0.5 고정
        # threshold로 계산한 위 지표들과는 별개로, best epoch에서만
        # 유형별 최적 threshold를 다시 찾을 때 사용한다).
        "probs": probs,
        "labels": labels,
    }


def find_best_thresholds(
    probs,
    labels,
    candidates=None,
) -> dict:
    """
    유형별로 F1이 가장 높은 threshold를 validation set에서 찾는다.

    Deepgram/Whisper confidence처럼 전 유형에 0.5를 일괄 적용하면,
    유형마다 확률 분포가 달라서(특히 정서학대처럼 애매한 유형) 최적점이
    아닐 수 있다 — 유형별로 독립적으로 가장 좋은 threshold를 고른다.
    """

    if candidates is None:
        candidates = [
            round(0.05 * i, 2)
            for i in range(3, 19)
        ]  # 0.15 ~ 0.90

    best_thresholds = {}

    for i, label_name in enumerate(LABEL_NAMES):
        label_probs = probs[:, i]
        label_true = labels[:, i]

        best_f1 = -1.0
        best_threshold = THRESHOLD

        for candidate in candidates:
            pred = (label_probs >= candidate).astype(int)

            f1 = f1_score(
                label_true,
                pred,
                zero_division=0,
            )

            if f1 > best_f1:
                best_f1 = f1
                best_threshold = candidate

        best_thresholds[label_name] = best_threshold

    return best_thresholds


# ============================================================
# 16. Training Loop + Early Stopping
# ============================================================

WEIGHT_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

RESULT_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

best_macro_f1 = -1.0
best_epoch = 0

patience_counter = 0

history = []


print("=" * 70)
print("TRAINING START")
print("=" * 70)


for epoch in range(
    1,
    EPOCHS + 1,
):

    print()
    print(
        f"[Epoch {epoch}/{EPOCHS}]"
    )

    train_loss = train_one_epoch(
        model,
        train_loader,
        optimizer,
        scheduler,
        criterion,
    )

    metrics = validate(
        model,
        valid_loader,
        criterion,
    )

    epoch_result = {
        "epoch": epoch,
        "train_loss":
            float(train_loss),

        "valid_loss":
            metrics["loss"],

        "micro_f1":
            metrics["micro_f1"],

        "macro_f1":
            metrics["macro_f1"],

        "macro_precision":
            metrics["macro_precision"],

        "macro_recall":
            metrics["macro_recall"],

        "exact_match":
            metrics["exact_match"],

        "per_label_f1":
            metrics["per_label_f1"],

        "per_label_precision":
            metrics["per_label_precision"],

        "per_label_recall":
            metrics["per_label_recall"],
    }

    history.append(
        epoch_result
    )


    print(
        f"Train Loss : "
        f"{train_loss:.4f}"
    )

    print(
        f"Valid Loss : "
        f"{metrics['loss']:.4f}"
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
        f"Macro Precision: "
        f"{metrics['macro_precision']:.4f}"
    )

    print(
        f"Macro Recall   : "
        f"{metrics['macro_recall']:.4f}"
    )

    print(
        f"Exact Match: "
        f"{metrics['exact_match']:.4f}"
    )

    print("Per-label F1 / Precision / Recall:")

    for label_name in LABEL_NAMES:

        print(
            f"  {label_name:<6}: "
            f"F1={metrics['per_label_f1'][label_name]:.4f}  "
            f"P={metrics['per_label_precision'][label_name]:.4f}  "
            f"R={metrics['per_label_recall'][label_name]:.4f}"
        )


    # ========================================================
    # Best model 저장
    # ========================================================

    if (
        metrics["macro_f1"]
        > best_macro_f1
    ):

        best_macro_f1 = (
            metrics["macro_f1"]
        )

        best_epoch = epoch

        patience_counter = 0

        best_thresholds = find_best_thresholds(
            metrics["probs"],
            metrics["labels"],
        )

        torch.save(
            {
                "model_state_dict":
                    model.state_dict(),

                "model_name":
                    MODEL_NAME,

                "epoch":
                    epoch,

                "macro_f1":
                    best_macro_f1,

                # 유형별로 F1이 가장 높은 threshold를 따로 저장한다
                # (전 유형 0.5 고정 대신) — find_best_thresholds 참고.
                "threshold":
                    best_thresholds,

                "label_names":
                    LABEL_NAMES,
            },
            BEST_MODEL_PATH,
        )

        print()
        print(
            "★ BEST MODEL SAVED"
        )

        print(
            f"  Epoch    : {epoch}"
        )

        print(
            f"  Macro F1 : "
            f"{best_macro_f1:.4f}"
        )

        print(
            "  유형별 threshold: "
            + ", ".join(
                f"{name}={value}"
                for name, value in best_thresholds.items()
            )
        )

        print(
            f"  Path     : "
            f"{BEST_MODEL_PATH}"
        )

    else:

        patience_counter += 1

        print(
            f"Early stopping: "
            f"{patience_counter}/{PATIENCE}"
        )


    # ========================================================
    # Early stopping
    # ========================================================

    if (
        patience_counter
        >= PATIENCE
    ):

        print()
        print(
            "Early stopping 실행"
        )

        break


# ============================================================
# 17. 결과 저장
# ============================================================

result = {
    "model_name":
        MODEL_NAME,

    "train_path":
        str(TRAIN_PATH),

    "valid_path":
        str(VALID_PATH),

    "train_size":
        len(train_df),

    "valid_size":
        len(valid_df),

    "best_epoch":
        best_epoch,

    "best_macro_f1":
        best_macro_f1,

    "threshold":
        THRESHOLD,

    "history":
        history,
}


with open(
    RESULT_PATH,
    "w",
    encoding="utf-8",
) as f:

    json.dump(
        result,
        f,
        ensure_ascii=False,
        indent=2,
    )


# ============================================================
# 18. 최종 출력
# ============================================================

print()
print("=" * 70)
print("TRAINING COMPLETE")
print("=" * 70)

print(
    f"Best Epoch    : "
    f"{best_epoch}"
)

print(
    f"Best Macro F1 : "
    f"{best_macro_f1:.4f}"
)

print()
print(
    f"Best Weight:"
    f"\n{BEST_MODEL_PATH}"
)

print()
print(
    f"Result:"
    f"\n{RESULT_PATH}"
)
