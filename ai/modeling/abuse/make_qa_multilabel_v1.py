"""
AI-Hub 아동상담 JSON의 '학대여부' Q+A를 상담 맥락 형태로 변환한다.
공식 Train/Validation 분할을 유지하며 4대 학대유형 멀티라벨 CSV를 생성한다.
"""

import ast
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd
from tqdm import tqdm


# ============================================================
# 1. 경로 설정
# ============================================================

PROJECT_ROOT = Path("/data/I-SPOT")

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

TRAIN_OUTPUT_PATH = (
    OUTPUT_DIR
    / "train_qa_multilabel_v1.csv"
)

VALID_OUTPUT_PATH = (
    OUTPUT_DIR
    / "valid_qa_multilabel_v1.csv"
)


# ============================================================
# 2. 라벨 정의
# ============================================================

# 기존 1차 모델과 동일한 순서를 반드시 유지한다.
LABEL_ITEMS = [
    "신체학대",
    "정서학대",
    "성학대",
    "방임",
]


# ============================================================
# 3. 텍스트 정리
# ============================================================

def clean_text(text: str) -> str:
    """문장의 불필요한 공백을 정리한다."""

    return " ".join(
        str(text).strip().split()
    )


# ============================================================
# 4. 학대여부 섹션 찾기
# ============================================================

def find_abuse_section(
    data: Dict,
) -> Optional[Dict]:
    """JSON에서 '학대여부' 문항을 찾는다."""

    for section in data.get("list", []):
        if section.get("문항") == "학대여부":
            return section

    return None


# ============================================================
# 5. Q+A 상담 텍스트 생성
# ============================================================

def build_qa_text(
    abuse_section: Dict,
) -> str:
    """
    학대여부 섹션의 Q/A 발화를 실제 대화 순서대로 연결한다.

    Q → [COUNSELOR]
    A → [CHILD]
    """

    lines: List[str] = []

    for item in abuse_section.get("list", []):

        audio_list = item.get("audio", [])

        for audio in audio_list:

            utterance_type = audio.get("type")
            text = clean_text(
                audio.get("text", "")
            )

            if not text:
                continue

            if utterance_type == "Q":
                speaker = "[COUNSELOR]"

            elif utterance_type == "A":
                speaker = "[CHILD]"

            else:
                continue

            lines.append(
                f"{speaker} {text}"
            )

    return "\n".join(lines)


# ============================================================
# 6. 4대 학대유형 라벨 생성
# ============================================================

def build_multilabel(
    abuse_section: Dict,
) -> List[int]:
    """
    신체학대, 정서학대, 성학대, 방임 순서로 라벨을 생성한다.

    각 항목의 점수가 0보다 크면 해당 학대유형 신호가 있는 것으로 처리한다.
    """

    score_map = {
        label_name: 0
        for label_name in LABEL_ITEMS
    }

    for item in abuse_section.get("list", []):

        item_name = item.get("항목")

        if item_name not in score_map:
            continue

        try:
            score = float(
                item.get("점수", 0)
            )
        except (TypeError, ValueError):
            score = 0

        score_map[item_name] = (
            1 if score > 0 else 0
        )

    return [
        score_map[label_name]
        for label_name in LABEL_ITEMS
    ]


# ============================================================
# 7. JSON 1개 처리
# ============================================================

def process_json(
    file_path: Path,
) -> Optional[Dict]:
    """JSON 한 사례를 모델 학습용 한 행으로 변환한다."""

    with open(
        file_path,
        "r",
        encoding="utf-8",
    ) as f:
        data = json.load(f)

    abuse_section = find_abuse_section(
        data
    )

    if abuse_section is None:
        return None

    audio_text = build_qa_text(
        abuse_section
    )

    label = build_multilabel(
        abuse_section
    )

    if not audio_text:
        return None

    return {
        "audio_text": audio_text,
        "label": str(label),
        "source_file": file_path.name,
    }


# ============================================================
# 8. Split 전체 변환
# ============================================================

def build_dataset(
    json_dir: Path,
    output_path: Path,
    split_name: str,
) -> pd.DataFrame:
    """하나의 공식 split 전체를 CSV로 변환한다."""

    json_files = sorted(
        json_dir.rglob("*.json")
    )

    rows: List[Dict] = []

    for file_path in tqdm(
        json_files,
        desc=f"{split_name} Q+A 변환",
    ):
        try:
            row = process_json(
                file_path
            )

            if row is not None:
                rows.append(row)

        except Exception as exc:
            print(
                f"\n[ERROR] {file_path.name}: {exc}"
            )

    df = pd.DataFrame(rows)

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    df.to_csv(
        output_path,
        index=False,
        encoding="utf-8-sig",
    )

    return df


# ============================================================
# 9. 데이터셋 진단
# ============================================================

def print_dataset_summary(
    df: pd.DataFrame,
    split_name: str,
) -> None:
    """생성된 데이터의 크기와 라벨 분포를 출력한다."""

    print()
    print("=" * 100)
    print(
        f"[{split_name} 데이터셋]"
    )
    print("=" * 100)

    print(
        f"전체 사례 수: {len(df)}"
    )

    label_counts = {
        label_name: 0
        for label_name in LABEL_ITEMS
    }

    no_abuse_count = 0

    for label_text in df["label"]:

        labels = ast.literal_eval(
            label_text
        )

        if sum(labels) == 0:
            no_abuse_count += 1

        for index, label_name in enumerate(
            LABEL_ITEMS
        ):
            if labels[index] == 1:
                label_counts[
                    label_name
                ] += 1

    print()

    for label_name in LABEL_ITEMS:
        count = label_counts[
            label_name
        ]

        ratio = (
            count / len(df) * 100
            if len(df)
            else 0
        )

        print(
            f"{label_name}: "
            f"{count}건 "
            f"({ratio:.2f}%)"
        )

    print(
        f"비학대: {no_abuse_count}건 "
        f"({no_abuse_count / len(df) * 100:.2f}%)"
        if len(df)
        else "비학대: 0건"
    )


# ============================================================
# 10. 샘플 확인
# ============================================================

def print_sample(
    df: pd.DataFrame,
    split_name: str,
) -> None:
    """생성 결과 중 첫 번째 사례를 화면에 출력한다."""

    if df.empty:
        return

    row = df.iloc[0]

    print()
    print("=" * 100)
    print(
        f"[{split_name} SAMPLE]"
    )
    print("=" * 100)

    print(
        "source_file:",
        row["source_file"],
    )

    print(
        "label:",
        row["label"],
    )

    print()

    print(
        row["audio_text"]
    )


# ============================================================
# 11. 실행
# ============================================================

def main() -> None:
    """Train/Validation Q+A 데이터셋을 생성한다."""

    train_df = build_dataset(
        json_dir=TRAIN_JSON_DIR,
        output_path=TRAIN_OUTPUT_PATH,
        split_name="TRAIN",
    )

    valid_df = build_dataset(
        json_dir=VALID_JSON_DIR,
        output_path=VALID_OUTPUT_PATH,
        split_name="VALID",
    )

    print_dataset_summary(
        train_df,
        "TRAIN",
    )

    print_dataset_summary(
        valid_df,
        "VALID",
    )

    print_sample(
        train_df,
        "TRAIN",
    )

    print()
    print("=" * 100)
    print("[저장 완료]")
    print("=" * 100)

    print(
        TRAIN_OUTPUT_PATH
    )

    print(
        VALID_OUTPUT_PATH
    )


if __name__ == "__main__":
    main()