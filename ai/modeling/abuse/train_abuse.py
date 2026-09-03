"""
I-SPOT 학대 유형 Multi-label 분류 모델 학습 코드

이 파일은 상담 텍스트를 입력받아 다음 4가지 학대 관련 신호를
동시에 예측할 수 있는 KLUE-RoBERTa 모델을 학습한다.

[예측 대상]
1. 신체학대
2. 정서학대
3. 성학대
4. 방임

[Multi-label 예시]
신체학대              -> [1, 0, 0, 0]
정서학대              -> [0, 1, 0, 0]
신체학대 + 정서학대    -> [1, 1, 0, 0]
해당 없음             -> [0, 0, 0, 0]

[학습 방식]
- Base Model: klue/roberta-base
- Output: 4개 독립 Logit
- Loss: BCEWithLogitsLoss
- Probability: Sigmoid
- 기본 Threshold: 0.5
- Evaluation: Micro F1 / Macro F1 / 유형별 F1

※ 이 모델의 출력은 학대 여부에 대한 최종 판정이 아니라
   상담 텍스트에서 학대 유형과 관련된 신호를 탐지하기 위한
   보조 결과이다.
"""

from pathlib import Path
import datetime
import random
import time

import numpy as np
import pandas as pd
import torch

from torch.utils.data import DataLoader
from transformers import AutoTokenizer, AutoModelForSequenceClassification
from torch.optim import AdamW

from sklearn.metrics import (
    f1_score,
    classification_report,
)

from tqdm.auto import tqdm

from ai.modeling.abuse.utils.Custom_utils import (
    KoreanTextDataset,
    LABEL_NAMES,
)


# ============================================================
# 기본 설정
# ============================================================

CFG = {
    "EPOCHS": 20,
    "LEARNING_RATE": 2e-5,
    "BATCH_SIZE": 16,   # 8 → 4
    "SEED": 69,
    "MAX_LEN": 512,
    "EARLY_STOP": 5,
    "MODEL_ID": "klue/roberta-base",
    "THRESHOLD": 0.5,
}


# ============================================================
# 현재 파일 기준 경로
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

TRAIN_DATA_PATH = BASE_DIR / "datasets" / "train_multilabel.csv"
VALID_DATA_PATH = BASE_DIR / "datasets" / "valid_multilabel.csv"
WEIGHT_DIR = BASE_DIR / "weight"
HISTORY_DIR = BASE_DIR / "history"

WEIGHT_DIR.mkdir(parents=True, exist_ok=True)
HISTORY_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================
# Device 설정
# ============================================================

device = torch.device(
    "cuda" if torch.cuda.is_available() else "cpu"
)

print("device:", device)

if torch.cuda.is_available():
    print("GPU:", torch.cuda.get_device_name(0))
else:
    print("CUDA device is not available. CPU를 사용합니다.")


# ============================================================
# Seed 고정
# ============================================================

def set_seed(seed):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)

    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


set_seed(CFG["SEED"])


# ============================================================
# 데이터 로드
# ============================================================

