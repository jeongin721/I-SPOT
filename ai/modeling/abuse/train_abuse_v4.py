"""
A-only v4 멀티라벨 학대 관련 신호 분류 모델을 학습한다.

train_multilabel_v4.csv를 학습하고 기존 official Validation을 그대로 사용해
Micro/Macro/라벨별 F1을 평가하며 가장 좋은 모델 가중치를 저장한다.
"""

# ============================================================
# 1. Import
# ============================================================

import ast
import random
import time
from pathlib import Path

import numpy as np
import pandas as pd
import torch

from sklearn.metrics import (
    f1_score,
    precision_recall_fscore_support,
)

from torch.optim import AdamW
from torch.utils.data import (
    DataLoader,
    Dataset,
)

from tqdm import tqdm

from transformers import (
    AutoModelForSequenceClassification,
    AutoTokenizer,
    get_linear_schedule_with_warmup,
)


# ============================================================
# 2. 기본 설정
# ============================================================

MODEL_ID = "klue/roberta-base"

MAX_LEN = 512

BATCH_SIZE = 16

EPOCHS = 15

LEARNING_RATE = 2e-5

WEIGHT_DECAY = 0.01

WARMUP_RATIO = 0.1

THRESHOLD = 0.50

PATIENCE = 3

SEED = 69


LABEL_NAMES = [
    "신체학대",
    "정서학대",
    "성학대",
    "방임",
]


# ============================================================
# 3. 경로 설정
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

DATASET_DIR = BASE_DIR / "datasets"

WEIGHT_DIR = BASE_DIR / "weight"

TRAIN_PATH = (
    DATASET_DIR
    / "train_multilabel_v4.csv"
)

VALID_PATH = (
    DATASET_DIR
    / "valid_multilabel.csv"
)

MODEL_SAVE_PATH = (
    WEIGHT_DIR
    / "roberta_multilabel_v4_2026-09-07.pth"
)


# ============================================================
# 4. Seed 고정
# ============================================================

def set_seed(seed: int):
    """
    재현 가능한 학습을 위해 random seed를 고정한다.
    """

    random.seed(seed)

    np.random.seed(seed)

    torch.manual_seed(seed)

    torch.cuda.manual_seed_all(seed)


set_seed(SEED)


# ============================================================
# 5. Device 설정
# ============================================================

device = torch.device(
    "cuda"
    if torch.cuda.is_available()
    else "cpu"
)

print()
print("=" * 70)
print("A-only v4 Multi-label Training")
print("=" * 70)

print(
    f"\nDevice : {device}"
)

if torch.cuda.is_available():

    print(
        "GPU    :",
        torch.cuda.get_device_name(0),
    )


# ============================================================
# 6. 입력 파일 확인
# ============================================================

for path in [
    TRAIN_PATH,
    VALID_PATH,
]:

    if not path.exists():

        raise FileNotFoundError(
            f"필요한 데이터가 없습니다: {path}"
        )


# ============================================================
# 7. 데이터 로드
# ============================================================

train_df = pd.read_csv(
    TRAIN_PATH
)

valid_df = pd.read_csv(
    VALID_PATH
)


print()
print("[Dataset]")

print(
    f"Train : {len(train_df)}"
)

print(
    f"Valid : {len(valid_df)}"
)


# ============================================================
# 8. 필수 컬럼 확인
# ============================================================

required_columns = {
    "audio_text",
    "label",
}

for name, df in [
    ("Train", train_df),
    ("Valid", valid_df),
]:

    missing_columns = (
        required_columns
        - set(df.columns)
    )

    if missing_columns:

        raise ValueError(
            f"{name} 데이터에 필요한 컬럼이 없습니다: "
            f"{missing_columns}"
        )


# ============================================================
# 9. Label 문자열 → List 변환
# ============================================================

def parse_label(
    value,
):
    """
    CSV에 문자열로 저장된 [0, 1, 0, 0] 형태의 라벨을
    float list로 변환한다.
    """

    if isinstance(
        value,
        list,
    ):
        label = value

    else:
        label = ast.literal_eval(
            str(value)
        )

    if len(label) != 4:

        raise ValueError(
            f"라벨 길이가 4가 아닙니다: {label}"
        )

    return [
        float(x)
        for x in label
    ]


train_df["parsed_label"] = (
    train_df["label"].apply(
        parse_label
    )
)

valid_df["parsed_label"] = (
    valid_df["label"].apply(
        parse_label
    )
)


# ============================================================
# 10. Tokenizer 로드
# ============================================================

tokenizer = (
    AutoTokenizer.from_pretrained(
        MODEL_ID
    )
)


# ============================================================
# 11. Dataset 클래스
# ============================================================

