"""
복합유형(2개 이상 학대유형이 동시에 존재하는) 상담일지 합성 데이터를 만든다.

note 전용 1차 모델의 학습 데이터(train_note_v1.csv)는 AI-HUB 원본 라벨이
사례당 유형 하나뿐이라, 실제로 여러 유형이 섞인 사례에서 가장 강한 유형
하나만 확신하고 나머지를 놓치는 경향이 확인됐다(성학대 98.8% vs 정서학대
8.3%, 2026-09-21 진단).

이 스크립트는 이미 만들어둔 단일유형 상담일지(counseling_note_train_v1.csv/
counseling_note_valid_v1.csv) 중 서로 다른 유형 2~4개를 골라, LLM으로
"한 아동에게 실제로 여러 유형이 함께 일어난 것처럼" 하나의 자연스러운
사례로 재구성한다. 정답 라벨은 원본 유형들의 합집합이므로 LLM이 유형을
새로 판단할 필요는 없다 — 서술만 자연스럽게 합치면 된다.
"""

import argparse
import csv
import itertools
import os
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pandas as pd
from tqdm import tqdm

from ai.modeling.abuse.llm_backend import (
    build_llm_client_and_model,
)
from ai.modeling.abuse.second_stage_llm import (
    _call_llm_with_retry,
)


BASE_DIR = Path(__file__).resolve().parent

LABEL_NAMES = [
    "신체학대",
    "정서학대",
    "성학대",
    "방임",
]

SOURCE_FILES = {
    "train": BASE_DIR / "datasets" / "counseling_note_train_v1.csv",
    "valid": BASE_DIR / "datasets" / "counseling_note_valid_v1.csv",
}

OUTPUT_FILES = {
    "train": BASE_DIR / "datasets" / "counseling_note_train_multitype_v1.csv",
    "valid": BASE_DIR / "datasets" / "counseling_note_valid_multitype_v1.csv",
}

# combo 크기별 (조합 개수, split별 생성 건수)
COMBO_COUNTS = {
    2: {"train": 30, "valid": 8},
    3: {"train": 15, "valid": 4},
    4: {"train": 10, "valid": 3},
}

OUTPUT_COLUMNS = [
    "case_id",
    "reference_abuse_label",
    "counseling_note",
    "source_case_ids",
    "model",
]

DEFAULT_MODEL = os.getenv(
    "COUNSELING_NOTE_MODEL",
    "gpt-5.6-luna",
)

DEFAULT_WORKERS = 4


# ============================================================
# 1. 병합 프롬프트
# ============================================================

SYSTEM_PROMPT = """
당신은 아동 상담일지 여러 건을 하나의 사례로 자연스럽게 재구성하는
도우미다.

아래에 서로 다른 학대유형을 담은 상담일지가 여러 건 주어진다. 이걸
별개 사례로 나열하지 말고, 마치 "한 아동"이 한 번의(또는 연속된)
상담에서 이 모든 내용을 겪고 진술한 것처럼 하나의 자연스러운
상담일지로 재구성하라.

[원칙]

1. 원본에 있는 사실(행위, 발화, 정황)만 사용한다 — 새로운 사건을
   지어내지 않는다.
2. 각 원본의 핵심 내용(구체적 행위, 인용 발화)은 최대한 살려서
   포함한다 — 요약하며 통째로 생략하지 않는다.
3. 여러 원본을 하나의 흐름으로 자연스럽게 잇는다. 실제 복합 사례에서
   흔한 패턴(예: 한 가해자가 여러 유형의 행위를 함께 하거나, 한
   유형의 피해를 누설하지 못하게 위협하는 것 자체가 다른 유형이 되는
   경우)을 참고해도 좋지만, 원본에 없는 새 위협·행위를 창작하지는
   않는다.
4. 학대 여부나 학대 유형을 판정하는 표현("신체학대", "성학대 의심",
   "위험도가 높다" 등)은 쓰지 않는다.
5. "~라고 진술함.", "~라고 하였음." 등 중립적 상담일지 문체를
   유지한다. 3인칭 서술형.

반드시 아래 JSON 형식으로만 답한다.

{"counseling_note": "..."}
"""


def build_user_prompt(
    notes: list,
) -> str:
    blocks = "\n\n".join(
        f"[원본 {i + 1}]\n{note}"
        for i, note in enumerate(notes)
    )

    return f"다음 {len(notes)}건의 상담일지를 하나의 사례로 합쳐줘.\n\n{blocks}"


# ============================================================
# 2. 데이터 로드/샘플링
# ============================================================

