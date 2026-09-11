"""
I-SPOT 1차 v4 학습데이터에서 특정 표현이 어떤 학대 라벨과 함께 등장하는지 확인한다.
모델의 shortcut learning 및 오탐 원인을 진단하기 위한 분석용 스크립트다.
"""

import ast

import pandas as pd


# ============================================================
# 1. 데이터 경로
# ============================================================

CSV_PATH = (
    "ai/modeling/abuse/datasets/"
    "train_multilabel_v4.csv"
)


# ============================================================
# 2. 확인할 표현
# ============================================================

KEYWORDS = [
    "나가라고",
    "집에 혼자",
    "혼자 있었",
    "벗기",
    "옷을 벗",
]


# ============================================================
# 3. 라벨 이름
# ============================================================

LABEL_NAMES = [
    "신체학대",
    "정서학대",
    "성학대",
    "방임",
]


# ============================================================
# 4. label 파싱
# ============================================================

def parse_label(value):
    """CSV의 문자열 label을 Python list로 변환한다."""

    if isinstance(value, list):
        return value

    return ast.literal_eval(
        str(value)
    )


# ============================================================
# 5. 실행
# ============================================================

def main() -> None:
    """키워드별 등장 문장과 라벨 분포를 출력한다."""

    df = pd.read_csv(
        CSV_PATH
    )

    print()
    print("=" * 100)
    print("I-SPOT 1차 v4 학습데이터 키워드-라벨 분석")
    print("=" * 100)

    for keyword in KEYWORDS:

        matched = df[
            df["audio_text"]
            .fillna("")
            .str.contains(
                keyword,
                regex=False,
            )
        ].copy()

        print()
        print("=" * 100)
        print(
            f"[키워드] {keyword}"
        )
        print(
            f"등장 건수: {len(matched)}"
        )
        print("=" * 100)

        if matched.empty:
            print("해당 표현 없음")
            continue

        label_counts = {
            label: 0
            for label in LABEL_NAMES
        }

        for _, row in matched.iterrows():

            labels = parse_label(
                row["label"]
            )

            for index, label_name in enumerate(
                LABEL_NAMES
            ):
                if labels[index] == 1:
                    label_counts[
                        label_name
                    ] += 1

        print()
        print("[라벨 동시 등장]")
        for label_name in LABEL_NAMES:
            print(
                f"- {label_name}: "
                f"{label_counts[label_name]}건"
            )

        print()
        print("[실제 문장 샘플]")

        for _, row in matched.head(
            15
        ).iterrows():

            print("-" * 100)

            print(
                "text:",
                row["audio_text"],
            )

            print(
                "label:",
                parse_label(
                    row["label"]
                ),
            )


# ============================================================
# 6. 실행
# ============================================================

if __name__ == "__main__":
    main()