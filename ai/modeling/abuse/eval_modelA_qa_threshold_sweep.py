"""
Model A(QA) 방임 임계값(threshold)을 바꿔가며 재현율/정밀도 트레이드오프를
확인한다. GPU 추론은 한 번만 돌리고(원문별 확률값을 저장), 임계값만
바꿔가며 재계산한다 — 재학습 없이 가장 싼 개선 레버부터 확인하는 용도.

사용법:
    python3 -m ai.modeling.abuse.eval_modelA_qa_threshold_sweep
"""

import ast
from pathlib import Path

import pandas as pd

from ai.modeling.abuse.infer_abuse_v3_adapter import (
    _engine,
    _build_ordered_qa_text,
    _split_counselor_child_text,
    _suppress_denied_labels,
    predict_abuse_v3,
)
from ai.modeling.abuse.eval_modelA_qa import _to_production_format, LABELS

VALID_CSV = str(
    Path(__file__).resolve().parent / "datasets" / "valid_qa_typeblock_v1.csv"
)

CANDIDATE_THRESHOLDS = [0.5, 0.45, 0.4, 0.35, 0.3, 0.25, 0.2, 0.15, 0.1]


def main() -> None:
    df = pd.read_csv(VALID_CSV)

    rows = []

    for i, row in df.iterrows():
        text = _to_production_format(row["audio_text"])
        gold = ast.literal_eval(row["label"])

        counselor_text, child_text = _split_counselor_child_text(text)
        ordered_text = _build_ordered_qa_text(text)

        raw_predictions = predict_abuse_v3(_engine, ordered_text)

        rows.append(
            {
                "gold": dict(zip(LABELS, gold)),
                "raw_predictions": raw_predictions,
                "child_text": child_text,
                "counselor_text": counselor_text,
            }
        )

        if (i + 1) % 200 == 0:
            print(f"  추론 {i + 1}/{len(df)}", flush=True)

    print("\n=== 방임 임계값별 정밀도/재현율/F1 (재추론 없이 재계산) ===", flush=True)

    for threshold in CANDIDATE_THRESHOLDS:
        tp = fp = fn = tn = 0

        for entry in rows:
            predictions = {}

            for label, pred in entry["raw_predictions"].items():
                th = threshold if label == "방임" else _engine.threshold_for(label)
                predictions[label] = {
                    "detected": pred["probability"] >= th,
                    "probability": pred["probability"],
                }

            predictions = _suppress_denied_labels(
                entry["child_text"],
                predictions,
                counselor_text=entry["counselor_text"],
            )

            predicted = predictions["방임"]["detected"]
            gold_bool = entry["gold"]["방임"]

            if predicted and gold_bool:
                tp += 1
            elif predicted and not gold_bool:
                fp += 1
            elif not predicted and gold_bool:
                fn += 1
            else:
                tn += 1

        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = (
            2 * precision * recall / (precision + recall)
            if (precision + recall)
            else 0.0
        )

        print(
            f"threshold={threshold:.2f} | 정밀도 {precision:.3f} 재현율 {recall:.3f} "
            f"F1 {f1:.3f} | TP {tp} FP {fp} FN {fn} TN {tn}",
            flush=True,
        )


if __name__ == "__main__":
    main()
