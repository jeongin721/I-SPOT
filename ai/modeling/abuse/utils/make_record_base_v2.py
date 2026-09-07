"""
AI-Hub 상담 JSON의 '학대여부' Q+A와 원본 4개 학대 유형 라벨을 추출한다.
판단/점수 필드는 제외하고 Record v2 재구성에 사용할 안전한 기반 CSV를 생성한다.
"""

import json
from pathlib import Path

import pandas as pd
from tqdm import tqdm


# ============================================================
# 1. 기본 설정
# ============================================================

LABEL_ORDER = [
    "신체학대",
    "정서학대",
    "성학대",
    "방임",
]


# ============================================================
# 2. 프로젝트 경로
# ============================================================

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

DATASET_DIR = (
    PROJECT_ROOT
    / "ai"
    / "modeling"
    / "abuse"
    / "datasets"
)

DATASET_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

TRAIN_OUTPUT = (
    DATASET_DIR
    / "train_record_base_v2.csv"
)

VALID_OUTPUT = (
    DATASET_DIR
    / "valid_record_base_v2.csv"
)


# ============================================================
# 3. JSON 로드
# ============================================================

def load_json(path: Path) -> dict:
    """UTF-8 AI-Hub JSON 파일을 읽는다."""

    with open(
        path,
        "r",
        encoding="utf-8",
    ) as file:
        return json.load(file)


# ============================================================
# 4. 학대여부 문항 찾기
# ============================================================

def find_abuse_section(data: dict):
    """최상위 list에서 '학대여부' 문항을 찾는다."""

    for item in data.get(
        "list",
        [],
    ):
        if item.get("문항") == "학대여부":
            return item

    return None


# ============================================================
# 5. 4개 유형 라벨 추출
# ============================================================

def extract_labels(
    abuse_section: dict,
) -> list:
    """
    '학대여부' 세부항목의 점수만 이용해 4차원 정답 라벨을 생성한다.

    점수 > 0 : 1
    점수 = 0 : 0

    주의:
    점수는 정답 생성에만 사용하며 모델 입력 text에는 절대 포함하지 않는다.
    """

    score_map = {}

    for item in abuse_section.get(
        "list",
        [],
    ):

        abuse_type = item.get(
            "항목"
        )

        score = item.get(
            "점수",
            0,
        )

        score_map[
            abuse_type
        ] = score

    return [
        1 if score_map.get(
            label_name,
            0,
        ) > 0 else 0
        for label_name in LABEL_ORDER
    ]


# ============================================================
# 6. 안전한 Q+A 추출
# ============================================================

def extract_qa_pairs(
    abuse_section: dict,
) -> list:
    """
    '학대여부'의 audio Q/A만 추출한다.

    임상가코멘트, 문제요인, 위기단계, 학대유형,
    점수 등 판단·라벨 누출 가능 필드는 사용하지 않는다.
    """

    qa_pairs = []

    for abuse_item in abuse_section.get(
        "list",
        [],
    ):

        category = abuse_item.get(
            "항목",
            "",
        )

        audio_items = abuse_item.get(
            "audio",
            [],
        )

        current_question = None

        for audio in audio_items:

            speaker_type = audio.get(
                "type"
            )

            text = str(
                audio.get(
                    "text",
                    "",
                )
            ).strip()

            if not text:
                continue

            # ------------------------------------------------
            # 상담사 질문
            # ------------------------------------------------

            if speaker_type == "Q":

                current_question = text

            # ------------------------------------------------
            # 아동 답변
            # ------------------------------------------------

            elif speaker_type == "A":

                qa_pairs.append(
                    {
                        "category": category,
                        "question": (
                            current_question
                            if current_question
                            else ""
                        ),
                        "answer": text,
                    }
                )

                current_question = None

    return qa_pairs


# ============================================================
# 7. Q+A를 중간 텍스트로 직렬화
# ============================================================

