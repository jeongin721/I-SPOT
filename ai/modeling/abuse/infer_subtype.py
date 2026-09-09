"""
I-SPOT 2차 세부유형 RoBERTa v2 추론 모듈이다.
15개 세부유형에 Validation-tuned threshold를 적용하고 외부에는 탐지 여부만 반환한다.
"""

# ============================================================
# 1. Import
# ============================================================

from pathlib import Path
from typing import Dict

import torch
from transformers import (
    AutoModelForSequenceClassification,
    AutoTokenizer,
)


# ============================================================
# 2. 기본 경로
# ============================================================

BASE_DIR = Path("/data/I-SPOT")

WEIGHT_PATH = (
    BASE_DIR
    / "ai"
    / "modeling"
    / "abuse"
    / "weight"
    / "roberta_subtype_v2_best.pth"
)


# ============================================================
# 3. 모델 설정
# ============================================================

MODEL_NAME = "klue/roberta-base"

MAX_LENGTH = 256


# ============================================================
# 4. 15개 세부유형 Label
# ============================================================

LABEL_NAMES = [
    "physical_direct",
    "physical_object",
    "physical_force",

    "emotional_verbal",
    "emotional_threat",
    "emotional_restriction",
    "emotional_discrimination",
    "emotional_dv_exposure",
    "emotional_cruelty",

    "sexual_exposure",
    "sexual_molestation",
    "sexual_intercourse",

    "neglect_physical",
    "neglect_education",
    "neglect_medical",
]

NUM_LABELS = len(LABEL_NAMES)


# ============================================================
# 5. 표시용 한글 이름
# ============================================================

LABEL_DISPLAY_NAMES = {
    "physical_direct": "직접 신체 가해",
    "physical_object": "도구 사용 가해",
    "physical_force": "완력·신체적 강압",

    "emotional_verbal": "언어적 모욕·적대",
    "emotional_threat": "위협·쫓아냄",
    "emotional_restriction": "감금·억제·강압",
    "emotional_discrimination": "차별·편애·가족 내 고립",
    "emotional_dv_exposure": "가정폭력 노출",
    "emotional_cruelty": "기타 가학적 행위",

    "sexual_exposure": "성적 노출·관찰·노출 요구",
    "sexual_molestation": "성적 추행",
    "sexual_intercourse": "성교",

    "neglect_physical": "물리적 방임",
    "neglect_education": "교육적 방임",
    "neglect_medical": "의료적 방임",
}


# ============================================================
# 6. Validation-tuned Threshold
# ============================================================

"""
주의:
아래 threshold는 독립 Test가 아닌 동일 Validation 데이터에서
튜닝된 값이므로 provisional threshold로 사용한다.

특히 support가 매우 작은 희소 라벨은 threshold 안정성이 낮을 수 있다.
"""

THRESHOLDS = {
    "physical_direct": 0.76,
    "physical_object": 0.92,
    "physical_force": 0.85,

    "emotional_verbal": 0.88,
    "emotional_threat": 0.50,
    "emotional_restriction": 0.72,
    "emotional_discrimination": 0.19,
    "emotional_dv_exposure": 0.58,
    "emotional_cruelty": 0.50,

    "sexual_exposure": 0.94,
    "sexual_molestation": 0.94,
    "sexual_intercourse": 0.50,

    "neglect_physical": 0.53,
    "neglect_education": 0.50,
    "neglect_medical": 0.92,
}


# ============================================================
# 7. Device
# ============================================================

DEVICE = torch.device(
    "cuda"
    if torch.cuda.is_available()
    else "cpu"
)


# ============================================================
# 8. 전역 모델 객체
# ============================================================

tokenizer = None
model = None


# ============================================================
# 9. 모델 로드
# ============================================================

def load_subtype_model() -> None:
    """
    2차 subtype v2 Best 모델과 tokenizer를 메모리에 로드한다.

    이미 로드된 경우 다시 로드하지 않는다.
    """

    global tokenizer
    global model

    if tokenizer is not None and model is not None:
        return

    if not WEIGHT_PATH.exists():
        raise FileNotFoundError(
            f"2차 모델 weight를 찾을 수 없습니다: {WEIGHT_PATH}"
        )

    checkpoint = torch.load(
        WEIGHT_PATH,
        map_location=DEVICE,
    )

    # --------------------------------------------------------
    # Checkpoint에 저장된 label 순서 검증
    # --------------------------------------------------------

    checkpoint_labels = checkpoint.get(
        "label_names"
    )

    if (
        checkpoint_labels is not None
        and checkpoint_labels != LABEL_NAMES
    ):
        raise ValueError(
            "Checkpoint label 순서와 "
            "infer_subtype.py의 LABEL_NAMES 순서가 다릅니다."
        )

    # --------------------------------------------------------
    # Checkpoint의 model_name이 있으면 우선 사용
    # --------------------------------------------------------

    model_name = checkpoint.get(
        "model_name",
        MODEL_NAME,
    )

    tokenizer = AutoTokenizer.from_pretrained(
        model_name
    )

    model = (
        AutoModelForSequenceClassification
        .from_pretrained(
            model_name,
            num_labels=NUM_LABELS,
            problem_type="multi_label_classification",
        )
    )

    model.load_state_dict(
        checkpoint["model_state_dict"]
    )

    model.to(DEVICE)
    model.eval()


