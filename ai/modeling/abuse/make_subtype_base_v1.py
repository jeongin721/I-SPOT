"""
AI-Hub 아동·청소년 상담 JSON에서 2차 세부유형 분류용 기초 데이터를 생성한다.
기존 4대 학대유형 라벨과 아동 발화/Q&A를 보존하되, 19개 세부유형 라벨은 아직 임의로 생성하지 않는다.
"""

# ============================================================
# 1. Import
# ============================================================

import ast
import json
from pathlib import Path
from typing import Dict, List

import pandas as pd
from tqdm import tqdm


# ============================================================
# 2. 경로 설정
# ============================================================

BASE_DIR = Path("/data/I-SPOT")

TRAIN_JSON_DIR = (
    BASE_DIR
    / "data"
    / "abuse"
    / "train"
    / "TL_out_data"
)

VALID_JSON_DIR = (
    BASE_DIR
    / "data"
    / "abuse"
    / "valid"
    / "VL_out_data"
)

OUTPUT_DIR = (
    BASE_DIR
    / "ai"
    / "modeling"
    / "abuse"
    / "datasets"
)

TRAIN_OUTPUT = OUTPUT_DIR / "subtype_base_train_v1.csv"
VALID_OUTPUT = OUTPUT_DIR / "subtype_base_valid_v1.csv"


# ============================================================
# 3. 4대 학대유형
# ============================================================

MAJOR_LABELS = [
    "신체학대",
    "정서학대",
    "성학대",
    "방임",
]


# ============================================================
# 4. 안전한 숫자 변환
# ============================================================

def to_number(value) -> float:
    """
    AI-Hub JSON의 점수 값을 안전하게 숫자로 변환한다.
    변환할 수 없는 값은 0으로 처리한다.
    """

    if value is None:
        return 0.0

    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


# ============================================================
# 5. audio에서 Q/A 추출
# ============================================================

def extract_qa(audio_list: List[Dict]):
    """
    audio 배열에서 질문(Q)과 아동 답변(A)을 각각 추출한다.
    원래 순서를 유지한다.
    """

    questions = []
    answers = []

    if not isinstance(audio_list, list):
        return questions, answers

    for audio in audio_list:

        if not isinstance(audio, dict):
            continue

        speaker_type = str(
            audio.get("type", "")
        ).strip().upper()

        text = str(
            audio.get("text", "")
        ).strip()

        if not text:
            continue

        if speaker_type == "Q":
            questions.append(text)

        elif speaker_type == "A":
            answers.append(text)

    return questions, answers


# ============================================================
# 6. 학대여부 항목 추출
# ============================================================

def extract_abuse_section(data: Dict):
    """
    AI-Hub JSON에서 '학대여부' 영역을 찾아
    4대 유형별 Q/A와 기존 라벨을 추출한다.

    주의:
    점수는 모델 입력으로 사용하는 것이 아니라
    기존 AI-Hub의 대분류 정답 라벨 확인에만 사용한다.
    """

    result = {
        label: {
            "questions": [],
            "answers": [],
            "score": 0.0,
        }
        for label in MAJOR_LABELS
    }

    sections = data.get("list", [])

    if not isinstance(sections, list):
        return result

    for section in sections:

        if not isinstance(section, dict):
            continue

        if str(section.get("문항", "")).strip() != "학대여부":
            continue

        items = section.get("list", [])

        if not isinstance(items, list):
            continue

        for item in items:

            if not isinstance(item, dict):
                continue

            subtype = str(
                item.get("항목", "")
            ).strip()

            if subtype not in MAJOR_LABELS:
                continue

            questions, answers = extract_qa(
                item.get("audio", [])
            )

            result[subtype]["questions"].extend(
                questions
            )

            result[subtype]["answers"].extend(
                answers
            )

            result[subtype]["score"] = max(
                result[subtype]["score"],
                to_number(item.get("점수", 0)),
            )

    return result


# ============================================================
# 7. 전체 A 발화 추출
# ============================================================

def collect_all_child_answers(obj) -> List[str]:
    """
    JSON 전체를 순회하면서 type=A인 아동 발화를 모두 추출한다.

    1차 모델에서 사용했던 A-only 입력과 비교하거나
    세부유형 라벨링 시 추가 맥락을 확인하기 위해 보존한다.
    """

    answers = []

    if isinstance(obj, dict):

        if str(obj.get("type", "")).strip().upper() == "A":

            text = str(
                obj.get("text", "")
            ).strip()

            if text:
                answers.append(text)

        for value in obj.values():
            answers.extend(
                collect_all_child_answers(value)
            )

    elif isinstance(obj, list):

        for item in obj:
            answers.extend(
                collect_all_child_answers(item)
            )

    return answers


