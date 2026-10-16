"""
Q+A + CHILD-only로 학습한 KLUE-RoBERTa v2 모델을 로드해 추론한다.
상담사+아동 대화(Q+A)와 아동 발화 단독(CHILD-only) 입력을 모두 지원한다.
"""

# ============================================================
# 1. Import
# ============================================================

import argparse
from pathlib import Path

import torch

from transformers import (
    AutoConfig,
    AutoModelForSequenceClassification,
    AutoTokenizer,
)


# ============================================================
# 2. 기본 설정
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

MODEL_PATH = (
    BASE_DIR
    / "weight"
    / "roberta_abuse_qa_child_v3_best.pth"
)

MODEL_NAME = "klue/roberta-base"

LABEL_NAMES = [
    "신체학대",
    "정서학대",
    "성학대",
    "방임",
]

NUM_LABELS = len(LABEL_NAMES)

MAX_LENGTH = 512

DEFAULT_THRESHOLD = 0.5


# ============================================================
# 3. 모델 로더
# ============================================================

class AbuseQAModel:
    """
    v2 학습 weight와 동일한
    AutoModelForSequenceClassification 구조를 사용한다.
    """

    def __init__(
        self,
        model_path=MODEL_PATH,
        threshold=None,
    ):
        self.device = torch.device(
            "cuda"
            if torch.cuda.is_available()
            else "cpu"
        )

        print("=" * 80)
        print("[MODEL LOAD]")
        print("=" * 80)

        print("Device:", self.device)

        if torch.cuda.is_available():
            print(
                "GPU:",
                torch.cuda.get_device_name(0),
            )

        # ====================================================
        # checkpoint 로드
        # ====================================================

        checkpoint = torch.load(
            model_path,
            map_location=self.device,
        )

        # checkpoint 안에 저장된 설정 사용
        self.model_name = checkpoint.get(
            "model_name",
            MODEL_NAME,
        )

        self.label_names = checkpoint.get(
            "label_names",
            LABEL_NAMES,
        )

        self.max_length = checkpoint.get(
            "max_length",
            MAX_LENGTH,
        )

        # threshold를 직접 넣지 않았으면
        # 학습 checkpoint의 threshold를 사용
        if threshold is None:
            self.threshold = checkpoint.get(
                "threshold",
                DEFAULT_THRESHOLD,
            )
        else:
            self.threshold = threshold

        # ====================================================
        # tokenizer
        # ====================================================

        self.tokenizer = (
            AutoTokenizer.from_pretrained(
                self.model_name
            )
        )

        # ====================================================
        # v2 학습과 동일한 모델 구조 생성
        # ====================================================

        config = AutoConfig.from_pretrained(
            self.model_name,
            num_labels=len(self.label_names),
            problem_type="multi_label_classification",
        )

        self.model = (
            AutoModelForSequenceClassification
            .from_config(
                config
            )
        )

        # ====================================================
        # 학습된 weight 로드
        # ====================================================

        self.model.load_state_dict(
            checkpoint["model_state_dict"]
        )

        self.model.to(
            self.device
        )

        self.model.eval()

        print("Model:", model_path)

        print(
            "Best Epoch:",
            checkpoint.get(
                "epoch",
                "unknown",
            ),
        )

        print(
            "Best Macro F1:",
            checkpoint.get(
                "macro_f1",
                "unknown",
            ),
        )

        print(
            "Threshold:",
            self.threshold,
        )

        print("=" * 80)

    def threshold_for(
        self,
        label_name: str,
    ) -> float:
        """
        threshold가 유형별 dict({"신체학대": 0.4, ...})면 그 유형의 값을,
        기존처럼 단일 숫자(구버전 체크포인트 호환)면 그 값을 그대로 쓴다.
        """

        if isinstance(self.threshold, dict):
            return self.threshold.get(
                label_name,
                DEFAULT_THRESHOLD,
            )

        return self.threshold


# ============================================================
# 4. 입력 포맷 생성
# ============================================================