# ============================================================
# 10. 내부 Score 계산
# ============================================================

@torch.no_grad()
def _predict_scores(
    text: str,
) -> Dict[str, float]:
    """
    내부 추론용 sigmoid score를 계산한다.

    이 함수의 score는 threshold 판정에만 사용하며
    API/UI 외부 결과에는 노출하지 않는다.
    """

    if not text or not text.strip():
        raise ValueError(
            "추론할 상담 텍스트가 비어 있습니다."
        )

    load_subtype_model()

    encoded = tokenizer(
        text.strip(),
        truncation=True,
        padding=True,
        max_length=MAX_LENGTH,
        return_tensors="pt",
    )

    input_ids = encoded[
        "input_ids"
    ].to(DEVICE)

    attention_mask = encoded[
        "attention_mask"
    ].to(DEVICE)

    outputs = model(
        input_ids=input_ids,
        attention_mask=attention_mask,
    )

    probabilities = torch.sigmoid(
        outputs.logits
    )[0]

    scores = {
        label: float(
            probabilities[index].item()
        )
        for index, label in enumerate(
            LABEL_NAMES
        )
    }

    return scores


# ============================================================
# 11. 외부용 세부유형 추론
# ============================================================

def predict_subtype(
    text: str,
) -> Dict[str, Dict[str, bool]]:
    """
    상담 텍스트에서 15개 세부유형 관련 신호를 탐지한다.

    반환값에는 확률 및 threshold를 노출하지 않고
    각 세부유형의 detected 여부만 포함한다.
    """

    scores = _predict_scores(
        text
    )

    result = {}

    for label in LABEL_NAMES:

        detected = (
            scores[label]
            >= THRESHOLDS[label]
        )

        result[label] = {
            "detected": bool(
                detected
            )
        }

    return result


# ============================================================
# 12. 탐지된 세부유형만 반환
# ============================================================

def get_detected_subtypes(
    text: str,
) -> Dict[str, Dict[str, str]]:
    """
    detected=True인 세부유형만 추려서 반환한다.

    LLM 설명 입력이나 후속 XAI 파이프라인 연결 시 사용할 수 있다.
    """

    predictions = predict_subtype(
        text
    )

    detected_result = {}

    for label, result in predictions.items():

        if result["detected"]:

            detected_result[label] = {
                "display_name": (
                    LABEL_DISPLAY_NAMES[
                        label
                    ]
                )
            }

    return detected_result


# ============================================================
# 13. CLI 테스트
# ============================================================

def main() -> None:
    """터미널에서 간단한 추론 테스트를 수행한다."""

    print()
    print("=" * 70)
    print("I-SPOT 2차 세부유형 추론")
    print("=" * 70)

    print(
        f"Device : {DEVICE}"
    )

    if torch.cuda.is_available():

        print(
            f"GPU    : "
            f"{torch.cuda.get_device_name(0)}"
        )

    print(
        f"Weight : {WEIGHT_PATH}"
    )

    print()

    text = input(
        "상담 텍스트 입력: "
    ).strip()

    predictions = predict_subtype(
        text
    )

    print()
    print("=" * 70)
    print("세부유형 관련 신호 탐지 결과")
    print("=" * 70)

    detected_count = 0

    for label in LABEL_NAMES:

        if predictions[
            label
        ]["detected"]:

            detected_count += 1

            print(
                f"[탐지] "
                f"{LABEL_DISPLAY_NAMES[label]} "
                f"({label})"
            )

    if detected_count == 0:

        print(
            "현재 입력에서 탐지된 세부유형 관련 신호가 없습니다."
        )

    print()
    print(
        "※ 본 결과는 상담사의 판단을 보조하기 위한 "
        "AI 분석 결과이며 최종 학대 판단이 아닙니다."
    )


# ============================================================
# 14. Entry Point
# ============================================================

if __name__ == "__main__":
    main()