class AbuseDataset(
    Dataset
):
    """
    상담 텍스트와 4-label multi-hot vector를 반환한다.
    """

    def __init__(
        self,
        dataframe,
        tokenizer,
        max_len,
    ):

        self.dataframe = (
            dataframe.reset_index(
                drop=True
            )
        )

        self.tokenizer = tokenizer

        self.max_len = max_len


    def __len__(
        self,
    ):

        return len(
            self.dataframe
        )


    def __getitem__(
        self,
        index,
    ):

        row = self.dataframe.iloc[
            index
        ]

        text = str(
            row["audio_text"]
        ).strip()

        label = torch.tensor(
            row["parsed_label"],
            dtype=torch.float,
        )

        encoded = self.tokenizer(
            text,
            max_length=self.max_len,
            padding="max_length",
            truncation=True,
            return_tensors="pt",
        )

        item = {
            "input_ids": encoded[
                "input_ids"
            ].squeeze(0),

            "attention_mask": encoded[
                "attention_mask"
            ].squeeze(0),

            "labels": label,
        }

        if "token_type_ids" in encoded:

            item[
                "token_type_ids"
            ] = encoded[
                "token_type_ids"
            ].squeeze(0)

        return item


# ============================================================
# 12. Dataset / DataLoader 생성
# ============================================================

train_dataset = AbuseDataset(
    dataframe=train_df,
    tokenizer=tokenizer,
    max_len=MAX_LEN,
)

valid_dataset = AbuseDataset(
    dataframe=valid_df,
    tokenizer=tokenizer,
    max_len=MAX_LEN,
)


train_loader = DataLoader(
    train_dataset,
    batch_size=BATCH_SIZE,
    shuffle=True,
)

valid_loader = DataLoader(
    valid_dataset,
    batch_size=BATCH_SIZE,
    shuffle=False,
)


# ============================================================
# 13. 모델 생성
# ============================================================

model = (
    AutoModelForSequenceClassification
    .from_pretrained(
        MODEL_ID,
        num_labels=4,
        problem_type=(
            "multi_label_classification"
        ),
    )
)

model.to(
    device
)


# ============================================================
# 14. Loss / Optimizer
# ============================================================

criterion = (
    torch.nn.BCEWithLogitsLoss()
)

optimizer = AdamW(
    model.parameters(),
    lr=LEARNING_RATE,
    weight_decay=WEIGHT_DECAY,
)


# ============================================================
# 15. Scheduler
# ============================================================

total_training_steps = (
    len(train_loader)
    * EPOCHS
)

warmup_steps = int(
    total_training_steps
    * WARMUP_RATIO
)

scheduler = (
    get_linear_schedule_with_warmup(
        optimizer,
        num_warmup_steps=warmup_steps,
        num_training_steps=(
            total_training_steps
        ),
    )
)


# ============================================================
# 16. Training 함수
# ============================================================

