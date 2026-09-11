"""
I-SPOT 1차 학대유형 모델의 내부 sigmoid 확률과 threshold를 비교한다.
오탐/미탐 문장이 threshold 문제인지 학습 문제인지 진단하기 위한 테스트 코드다.
"""

import torch

from ai.modeling.abuse.infer_abuse import (
    LABEL_NAMES,
    THRESHOLDS,
    model,
    tokenizer,
    device,
)


# ============================================================
# 1. 진단 문장
# ============================================================

TEST_CASES = [
    {
        "name": "정서학대 문장 → 신체학대 FP",
        "text": "아빠가 말을 안 들으면 집에서 나가라고 했어요.",
    },
    {
        "name": "성학대 문장 → 성학대 FN",
        "text": "싫다고 했는데 제 옷을 벗기려고 했어요.",
    },
    {
        "name": "애매 문장 → 방임 FP",
        "text": "집에 혼자 있었어요.",
    },
]


# ============================================================
# 2. 내부 확률 계산
# ============================================================

def predict_probabilities(text: str):
    """문장의 4개 학대유형별 sigmoid 확률을 반환한다."""

    encoded = tokenizer(
        text,
        return_tensors="pt",
        truncation=True,
        padding=True,
        max_length=512,
    )

    encoded = {
        key: value.to(device)
        for key, value in encoded.items()
    }

    model.eval()

    with torch.no_grad():
        outputs = model(
            **encoded
        )

        probabilities = torch.sigmoid(
            outputs.logits
        )[0]

    return {
        label: float(
            probabilities[index].item()
        )
        for index, label in enumerate(LABEL_NAMES)
    }


# ============================================================
# 3. 출력
# ============================================================

def main() -> None:
    """문제 문장의 확률과 threshold를 비교 출력한다."""

    print()
    print("=" * 90)
    print("I-SPOT 1차 모델 내부 확률 진단")
    print("=" * 90)

    for case in TEST_CASES:

        probabilities = predict_probabilities(
            case["text"]
        )

        print()
        print("-" * 90)
        print(case["name"])
        print(f"문장: {case['text']}")
        print()

        for label in LABEL_NAMES:

            probability = probabilities[
                label
            ]

            threshold = THRESHOLDS[
                label
            ]

            detected = (
                probability >= threshold
            )

            print(
                f"{label:8s} "
                f"확률={probability:.4f} "
                f"threshold={threshold:.2f} "
                f"→ {'탐지' if detected else '미탐지'}"
            )


# ============================================================
# 4. 실행
# ============================================================

if __name__ == "__main__":
    main()