def build_qa_text(
    qa_pairs: list,
) -> str:
    """
    이후 상담기록 재작성 단계가 문맥을 이해할 수 있도록
    질문과 답변을 명시적으로 보존한다.
    """

    parts = []

    for pair in qa_pairs:

        category = pair[
            "category"
        ]

        question = pair[
            "question"
        ]

        answer = pair[
            "answer"
        ]

        part = (
            f"[{category}] "
            f"Q: {question} "
            f"A: {answer}"
        )

        parts.append(
            part
        )

    return " ".join(
        parts
    )


# ============================================================
# 8. 하나의 JSON 처리
# ============================================================

def process_json(
    path: Path,
):
    """한 사례에서 Q+A와 원본 라벨을 추출한다."""

    data = load_json(
        path
    )

    abuse_section = (
        find_abuse_section(
            data
        )
    )

    if abuse_section is None:
        return None

    labels = extract_labels(
        abuse_section
    )

    qa_pairs = extract_qa_pairs(
        abuse_section
    )

    if not qa_pairs:
        return None

    qa_text = build_qa_text(
        qa_pairs
    )

    return {
        "source_file": path.name,
        "qa_text": qa_text,
        "label": str(labels),
        "qa_count": len(
            qa_pairs
        ),
    }


# ============================================================
# 9. 폴더 전체 처리
# ============================================================

def build_dataset(
    json_dir: Path,
) -> pd.DataFrame:
    """JSON 폴더 전체를 Record v2 기반 데이터로 변환한다."""

    paths = sorted(
        json_dir.glob(
            "*.json"
        )
    )

    rows = []

    skipped = 0

    for path in tqdm(
        paths,
        desc=f"Processing {json_dir.name}",
    ):

        try:

            row = process_json(
                path
            )

            if row is None:

                skipped += 1
                continue

            rows.append(
                row
            )

        except Exception as error:

            skipped += 1

            print(
                f"\n[SKIP] {path.name}: {error}"
            )

    dataframe = pd.DataFrame(
        rows
    )

    print()
    print(
        f"JSON      : {len(paths)}"
    )
    print(
        f"생성      : {len(dataframe)}"
    )
    print(
        f"SKIP      : {skipped}"
    )

    return dataframe


# ============================================================
# 10. 데이터 검증
# ============================================================

def validate_dataframe(
    dataframe: pd.DataFrame,
    name: str,
) -> None:
    """행, 결측치, 중복 source_file, 라벨 형식을 확인한다."""

    print()
    print("=" * 70)
    print(name)
    print("=" * 70)

    print(
        f"전체 사례 : {len(dataframe)}"
    )

    print(
        "qa_text 결측 :",
        dataframe[
            "qa_text"
        ].isna().sum(),
    )

    print(
        "label 결측 :",
        dataframe[
            "label"
        ].isna().sum(),
    )

    print(
        "source_file 중복 :",
        dataframe[
            "source_file"
        ].duplicated().sum(),
    )

    print()
    print("[Label Distribution]")

    print(
        dataframe[
            "label"
        ].value_counts()
    )


# ============================================================
# 11. 실행
# ============================================================

def main() -> None:
    """공식 Train/Validation을 각각 별도의 기반 CSV로 생성한다."""

    print("=" * 70)
    print("AI-Hub Record v2 Base Dataset Generator")
    print("=" * 70)

    print()
    print("[TRAIN]")

    train_df = build_dataset(
        TRAIN_JSON_DIR
    )

    validate_dataframe(
        train_df,
        "TRAIN",
    )

    print()
    print("[VALIDATION]")

    valid_df = build_dataset(
        VALID_JSON_DIR
    )

    validate_dataframe(
        valid_df,
        "VALIDATION",
    )

    # --------------------------------------------------------
    # 공식 Train / Validation 분리를 그대로 유지한다.
    # --------------------------------------------------------

    train_df.to_csv(
        TRAIN_OUTPUT,
        index=False,
        encoding="utf-8-sig",
    )

    valid_df.to_csv(
        VALID_OUTPUT,
        index=False,
        encoding="utf-8-sig",
    )

    print()
    print("=" * 70)
    print("생성 완료")
    print("=" * 70)

    print(
        f"Train : {TRAIN_OUTPUT}"
    )

    print(
        f"Valid : {VALID_OUTPUT}"
    )


if __name__ == "__main__":
    main()