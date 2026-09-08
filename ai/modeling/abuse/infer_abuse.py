"""
I-SPOT 1차 학대유형 관련 신호 분류 추론 모듈.
상담 텍스트에서 4대 학대유형 관련 신호의 탐지 여부만 반환하며 확률은 외부에 노출하지 않는다.
"""

from pathlib import Path
import re

import torch
from transformers import (
    AutoModelForSequenceClassification,
    AutoTokenizer,
)


# ============================================================
# 기본 설정
# ============================================================

MODEL_ID = "klue/roberta-base"
MAX_LEN = 512
NUM_LABELS = 4

BASE_DIR = Path(__file__).resolve().parent

MODEL_PATH = (
    BASE_DIR
    / "weight"
    / "roberta_multilabel_v4_2026-09-07.pth"
)

LABEL_NAMES = [
    "신체학대",
    "정서학대",
    "성학대",
    "방임",
]


# ============================================================
# 내부 판정 Threshold
#
# Validation 데이터에서 튜닝한 값.
# 사용자 화면/API 결과에는 노출하지 않는다.
# ============================================================

THRESHOLDS = {
    "신체학대": 0.57,
    "정서학대": 0.54,
    "성학대": 0.19,
    "방임": 0.55,
}


# ============================================================
# Device 설정
# ============================================================

device = torch.device(
    "cuda" if torch.cuda.is_available() else "cpu"
)


# ============================================================
# 텍스트 전처리
# ============================================================

def clean_text(text: str) -> str:
    """입력 상담 텍스트의 불필요한 공백을 정리한다."""

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
    num_labels=NUM_LABELS,
    problem_type="multi_label_classification",
)

checkpoint = torch.load(
    MODEL_PATH,
    map_location=device,
)

# ------------------------------------------------------------
# 학습 checkpoint / 순수 state_dict 형식 모두 지원
# ------------------------------------------------------------

if (
    isinstance(checkpoint, dict)
    and "model_state_dict" in checkpoint
):
    state_dict = checkpoint["model_state_dict"]
else:
    state_dict = checkpoint

model.load_state_dict(
    state_dict
)

model.to(
    device
)

model.eval()

print(
    "Model loaded :",
    MODEL_PATH,
)


# ============================================================
# 1차 학대유형 관련 신호 추론
# ============================================================

def predict_abuse(text: str) -> dict:
    """
    상담 텍스트를 분석하여 4대 학대유형 관련 신호 여부를 반환한다.

    확률과 threshold는 내부 판정에만 사용하고 외부 결과에는 포함하지 않는다.
    """

    text = clean_text(
        text
    )

    if not text:
        raise ValueError(
            "분석할 상담 텍스트가 없습니다."
        )

    # --------------------------------------------------------
    # Tokenization
    # --------------------------------------------------------

    encoded = tokenizer(
        text,
        max_length=MAX_LEN,
        padding="max_length",
        truncation=True,
        return_tensors="pt",
    )

    encoded = {
        key: value.to(device)
        for key, value in encoded.items()
    }

    # --------------------------------------------------------
    # RoBERTa 추론
    # --------------------------------------------------------

    with torch.no_grad():

        outputs = model(
            **encoded
        )

        probabilities = torch.sigmoid(
            outputs.logits
        )[0]

    # --------------------------------------------------------
    # Threshold 기반 관련 신호 판정
    #
    # probability 자체는 반환하지 않는다.
    # --------------------------------------------------------

    results = {}

    for index, label in enumerate(
        LABEL_NAMES
    ):

        probability = float(
            probabilities[index].item()
        )

        threshold = THRESHOLDS[
            label
        ]

        results[label] = {
            "detected": bool(
                probability >= threshold
            )
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

    result = predict_abuse(
        text
    )

    print()
    print("===== 분석 결과 =====")

    detected_labels = []

    for label in LABEL_NAMES:

        if result[label]["detected"]:
            detected_labels.append(
                label
            )

    # --------------------------------------------------------
    # 사용자에게는 탐지 여부만 표시
    # --------------------------------------------------------

    if detected_labels:

        for label in detected_labels:
            print(
                f"✓ {label} 관련 신호 탐지"
            )

    else:
        print(
            "탐지된 학대 관련 신호 없음"
        )

    print()
    print(
        "※ AI 분석 결과는 상담사의 판단을 "
        "보조하기 위한 정보입니다."
    )