def load_pool(
    split_name: str,
) -> dict:
    """
    유형별로 counseling_note 목록을 모은 dict를 반환한다.
    (해당 없음)인 행과 복수 유형이 이미 섞인 행은 제외한다.
    """

    path = SOURCE_FILES[split_name]

    df = pd.read_csv(path)

    pool = {label: [] for label in LABEL_NAMES}

    for _, row in df.iterrows():
        label = str(
            row.get("reference_abuse_label", "")
        ).strip()

        note = str(
            row.get("counseling_note", "")
        ).strip()

        if label not in LABEL_NAMES or not note:
            continue

        pool[label].append(
            {
                "case_id": row.get("case_id", ""),
                "note": note,
            }
        )

    return pool


def iter_combos(
    combo_size: int,
    count: int,
    pool: dict,
    rng: random.Random,
):
    """
    combo_size개 유형 조합마다 count건씩, 각 조합에서 유형별로
    한 건씩 무작위로 뽑아 (라벨 조합, 원본 case 리스트)를 yield한다.
    """

    for combo in itertools.combinations(LABEL_NAMES, combo_size):

        if any(
            len(pool[label]) == 0
            for label in combo
        ):
            print(
                f"[SKIP] {combo}: 원본 데이터 부족"
            )
            continue

        for _ in range(count):
            picks = [
                rng.choice(pool[label])
                for label in combo
            ]

            yield combo, picks


# ============================================================
# 3. 생성
# ============================================================

def _synthesize_one(
    combo,
    picks,
    client,
    model: str,
) -> dict:
    """
    worker thread에서 실행 — LLM 호출만 하고 파일 I/O는 하지 않는다.
    """

    notes = [
        p["note"]
        for p in picks
    ]

    parsed = _call_llm_with_retry(
        client=client,
        model=model,
        system_prompt=SYSTEM_PROMPT,
        user_prompt=build_user_prompt(
            notes
        ),
        max_retries=3,
        timeout_seconds=120.0,
    )

    merged_note = str(
        parsed.get(
            "counseling_note",
            "",
        )
    ).strip()

    if not merged_note:
        raise ValueError(
            "counseling_note가 비어 있습니다."
        )

    return {
        "reference_abuse_label": ",".join(
            combo
        ),
        "counseling_note": merged_note,
        "source_case_ids": ",".join(
            str(p["case_id"])
            for p in picks
        ),
        "model": model,
    }


def generate_multitype(
    split_name: str,
    client,
    model: str,
    seed: int = 42,
    workers: int = DEFAULT_WORKERS,
) -> None:
    pool = load_pool(split_name)

    for label in LABEL_NAMES:
        print(
            f"  {label:<6}: {len(pool[label])}건 보유"
        )

    rng = random.Random(seed)

    output_path = OUTPUT_FILES[split_name]

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    # 먼저 조합/원본을 전부 뽑아둔다 (LLM 호출 전, 순수 샘플링).
    tasks = []

    for combo_size, counts in COMBO_COUNTS.items():

        count = counts[split_name]

        for combo, picks in iter_combos(
            combo_size,
            count,
            pool,
            rng,
        ):
            tasks.append(
                (combo, picks)
            )

    rows_written = 0
    failed_count = 0

    with output_path.open(
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as f:

        writer = csv.DictWriter(
            f,
            fieldnames=OUTPUT_COLUMNS,
        )

        writer.writeheader()

        executor = ThreadPoolExecutor(
            max_workers=workers
        )

        futures = {
            executor.submit(
                _synthesize_one,
                combo,
                picks,
                client,
                model,
            ): (combo, picks)
            for combo, picks in tasks
        }

        try:
            for future in tqdm(
                as_completed(
                    futures
                ),
                total=len(futures),
                desc=f"multitype ({split_name})",
            ):
                combo, picks = futures[future]

                try:
                    row = future.result()

                except Exception as exc:
                    failed_count += 1

                    tqdm.write(
                        f"[FAIL] {combo}: {exc}"
                    )

                    continue

                rows_written += 1

                row["case_id"] = (
                    f"multitype_{'_'.join(combo)}_"
                    f"{rows_written}"
                )

                writer.writerow(
                    row
                )

                f.flush()

                tqdm.write(
                    f"[{rows_written}] {','.join(combo)} 완료"
                )

        finally:
            executor.shutdown(
                wait=True
            )

    print(
        f"[{split_name.upper()}] "
        f"성공 {rows_written}건 / 실패 {failed_count}건 저장"
        f" -> {output_path}"
    )


# ============================================================
# 4. Main
# ============================================================

def main() -> None:
    parser = argparse.ArgumentParser(
        description="복합유형 상담일지 합성 데이터 생성"
    )

    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
    )

    parser.add_argument(
        "--workers",
        type=int,
        default=DEFAULT_WORKERS,
    )

    args = parser.parse_args()

    client, model = build_llm_client_and_model(
        default_openai_model=args.model,
    )

    for split_name in ("train", "valid"):
        print()
        print("=" * 60)
        print(f"[{split_name.upper()}]")
        print("=" * 60)

        generate_multitype(
            split_name,
            client,
            model,
            workers=args.workers,
        )


if __name__ == "__main__":
    main()
