"""
v4 학대유형 모델의 탐지 결과와 XAI 근거 표현을 LLM 입력 JSON으로 변환한다.
> 전달하지 않고 탐지된 유형과 해당 유형의 근거 표현만 포함한다.
"""

# ============================================================
# 1. Import
# ============================================================

import json
from typing import Dict, List

from ai.modeling.abuse.infer_abuse import (
    LABEL_NAMES,
    predict_abuse,
)

from ai.modeling.abuse.explain_abuse import (
    explain_abuse,
)


# ============================================================
# 2. LLM 입력 데이터 생성
# ============================================================

def build_abuse_explanation_input(
    text: str,
) -> Dict:
    """
    상담 텍스트를 분석해 LLM 설명 생성용 입력 데이터를 만든다.

    반환 예시:
        {
            "detected_signals": [
                {
                    "type": "신체학대",
                    "evidence_phrases": [
                        "팔을 세게 잡았어요"
                    ]
                }
            ]
        }

    주의:
        - 모델 확률은 LLM에 전달하지 않는다.
        - 탐지되지 않은 유형은 포함하지 않는다.
        - XAI 근거가 없는 경우 evidence_phrases는 빈 리스트로 둔다.
    """

    # --------------------------------------------------------
    # v4 모델의 4대 학대유형 관련 신호 탐지
    # --------------------------------------------------------

    predictions = predict_abuse(
        text
    )

    # --------------------------------------------------------
    # 동일한 v4 모델을 이용한 Phrase Occlusion XAI
    # --------------------------------------------------------

    explanations = explain_abuse(
        text
    )

    # --------------------------------------------------------
    # LLM에 전달할 탐지 신호 구성
    # --------------------------------------------------------

    detected_signals: List[Dict] = []

    for label in LABEL_NAMES:

        prediction = predictions.get(
            label,
            {}
        )

        # 탐지되지 않은 유형은 LLM 입력에서 제외
        if not prediction.get(
            "detected",
            False,
        ):
            continue

        evidence_items = explanations.get(
            label,
            [],
        )

        # XAI 결과에서는 phrase 문자열만 추출
        evidence_phrases = []

        for item in evidence_items:

            phrase = item.get(
                "phrase",
                ""
            ).strip()

            if (
                phrase
                and phrase not in evidence_phrases
            ):
                evidence_phrases.append(
                    phrase
                )

        detected_signals.append(
            {
                "type": label,
                "evidence_phrases": evidence_phrases,
            }
        )

    # --------------------------------------------------------
    # 최종 LLM 입력
    # --------------------------------------------------------

    return {
        "detected_signals": detected_signals,
    }


# ============================================================
# 3. 터미널 테스트
# ============================================================

if __name__ == "__main__":

    print(
        "\nI-SPOT LLM 입력 생성 테스트"
    )

    print(
        "종료하려면 exit 입력\n"
    )

    while True:

        text = input(
            "상담 텍스트 입력: "
        ).strip()

        if text.lower() == "exit":
            break

        if not text:
            print(
                "상담 텍스트를 입력해주세요.\n"
            )
            continue

        try:

            result = (
                build_abuse_explanation_input(
                    text
                )
            )

            print(
                "\n[LLM 입력 JSON]"
            )

            print(
                json.dumps(
                    result,
                    ensure_ascii=False,
                    indent=2,
                )
            )

            print()

        except Exception as error:

            print(
                f"\n오류: {error}\n"
            )
