"""
qa 모드에 추가한 LLM 보완체크(_verify_major_types_qa)의 순효과를 측정한다.
1차 분류기 단독 결과(before)와 LLM 보완체크까지 거친 결과(after)를 같은
샘플로 비교해서, 실제로 Macro F1이 올라가는지 확인한다.

2차(세부유형/OpenAI) 단계는 이 측정과 무관해서 호출하지 않는다 — 1차
detected_major_types 정확도만 비교한다.

사용법:
    python3 -m ai.modeling.abuse.eval_modelA_qa_llm_verify --n 100
"""

import argparse
import ast
from collections import defaultdict
from pathlib import Path

import pandas as pd

from ai.modeling.abuse.infer_abuse_v3_adapter import predict_major_types
from ai.modeling.abuse.infer_abuse_pipeline import _verify_major_types_qa
from ai.modeling.abuse.llm_backend import build_openai_client_and_model
from ai.modeling.abuse.privacy_gateway import mask_for_outbound
from ai.modeling.abuse.eval_modelA_qa import _to_production_format, LABELS

VALID_CSV = str(
    Path(__file__).resolve().parent / "datasets" / "valid_qa_typeblock_v1.csv"
)


def _score(rows, key):
    tp = defaultdict(int)
    fp = defaultdict(int)
    fn = defaultdict(int)

    for r in rows:
        for label in LABELS:
            predicted = label in r[key]
            gold = r["gold"][label]
            if predicted and gold:
                tp[label] += 1
            elif predicted and not gold:
                fp[label] += 1
            elif not predicted and gold:
                fn[label] += 1

    macro_f1 = 0.0
    print(f"\n--- {key} ---")
    for label in LABELS:
        p = tp[label] / (tp[label] + fp[label]) if (tp[label] + fp[label]) else 0.0
        rcl = tp[label] / (tp[label] + fn[label]) if (tp[label] + fn[label]) else 0.0
        f1 = 2 * p * rcl / (p + rcl) if (p + rcl) else 0.0
        macro_f1 += f1
        print(f"{label}: 정밀도 {p:.3f} 재현율 {rcl:.3f} F1 {f1:.3f} | TP {tp[label]} FP {fp[label]} FN {fn[label]}")
    macro_f1 /= len(LABELS)
    print(f"Macro F1: {macro_f1:.4f}")
    return macro_f1


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n", type=int, default=100)
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args()

    client, model = build_openai_client_and_model(
        default_openai_model="gpt-5.6-luna",
    )

    df = pd.read_csv(VALID_CSV)
    sample = df.sample(n=args.n, random_state=args.seed).sort_index()

    rows = []
    errors = 0

    for i, row in sample.iterrows():
        text = _to_production_format(row["audio_text"])
        gold = dict(zip(LABELS, ast.literal_eval(row["label"])))

        before = predict_major_types(text=text, input_mode="qa")
        before_types = [l for l in LABELS if before[l]["detected"]]

        try:
            masked_text, _ = mask_for_outbound(text)

            after_types = _verify_major_types_qa(
                text=masked_text,
                client=client,
                model=model,
                detected_major_types=before_types,
            )
        except Exception as exc:
            errors += 1
            print(f"  row={i} 실패: {exc}", flush=True)
            after_types = before_types

        rows.append({"row": i, "gold": gold, "before": before_types, "after": after_types})

        if (i + 1) % 25 == 0:
            print(f"  처리 중... (원본 인덱스 {i + 1})", flush=True)

    print(f"\n=== {args.n}건 샘플 (호출실패 {errors}건) ===")
    before_f1 = _score(rows, "before")
    after_f1 = _score(rows, "after")

    print(f"\n=== 순효과 ===")
    print(f"Before(1차 단독): Macro F1 {before_f1:.4f}")
    print(f"After(LLM 보완체크): Macro F1 {after_f1:.4f}")
    print(f"차이: {after_f1 - before_f1:+.4f}")


if __name__ == "__main__":
    main()
