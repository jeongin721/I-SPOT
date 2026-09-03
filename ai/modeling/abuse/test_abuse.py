from pathlib import Path
import ast
import random
import warnings

import numpy as np
import pandas as pd
import torch
from torch.utils.data import DataLoader
from transformers import AutoTokenizer, AutoModelForSequenceClassification
from sklearn.metrics import f1_score, classification_report

from ai.modeling.abuse.utils.Custom_utils import (
    KoreanTextDataset,
    LABEL_NAMES,
)

warnings.filterwarnings("ignore")

# ============================================================
# 설정
# ============================================================

SEED = 69
BATCH_SIZE = 32
MAX_LEN = 512
THRESHOLD = 0.5
MODEL_ID = "klue/roberta-base"

BASE_DIR = Path(__file__).resolve().parent

VALID_DATA_PATH = BASE_DIR / "datasets" / "valid_multilabel.csv"
MODEL_PATH = BASE_DIR / "weight" / "roberta_multilabel_2026-09-03.pth"
RESULT_PATH = BASE_DIR / "results" / "validation_predictions.csv"

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

print("Device :", device)

if torch.cuda.is_available():
    print("GPU :", torch.cuda.get_device_name(0))


# ============================================================
# Seed
# ============================================================

def set_seed(seed=69):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)

    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


set_seed(SEED)


# ============================================================
# 데이터 로드
# ============================================================

print("\n===== Load Validation Dataset =====")

df = pd.read_csv(VALID_DATA_PATH)

print("Validation shape :", df.shape)


# label 컬럼이 문자열 형태의 리스트라면 실제 리스트로 변환
def parse_label(value):
    if isinstance(value, str):
        return ast.literal_eval(value)

    return value


df["label"] = df["label"].apply(parse_label)


print("\n===== Label Distribution =====")

for idx, label_name in enumerate(LABEL_NAMES):

    count = df["label"].apply(
        lambda x: int(x[idx])
    ).sum()

    print(f"{label_name}: {count}")


# ============================================================
# Tokenizer / Dataset
# ============================================================

tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)

test_dataset = KoreanTextDataset(
    df,
    tokenizer,
    MAX_LEN,
)

test_dataloader = DataLoader(
    test_dataset,
    batch_size=BATCH_SIZE,
    shuffle=False,
    num_workers=4,
)


# ============================================================
# Model
# ============================================================

print("\n===== Load Best Model =====")

model = AutoModelForSequenceClassification.from_pretrained(
    MODEL_ID,
    num_labels=4,
    problem_type="multi_label_classification",
)

state_dict = torch.load(
    MODEL_PATH,
    map_location=device,
)

model.load_state_dict(state_dict)

model.to(device)
model.eval()

print("Model :", MODEL_PATH)


# ============================================================
# Evaluation
# ============================================================

all_probs = []
all_preds = []
all_labels = []

with torch.no_grad():

    for data in test_dataloader:

        ids = data["ids"].to(device)
        mask = data["mask"].to(device)
        token_type_ids = data["token_type_ids"].to(device)

        labels = data["labels"].to(device)

        outputs = model(
            input_ids=ids,
            attention_mask=mask,
            token_type_ids=token_type_ids,
        )

        # Multi-label → sigmoid
        probs = torch.sigmoid(outputs.logits)

        # 현재 baseline threshold = 0.5
        preds = (probs >= THRESHOLD).int()

        all_probs.append(probs.cpu().numpy())
        all_preds.append(preds.cpu().numpy())
        all_labels.append(labels.cpu().numpy())


y_prob = np.concatenate(all_probs, axis=0)
y_pred = np.concatenate(all_preds, axis=0)
y_true = np.concatenate(all_labels, axis=0).astype(int)


# ============================================================
# Metrics
# ============================================================

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


print("\n======================================")
print("       BEST MODEL EVALUATION")
print("======================================")

print(f"Threshold : {THRESHOLD}")
print(f"Micro F1  : {micro_f1:.4f}")
print(f"Macro F1  : {macro_f1:.4f}")


print("\n===== Per-label F1 =====")

for idx, label_name in enumerate(LABEL_NAMES):

    score = f1_score(
        y_true[:, idx],
        y_pred[:, idx],
        zero_division=0,
    )

    print(f"{label_name}: {score:.4f}")


print("\n===== Classification Report =====")

print(
    classification_report(
        y_true,
        y_pred,
        target_names=LABEL_NAMES,
        zero_division=0,
    )
)


# ============================================================
# 개별 예측 결과 저장
# ============================================================

RESULT_PATH.parent.mkdir(
    parents=True,
    exist_ok=True,
)

result_df = df.copy()


for idx, label_name in enumerate(LABEL_NAMES):

    # 실제 라벨
    result_df[f"{label_name}_true"] = y_true[:, idx]

    # 예측 라벨
    result_df[f"{label_name}_pred"] = y_pred[:, idx]

    # 확률
    result_df[f"{label_name}_prob"] = y_prob[:, idx]


result_df.to_csv(
    RESULT_PATH,
    index=False,
    encoding="utf-8-sig",
)


print("\nResults saved:")
print(RESULT_PATH)