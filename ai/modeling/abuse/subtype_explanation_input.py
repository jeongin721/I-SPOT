# 2차 모델 탐지 결과
# XAI 후보 표현
# 원문을 하나로 묶는 것.
# 확률/threshold는 넣지 않음
# 아직 LLM 호출은 안 함

"""
I-SPOT 2차 세부유형 분석 결과와 XAI 근거 후보를 LLM 입력 JSON으로 변환한다.
LLM은 세부유형을 재판단하지 않고, 원문과 XAI 후보를 바탕으로 설명만 수행하도록 입력을 구성한다.
"""

# ============================================================
# 1. Import
# ============================================================

import json
from typing import Dict, List

from ai.modeling.abuse import infer_subtype
from ai.modeling.abuse import explain_subtype


# ============================================================
# 2. LLM 입력 구조 생성
# ============================================================

def build_subtype_explanation_input(
    text: str,
) -> Dict:
    """
    상담 텍스트를 입력받아 LLM 설명용 JSON 구조를 생성한다.

    포함:
    - original_text
    - detected_subtypes
    - subtype별 display_name
    - XAI evidence_candidates

    제외:
    - probability
    - threshold
    - 모델 내부 score
    """

    if not text or not text.strip():
        raise ValueError(
            "상담 텍스트가 비어 있습니다."
        )

    text = text.strip()

    # --------------------------------------------------------
    # 2차 subtype 탐지
    # --------------------------------------------------------

    predictions = (
        infer_subtype.predict_subtype(
            text
        )
    )

    # --------------------------------------------------------
    # 탐지된 subtype만 추출
    # --------------------------------------------------------

    detected_labels = [
        label
        for label in infer_subtype.LABEL_NAMES
        if predictions[label]["detected"]
    ]

    # --------------------------------------------------------
    # 탐지 결과가 없는 경우
    # --------------------------------------------------------

    if not detected_labels:

        return {
            "original_text": text,
            "detected_subtypes": [],
        }

    # --------------------------------------------------------
    # XAI 실행
    # --------------------------------------------------------

    xai_results = (
        explain_subtype.explain_subtype(
            text
        )
    )

    # --------------------------------------------------------
    # LLM 입력 구성
    # --------------------------------------------------------

    detected_subtypes: List[Dict] = []

    for label in detected_labels:

        xai_result = xai_results.get(
            label,
            {},
        )

        evidence_candidates = (
            xai_result.get(
                "evidence_phrases",
                [],
            )
        )

        detected_subtypes.append(
            {
                "subtype": label,
                "subtype_name": (
                    infer_subtype
                    .LABEL_DISPLAY_NAMES[
                        label
                    ]
                ),
                "evidence_candidates": (
                    evidence_candidates
                ),
            }
        )

    return {
        "original_text": text,
        "detected_subtypes": detected_subtypes,
    }


# ============================================================
# 3. LLM 전달용 JSON 문자열 생성
# ============================================================

def build_subtype_explanation_json(
    text: str,
) -> str:
    """
    LLM Prompt에 바로 넣을 수 있는 JSON 문자열을 생성한다.
    """

    result = (
        build_subtype_explanation_input(
            text
        )
    )

    return json.dumps(
        result,
        ensure_ascii=False,
        indent=2,
    )


# ============================================================
# 4. CLI 테스트
# ============================================================

def main() -> None:
    """터미널에서 LLM 입력 JSON 생성 결과를 확인한다."""

    print()
    print("=" * 70)
    print("I-SPOT 2차 세부유형 LLM 입력 생성")
    print("=" * 70)
    print()

    text = input(
        "상담 텍스트 입력: "
    ).strip()

    result_json = (
        build_subtype_explanation_json(
            text
        )
    )

    print()
    print("=" * 70)
    print("LLM 입력 JSON")
    print("=" * 70)
    print()

    print(
        result_json
    )

    print()
    print(
        "※ probability 및 threshold는 LLM 입력에 포함하지 않습니다."
    )

    print(
        "※ LLM은 세부유형을 재판단하지 않고 "
        "근거 정리 및 설명 역할만 수행하도록 제한합니다."
    )


# ============================================================
# 5. Entry Point
# ============================================================

if __name__ == "__main__":
    main()