def build_qa_text(
    counselor_text,
    child_text,
):
    """
    상담사 질문 + 아동 답변을
    학습 데이터와 동일한 형식으로 만든다.
    """

    counselor_text = (
        counselor_text.strip()
        if counselor_text
        else ""
    )

    child_text = (
        child_text.strip()
        if child_text
        else ""
    )

    parts = []

    if counselor_text:
        parts.append(
            "[COUNSELOR] "
            + counselor_text
        )

    if child_text:
        parts.append(
            "[CHILD] "
            + child_text
        )

    return "\n".join(parts)


def build_child_only_text(
    child_text,
):
    """
    아동 발화 단독 입력에 [CHILD] tag를 붙인다.
    """

    child_text = (
        child_text.strip()
        if child_text
        else ""
    )

    if not child_text:
        return ""

    return (
        "[CHILD] "
        + child_text
    )


# ============================================================
# 5. 단일 텍스트 추론
# ============================================================

@torch.no_grad()
def predict_abuse(
    engine,
    text,
):
    """
    입력 텍스트에 대해
    4대 학대유형별 확률과 detected 여부를 반환한다.
    """

    if not text.strip():
        raise ValueError(
            "입력 텍스트가 비어 있습니다."
        )

    encoded = engine.tokenizer(
        text,
        max_length=engine.max_length,
        truncation=True,
        padding="max_length",
        return_tensors="pt",
    )

    input_ids = (
        encoded["input_ids"]
        .to(engine.device)
    )

    attention_mask = (
        encoded["attention_mask"]
        .to(engine.device)
    )

    # v2 학습 모델은
    # AutoModelForSequenceClassification 구조이므로
    # outputs.logits를 사용해야 한다.
    outputs = engine.model(
        input_ids=input_ids,
        attention_mask=attention_mask,
    )

    logits = outputs.logits

    probabilities = torch.sigmoid(
        logits
    )[0]

    probabilities = (
        probabilities
        .detach()
        .cpu()
        .numpy()
    )

    result = {}

    for label_name, probability in zip(
        engine.label_names,
        probabilities,
    ):
        probability = float(
            probability
        )

        result[label_name] = {
            "probability": round(
                probability,
                4,
            ),

            "detected": (
                probability
                >= engine.threshold_for(label_name)
            ),
        }

    return result


# ============================================================
# 6. Q+A 추론
# ============================================================

def predict_qa(
    engine,
    counselor_text,
    child_text,
):
    """
    상담사 질문 + 아동 답변을 함께 분석한다.
    """

    formatted_text = build_qa_text(
        counselor_text,
        child_text,
    )

    return {
        "input_mode": "qa",
        "input_text": formatted_text,
        "predictions": predict_abuse(
            engine,
            formatted_text,
        ),
    }


# ============================================================
# 7. CHILD-only 추론
# ============================================================

def predict_child_only(
    engine,
    child_text,
):
    """
    아동 발화 단독으로 분석한다.
    """

    formatted_text = (
        build_child_only_text(
            child_text
        )
    )

    return {
        "input_mode": "child_only",
        "input_text": formatted_text,
        "predictions": predict_abuse(
            engine,
            formatted_text,
        ),
    }


# ============================================================
# 8. 결과 출력
# ============================================================

def print_prediction(
    result,
):
    """
    터미널에서 결과를 보기 쉽게 출력한다.
    """

    print()
    print("=" * 80)
    print("[INPUT]")
    print("=" * 80)

    print(
        result["input_text"]
    )

    print()
    print("=" * 80)
    print("[PREDICTION]")
    print("=" * 80)

    for label_name, item in (
        result["predictions"].items()
    ):
        detected_text = (
            "O"
            if item["detected"]
            else "X"
        )

        print(
            "{:<6} {} ({:.4f})".format(
                label_name,
                detected_text,
                item["probability"],
            )
        )


# ============================================================
# 9. Sanity Test
# ============================================================

