"""
I-SPOT A-only 멀티라벨 학대유형 분류 데이터 전처리 예시.

AI-Hub 상담 라벨링 JSON에서 아동 답변(A)만 추출하여 입력 텍스트를 만들고,
'학대여부' 상세 항목을 이용해 [신체학대, 정서학대, 성학대, 방임] 멀티라벨을 생성한다.
"""

from pathlib import Path
import json

import pandas as pd


# ============================================================
# 1. 기본 설정
# ============================================================

# 라벨 순서 고정
LABEL_NAMES = [
    "신체학대",
    "정서학대",
    "성학대",
    "방임",
]

# 프로젝트 기준 경로
PROJECT_ROOT = Path(__file__).resolve().parents[4]

TRAIN_JSON_DIR = (
    PROJECT_ROOT
    / "data"
    / "abuse"
    / "train"
    / "TL_out_data"
)

VALID_JSON_DIR = (
    PROJECT_ROOT
    / "data"
    / "abuse"
    / "valid"
    / "VL_out_data"
)

OUTPUT_DIR = (
    PROJECT_ROOT
    / "ai"
    / "modeling"
    / "abuse"
    / "datasets"
)


# ============================================================
# 2. 전처리 방식 요약
# ============================================================

"""
[A-only 전처리 원칙]

1. 입력 데이터
   - AI-Hub 아동·청소년 상담 라벨링 JSON 사용
   - Training: TL_out_data
   - Validation: VL_out_data
   - 음성 wav 자체는 사용하지 않음
   - JSON 내부에 포함된 상담 발화 text 사용

2. 모델 입력
   - JSON 내부 audio 배열에서 type == "A"인 아동 답변만 추출
   - 상담사 질문 Q는 제외
   - 여러 아동 답변을 공백으로 연결하여 하나의 audio_text 생성

예:
    Q: 아픈 곳 있어요?
    A: 머리를 많이 맞았는데 계속 아파요.
    Q: 누구에게 맞았어요?
    A: 아빠한테요.

최종 입력:
    "머리를 많이 맞았는데 계속 아파요. 아빠한테요."

3. 정답 라벨
   - 상위 info["학대의심"] 대표 라벨은 사용하지 않음
   - JSON 내부 문항 == "학대여부"의 상세 4개 항목 사용

라벨 순서:
    [신체학대, 정서학대, 성학대, 방임]

각 항목:
    점수 > 0  → 1
    점수 == 0 → 0

예:
    신체학대 > 0
    정서학대 > 0
    성학대 = 0
    방임 = 0

→ [1, 1, 0, 0]

4. 해당 없음
   - 별도의 '정상' 클래스를 만들지 않음
   - 4개 라벨이 모두 0이면 해당 없음

→ [0, 0, 0, 0]

5. 데이터 누수 방지
   아래 정보는 모델 입력에 사용하지 않음.

   - info["학대의심"]
   - 점수 자체
   - 위기단계
   - 문항합계
   - 임상가코멘트
   - 문제요인
   - 기타 학대 판단/진단성 메타데이터

이유:
    임상가코멘트 등에
    "학대 가능성이 있습니다."
    같은 정답성 정보가 포함될 수 있기 때문.
"""


# ============================================================
# 3. JSON 내부 모든 아동 답변(A) 추출
# ============================================================

def extract_child_answers(node):
    """
    JSON 전체를 순회하면서 audio 내부의 type == 'A' 발화만 추출한다.

    반환:
        str
        예) "아빠한테 맞았어요. 팔이 계속 아파요."
    """

    answers = []

    def walk(obj):
        if isinstance(obj, dict):

            # audio 배열이 있는 경우
            if "audio" in obj and isinstance(obj["audio"], list):

                for utterance in obj["audio"]:

                    if not isinstance(utterance, dict):
                        continue

                    if utterance.get("type") != "A":
                        continue

                    text = utterance.get("text", "")

                    if isinstance(text, str):
                        text = " ".join(text.split())

                        if text:
                            answers.append(text)

            # 하위 구조 계속 탐색
            for value in obj.values():
                walk(value)

        elif isinstance(obj, list):

            for item in obj:
                walk(item)

    walk(node)

    return " ".join(answers)


# ============================================================
# 4. '학대여부' 문항 찾기
# ============================================================