def load_data():
    """
    make_csv.py에서 생성한
    Training / Validation CSV를 각각 불러온다.

    Training:
        train_multilabel.csv

    Validation:
        valid_multilabel.csv

    AI-Hub에서 공식적으로 제공한
    Training / Validation 구분을 그대로 사용하므로
    추가적인 random split은 수행하지 않는다.
    """

    # ========================================================
    # 파일 존재 여부 확인
    # ========================================================

    if not TRAIN_DATA_PATH.exists():
        raise FileNotFoundError(
            "\nTraining CSV를 찾을 수 없습니다.\n"
            f"예상 경로: {TRAIN_DATA_PATH}\n"
            "먼저 make_csv.py를 실행해야 합니다."
        )

    if not VALID_DATA_PATH.exists():
        raise FileNotFoundError(
            "\nValidation CSV를 찾을 수 없습니다.\n"
            f"예상 경로: {VALID_DATA_PATH}\n"
            "먼저 make_csv.py를 실행해야 합니다."
        )


    # ========================================================
    # CSV 로드
    # ========================================================

    train_df = pd.read_csv(
        TRAIN_DATA_PATH
    )

    val_df = pd.read_csv(
        VALID_DATA_PATH
    )


    # ========================================================
    # 필수 컬럼 확인
    # ========================================================

    required_columns = {
        "audio_text",
        "label",
    }


    train_missing = (
        required_columns
        - set(train_df.columns)
    )

    val_missing = (
        required_columns
        - set(val_df.columns)
    )


    if train_missing:
        raise ValueError(
            "Training CSV에 필요한 컬럼이 없습니다: "
            f"{train_missing}"
        )

    if val_missing:
        raise ValueError(
            "Validation CSV에 필요한 컬럼이 없습니다: "
            f"{val_missing}"
        )


    # ========================================================
    # 빈 데이터 확인
    # ========================================================

    if len(train_df) == 0:
        raise ValueError(
            "Training 데이터가 없습니다."
        )

    if len(val_df) == 0:
        raise ValueError(
            "Validation 데이터가 없습니다."
        )


    # ========================================================
    # 데이터 정보 출력
    # ========================================================

    print(
        "\n===== Train Label 분포 ====="
    )

    print(
        train_df["label"].value_counts(
            dropna=False
        )
    )


    print(
        "\n===== Validation Label 분포 ====="
    )

    print(
        val_df["label"].value_counts(
            dropna=False
        )
    )


    print(
        "\nTrain:",
        train_df.shape,
    )

    print(
        "Validation:",
        val_df.shape,
    )


    return (
        train_df.reset_index(drop=True),
        val_df.reset_index(drop=True),
    )


# ============================================================
# 모델 평가
# ============================================================

def evaluate(
    model,
    dataloader,
    criterion,
    threshold,
):

    model.eval()

    total_loss = 0.0

    all_probs = []
    all_preds = []
    all_labels = []

    with torch.no_grad():

        for data in dataloader:

            ids = data["ids"].to(device)
            mask = data["mask"].to(device)
            labels = data["labels"].to(device)

            outputs = model(
                input_ids=ids,
                attention_mask=mask,
            )

            logits = outputs.logits

            loss = criterion(
                logits,
                labels.float(),
            )

            total_loss += loss.item()

            # --------------------------------------------
            # Multi-label 핵심
            #
            # Softmax / argmax 사용 X
            # 각각의 logit에 Sigmoid 적용
            # --------------------------------------------

            probs = torch.sigmoid(logits)

            preds = (
                probs >= threshold
            ).int()

            all_probs.extend(
                probs.cpu().numpy()
            )

            all_preds.extend(
                preds.cpu().numpy()
            )

            all_labels.extend(
                labels.cpu().numpy()
            )

    all_probs = np.array(all_probs)
    all_preds = np.array(all_preds)
    all_labels = np.array(all_labels).astype(int)

    avg_loss = total_loss / len(dataloader)

    micro_f1 = f1_score(
        all_labels,
        all_preds,
        average="micro",
        zero_division=0,
    )

    macro_f1 = f1_score(
        all_labels,
        all_preds,
        average="macro",
        zero_division=0,
    )

    report = classification_report(
        all_labels,
        all_preds,
        target_names=LABEL_NAMES,
        zero_division=0,
    )

    return {
        "loss": avg_loss,
        "micro_f1": micro_f1,
        "macro_f1": macro_f1,
        "report": report,
        "probabilities": all_probs,
        "predictions": all_preds,
        "labels": all_labels,
    }


# ============================================================
# 학습
# ============================================================