# ============================================================
# 8. JSON 한 건 처리
# ============================================================

def process_json(json_path: Path, split: str):
    """
    JSON 한 건을 2차 데이터 구축용 기초 행으로 변환한다.
    """

    try:
        with json_path.open(
            "r",
            encoding="utf-8",
        ) as file:
            data = json.load(file)

    except Exception as error:
        print(
            f"\n[읽기 실패] {json_path.name}: {error}"
        )
        return None

    info = data.get("info", {})

    abuse = extract_abuse_section(data)

    all_answers = collect_all_child_answers(data)

    # --------------------------------------------------------
    # 기존 AI-Hub 4대 유형 Multi-label
    # --------------------------------------------------------

    major_targets = {
        label: int(abuse[label]["score"] > 0)
        for label in MAJOR_LABELS
    }

    # --------------------------------------------------------
    # 학대여부 문항에서 나온 아동 답변
    # --------------------------------------------------------

    abuse_answers = []

    for label in MAJOR_LABELS:
        abuse_answers.extend(
            abuse[label]["answers"]
        )

    # --------------------------------------------------------
    # CSV 한 행
    # --------------------------------------------------------

    return {
        "case_id": str(
            info.get("ID", json_path.stem)
        ),

        "split": split,

        # 전체 A-only 발화
        "all_child_text": " ".join(all_answers),

        # 학대여부 문항의 A 발화만
        "abuse_child_text": " ".join(abuse_answers),

        # 유형별 질문/답변
        "physical_questions": json.dumps(
            abuse["신체학대"]["questions"],
            ensure_ascii=False,
        ),
        "physical_answers": json.dumps(
            abuse["신체학대"]["answers"],
            ensure_ascii=False,
        ),

        "emotional_questions": json.dumps(
            abuse["정서학대"]["questions"],
            ensure_ascii=False,
        ),
        "emotional_answers": json.dumps(
            abuse["정서학대"]["answers"],
            ensure_ascii=False,
        ),

        "sexual_questions": json.dumps(
            abuse["성학대"]["questions"],
            ensure_ascii=False,
        ),
        "sexual_answers": json.dumps(
            abuse["성학대"]["answers"],
            ensure_ascii=False,
        ),

        "neglect_questions": json.dumps(
            abuse["방임"]["questions"],
            ensure_ascii=False,
        ),
        "neglect_answers": json.dumps(
            abuse["방임"]["answers"],
            ensure_ascii=False,
        ),

        # 기존 4대 유형 라벨
        "label_physical": major_targets["신체학대"],
        "label_emotional": major_targets["정서학대"],
        "label_sexual": major_targets["성학대"],
        "label_neglect": major_targets["방임"],

        # 원본 추적용
        "source_file": json_path.name,
    }


# ============================================================
# 9. Split 처리
# ============================================================

def process_split(
    json_dir: Path,
    output_path: Path,
    split: str,
):
    """
    Train 또는 Validation JSON 전체를 처리한다.
    """

    json_files = sorted(
        json_dir.rglob("*.json")
    )

    print()
    print("=" * 60)
    print(f"{split.upper()} 처리")
    print(f"JSON 경로 : {json_dir}")
    print(f"파일 수   : {len(json_files)}")
    print("=" * 60)

    rows = []

    for json_path in tqdm(
        json_files,
        desc=f"{split} 전처리",
    ):

        row = process_json(
            json_path,
            split,
        )

        if row is not None:
            rows.append(row)

    dataframe = pd.DataFrame(rows)

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    dataframe.to_csv(
        output_path,
        index=False,
        encoding="utf-8-sig",
    )

    # --------------------------------------------------------
    # 결과 확인
    # --------------------------------------------------------

    print()
    print(f"저장 완료 : {output_path}")
    print(f"총 사례   : {len(dataframe)}")

    if len(dataframe) > 0:

        print()
        print("[4대 유형 Positive 수]")

        for column in [
            "label_physical",
            "label_emotional",
            "label_sexual",
            "label_neglect",
        ]:
            print(
                f"{column:20s}: "
                f"{int(dataframe[column].sum())}"
            )

        no_signal = (
            dataframe[
                [
                    "label_physical",
                    "label_emotional",
                    "label_sexual",
                    "label_neglect",
                ]
            ].sum(axis=1)
            == 0
        ).sum()

        print(
            f"{'no_signal':20s}: {int(no_signal)}"
        )


# ============================================================
# 10. Main
# ============================================================

def main():

    process_split(
        TRAIN_JSON_DIR,
        TRAIN_OUTPUT,
        "train",
    )

    process_split(
        VALID_JSON_DIR,
        VALID_OUTPUT,
        "valid",
    )


if __name__ == "__main__":
    main()