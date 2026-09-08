"""
I-SPOT 2차 세부유형 모델의 라벨링 CSV 템플릿을 생성한다.
 텍스트와 세부유형 Multi-label뿐 아니라 판례·공식자료의 라벨 근거와 출처를 함께 기록한다.
"""

# ============================================================
# 1. Import
# ============================================================

from pathlib import Path

import pandas as pd

from ai.modeling.abuse.subtype_label_config import (
    ALL_SUBTYPE_LABELS,
)


# ============================================================
# 2. 경로 설정
# ============================================================

BASE_DIR = Path(
    "/data/I-SPOT"
)

OUTPUT_PATH = (
    BASE_DIR
    / "ai"
    / "modeling"
    / "abuse"
    / "datasets"
    / "subtype_label_template.csv"
)


# ============================================================
# 3. 기본 데이터 컬럼
# ============================================================

BASE_COLUMNS = [
    "case_id",

    # 실제 모델에 입력할 상담형 텍스트
    "text",

    # 1차 4대 유형
    "major_label",
]


# ============================================================
# 4. 세부유형 Multi-label 컬럼
# ============================================================

SUBTYPE_COLUMNS = [
    f"label_{label}"
    for label in ALL_SUBTYPE_LABELS
]


# ============================================================
# 5. 공식 근거 및 출처 컬럼
# ============================================================
# source_type:
#   판례 / 법령 / 공식가이드 / AI-Hub / 보강데이터
#
# official_basis:
#   해당 세부유형 라벨을 부여한 공식 판단 근거
# ============================================================

EVIDENCE_COLUMNS = [
    "official_basis",
    "source_type",
    "source_name",
    "source_id",
    "source_url",
    "label_note",
]


# ============================================================
# 6. CSV 생성
# ============================================================

def make_template():
    """
    2차 세부유형 학습 데이터 구축을 위한 빈 CSV를 생성한다.
    """

    columns = (
        BASE_COLUMNS
        + SUBTYPE_COLUMNS
        + EVIDENCE_COLUMNS
    )

    dataframe = pd.DataFrame(
        columns=columns
    )

    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    dataframe.to_csv(
        OUTPUT_PATH,
        index=False,
        encoding="utf-8-sig",
    )

    print(
        f"생성 완료: {OUTPUT_PATH}"
    )

    print(
        f"세부유형 라벨 수: {len(ALL_SUBTYPE_LABELS)}"
    )

    print(
        f"전체 컬럼 수: {len(columns)}"
    )


# ============================================================
# 7. 실행
# ============================================================

if __name__ == "__main__":
    make_template()