def train_model(
    model,
    tokenizer,
    train_df,
    val_df,
):

    train_dataset = KoreanTextDataset(
        train_df,
        tokenizer,
        CFG["MAX_LEN"],
    )

    val_dataset = KoreanTextDataset(
        val_df,
        tokenizer,
        CFG["MAX_LEN"],
    )

    train_loader = DataLoader(
        train_dataset,
        batch_size=CFG["BATCH_SIZE"],
        shuffle=True,
        num_workers=0,
    )

    val_loader = DataLoader(
        val_dataset,
        batch_size=CFG["BATCH_SIZE"],
        shuffle=False,
        num_workers=0,
    )

    optimizer = AdamW(
        model.parameters(),
        lr=CFG["LEARNING_RATE"],
    )

    # Multi-label classification loss
    criterion = torch.nn.BCEWithLogitsLoss()

    best_macro_f1 = -1.0
    no_improve = 0

    best_model_path = (
        WEIGHT_DIR
        / f"roberta_multilabel_{datetime.date.today()}.pth"
    )

    for epoch in range(CFG["EPOCHS"]):

        print(
            f"\n========== "
            f"EPOCH {epoch + 1}/{CFG['EPOCHS']} "
            f"=========="
        )

        model.train()

        running_loss = 0.0

        progress_bar = tqdm(
            train_loader,
            desc=f"Train {epoch + 1}",
        )

        for data in progress_bar:

            ids = data["ids"].to(device)
            mask = data["mask"].to(device)
            labels = data["labels"].to(device)

            optimizer.zero_grad()

            outputs = model(
                input_ids=ids,
                attention_mask=mask,
            )

            logits = outputs.logits

            loss = criterion(
                logits,
                labels.float(),
            )

            loss.backward()

            optimizer.step()

            running_loss += loss.item()

            progress_bar.set_postfix(
                loss=f"{loss.item():.4f}"
            )

        train_loss = (
            running_loss / len(train_loader)
        )

        # --------------------------------------------
        # Validation
        # --------------------------------------------

        result = evaluate(
            model=model,
            dataloader=val_loader,
            criterion=criterion,
            threshold=CFG["THRESHOLD"],
        )

        print(
            f"\nTrain Loss : {train_loss:.4f}"
        )

        print(
            f"Validation Loss : "
            f"{result['loss']:.4f}"
        )

        print(
            f"Validation Micro F1 : "
            f"{result['micro_f1']:.4f}"
        )

        print(
            f"Validation Macro F1 : "
            f"{result['macro_f1']:.4f}"
        )

        print("\n===== Classification Report =====")
        print(result["report"])

        # --------------------------------------------
        # 가장 좋은 모델 저장
        # --------------------------------------------

        if result["macro_f1"] > best_macro_f1:

            best_macro_f1 = result["macro_f1"]

            torch.save(
                model.state_dict(),
                best_model_path,
            )

            no_improve = 0

            print(
                "\nBest Model 저장:"
                f"\n{best_model_path}"
            )

        else:
            no_improve += 1

            print(
                f"\n성능 개선 없음: "
                f"{no_improve}/{CFG['EARLY_STOP']}"
            )

        # --------------------------------------------
        # Early Stopping
        # --------------------------------------------

        if no_improve >= CFG["EARLY_STOP"]:

            print("\nEarly Stopping")
            break

    print(
        f"\nBest Validation Macro F1: "
        f"{best_macro_f1:.4f}"
    )

    return best_model_path


# ============================================================
# Main
# ============================================================

def main():

    print("\n========================================")
    print("I-SPOT Abuse Multi-label Training")
    print("========================================")

    print(
        "\nTrain Start:",
        datetime.datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        ),
    )

    start_time = time.time()

    # 데이터
    train_df, val_df = load_data()

    # Tokenizer
    tokenizer = AutoTokenizer.from_pretrained(
        CFG["MODEL_ID"]
    )

    # --------------------------------------------------------
    # 중요
    # 기존 num_labels=5가 아니라 4
    # --------------------------------------------------------

    model = AutoModelForSequenceClassification.from_pretrained(
        CFG["MODEL_ID"],
        num_labels=4,
        problem_type="multi_label_classification",
    )

    model.to(device)

    best_model_path = train_model(
        model=model,
        tokenizer=tokenizer,
        train_df=train_df,
        val_df=val_df,
    )

    end_time = time.time()

    print(
        "\nTrain End:",
        datetime.datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        ),
    )

    print(
        f"Total Training Time: "
        f"{(end_time - start_time) / 60:.2f} min"
    )

    print(
        f"Best Model Path: {best_model_path}"
    )


if __name__ == "__main__":
    main()