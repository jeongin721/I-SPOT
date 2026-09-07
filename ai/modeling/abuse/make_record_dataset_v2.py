"""
AI-Hub 상담 Q+A를 원래 사실과 라벨을 보존한 상담사 기록형 텍스트로 재구성한다.
먼저 Train 10건만 LLM으로 변환해 문체·사실 보존·환각 여부를 검수한다.
"""

import ast
import os
from pathlib import Path
from typing import Literal

import pandas as pd
from openai import OpenAI
from pydantic import BaseModel, Field
from tqdm import tqdm


# ============================================================
# 1. 기본 설정
# ============================================================

SEED = 69

# 처음에는 반드시 소량만 검증한다.
LIMIT = 10

MODEL = (
    os.getenv("OPENAI_MODEL")
    or "gpt-4o-mini"
).strip()

PROJECT_ROOT = Path(__file__).resolve().parents[4]

DATASET_DIR = (
    PROJECT_ROOT
    / "ai"
    / "modeling"
    / "abuse"
    / "datasets"
)

INPUT_PATH = (
    DATASET_DIR
    / "train_record_base_v2.csv"
)

OUTPUT_PATH = (
    DATASET_DIR
    / "train_record_v2_preview.csv"
)


# ============================================================
# 2. Record 문체
# ============================================================

RecordStyle = Literal[
    "formal",
    "concise",
    "memo",
    "narrative",
    "mixed",
]

RECORD_STYLES = [
    "formal",
    "concise",
    "memo",
    "narrative",
    "mixed",
]


# ============================================================
# 3. Structured Output
# ============================================================

class RecordRewriteOutput(BaseModel):
    """LLM이 반환해야 하는 상담기록 재구성 결과."""

    record_text: str = Field(
        ...,
        description="원본 Q+A의 사실만 이용해 재구성한 상담기록",
    )

    style: RecordStyle

    omitted_information: list[str] = Field(
        default_factory=list,
        description="기록 압축 과정에서 생략한 정보",
    )

    warnings: list[str] = Field(
        default_factory=list,
        description="재구성 과정에서 주의가 필요한 사항",
    )


# ============================================================
# 4. 프롬프트
# ============================================================

SYSTEM_PROMPT = """
당신의 역할은 아동·청소년 상담 Q&A를
'상담사가 상담 후 작성한 기록' 형태로 재작성하는 것입니다.

이 작업은 학대 여부를 판단하는 작업이 아닙니다.
주어진 상담 내용을 기록 문체로 변환하는 작업만 수행하십시오.

[절대 규칙]

1. 원문 Q&A에 존재하는 사실만 기록하십시오.
2. 새로운 사건, 인물, 행동, 빈도, 부위, 원인, 감정 등을 만들지 마십시오.
3. 학대 여부를 새롭게 판단하거나 진단하지 마십시오.
4. '학대가 의심됨', '위험함', '학대로 판단됨' 같은 판단 문구를 추가하지 마십시오.
5. 질문에 포함된 정보를 아동이 직접 진술한 사실처럼 바꾸지 마십시오.
6. 아동의 답변이 부정이라면 긍정적인 사건으로 바꾸지 마십시오.
7. '상담사가 확인함', '관찰됨', '멍 확인됨'처럼 원문에 없는 관찰 사실을 만들지 마십시오.
8. 질문 자체는 최종 기록에 그대로 복사하지 마십시오.
9. 답변의 의미와 사실관계는 유지하십시오.
10. 입력에 포함된 [신체학대], [정서학대], [성학대], [방임] 표시는
    데이터 구조를 구분하기 위한 메타데이터일 뿐입니다.
    최종 기록에 이 카테고리명을 쓰지 마십시오.
11. 정답 라벨을 추론하거나 기록에 노출하지 마십시오.
12. 불필요한 일반론이나 상담 권고를 추가하지 마십시오.

[문체]

formal:
- 비교적 정식 상담일지 문체
- '~라고 진술함', '~라고 이야기함' 등을 사용

concise:
- 핵심 사실 위주의 짧은 기록
- 불필요한 반복 제거

memo:
- 상담사가 빠르게 작성한 메모 형태
- 짧은 구문과 간결한 표현 사용

narrative:
- 상담 흐름이 자연스럽게 이어지는 서술형 기록

mixed:
- 정식 기록체와 간결한 메모체가 섞인 실제 업무 기록 형태

중요:
원문의 의미를 보존하는 것이 문장을 자연스럽게 만드는 것보다 우선입니다.
"""


# ============================================================
# 5. 입력 검증
# ============================================================

def validate_label(label_text: str) -> list[int]:
    """기존 AI-Hub 4차원 라벨 형식이 유지되는지 확인한다."""

    label = ast.literal_eval(label_text)

    if (
        not isinstance(label, list)
        or len(label) != 4
        or any(value not in (0, 1) for value in label)
    ):
        raise ValueError(
            f"잘못된 label 형식: {label_text}"
        )

    return label


# ============================================================
# 6. LLM 입력 생성
# ============================================================

