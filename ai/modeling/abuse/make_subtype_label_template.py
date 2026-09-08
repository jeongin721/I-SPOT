"""
I-SPOT 2차 세부유형 모델 학습을 위한 수동 라벨링 CSV 템플릿을 생성한다.
,,,,,,,, 1차 대분류, 세부유형 Multi-label, 5단계 신호 수준과 출처를 기록한다.
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
# 3. 기본 컬럼
# ============================================================

BASE_COLUMNS = [
    "case_id",
    "text",
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
# 5. 신호 수준 및 출처 컬럼
# ============================================================

META_COLUMNS = [
    "signal_level",
    "source",
    "source_id",
    "label_note",
]


# ============================================================
# 6. CSV 생성
# ============================================================

def make_template():
    """
    2차 학습 데이터 라벨링을 위한 빈 CSV 파일을 생성한다.
    """

    columns = (
        BASE_COLUMNS
        + SUBTYPE_COLUMNS
        + META_COLUMNS
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
