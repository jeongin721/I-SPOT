"""
1차 RoBERTa 대분류 모델과 2차 LLM 세부유형 분석을 하나로 묶는 통합 파이프라인.

입력 유형(input_mode)에 따라 1차 모델 경로만 다르게 타고,
2차 세부유형 분석은 입력 유형과 무관하게 1차에서 탐지된
major_type과 원문 텍스트만으로 동일하게 동작한다.
"""

import json

from ai.modeling.abuse.infer_abuse_v3_adapter import (
    predict_major_types,
)
from ai.modeling.abuse.second_stage_llm import (
    analyze_subtypes,
)


# ============================================================
# 1. 통합 함수
# ============================================================

def analyze_abuse(
    text: str,
    input_mode: str = "qa",
) -> dict:
    """
    1차 대분류 판정 → 2차 세부유형 분석까지 이어서 수행한다.

    input_mode: "qa" | "child_only"
    (note 모드는 대응하는 1차 모델이 아직 없어 지원하지 않는다.)
    """

    major_result = predict_major_types(
        text=text,
        input_mode=input_mode,
    )

    detected_major_types = [
        label
        for label, prediction in major_result.items()
        if prediction.get(
            "detected",
            False,
        )
    ]

    if not detected_major_types:
        subtype_result = {
            "results": [],
            "note": "탐지된 대분류 없음",
        }
    else:
        subtype_result = analyze_subtypes(
            text=text,
            major_types=detected_major_types,
        )

    return {
        "input_mode": input_mode,
        "major_types": major_result,
        "detected_major_types": detected_major_types,
        "subtype_analysis": subtype_result,
    }


# ============================================================
# 2. 데모
# ============================================================

if __name__ == "__main__":

    text = "아빠가 막대기로 제 팔을 때렸어요."

    input_mode = "child_only"

    result = analyze_abuse(
        text=text,
        input_mode=input_mode,
    )

    print(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2,
        )
    )
