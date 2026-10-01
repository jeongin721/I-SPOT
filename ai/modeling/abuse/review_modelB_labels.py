"""
valid_note_v1.csv(Model B 검증셋) 457건을 LLM(로컬 Ollama)으로 재검토해서,
reference_abuse_label 하나만 보고 라벨링하면서 놓쳤을 수 있는 다른 유형의
증거를 찾는다. QA 데이터셋에서 이미 확인한 것과 같은 문제(주 라벨만 보고
동시에 있는 다른 유형 증거를 놓침)가 note 데이터셋에도 있는지, 있다면
얼마나 심각한지 전수로 스캔한다.

LLM은 SUBTYPE_DEFINITIONS 기준으로 4개 유형을 현재 gold label과 무관하게
독립적으로 판단하게 하고(현재 라벨을 보여주지 않음), 그 결과를 현재
label과 비교해서 "현재 False인데 LLM은 True로 본" 경우만 추려낸다 —
이게 바로 "놓친 라벨일 가능성이 있는" 후보들이다. 최종 확정은 사람이
직접 원문을 읽고 판단해야 한다(이 스크립트는 후보를 추려주는 역할).

사용법:
    python3 -m ai.modeling.abuse.review_modelB_labels
    python3 -m ai.modeling.abuse.review_modelB_labels --limit 50
"""

import argparse
import ast
import json
from pathlib import Path

import pandas as pd

from ai.modeling.abuse.llm_backend import build_local_llm_client_and_model
from ai.modeling.abuse.second_stage_llm import (
    SUBTYPE_DEFINITIONS,
    build_subtype_definition_text,
    _call_llm_with_retry,
)

VALID_CSV = str(
    Path(__file__).resolve().parent / "datasets" / "valid_note_v1.csv"
)
LABELS = ["신체학대", "정서학대", "성학대", "방임"]

DEFINITIONS_TEXT = build_subtype_definition_text(LABELS)

SYSTEM_PROMPT = f"""다음은 아동학대 상담/사례 기록(3인칭 서술형)이다. 아래 학대유형
정의를 기준으로, 원문에 각 유형에 해당하는 내용이 실제로 있는지 독립적으로
판단해라.

{DEFINITIONS_TEXT}

규칙:
- 원문에 명확한 근거(실제로 서술된 사실)가 있을 때만 해당 유형을 true로
  판단한다. 추측이나 일반화로 true를 주지 않는다.
- 각 유형은 서로 독립적으로 판단한다 — 한 유형이 true라고 다른 유형을
  자동으로 false/true로 보지 않는다.
- 근거 문장을 따로 쓰지 말고 반드시 아래 JSON 형식으로만, 참/거짓만 답해라:
{{"신체학대": true/false, "정서학대": true/false, "성학대": true/false, "방임": true/false}}
"""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    client, model = build_local_llm_client_and_model()

    df = pd.read_csv(VALID_CSV)
    if args.limit:
        df = df.sample(n=args.limit, random_state=42).sort_index()

    candidates = []  # gold=False인데 LLM=True로 본 경우(놓쳤을 가능성)
    agree_true = 0
    agree_false = 0
    llm_missed = 0  # gold=True인데 LLM=False (참고용, LLM 자체의 한계 확인)
    errors = 0

    for i, row in df.iterrows():
        text = row["audio_text"]
        gold = dict(zip(LABELS, ast.literal_eval(row["label"])))

        try:
            parsed = _call_llm_with_retry(
                client=client,
                model=model,
                system_prompt=SYSTEM_PROMPT,
                user_prompt=text,
                max_retries=1,
                timeout_seconds=240.0,
            )
        except Exception as exc:
            errors += 1
            print(f"  row={i} 호출 실패: {exc}", flush=True)
            continue

        for label in LABELS:
            llm_says = bool(parsed.get(label, False))
            gold_says = bool(gold[label])

            if gold_says and llm_says:
                agree_true += 1
            elif not gold_says and not llm_says:
                agree_false += 1
            elif not gold_says and llm_says:
                candidates.append(
                    {
                        "row": i,
                        "label": label,
                        "reference_abuse_label": row.get("reference_abuse_label"),
                    }
                )
            else:
                llm_missed += 1

        if (i + 1) % 25 == 0:
            print(
                f"  {i + 1}/{len(df)} 처리 | 현재까지 놓친라벨후보 {len(candidates)}건",
                flush=True,
            )

    print(f"\n=== 결과 ({len(df)}건, 호출실패 {errors}건) ===", flush=True)
    print(f"gold=True, LLM=True (일치): {agree_true}건", flush=True)
    print(f"gold=False, LLM=False (일치): {agree_false}건", flush=True)
    print(f"gold=True, LLM=False (LLM이 놓침, 참고용): {llm_missed}건", flush=True)
    print(f"gold=False, LLM=True (라벨 누락 후보!): {len(candidates)}건", flush=True)

    with open("review_modelB_candidates.json", "w", encoding="utf-8") as f:
        json.dump(candidates, f, ensure_ascii=False, indent=2)

    print(f"\n후보 목록을 review_modelB_candidates.json에 저장함", flush=True)

    print("\n=== 라벨 누락 후보 중 유형별 집계 ===", flush=True)
    by_label = {}
    for c in candidates:
        by_label.setdefault(c["label"], 0)
        by_label[c["label"]] += 1
    for label, count in by_label.items():
        print(f"  {label}: {count}건", flush=True)


if __name__ == "__main__":
    main()
