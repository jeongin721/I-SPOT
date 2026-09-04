"""
I-SPOT 학대 유형 Multi-label 학습 데이터 생성 코드

AI-Hub 아동 상담 JSON 데이터를 읽어
KLUE-RoBERTa Multi-label 학습에 사용할 CSV 파일을 생성한다.

[입력]
- TL_out_data : Training JSON
- VL_out_data : Validation JSON

[공통 전처리]
ai/modeling/common/consultation_preprocessor.py 사용

- extract_child_answers()
    → 학대유형 모델 입력으로 사용할 아동 답변(A) 추출

- extract_multilabel()
    → 학대여부 문항의 점수를 이용하여 4개 Multi-label 생성

[Multi-label 순서]

    [신체학대, 정서학대, 성학대, 방임]

예:
    신체학대 8점
    정서학대 5점
    성학대   0점
    방임     0점

    → [1, 1, 0, 0]

[출력]
- train_multilabel.csv
- valid_multilabel.csv

CSV 컬럼:
- file
- split
- label
- physical_abuse
- emotional_abuse
- sexual_abuse
- neglect
- audio_text

※ 이 파일은 데이터 전처리만 수행한다.
   실제 모델 학습은 train_abuse.py에서 수행한다.
"""

from pathlib import Path
import json

import pandas as pd

from ai.modeling.common.consultation_preprocessor import (
    extract_child_answers,
    extract_multilabel,
)


# ============================================================
# 1. 프로젝트 경로 설정
# ============================================================

# 현재 파일 위치:
# I-SPOT/ai/modeling/abuse/utils/make_csv.py
#
# 프로젝트 최상위:
# I-SPOT/
PROJECT_ROOT = Path(__file__).resolve().parents[4]


# ============================================================
# 2. 원본 JSON 데이터 경로
# ============================================================

# Training / Validation JSON 경로
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


# ============================================================
# 3. CSV 저장 경로
# ============================================================

OUTPUT_DIR = (
    PROJECT_ROOT
    / "ai"
    / "modeling"
    / "abuse"
    / "datasets"
)

# datasets 폴더가 없으면 자동 생성
OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


TRAIN_SAVE_PATH = (
    OUTPUT_DIR
    / "train_multilabel.csv"
)

VALID_SAVE_PATH = (
    OUTPUT_DIR
    / "valid_multilabel.csv"
)


# ============================================================
# 4. JSON 파일 하나 전처리
# ============================================================

def process_json_file(json_path):
    """
    JSON 파일 하나를 읽어서
    학대유형 모델 학습용 데이터 한 행(row)을 생성한다.

    처리 과정:

    JSON
      ↓
    아동 답변(A) 추출
      ↓
    Multi-label 추출
      ↓
    CSV 한 행 생성

    정상 처리:
        dict 반환

    사용할 수 없는 데이터:
        None 반환
    """

    # --------------------------------------------------------
    # JSON 읽기
    # --------------------------------------------------------

    try:
        with open(
            json_path,
            "r",
            encoding="utf-8",
        ) as json_file:

            json_data = json.load(
                json_file
            )

    except (
        json.JSONDecodeError,
        UnicodeDecodeError,
        OSError,
    ) as error:

        print(
            f"[JSON 읽기 실패] "
            f"{json_path.name}: {error}"
        )

        return None


    # --------------------------------------------------------
    # 학대유형 모델 입력 텍스트 추출
    #
    # 상담사 질문(Q)은 제외하고
    # 아동 답변(A)만 가져온다.
    # --------------------------------------------------------

    audio_text = extract_child_answers(
        json_data
    )

    if not audio_text:

        print(
            f"[아동 답변 없음] "
            f"{json_path.name}"
        )

        return None


    # --------------------------------------------------------
    # Multi-label 추출
    #
    # 결과 순서:
    # [신체학대, 정서학대, 성학대, 방임]
    # --------------------------------------------------------

    label = extract_multilabel(
        json_data
    )

    # 학대여부 문항 자체가 없는 데이터
    if label is None:

        print(
            f"[학대여부 문항 없음] "
            f"{json_path.name}"
        )

        return None


    # --------------------------------------------------------
    # 개별 label
    # --------------------------------------------------------

    physical_abuse = label[0]
    emotional_abuse = label[1]
    sexual_abuse = label[2]
    neglect = label[3]


    # --------------------------------------------------------
    # CSV 한 행 생성
    # --------------------------------------------------------

    return {
        "file": json_path.name,

        # CSV에서는 "[1, 1, 0, 0]" 형태로 저장
        #
        # Custom_utils.py에서 학습 시
        # 다시 list 형태로 변환한다.
        "label": str(label),

        "physical_abuse": physical_abuse,
        "emotional_abuse": emotional_abuse,
        "sexual_abuse": sexual_abuse,
        "neglect": neglect,

        "audio_text": audio_text,
    }


# ============================================================
# 5. 폴더 전체 JSON → CSV 변환
# ============================================================

