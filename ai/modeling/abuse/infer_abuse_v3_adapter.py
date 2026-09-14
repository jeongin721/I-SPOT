"""
I-SPOT v3 1차 학대유형 모델을 기존 회기 분석 파이프라인에 연결하는 Adapter다.
v3 내부 확률값은 판정에만 사용하고 외부에는 detected 여부만 반환한다.
"""

# ============================================================
# 1. Import
# ============================================================

import re

from ai.modeling.abuse.infer_abuse_qa_v3 import (
    MODEL_PATH,
    AbuseQAModel,
    predict_abuse as predict_abuse_v3,
    predict_qa,
    predict_child_only,
)


# ============================================================
# 2. v3 모델 로딩
# ============================================================
# 서버 시작 시 한 번만 모델을 메모리에 올리고
# 이후 요청에서는 같은 모델 객체를 재사용한다.

_engine = AbuseQAModel(
    model_path=MODEL_PATH,
)


# ============================================================
# 3. 공통 결과 단순화
# ============================================================

def _simplify_predictions(raw_predictions: dict) -> dict:
    """
    v3 모델의 label별 예측 결과에서 probability는 버리고
    detected 여부만 남긴다.
    """

    result = {}

    for label, prediction in raw_predictions.items():

        result[label] = {
            "detected": bool(
                prediction.get(
                    "detected",
                    False,
                )
            )
        }

    return result


# ============================================================
# 4. 기존 infer_session 호환 함수
# ============================================================

def predict_abuse(text: str) -> dict:
    """
    기존 infer_session.py가 사용하는 predict_abuse(text) 형식에 맞춘다.

    v3 모델 내부에서는 probability를 계산하지만,
    통합 파이프라인에는 detected 값만 전달한다.
    """

    raw_result = predict_abuse_v3(
        _engine,
        text,
    )

    return _simplify_predictions(raw_result)


# ============================================================
# 5. 입력 유형별 1차 모델 경로 통합
# ============================================================
# Q+A(상담사+아동 대화) 텍스트에서 화자별 발화를 분리하기 위한 패턴이다.
# "상담사: ...", "아동: ..." 형식의 줄만 인식하며,
# 그 외의 줄(빈 줄, 화자 표시가 없는 줄)은 무시한다.

_SPEAKER_LINE_PATTERN = re.compile(
    r"^\s*(상담사|아동)\s*[:：]\s*(.*)$"
)


def _split_counselor_child_text(text: str):
    """
    "상담사: ...\n아동: ..." 형식의 대화 텍스트를
    화자별로 분리해 counselor_text, child_text로 합친다.
    """

    counselor_lines = []
    child_lines = []

    for line in text.splitlines():
        match = _SPEAKER_LINE_PATTERN.match(line)

        if not match:
            continue

        speaker, content = match.groups()
        content = content.strip()

        if not content:
            continue

        if speaker == "상담사":
            counselor_lines.append(content)
        else:
            child_lines.append(content)

    return (
        "\n".join(counselor_lines),
        "\n".join(child_lines),
    )


def predict_major_types(
    text: str,
    input_mode: str = "qa",
) -> dict:
    """
    입력 유형에 맞는 1차 RoBERTa 경로로 4대 학대유형을 판정한다.

    input_mode="qa": "상담사: .../아동: ..." 형식의 대화 텍스트를
    화자별로 분리해 predict_qa 경로(Q+A 모델)로 분석한다.

    input_mode="child_only": text 전체를 아동 발화로 보고
    predict_child_only 경로(CHILD-only 모델)로 분석한다.
    """

    if input_mode == "qa":
        counselor_text, child_text = (
            _split_counselor_child_text(text)
        )

        raw_result = predict_qa(
            _engine,
            counselor_text,
            child_text,
        )

    elif input_mode == "child_only":
        raw_result = predict_child_only(
            _engine,
            text,
        )

    else:
        raise ValueError(
            "input_mode must be 'qa' or 'child_only'"
        )

    return _simplify_predictions(
        raw_result["predictions"]
    )