def train_one_epoch(
    model,
    loader,
    optimizer,
    scheduler,
    criterion,
):
    """
    1 epoch 학습을 수행하고 평균 loss를 반환한다.
    """

    model.train()

    total_loss = 0.0

    progress_bar = tqdm(
        loader,
        desc="Train",
        leave=False,
    )

    for batch in progress_bar:

        optimizer.zero_grad()

        input_ids = batch[
            "input_ids"
        ].to(device)

        attention_mask = batch[
            "attention_mask"
        ].to(device)

        labels = batch[
            "labels"
        ].to(device)

        model_inputs = {
            "input_ids": input_ids,
            "attention_mask": (
                attention_mask
            ),
        }

        if (
            "token_type_ids"
            in batch
        ):

            model_inputs[
                "token_type_ids"
            ] = batch[
                "token_type_ids"
            ].to(device)

        outputs = model(
            **model_inputs
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

        total_loss += (
            loss.item()
        )

        progress_bar.set_postfix(
            loss=f"{loss.item():.4f}"
        )

    average_loss = (
        total_loss
        / len(loader)
    )

    return average_loss


# ============================================================
# 17. Validation 함수
# ============================================================

def evaluate(
    model,
    loader,
    threshold=THRESHOLD,
):
    """
    Validation 데이터에서 확률을 계산하고
    Micro/Macro/라벨별 F1을 반환한다.
    """

    model.eval()

    all_labels = []
    all_probabilities = []

    progress_bar = tqdm(
        loader,
        desc="Valid",
        leave=False,
    )

    with torch.no_grad():

        for batch in progress_bar:

            input_ids = batch[
                "input_ids"
            ].to(device)

            attention_mask = batch[
                "attention_mask"
            ].to(device)

            labels = batch[
                "labels"
            ].to(device)

            model_inputs = {
                "input_ids": input_ids,
                "attention_mask": (
                    attention_mask
                ),
            }

            if (
                "token_type_ids"
                in batch
            ):

                model_inputs[
                    "token_type_ids"
                ] = batch[
                    "token_type_ids"
                ].to(device)

            outputs = model(
                **model_inputs
            )

            probabilities = (
                torch.sigmoid(
                    outputs.logits
                )
            )

            all_labels.append(
                labels.cpu()
            )

            all_probabilities.append(
                probabilities.cpu()
            )

    y_true = torch.cat(
        all_labels,
        dim=0,
    ).numpy()

    y_prob = torch.cat(
        all_probabilities,
        dim=0,
    ).numpy()

    y_pred = (
        y_prob
        >= threshold
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
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "support": support,
    }


# ============================================================
# 18. Weight 저장 함수
# ============================================================

def save_checkpoint(
    model,
    epoch,
    metrics,
):
    """
    가장 좋은 모델의 checkpoint를 저장한다.

    infer_abuse.py에서 model_state_dict를 읽어 사용할 수 있는
    동일한 checkpoint 형식을 사용한다.
    """

    WEIGHT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    checkpoint = {
        "model_state_dict": (
            model.state_dict()
        ),

        "model_id": MODEL_ID,

        "num_labels": 4,

        "label_names": LABEL_NAMES,

        "threshold": THRESHOLD,

        "epoch": epoch,

        "macro_f1": (
            metrics["macro_f1"]
        ),

        "micro_f1": (
            metrics["micro_f1"]
        ),

        "train_size": (
            len(train_dataset)
        ),

        "valid_size": (
            len(valid_dataset)
        ),

        "seed": SEED,
    }

    torch.save(
        checkpoint,
        MODEL_SAVE_PATH,
    )


# ============================================================
# 19. 학습 시작
# ============================================================

start_time = time.time()

best_macro_f1 = -1.0

best_micro_f1 = 0.0

best_epoch = 0

early_stop_count = 0


for epoch in range(
    1,
    EPOCHS + 1,
):

    print()
    print("=" * 70)

    print(
        f"Epoch {epoch}/{EPOCHS}"
    )

    print("=" * 70)

    # --------------------------------------------------------
    # Train
    # --------------------------------------------------------

    train_loss = train_one_epoch(
        model=model,
        loader=train_loader,
        optimizer=optimizer,
        scheduler=scheduler,
        criterion=criterion,
    )

    # --------------------------------------------------------
    # Validation
    # --------------------------------------------------------

    metrics = evaluate(
        model=model,
        loader=valid_loader,
        threshold=THRESHOLD,
    )

    print(
        f"Train Loss : "
        f"{train_loss:.4f}"
    )

    print(
        f"Micro F1   : "
        f"{metrics['micro_f1']:.4f}"
    )

    print(
        f"Macro F1   : "
        f"{metrics['macro_f1']:.4f}"
    )

    print()

    for index, label in enumerate(
        LABEL_NAMES
    ):

        print(
            f"{label:<6} "
            f"P={metrics['precision'][index]:.4f} "
            f"R={metrics['recall'][index]:.4f} "
            f"F1={metrics['f1'][index]:.4f} "
            f"N={int(metrics['support'][index])}"
        )

    # --------------------------------------------------------
    # Best Model 저장
    # --------------------------------------------------------

    if (
        metrics["macro_f1"]
        > best_macro_f1
    ):

        best_macro_f1 = (
            metrics["macro_f1"]
        )

        best_micro_f1 = (
            metrics["micro_f1"]
        )

        best_epoch = epoch

        early_stop_count = 0

        save_checkpoint(
            model=model,
            epoch=epoch,
            metrics=metrics,
        )

        print()
        print(
            f"★ Best Model 저장 "
            f"(Macro F1 "
            f"{best_macro_f1:.4f})"
        )

    else:

        early_stop_count += 1

        print()
        print(
            f"Early Stop Count : "
            f"{early_stop_count}/{PATIENCE}"
        )

    # --------------------------------------------------------
    # Early Stopping
    # --------------------------------------------------------

    if (
        early_stop_count
        >= PATIENCE
    ):

        print()
        print(
            "Early Stopping"
        )

        break


# ============================================================
# 20. Best Weight 재로드 후 최종 평가
# ============================================================

checkpoint = torch.load(
    MODEL_SAVE_PATH,
    map_location=device,
)

model.load_state_dict(
    checkpoint[
        "model_state_dict"
    ]
)

model.to(
    device
)

final_metrics = evaluate(
    model=model,
    loader=valid_loader,
    threshold=THRESHOLD,
)


# ============================================================
# 21. 최종 결과 출력
# ============================================================

elapsed_time = (
    time.time()
    - start_time
)

print()
print("=" * 70)
print("A-only v4 Final Result")
print("=" * 70)

print(
    f"\nBest Epoch : {best_epoch}"
)

print(
    f"Threshold  : {THRESHOLD:.2f}"
)

print(
    f"Micro F1   : "
    f"{final_metrics['micro_f1']:.4f}"
)

print(
    f"Macro F1   : "
    f"{final_metrics['macro_f1']:.4f}"
)

print()
print("===== Per-label Result =====")

for index, label in enumerate(
    LABEL_NAMES
):

    print(
        f"{label:<6} "
        f"P={final_metrics['precision'][index]:.4f} "
        f"R={final_metrics['recall'][index]:.4f} "
        f"F1={final_metrics['f1'][index]:.4f} "
        f"N={int(final_metrics['support'][index])}"
    )

print()
print(
    "Best Weight:"
)

print(
    MODEL_SAVE_PATH
)

print()
print(
    f"Total Time : "
    f"{elapsed_time / 60:.2f} min"
)