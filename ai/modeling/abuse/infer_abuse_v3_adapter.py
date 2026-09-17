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
    BASE_DIR,
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

# note(상담일지) 문체 전용 모델. qa/child_only 모델과 아키텍처는
# 동일하고 학습 데이터만 다르므로 같은 AbuseQAModel 클래스를 재사용한다.
NOTE_MODEL_PATH = (
    BASE_DIR
    / "weight"
    / "roberta_abuse_note_v1_best.pth"
)

_note_engine = AbuseQAModel(
    model_path=NOTE_MODEL_PATH,
)


# ============================================================
# 3. 공통 결과 단순화
# ============================================================

def _simplify_predictions(raw_predictions: dict) -> dict:
    """
    v3 모델의 label별 예측 결과에서 probability는 버리고
    detected 여부만 남긴다. _suppress_denied_labels가 남긴
    filtered_reason이 있으면 그대로 함께 전달한다.
    """

    result = {}

    for label, prediction in raw_predictions.items():

        simplified = {
            "detected": bool(
                prediction.get(
                    "detected",
                    False,
                )
            )
        }

        if prediction.get("filtered_reason"):
            simplified["filtered_reason"] = prediction[
                "filtered_reason"
            ]

        result[label] = simplified

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


# ============================================================
# 6. 명확한 부정 응답 필터
# ============================================================
# 1차 모델이 detected=True로 판정해도, 관련 키워드가 원문에서
# 전부 부정문으로만 등장하면("굶은 적 있어요? / 아니요, 안 굶어요")
# 오탐으로 보고 detected를 False로 내린다.
#
# 근거 문장이 하나라도 부정 없이(=긍정적으로) 등장하면 절대
# 건드리지 않는다 — 실제 탐지를 놓치지 않기 위한 보수적 규칙이다.
#
# qa/child_only 모드처럼 아동 발화를 따로 뽑을 수 있을 때만
# 적용되고, note 모드(3인칭 서술문)는 화자 구분이 없어
# 아직 적용하지 않는다.

_LABEL_KEYWORDS = {
    "신체학대": [
        "때리", "맞았", "맞은", "맞아", "멍",
        "다쳤", "부러지", "흉기", "벨트", "막대기", "조르",
    ],
    "정서학대": [
        "욕하", "협박", "죽이겠", "버리겠",
        "가두", "무시", "소리 지르", "폭언",
    ],
    "성학대": [
        "만지", "성기", "가슴", "성폭행", "성추행", "보여달라",
    ],
    "방임": [
        "굶", "못 먹", "안 챙기", "혼자 두", "방치", "씻지", "병원",
    ],
}

_NEGATION_PATTERN = re.compile(
    r"아니요|아니예요|아니에요|아뇨|없어요|없었어요|없습니다|안\s|않았|못\s"
)


def _split_sentences(
    text: str,
):
    return re.split(
        r"(?<=[.?!])\s+|\n",
        text,
    )


def _suppress_denied_labels(
    child_text: str,
    predictions: dict,
) -> dict:
    """
    child_text 안에서 각 유형의 키워드가 등장하는 문장을 찾아,
    전부 부정문일 때만 해당 유형의 detected를 False로 내린다.
    """

    if not child_text.strip():
        return predictions

    sentences = _split_sentences(
        child_text
    )

    for label, keywords in _LABEL_KEYWORDS.items():
        prediction = predictions.get(
            label
        )

        if not prediction or not prediction.get(
            "detected"
        ):
            continue

        has_affirmative = False
        has_negated_mention = False

        for sentence in sentences:
            if not any(
                keyword in sentence
                for keyword in keywords
            ):
                continue

            if _NEGATION_PATTERN.search(
                sentence
            ):
                has_negated_mention = True
            else:
                has_affirmative = True

        if has_negated_mention and not has_affirmative:
            prediction["detected"] = False

            prediction["filtered_reason"] = (
                "아동이 관련 발화를 명확히 부정함"
            )

    return predictions


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

    input_mode="note": 상담일지(3인칭 서술형) 문체 텍스트를
    note 전용 모델(roberta_abuse_note_v1)로 태깅 없이 그대로 분석한다.
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

        predictions = raw_result["predictions"]

        predictions = _suppress_denied_labels(
            child_text,
            predictions,
        )

    elif input_mode == "child_only":
        raw_result = predict_child_only(
            _engine,
            text,
        )

        predictions = raw_result["predictions"]

        predictions = _suppress_denied_labels(
            text,
            predictions,
        )

    elif input_mode == "note":
        predictions = predict_abuse_v3(
            _note_engine,
            text,
        )

    else:
        raise ValueError(
            "input_mode must be 'qa', 'child_only', or 'note'"
        )

    return _simplify_predictions(
        predictions
    )
