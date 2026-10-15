"""
AI-Hub의 학대여부 상담사 질문(Q)과 아동 답변(A)을 2차 모델용 Q+A 문맥으로 구성한다.
녹음이 있는 서비스 환경을 가정하여 상담사 질문과 아동 답변의 역할을 명시적으로 보존한다.
"""

# ============================================================
# 1. Import
# ============================================================

import ast
from pathlib import Path
from typing import List

import pandas as pd
from tqdm import tqdm


# ============================================================
# 2. 경로
# ============================================================

BASE_DIR = Path("/data/I-SPOT")

DATASET_DIR = (
    BASE_DIR
    / "ai"
    / "modeling"
    / "abuse"
    / "datasets"
)

TRAIN_INPUT = DATASET_DIR / "subtype_base_train_v1.csv"
VALID_INPUT = DATASET_DIR / "subtype_base_valid_v1.csv"

TRAIN_OUTPUT = DATASET_DIR / "subtype_qa_train_v1.csv"
VALID_OUTPUT = DATASET_DIR / "subtype_qa_valid_v1.csv"


# ============================================================
# 3. 대분류 설정
# ============================================================

MAJOR_CONFIG = {
    "신체학대": {
        "major_column": "label_physical",
        "question_column": "physical_questions",
        "answer_column": "physical_answers",
    },
    "정서학대": {
        "major_column": "label_emotional",
        "question_column": "emotional_questions",
        "answer_column": "emotional_answers",
    },
    "성학대": {
        "major_column": "label_sexual",
        "question_column": "sexual_questions",
        "answer_column": "sexual_answers",
    },
    "방임": {
        "major_column": "label_neglect",
        "question_column": "neglect_questions",
        "answer_column": "neglect_answers",
    },
}


# ============================================================
# 4. CSV 문자열 리스트 복원
# ============================================================

def parse_list(value) -> List[str]:
    """
    CSV에 문자열 형태로 저장된 질문/답변 리스트를
    Python List[str] 형태로 복원한다.
    """

    if pd.isna(value):
        return []

    if isinstance(value, list):
        return [
            str(item).strip()
            for item in value
            if str(item).strip()
        ]

    try:
        parsed = ast.literal_eval(str(value))

        if isinstance(parsed, list):
            return [
                str(item).strip()
                for item in parsed
                if str(item).strip()
            ]

    except (ValueError, SyntaxError):
        pass

    text = str(value).strip()

    return [text] if text else []


# ============================================================
# 5. Q+A 문맥 생성
# ============================================================

def build_qa_text(
    questions: List[str],
    answers: List[str],
) -> str:
    """
    상담사 질문과 아동 답변의 순서를 유지하여
    2차 모델용 대화 문맥을 생성한다.

    질문/답변 개수가 다를 경우에도 존재하는 내용은
    삭제하지 않고 최대한 보존한다.
    """

    conversations = []

    max_length = max(
        len(questions),
        len(answers),
    )

    for index in range(max_length):

        if index < len(questions):

            question = questions[index].strip()

            if question:
                conversations.append(
                    f"[COUNSELOR] {question}"
                )

        if index < len(answers):

            answer = answers[index].strip()

            if answer:
                conversations.append(
                    f"[CHILD] {answer}"
                )

    return "\n".join(conversations)


# ============================================================
# 6. 한 사례 처리
# ============================================================

def process_row(
    row: pd.Series,
    split: str,
) -> List[dict]:
    """
    하나의 AI-Hub 사례에서 4대 유형별 Q+A 문맥을 생성한다.

    한 사례가 여러 대분류에 해당할 수 있으므로
    대분류별로 한 행씩 생성한다.
    """

    output_rows = []

    for major_name, config in MAJOR_CONFIG.items():

        questions = parse_list(
            row.get(
                config["question_column"],
                "",
            )
        )

        answers = parse_list(
            row.get(
                config["answer_column"],
                "",
            )
        )

        qa_text = build_qa_text(
            questions,
            answers,
        )

        # Q+A 자체가 없는 경우 제외
        if not qa_text.strip():
            continue

        output_rows.append(
            {
                "case_id": row.get(
                    "case_id",
                    "",
                ),

                "split": split,

                # 어느 4대 유형의 상담 문항인지
                "major_section": major_name,

                # 기존 AI-Hub 대분류 GT
                "major_positive": int(
                    row.get(
                        config["major_column"],
                        0,
                    )
                ),

                # 원본 질문/답변 보존
                "questions": questions,
                "answers": answers,

                # 실제 2차 모델 후보 입력
                "qa_text": qa_text,

                "source_file": row.get(
                    "source_file",
                    "",
                ),
            }
        )

    return output_rows


# ============================================================
# 7. 전체 데이터 처리
# ============================================================

def process_dataset(
    input_path: Path,
    output_path: Path,
    split: str,
):
    """
    AI-Hub 기초 데이터 전체를 2차 Q+A 형식으로 변환한다.
    """

    print()
    print("=" * 70)
    print(f"{split.upper()} 2차 Q+A 데이터 생성")
    print(f"입력: {input_path}")
    print("=" * 70)

    dataframe = pd.read_csv(
        input_path
    )

    output_rows = []

    for _, row in tqdm(
        dataframe.iterrows(),
        total=len(dataframe),
        desc=f"{split} Q+A 생성",
    ):

        output_rows.extend(
            process_row(
                row,
                split,
            )
        )

    result = pd.DataFrame(
        output_rows
    )

    # ========================================================
    # 저장
    # ========================================================

    result.to_csv(
        output_path,
        index=False,
        encoding="utf-8-sig",
    )

    # ========================================================
    # 통계
    # ========================================================

    print()
    print(f"원본 사례 수 : {len(dataframe)}")
    print(f"Q+A 행 수    : {len(result)}")

    print()
    print("[대분류별 Q+A 행 수]")

    for major_name in MAJOR_CONFIG:

        subset = result[
            result["major_section"]
            == major_name
        ]

        positive_count = int(
            subset["major_positive"].sum()
        )

        print(
            f"{major_name:10s}: "
            f"{len(subset):4d}개 "
            f"(positive={positive_count})"
        )

    print()
    print("[Q+A 샘플]")

    for major_name in MAJOR_CONFIG:

        subset = result[
            result["major_section"]
            == major_name
        ]

        if len(subset) == 0:
            continue

        sample = subset.iloc[0]

        print()
        print(f"--- {major_name} ---")
        print(
            str(sample["qa_text"])[:1000]
        )

    print()
    print(f"저장 완료: {output_path}")


# ============================================================
# 8. Main
# ============================================================

def main():

    process_dataset(
        TRAIN_INPUT,
        TRAIN_OUTPUT,
        "train",
    )

    process_dataset(
        VALID_INPUT,
        VALID_OUTPUT,
        "valid",
    )


if __name__ == "__main__":
    main()