def convert_json_folder(
    json_dir,
    save_path,
    split_name,
):
    """
    지정된 폴더의 모든 JSON 파일을 전처리하여
    하나의 CSV 파일로 저장한다.

    rglob("*.json")을 사용하므로
    JSON이 하위 폴더에 있어도 자동으로 검색한다.
    """

    # --------------------------------------------------------
    # 데이터 폴더 존재 여부 확인
    # --------------------------------------------------------

    if not json_dir.exists():

        raise FileNotFoundError(
            "\n데이터 폴더를 찾을 수 없습니다."
            f"\n경로: {json_dir}"
        )


    # --------------------------------------------------------
    # JSON 파일 검색
    # --------------------------------------------------------

    json_files = sorted(
        json_dir.rglob("*.json")
    )


    print(
        "\n========================================"
    )

    print(
        f"{split_name.upper()} DATA"
    )

    print(
        "========================================"
    )

    print(
        f"JSON 경로: {json_dir}"
    )

    print(
        f"발견한 JSON: {len(json_files)}개"
    )


    if len(json_files) == 0:

        raise ValueError(
            f"JSON 파일이 없습니다: {json_dir}"
        )


    # --------------------------------------------------------
    # JSON 하나씩 처리
    # --------------------------------------------------------

    rows = []

    skipped_count = 0


    for index, json_path in enumerate(
        json_files,
        start=1,
    ):

        row = process_json_file(
            json_path
        )


        # 처리할 수 없는 JSON
        if row is None:

            skipped_count += 1
            continue


        # train / valid 표시
        row["split"] = split_name

        rows.append(
            row
        )


        # 100개 처리할 때마다 진행 상황 출력
        if index % 100 == 0:

            print(
                f"처리 중: "
                f"{index}/{len(json_files)}"
            )


    # ========================================================
    # 6. DataFrame 생성
    # ========================================================

    df = pd.DataFrame(
        rows
    )


    if df.empty:

        raise ValueError(
            f"{split_name}에서 "
            "사용 가능한 데이터가 없습니다."
        )


    # --------------------------------------------------------
    # CSV 컬럼 순서 정리
    # --------------------------------------------------------

    df = df[
        [
            "file",
            "split",
            "label",
            "physical_abuse",
            "emotional_abuse",
            "sexual_abuse",
            "neglect",
            "audio_text",
        ]
    ]


    # ========================================================
    # 7. CSV 저장
    # ========================================================

    df.to_csv(
        save_path,
        index=False,
        encoding="utf-8-sig",
    )


    # ========================================================
    # 8. 전처리 결과 확인
    # ========================================================

    print(
        f"\nCSV 저장 완료:"
        f"\n{save_path}"
    )

    print(
        f"\n정상 변환: {len(df)}개"
    )

    print(
        f"제외 데이터: {skipped_count}개"
    )


    # --------------------------------------------------------
    # 학대 유형별 Positive 데이터 개수
    # --------------------------------------------------------

    print(
        "\n===== 유형별 Positive 개수 ====="
    )

    print(
        "신체학대:",
        int(
            df["physical_abuse"].sum()
        ),
    )

    print(
        "정서학대:",
        int(
            df["emotional_abuse"].sum()
        ),
    )

    print(
        "성학대:",
        int(
            df["sexual_abuse"].sum()
        ),
    )

    print(
        "방임:",
        int(
            df["neglect"].sum()
        ),
    )


    # --------------------------------------------------------
    # Multi-label 조합 분포
    #
    # 예:
    # [0, 0, 0, 0]  100
    # [1, 0, 0, 0]   30
    # [1, 1, 0, 0]   20
    # --------------------------------------------------------

    print(
        "\n===== Multi-label 조합 분포 ====="
    )

    print(
        df["label"].value_counts()
    )


    return df


# ============================================================
# 9. Main
# ============================================================

def main():
    """
    Training / Validation 데이터를 각각 전처리한다.

    TL_out_data
        ↓
    train_multilabel.csv

    VL_out_data
        ↓
    valid_multilabel.csv
    """

    print(
        "========================================"
    )

    print(
        "I-SPOT Abuse Multi-label Preprocessing"
    )

    print(
        "========================================"
    )


    # --------------------------------------------------------
    # Training 데이터 전처리
    # --------------------------------------------------------

    train_df = convert_json_folder(
        json_dir=TRAIN_JSON_DIR,
        save_path=TRAIN_SAVE_PATH,
        split_name="train",
    )


    # --------------------------------------------------------
    # Validation 데이터 전처리
    # --------------------------------------------------------

    valid_df = convert_json_folder(
        json_dir=VALID_JSON_DIR,
        save_path=VALID_SAVE_PATH,
        split_name="valid",
    )


    # ========================================================
    # 최종 결과
    # ========================================================

    print(
        "\n========================================"
    )

    print(
        "전처리 완료"
    )

    print(
        "========================================"
    )

    print(
        f"Train 데이터: {len(train_df)}개"
    )

    print(
        f"Valid 데이터: {len(valid_df)}개"
    )

    print(
        "\n생성된 CSV:"
    )

    print(
        TRAIN_SAVE_PATH
    )

    print(
        VALID_SAVE_PATH
    )


# ============================================================
# 프로그램 실행
# ============================================================

if __name__ == "__main__":
    main()