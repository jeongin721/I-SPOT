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


def _build_ordered_qa_text(text: str) -> str:
    """
    "상담사: .../아동: ..." 형식의 대화에서, 화자 표시가 있는 줄만
    걸러내고 원래 줄 순서는 그대로 유지해서 다시 합친다.

    예전 경로(_split_counselor_child_text + build_qa_text)는 화자별로
    전부 따로 모았다가 다시 합쳐서, 질문-답변이 번갈아 나오는 순서를
    깨뜨렸다. 특히 여러 턴이 있는 입력(예: 음성 1,000자 청크)에서
    이 문제가 커서, 명확한 신체학대 진술도 놓치는 경우가 확인됐다
    (질문 뭉치+답변 뭉치로 섞으면 원시 확률이 0.001까지 떨어지는데,
    순서를 그대로 두면 같은 문장이 0.99 이상으로 나온다).

    태그는 학습 데이터의 "[COUNSELOR]"/"[CHILD]"로 바꾸지 않고 원래
    한글 태그("상담사:"/"아동:")를 그대로 둔다 — 대괄호+영단어 태그는
    klue/roberta 토크나이저에서 토큰을 훨씬 많이 잡아먹어서(같은 내용
    기준 510 -> 635토큰), 여러 턴이 있는 긴 입력에서 512토큰 한도를
    넘겨 뒷부분이 잘리는 사고가 실제로 확인됐다. 한글 태그는 훨씬
    짧아서 이 한도 초과를 피할 수 있고, 실측 확률도 더 정확했다.
    """

    lines = []

    for line in text.splitlines():
        match = _SPEAKER_LINE_PATTERN.match(line)

        if not match:
            continue

        speaker, content = match.groups()
        content = content.strip()

        if not content:
            continue

        lines.append(f"{speaker}: {content}")

    return "\n".join(lines)


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
    # 방임은 일부러 뺐다 — 다른 세 유형은 가해 행위를 긍정형 동사로
    # 서술하지만("때렸어요"/"만졌어요"/"욕했어요"), 방임은 그 반대로
    # "안 챙겨줘요"/"못 먹어요"/"병원 안 데려가요"처럼 보호자가 "하지
    # 않은 행동"을 서술하는 게 정상적인 긍정 진술이다. 그래서 방임
    # 키워드 자체("못 먹"/"안 챙기")가 이미 부정형을 포함하고, "병원"
    # 같은 키워드도 "병원 안 데려가요"처럼 "안\s"을 동반하는 문장에서
    # 흔히 등장한다. valid_qa_typeblock_v1.csv 1,440건 재검증 결과
    # 방임 재현율이 61.1%(FN 21건)까지 떨어졌는데, 그중 13건은 모델이
    # 0.999대 확률로 정확히 잡아낸 걸 이 필터가 "부정됨"으로 오판해
    # 지운 것이었다(2026-10-01 확인). 방임을 필터 대상에서 빼면 그
    # 13건은 복구되고, 필터가 유일하게 도움이 됐던 1건(모델이 실제로
    # 틀렸던 케이스)만 다시 오탐으로 돌아온다 — 13:1로 압도적으로
    # 유리해 방임은 이 필터를 적용하지 않기로 했다.
}

_NEGATION_PATTERN = re.compile(
    r"아니요|아니예요|아니에요|아뇨|없어요|없었어요|없습니다|안\s|않았|못\s"
)


def _split_sentences(
    text: str,
):
    # 쉼표도 절 경계로 취급한다 — "아니요, 며칠 굶은 적도 있어요"처럼
    # 문장 앞의 감탄사성 부정어가 뒤따르는 긍정 진술까지
    # 통째로 부정문으로 오인하는 것을 막기 위함이다.
    return re.split(
        r"(?<=[.?!])\s+|\n|,\s*",
        text,
    )


# 표준 문진(AI-Hub 선별 질문지)은 "~한 적 있어요?"처럼 상담사 질문 자체에
# 유형 키워드가 들어 있고, 아동은 그 키워드를 되풀이하지 않고 "아니요"로만
# 짧게 답하는 경우가 있다(예: 성학대 질문에 "아니요. 본 적 없어요."만 답함).
# 이런 일반 부정 응답을 상담사 질문의 키워드와 엮어서 눌러주는 방식을
# 한때 시도했으나, 여러 턴이 섞인 긴 입력(음성 청크 등)에서 전혀 다른
# 질문에 대한 부정 응답까지 같이 걸려서 실제 긍정 진술을 지우는 사고가
# 발생해 되돌렸다(_suppress_denied_labels 주석 참고). 이 문제는 아직
# 안전하게 해결하지 못한 상태로 남아 있다.


def _suppress_denied_labels(
    child_text: str,
    predictions: dict,
    counselor_text: str = "",
) -> dict:
    """
    child_text 안에서 각 유형의 키워드가 등장하는 문장을 찾아,
    전부 부정문일 때만 해당 유형의 detected를 False로 내린다.

    "상담사 질문에 키워드가 있고 아동이 일반 부정('아니요')으로만
    답했으면 눌러준다"는 조건을 한때 추가했다가 되돌렸다 — 실제
    음성(0280.mp3)에서 아동이 "아빠가 저를 때렸어요"라고 명확히
    긍정했는데도, 키워드 "때리"가 활용형 "때렸"과 문자열이 달라
    매칭에 실패하고, 같은 청크 뒤쪽 전혀 다른 질문(사진·영상 유포
    등)에 대한 "아니요"를 근거로 삼아 신체학대를 잘못 지운 사고가
    확인됐다. 여러 턴이 섞인 긴 입력에서는 "어딘가에 있는 일반
    부정"이 그 유형과 무관할 위험이 너무 커서, 같은 문장 안에서
    키워드+부정이 함께 있을 때만 지우는 원래 방식으로 되돌린다.
    counselor_text 인자는 호출부 호환을 위해 남겨두되 쓰지 않는다.
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
    줄 순서를 그대로 유지한 채 태그만 바꿔서(Q+A 모델 학습 형식과
    동일하게) 분석한다.

    input_mode="child_only": text 전체를 아동 발화로 보고
    predict_child_only 경로(CHILD-only 모델)로 분석한다.

    input_mode="note": 상담일지(3인칭 서술형) 문체 텍스트를
    note 전용 모델(roberta_abuse_note_v1)로 태깅 없이 그대로 분석한다.
    """

    if input_mode == "qa":
        # 부정 응답 필터(_suppress_denied_labels)에는 화자별로 분리한
        # 텍스트가 필요하므로 그대로 구한다. 다만 모델에 실제로 넣는
        # 입력은 이걸로 만들지 않고, 아래 _build_ordered_qa_text로
        # 원래 대화 순서를 그대로 유지한 텍스트를 쓴다.
        counselor_text, child_text = (
            _split_counselor_child_text(text)
        )

        ordered_text = _build_ordered_qa_text(text)

        predictions = predict_abuse_v3(
            _engine,
            ordered_text,
        )

        predictions = _suppress_denied_labels(
            child_text,
            predictions,
            counselor_text=counselor_text,
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