def run_sanity_tests(
    engine,
):
    """
    Q+A 문맥 활용과 CHILD-only 일반화 여부를
    빠르게 확인하기 위한 테스트다.
    """

    test_cases = [

        # ----------------------------------------------------
        # 1. Q+A 신체학대 부정
        # ----------------------------------------------------

        {
            "name": "Q+A 신체 부정",

            "mode": "qa",

            "counselor":
                "집에서 맞은 적이 있어?",

            "child":
                "아니요.",
        },

        # ----------------------------------------------------
        # 2. CHILD-only 신체학대
        # ----------------------------------------------------

        {
            "name": "CHILD-only 신체",

            "mode": "child",

            "child":
                "아빠가 막대기로 제 팔을 여러 번 때렸어요.",
        },

        # ----------------------------------------------------
        # 3. CHILD-only 방임
        # ----------------------------------------------------

        {
            "name": "CHILD-only 방임",

            "mode": "child",

            "child":
                "엄마가 며칠 동안 집에 안 와서 밥을 못 먹었어요.",
        },

        # ----------------------------------------------------
        # 4. CHILD-only 성학대
        # v1에서 실패했던 핵심 테스트
        # ----------------------------------------------------

        {
            "name": "CHILD-only 성학대",

            "mode": "child",

            "child":
                "싫다고 했는데 제 옷을 벗기려고 했어요.",
        },

        # ----------------------------------------------------
        # 5. 일반적인 비학대 발화
        # ----------------------------------------------------

        {
            "name": "CHILD-only 일반",

            "mode": "child",

            "child":
                "오늘 학교에서 친구랑 축구하고 집에 왔어요.",
        },

        # ----------------------------------------------------
        # 6. Q+A 문맥 기반 신체학대
        # 아동의 '네'만 보면 의미가 없지만
        # 상담사 질문과 같이 보면 의미가 생김
        # ----------------------------------------------------

        {
            "name": "Q+A 신체 긍정 문맥",

            "mode": "qa",

            "counselor":
                "아빠가 때린 적이 있나요?",

            "child":
                "네.",
        },

        # ----------------------------------------------------
        # 7. CHILD-only '네'
        # 단독으로는 학대 판단하면 안 됨
        # ----------------------------------------------------

        {
            "name": "CHILD-only 단답 네",

            "mode": "child",

            "child":
                "네.",
        },
    ]

    for index, case in enumerate(
        test_cases,
        start=1,
    ):
        print()
        print("#" * 80)

        print(
            "TEST {}: {}".format(
                index,
                case["name"],
            )
        )

        print("#" * 80)

        if case["mode"] == "qa":

            result = predict_qa(
                engine,
                case["counselor"],
                case["child"],
            )

        else:

            result = predict_child_only(
                engine,
                case["child"],
            )

        print_prediction(
            result
        )


# ============================================================
# 10. Argument Parser
# ============================================================

def parse_args():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--mode",
        choices=[
            "test",
            "qa",
            "child",
        ],
        default="test",
    )

    parser.add_argument(
        "--counselor",
        default="",
    )

    parser.add_argument(
        "--child",
        default="",
    )

    parser.add_argument(
        "--threshold",
        type=float,
        default=None,
    )

    return parser.parse_args()


# ============================================================
# 11. Main
# ============================================================

def main():

    args = parse_args()

    engine = AbuseQAModel(
        model_path=MODEL_PATH,
        threshold=args.threshold,
    )

    if args.mode == "test":

        run_sanity_tests(
            engine
        )

        return

    if args.mode == "qa":

        if not args.child:
            raise ValueError(
                "--mode qa 사용 시 "
                "--child 입력이 필요합니다."
            )

        result = predict_qa(
            engine,
            args.counselor,
            args.child,
        )

        print_prediction(
            result
        )

        return

    if args.mode == "child":

        if not args.child:
            raise ValueError(
                "--mode child 사용 시 "
                "--child 입력이 필요합니다."
            )

        result = predict_child_only(
            engine,
            args.child,
        )

        print_prediction(
            result
        )


# ============================================================
# 12. 실행
# ============================================================

if __name__ == "__main__":
    main()
