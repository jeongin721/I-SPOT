"""
Model B(roberta_abuse_note_v1) 성능을 실제 서비스 코드 경로
(infer_abuse_v3_adapter.predict_major_types, input_mode="note")로 검증한다.

note 모드는 qa 모드와 달리 화자 태그 변환/순서 재구성이 없고 원문을
그대로 모델에 넣으므로(어댑터에 변환 로직이 없음), 학습 스크립트가
보고한 숫자와 서비스 코드 경로 결과가 다를 이유가 구조적으로 없다 —
그래도 실제로 같은지 직접 확인한다.

사용법:
    python3 -m ai.modeling.abuse.eval_modelB_note
"""

import argparse
import ast
from collections import defaultdict
from pathlib import Path

import pandas as pd

from ai.modeling.abuse.infer_abuse_v3_adapter import predict_major_types

VALID_CSV = str(
    Path(__file__).resolve().parent / "datasets" / "valid_note_v1.csv"
)
LABELS = ["신체학대", "정서학대", "성학대", "방임"]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--csv", default=VALID_CSV)
    args = parser.parse_args()

    df = pd.read_csv(args.csv)

    if args.limit:
        df = df.head(args.limit)

    tp = defaultdict(int)
    fp = defaultdict(int)
    fn = defaultdict(int)
    tn = defaultdict(int)

    mismatches = []

    for i, row in df.iterrows():
        text = row["audio_text"]
        gold = ast.literal_eval(row["label"])

        predictions = predict_major_types(text=text, input_mode="note")

        for label, gold_value in zip(LABELS, gold):
            predicted = predictions.get(label, {}).get("detected", False)
            gold_bool = bool(gold_value)

            if predicted and gold_bool:
                tp[label] += 1
            elif predicted and not gold_bool:
                fp[label] += 1
            elif not predicted and gold_bool:
                fn[label] += 1
            else:
                tn[label] += 1

            if predicted != gold_bool:
                mismatches.append(
                    {
                        "row": i,
                        "label": label,
                        "predicted": predicted,
                        "gold": gold_bool,
                        "reference_abuse_label": row.get("reference_abuse_label"),
                        "text_preview": text[:80],
                    }
                )

        if (i + 1) % 100 == 0:
            print(f"  {i + 1}/{len(df)} 처리", flush=True)

    print(f"\n=== Model B(note) 실제 서비스 코드 경로 기준 — {len(df)}건 ===", flush=True)

    macro_f1_sum = 0.0

    for label in LABELS:
        precision = (
            tp[label] / (tp[label] + fp[label])
            if (tp[label] + fp[label])
            else 0.0
        )
        recall = (
            tp[label] / (tp[label] + fn[label])
            if (tp[label] + fn[label])
            else 0.0
        )
        f1 = (
            2 * precision * recall / (precision + recall)
            if (precision + recall)
            else 0.0
        )
        macro_f1_sum += f1

        print(
            f"{label}: 정밀도 {precision:.3f} 재현율 {recall:.3f} F1 {f1:.3f} "
            f"| TP {tp[label]} FP {fp[label]} FN {fn[label]} TN {tn[label]}",
            flush=True,
        )

    print(f"\nMacro F1: {macro_f1_sum / len(LABELS):.4f}", flush=True)

    print(f"\n=== 오분류 예시 (최대 30개, 총 {len(mismatches)}건) ===", flush=True)

    for m in mismatches[:30]:
        kind = "미탐(FN)" if m["gold"] and not m["predicted"] else "오탐(FP)"
        print(
            f"  [{m['label']} {kind}] row={m['row']} ref={m['reference_abuse_label']} "
            f"| {m['text_preview']}...",
            flush=True,
        )


if __name__ == "__main__":
    main()
