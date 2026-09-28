"""
I-SPOT 상담 데이터 공통 전처리 모듈

AI-Hub 아동 상담 JSON을 읽어
I-SPOT의 여러 AI 기능에서 공통으로 사용할 데이터를 추출한다.

[사용 기능]

1. 학대 유형 Multi-label 모델
   - 아동 답변(A) 추출
   - 신체학대 / 정서학대 / 성학대 / 방임 라벨 추출

2. 상담 요약 LLM
   - 상담사 질문(Q) + 아동 답변(A)을 모두 추출
   - 발화 순서를 유지한 Transcript 생성

[중요]

학대유형 모델:
    아동 답변(A) 중심 텍스트 사용

상담요약:
    상담사(Q) + 아동(A) 전체 대화 사용

두 기능이 동일한 원본 JSON 파싱 코드를 공유하도록 만든다.
"""

import re


# ============================================================
# 학대 유형 순서
# ============================================================

LABEL_NAMES = [
    "신체학대",
    "정서학대",
    "성학대",
    "방임",
]


# ============================================================
# 텍스트 정리
# ============================================================

def clean_text(text):
    """
    상담 발화의 불필요한 공백을 제거한다.

    요약 모델에서도 원문을 사용해야 하므로
    의미가 달라질 수 있는 과도한 문자 제거는 하지 않는다.
    """

    if text is None:
        return ""

    text = str(text).strip()

    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    return text


# ============================================================
# JSON 내부의 모든 상담 발화 순회
# ============================================================

def iter_dialogues(json_data):
    """
    JSON 내부에 존재하는 audio 발화를 순서대로 반환한다.

    반환 예:

    {
        "type": "Q",
        "text": "요즘 가장 걱정되는 게 있어?"
    }

    {
        "type": "A",
        "text": "아빠가 화내는 게 무서워요."
    }
    """

    for section in json_data.get("list", []):

        for item in section.get("list", []):

            for audio in item.get("audio", []):

                speaker_type = audio.get("type")
                text = clean_text(
                    audio.get("text", "")
                )

                if speaker_type not in {
                    "Q",
                    "A",
                }:
                    continue

                if not text:
                    continue

                if text == "질문":
                    continue

                yield {
                    "type": speaker_type,
                    "text": text,
                    "start": audio.get("start"),
                    "end": audio.get("end"),
                }


# ============================================================
# 학대유형 모델용 텍스트
# ============================================================

def extract_child_answers(json_data):
    """
    학대유형 Multi-label 모델에서 사용할
    아동 답변(A)만 추출한다.

    예:

    아빠가 화내면 무서워요.
    저랑 동생을 계속 때려요.

        ↓

    "아빠가 화내면 무서워요. 저랑 동생을 계속 때려요."
    """

    answers = []

    for dialogue in iter_dialogues(
        json_data
    ):

        if dialogue["type"] != "A":
            continue

        answers.append(
            dialogue["text"]
        )

    return " ".join(answers)


# ============================================================
# 상담요약용 전체 Transcript
# ============================================================

def extract_full_transcript(json_data):
    """
    상담 요약 LLM에서 사용할 전체 상담 대화를 생성한다.

    Q -> COUNSELOR
    A -> CHILD

    예:

    COUNSELOR: 아빠가 화내면 기분이 어때?
    CHILD: 무서워요.
    """

    transcript = []

    for dialogue in iter_dialogues(
        json_data
    ):

        if dialogue["type"] == "Q":
            speaker = "COUNSELOR"

        else:
            speaker = "CHILD"

        transcript.append(
            {
                "speaker": speaker,
                "text": dialogue["text"],
                "start": dialogue["start"],
                "end": dialogue["end"],
            }
        )

    return transcript


# ============================================================
# 학대유형 Multi-label 추출
# ============================================================

def extract_multilabel(json_data):
    """
    JSON의 '학대여부' 문항에서
    4개 학대 유형의 점수를 읽는다.

    출력 순서:

    [
        신체학대,
        정서학대,
        성학대,
        방임
    ]

    점수 > 0:
        1

    점수 == 0:
        0

    예:

    신체학대 = 8
    정서학대 = 5
    성학대 = 0
    방임 = 0

        ↓

    [1, 1, 0, 0]
    """

    labels = {
        "신체학대": 0,
        "정서학대": 0,
        "성학대": 0,
        "방임": 0,
    }

    found_abuse_section = False

    for section in json_data.get(
        "list",
        [],
    ):

        if section.get("문항") != "학대여부":
            continue

        found_abuse_section = True

        for item in section.get(
            "list",
            [],
        ):

            abuse_type = item.get(
                "항목"
            )

            if abuse_type not in labels:
                continue

            score = item.get(
                "점수",
                0,
            )

            try:
                score = float(score)

            except (
                TypeError,
                ValueError,
            ):
                score = 0

            labels[abuse_type] = (
                1 if score > 0 else 0
            )

        break

    # 학대여부 문항 자체가 없는 JSON
    if not found_abuse_section:
        return None

    return [
        labels["신체학대"],
        labels["정서학대"],
        labels["성학대"],
        labels["방임"],
    ]