def find_abuse_section(node):
    """
    JSON 전체에서 문항 == '학대여부'인 객체를 찾는다.
    """

    if isinstance(node, dict):

        if node.get("문항") == "학대여부":
            return node

        for value in node.values():

            result = find_abuse_section(value)

            if result is not None:
                return result

    elif isinstance(node, list):

        for item in node:

            result = find_abuse_section(item)

            if result is not None:
                return result

    return None


# ============================================================
# 5. 상세 점수를 4-label Multi-label로 변환
# ============================================================

def extract_multilabel(data):
    """
    '학대여부' 상세 항목에서 4개 멀티라벨을 생성한다.

    반환 순서:
        [신체학대, 정서학대, 성학대, 방임]

    기준:
        점수 > 0  → 1
        점수 <= 0 → 0
    """

    section = find_abuse_section(data)

    if section is None:
        return [0, 0, 0, 0]

    labels = {
        "신체학대": 0,
        "정서학대": 0,
        "성학대": 0,
        "방임": 0,
    }

    items = section.get("list", [])

    for item in items:

        if not isinstance(item, dict):
            continue

        abuse_type = item.get("항목")

        if abuse_type not in labels:
            continue

        score = item.get("점수", 0)

        try:
            score = float(score)
        except (TypeError, ValueError):
            score = 0

        labels[abuse_type] = 1 if score > 0 else 0

    return [
        labels["신체학대"],
        labels["정서학대"],
        labels["성학대"],
        labels["방임"],
    ]


# ============================================================
# 6. JSON 1개 → 학습 row 1개
# ============================================================

def preprocess_json(json_path):
    """
    JSON 하나를 A-only 학습 데이터 한 행으로 변환한다.

    출력 예:
        {
            "audio_text": "아빠한테 맞았어요.",
            "label": "[1, 0, 0, 0]"
        }
    """

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    audio_text = extract_child_answers(data)
    label = extract_multilabel(data)

    return {
        "audio_text": audio_text,

        # CSV 저장 후 기존 encode_multilabel에서 처리할 수 있도록
        # 문자열 형태로 저장
        "label": str(label),

        # 추적용
        "source_file": json_path.name,
    }


# ============================================================
# 7. 폴더 전체 전처리
# ============================================================

def preprocess_directory(json_dir):
    """
    지정된 폴더의 모든 JSON을 A-only 데이터셋으로 변환한다.
    """

    rows = []

    json_files = sorted(json_dir.rglob("*.json"))

    for json_path in json_files:

        row = preprocess_json(json_path)

        # 텍스트가 완전히 비어 있는 경우 제외
        if not row["audio_text"]:
            continue

        rows.append(row)

    return pd.DataFrame(rows)


# ============================================================
# 8. Train / Validation CSV 생성
# ============================================================

def main():
    """
    기존 공식 Train / Validation split을 그대로 유지해서 CSV를 생성한다.

    랜덤 train_test_split을 새로 하지 않는다.
    """

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    train_df = preprocess_directory(TRAIN_JSON_DIR)
    valid_df = preprocess_directory(VALID_JSON_DIR)

    train_output = OUTPUT_DIR / "train_multilabel.csv"
    valid_output = OUTPUT_DIR / "valid_multilabel.csv"

    train_df.to_csv(
        train_output,
        index=False,
        encoding="utf-8-sig",
    )

    valid_df.to_csv(
        valid_output,
        index=False,
        encoding="utf-8-sig",
    )

    # ========================================================
    # 결과 확인
    # ========================================================

    print("=" * 70)
    print("A-only Multi-label 전처리 완료")
    print("=" * 70)

    print(f"Train JSON 경로 : {TRAIN_JSON_DIR}")
    print(f"Valid JSON 경로 : {VALID_JSON_DIR}")

    print()
    print(f"Train 샘플 수   : {len(train_df)}")
    print(f"Valid 샘플 수   : {len(valid_df)}")

    print()
    print(f"Train CSV       : {train_output}")
    print(f"Valid CSV       : {valid_output}")

    print("\n[Train Label Distribution]")
    print(train_df["label"].value_counts())

    print("\n[Valid Label Distribution]")
    print(valid_df["label"].value_counts())


# ============================================================
# 9. 실행
# ============================================================

if __name__ == "__main__":
    main()