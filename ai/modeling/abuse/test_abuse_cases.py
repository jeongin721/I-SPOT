"""
I-SPOT 1차 학대유형 모델의 기본 문장별 탐지 성능을 빠르게 점검한다.
정상/학대/애매 문장을 함께 넣어 False Positive와 False Negative 후보를 확인한다.
"""

from typing import Dict, List, Set

from tqdm import tqdm

from ai.modeling.abuse.infer_abuse import predict_abuse


# ============================================================
# 1. 학대유형
# ============================================================

ABUSE_LABELS = [
    "신체학대",
    "정서학대",
    "성학대",
    "방임",
]


# ============================================================
# 2. 테스트 문장
# ============================================================

TEST_CASES = [
    # --------------------------------------------------------
    # 신체학대
    # --------------------------------------------------------
    {
        "category": "신체학대",
        "text": "아빠가 저를 손으로 여러 번 때렸어요.",
        "expected": {"신체학대"},
    },
    {
        "category": "신체학대",
        "text": "엄마가 화가 나서 제 팔을 세게 잡아당겼어요.",
        "expected": {"신체학대"},
    },
    {
        "category": "신체학대",
        "text": "아빠가 막대기로 제 다리를 때렸어요.",
        "expected": {"신체학대"},
    },

    # --------------------------------------------------------
    # 정서학대
    # --------------------------------------------------------
    {
        "category": "정서학대",
        "text": "엄마가 저한테 쓸모없는 아이라고 계속 욕해요.",
        "expected": {"정서학대"},
    },
    {
        "category": "정서학대",
        "text": "아빠가 말을 안 들으면 집에서 나가라고 했어요.",
        "expected": {"정서학대"},
    },
    {
        "category": "정서학대",
        "text": "아빠가 죽여버리겠다고 말해서 무서웠어요.",
        "expected": {"정서학대"},
    },

    # --------------------------------------------------------
    # 성학대
    # --------------------------------------------------------
    {
        "category": "성학대",
        "text": "아빠가 제 몸의 중요한 부위를 만졌어요.",
        "expected": {"성학대"},
    },
    {
        "category": "성학대",
        "text": "싫다고 했는데 제 옷을 벗기려고 했어요.",
        "expected": {"성학대"},
    },
    {
        "category": "성학대",
        "text": "제 몸을 보여달라고 계속 말했어요.",
        "expected": {"성학대"},
    },

    # --------------------------------------------------------
    # 방임
    # --------------------------------------------------------
    {
        "category": "방임",
        "text": "엄마가 며칠 동안 밥을 주지 않았어요.",
        "expected": {"방임"},
    },
    {
        "category": "방임",
        "text": "아파도 병원에 데려가지 않았어요.",
        "expected": {"방임"},
    },
    {
        "category": "방임",
        "text": "집에 혼자 있는 날이 많고 밥도 혼자 챙겨 먹어요.",
        "expected": {"방임"},
    },

    # --------------------------------------------------------
    # 정상 문장
    # --------------------------------------------------------
    {
        "category": "정상",
        "text": "어제 엄마랑 같이 저녁을 먹었어요.",
        "expected": set(),
    },
    {
        "category": "정상",
        "text": "학교가 끝나고 친구들이랑 놀았어요.",
        "expected": set(),
    },
    {
        "category": "정상",
        "text": "아빠랑 주말에 영화를 봤어요.",
        "expected": set(),
    },
    {
        "category": "정상",
        "text": "엄마가 아침에 학교까지 데려다줬어요.",
        "expected": set(),
    },

    # --------------------------------------------------------
    # 애매한 문장
    # --------------------------------------------------------
    {
        "category": "애매",
        "text": "아빠가 화를 냈어요.",
        "expected": set(),
    },
    {
        "category": "애매",
        "text": "엄마가 늦게 들어왔어요.",
        "expected": set(),
    },
    {
        "category": "애매",
        "text": "아빠랑 크게 싸웠어요.",
        "expected": set(),
    },
    {
        "category": "애매",
        "text": "집에 혼자 있었어요.",
        "expected": set(),
    },
]


# ============================================================
# 3. 탐지 결과 변환
# ============================================================

def get_detected_labels(
    prediction: Dict,
) -> Set[str]:
    """모델 결과에서 detected=True인 학대유형만 추출한다."""

    return {
        label
        for label in ABUSE_LABELS
        if prediction.get(
            label,
            {},
        ).get(
            "detected",
            False,
        )
    }


# ============================================================
# 4. 테스트 실행
# ============================================================

def main() -> None:
    """테스트 문장 전체를 추론하고 오탐/미탐 후보를 출력한다."""

    total = len(TEST_CASES)
    correct = 0

    false_positive_count = 0
    false_negative_count = 0

    print()
    print("=" * 90)
    print("I-SPOT 1차 학대유형 모델 문장별 진단")
    print("=" * 90)

    for index, case in enumerate(
        tqdm(
            TEST_CASES,
            desc="1차 모델 진단",
        ),
        start=1,
    ):
        text = case["text"]
        expected = case["expected"]

        prediction = predict_abuse(
            text
        )

        detected = get_detected_labels(
            prediction
        )

        false_positive = detected - expected
        false_negative = expected - detected

        is_correct = (
            not false_positive
            and not false_negative
        )

        if is_correct:
            correct += 1

        false_positive_count += len(
            false_positive
        )

        false_negative_count += len(
            false_negative
        )

        print()
        print("-" * 90)
        print(
            f"[{index:02d}] "
            f"{case['category']}"
        )
        print(
            f"문장 : {text}"
        )
        print(
            f"기대 : "
            f"{sorted(expected) if expected else ['없음']}"
        )
        print(
            f"탐지 : "
            f"{sorted(detected) if detected else ['없음']}"
        )

        if is_correct:
            print("결과 : ✅ 정상")
        else:
            print("결과 : ❌ 확인 필요")

            if false_positive:
                print(
                    "  FP :",
                    sorted(false_positive),
                )

            if false_negative:
                print(
                    "  FN :",
                    sorted(false_negative),
                )

    # ========================================================
    # 5. 최종 요약
    # ========================================================

    print()
    print("=" * 90)
    print("진단 요약")
    print("=" * 90)

    print(
        f"전체 문장       : {total}"
    )
    print(
        f"정확히 일치     : {correct}"
    )
    print(
        f"일치율          : {correct / total:.2%}"
    )
    print(
        f"False Positive : {false_positive_count}"
    )
    print(
        f"False Negative : {false_negative_count}"
    )


# ============================================================
# 6. 실행
# ============================================================

if __name__ == "__main__":
    main()