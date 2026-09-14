"""
1차 RoBERTa 대분류 모델, 2차 LLM 세부유형 분석, 상담 요약·상담일지 생성까지
하나로 묶는 전체 세션 파이프라인.

입력 유형(input_mode)에 따라 1차 모델 경로만 다르게 타고,
2차 세부유형 분석과 상담 요약·상담일지 생성은 입력 유형과 무관하게
원문 텍스트만으로 동일하게 동작한다.

note(상담일지/서술형 텍스트) 입력용 1차 모델은 아직 없으므로
input_mode="note"는 이번 범위에 포함하지 않는다.
"""

import json
import os

from openai import OpenAI

from ai.modeling.abuse.infer_abuse_v3_adapter import (
    predict_major_types,
)
from ai.modeling.abuse.second_stage_llm import (
    analyze_subtypes,
)
from ai.modeling.abuse.audio_to_counseling_note import (
    DEFAULT_MODEL as DEFAULT_NOTE_MODEL,
    generate_counseling_records,
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
# 2. 전체 세션 파이프라인 (1차 + 2차 + 상담 요약/상담일지)
# ============================================================

def analyze_session(
    text: str,
    input_mode: str = "qa",
    client: OpenAI = None,
    note_model: str = DEFAULT_NOTE_MODEL,
) -> dict:
    """
    한 세션 텍스트에 대해
    1차 대분류 판정 → 2차 세부유형 분석 → 상담 요약·상담일지 생성까지
    한 번에 수행한다.

    상담 요약/상담일지는 학대 탐지 여부와 무관하게 항상 생성한다.

    input_mode="child_only"인 경우 generate_counseling_records도
    아동 발화만 보고 상담일지를 작성하게 된다. 상담사 질문이 빠져 있으므로
    "상담 일지"보다는 "아동 진술 기반 기록"에 가까운 결과가 나온다는 점에 유의한다.
    """

    # analyze_abuse(1차+2차 판정)와 generate_counseling_records(요약/일지)는
    # 서로 결과를 참조하지 않는 독립 호출이라 순차 실행해도 결과는 같다.
    # FastAPI로 옮길 때는 asyncio.gather 등으로 병렬화할 수 있다.
    abuse_result = analyze_abuse(
        text=text,
        input_mode=input_mode,
    )

    if client is None:
        api_key = os.environ.get(
            "OPENAI_API_KEY"
        )

        if not api_key:
            raise RuntimeError(
                "환경변수 OPENAI_API_KEY가 설정되어 있지 않습니다."
            )

        client = OpenAI(
            api_key=api_key
        )

    counseling_records = generate_counseling_records(
        client=client,
        transcript=text,
        model=note_model,
    )

    return {
        **abuse_result,
        "counseling_summary": counseling_records[
            "counseling_summary"
        ],
        "counseling_note": counseling_records[
            "counseling_note"
        ],
        "counseling_record_model": note_model,
    }


# ============================================================
# 3. 데모
# ============================================================

if __name__ == "__main__":

    text = """
상담사: 아빠가 어떻게 했어?
아동: 아빠가 막대기로 제 팔을 여러 번 때렸어요.
상담사: 또 다른 일도 있었어?
아동: 저번에는 벨트로 허벅지를 때렸어요.
"""

    input_mode = "qa"

    result = analyze_session(
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
