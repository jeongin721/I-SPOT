from pathlib import Path
import re

import numpy as np
import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification


# ============================================================
# 설정
# ============================================================

MODEL_ID = "klue/roberta-base"
MAX_LEN = 512

BASE_DIR = Path(__file__).resolve().parent

MODEL_PATH = (
    BASE_DIR
    / "weight"
    / "roberta_multilabel_2026-09-03.pth"
)

LABEL_NAMES = [
    "신체학대",
    "정서학대",
    "성학대",
    "방임",
]

# Validation 데이터에서 튜닝한 라벨별 threshold
THRESHOLDS = {
    "신체학대": 0.72,
    "정서학대": 0.39,
    "성학대": 0.53,
    "방임": 0.32,
}

device = torch.device(
    "cuda" if torch.cuda.is_available() else "cpu"
)


# ============================================================
# 텍스트 전처리
# ============================================================

def clean_text(text: str) -> str:
    text = str(text)

    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    return text.strip()


# ============================================================
# 모델 로드
# ============================================================

print("Device :", device)

if torch.cuda.is_available():
    print(
        "GPU :",
        torch.cuda.get_device_name(0),
    )


tokenizer = AutoTokenizer.from_pretrained(
    MODEL_ID
)

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

print("Model loaded :", MODEL_PATH)


# ============================================================
# 추론
# ============================================================

def predict_abuse(text: str) -> dict:

    text = clean_text(text)

    if not text:
        raise ValueError(
            "분석할 상담 텍스트가 없습니다."
        )

    encoded = tokenizer(
        text,
        max_length=MAX_LEN,
        padding="max_length",
        truncation=True,
        return_tensors="pt",
    )

    input_ids = encoded[
        "input_ids"
    ].to(device)

    attention_mask = encoded[
        "attention_mask"
    ].to(device)

    token_type_ids = encoded.get(
        "token_type_ids"
    )

    if token_type_ids is not None:
        token_type_ids = token_type_ids.to(device)

    with torch.no_grad():

        outputs = model(
            input_ids=input_ids,
            attention_mask=attention_mask,
            token_type_ids=token_type_ids,
        )

        probabilities = torch.sigmoid(
            outputs.logits
        )[0].cpu().numpy()

    results = {}

    for label, probability in zip(
        LABEL_NAMES,
        probabilities,
    ):

        threshold = THRESHOLDS[label]

        results[label] = {
            "probability": float(probability),
            "percentage": round(
                float(probability) * 100,
                2,
            ),
            "threshold": threshold,
            "detected": bool(
                probability >= threshold
            ),
        }

    return results


# ============================================================
# 터미널 테스트
# ============================================================

if __name__ == "__main__":

    print()
    print("==============================")
    print("   학대 관련 신호 테스트")
    print("==============================")

    text = input(
        "\n상담 텍스트 입력: "
    )

    result = predict_abuse(text)

    print("\n===== 분석 결과 =====")

    for label in LABEL_NAMES:

        item = result[label]

        status = (
            "신호 있음"
            if item["detected"]
            else "신호 없음"
        )

        print(
            f"{label:<6} "
            f"{item['percentage']:>6.2f}% "
            f"(기준 {item['threshold']:.2f}) "
            f"→ {status}"
        )