def build_user_prompt(
    qa_text: str,
    style: str,
) -> str:
    """Q+A와 목표 Record 문체만 LLM에 전달한다."""

    return f"""
다음 상담 Q&A를 상담기록으로 재작성하십시오.

목표 문체:
{style}

상담 Q&A:
{qa_text}

다시 강조합니다.
원문에 없는 사실이나 판단은 절대 추가하지 마십시오.
"""


# ============================================================
# 7. 한 사례 재구성
# ============================================================

def rewrite_record(
    client: OpenAI,
    qa_text: str,
    style: str,
) -> RecordRewriteOutput:
    """OpenAI Structured Output으로 한 사례를 재구성한다."""

    response = client.beta.chat.completions.parse(
        model=MODEL,
        messages=[
            {
                "role": "system",
                "content": SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": build_user_prompt(
                    qa_text=qa_text,
                    style=style,
                ),
            },
        ],
        response_format=RecordRewriteOutput,
        temperature=0.0,
    )

    parsed = response.choices[0].message.parsed

    if parsed is None:
        raise RuntimeError(
            "Structured Output 파싱 실패"
        )

    record_text = parsed.record_text.strip()

    if not record_text:
        raise RuntimeError(
            "빈 상담기록이 생성됨"
        )

    return parsed


# ============================================================
# 8. Preview 생성
# ============================================================

def make_preview() -> pd.DataFrame:
    """Train 기반 데이터 중 10건만 상담기록으로 재구성한다."""

    if not INPUT_PATH.exists():
        raise FileNotFoundError(
            f"입력 CSV가 없습니다: {INPUT_PATH}"
        )

    api_key = os.getenv("OPENAI_API_KEY")

    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY 환경변수가 설정되지 않았습니다."
        )

    client = OpenAI(
        api_key=api_key
    )

    df = pd.read_csv(
        INPUT_PATH
    )

    # --------------------------------------------------------
    # 여러 라벨 조합을 조금이라도 확인하기 위해
    # 랜덤 10건을 고정 seed로 선택한다.
    # --------------------------------------------------------

    preview_df = (
        df.sample(
            n=min(LIMIT, len(df)),
            random_state=SEED,
        )
        .reset_index(drop=True)
    )

    rows = []

    for index, row in tqdm(
        preview_df.iterrows(),
        total=len(preview_df),
        desc="Record v2 Preview",
    ):

        source_file = row["source_file"]
        qa_text = str(row["qa_text"])
        label_text = str(row["label"])

        # 라벨은 검증만 하고 LLM에는 전달하지 않는다.
        validate_label(
            label_text
        )

        # ----------------------------------------------------
        # 사례마다 문체를 순환 배정한다.
        # ----------------------------------------------------

        target_style = RECORD_STYLES[
            index % len(RECORD_STYLES)
        ]

        try:
            result = rewrite_record(
                client=client,
                qa_text=qa_text,
                style=target_style,
            )

            rows.append(
                {
                    "source_file": source_file,
                    "qa_text": qa_text,
                    "record_text": result.record_text,
                    "label": label_text,
                    "target_style": target_style,
                    "generated_style": result.style,
                    "omitted_information": str(
                        result.omitted_information
                    ),
                    "warnings": str(
                        result.warnings
                    ),
                }
            )

        except Exception as error:
            print(
                f"\n[ERROR] {source_file}: {error}"
            )

    return pd.DataFrame(
        rows
    )


# ============================================================
# 9. Preview 출력
# ============================================================

def print_preview(
    dataframe: pd.DataFrame,
) -> None:
    """생성 결과를 터미널에서 바로 비교할 수 있게 출력한다."""

    print()
    print("=" * 80)
    print("RECORD V2 PREVIEW")
    print("=" * 80)

    for _, row in dataframe.iterrows():

        print()
        print("=" * 80)
        print(
            "FILE :",
            row["source_file"],
        )
        print(
            "LABEL:",
            row["label"],
        )
        print(
            "STYLE:",
            row["target_style"],
        )

        print()
        print("[원본 Q+A]")
        print(
            row["qa_text"]
        )

        print()
        print("[생성 Record]")
        print(
            row["record_text"]
        )

        if (
            row["omitted_information"]
            != "[]"
        ):
            print()
            print("[생략 정보]")
            print(
                row["omitted_information"]
            )

        if row["warnings"] != "[]":
            print()
            print("[WARNING]")
            print(
                row["warnings"]
            )


# ============================================================
# 10. 실행
# ============================================================

def main() -> None:
    """10건 Preview를 생성하고 CSV로 저장한다."""

    print("=" * 80)
    print("AI-Hub -> Counselor Record v2 Preview")
    print("=" * 80)

    print(
        f"Model : {MODEL}"
    )
    print(
        f"Limit : {LIMIT}"
    )

    result_df = make_preview()

    result_df.to_csv(
        OUTPUT_PATH,
        index=False,
        encoding="utf-8-sig",
    )

    print_preview(
        result_df
    )

    print()
    print("=" * 80)
    print(
        f"생성 성공 : {len(result_df)} / {LIMIT}"
    )
    print(
        f"저장 위치 : {OUTPUT_PATH}"
    )
    print("=" * 80)


if __name__ == "__main__":
    main()