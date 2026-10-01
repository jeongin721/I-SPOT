"""
Model A(roberta_abuse_qa_child_v3) 성능을 실제 서비스 코드 경로
(infer_abuse_v3_adapter.predict_major_types)로 재검증한다.

학습 스크립트가 보고한 valid_qa_typeblock_v1.csv 기준 Macro F1 0.9454는
CSV의 [COUNSELOR]/[CHILD] 텍스트를 토크나이저에 직접 넣어 계산한
값이라, 실제 서비스가 쓰는 predict_major_types(화자 순서 보존 +
"상담사:"/"아동:" 태그 변환 + 부정 응답 필터)를 거치지 않는다. 이
스크립트는 그 차이를 없애고 실제 서비스 코드 그대로 평가한다.

사용법:
    python3 -m ai.modeling.abuse.eval_modelA_qa
    python3 -m ai.modeling.abuse.eval_modelA_qa --limit 200
"""

import argparse
import ast
import re
from collections import defaultdict
from pathlib import Path

import pandas as pd

from ai.modeling.abuse.infer_abuse_v3_adapter import predict_major_types

VALID_CSV = str(
    Path(__file__).resolve().parent / "datasets" / "valid_qa_typeblock_v1.csv"
)
LABELS = ["신체학대", "정서학대", "성학대", "방임"]

_TAG_PATTERN = re.compile(r"\[(COUNSELOR|CHILD)\]\s*")
_TAG_TO_SPEAKER = {"COUNSELOR": "상담사", "CHILD": "아동"}


def _to_production_format(audio_text: str) -> str:
    """valid_qa_typeblock_v1.csv의 [COUNSELOR]/[CHILD] 텍스트를
    실제 서비스가 받는 "상담사: .../아동: ..." 형식으로 바꾼다."""

    def _replace(match):
        return f"{_TAG_TO_SPEAKER[match.group(1)]}: "

    return _TAG_PATTERN.sub(_replace, audio_text)


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
        text = _to_production_format(row["audio_text"])
        gold = ast.literal_eval(row["label"])  # "[0, 1, 0, 0]" 형태 문자열 -> 리스트

        predictions = predict_major_types(text=text, input_mode="qa")

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
                        "target_type": row.get("target_type"),
                        "text_preview": text[:80],
                    }
                )

        if (i + 1) % 100 == 0:
            print(f"  {i + 1}/{len(df)} 처리", flush=True)

    print(f"\n=== Model A(QA) 실제 서비스 코드 경로 기준 — {len(df)}건 ===", flush=True)

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

    print(f"\n=== 오분류 예시 (최대 20개, 총 {len(mismatches)}건) ===", flush=True)

    for m in mismatches[:20]:
        kind = "미탐(FN)" if m["gold"] and not m["predicted"] else "오탐(FP)"
        print(
            f"  [{m['label']} {kind}] row={m['row']} target_type={m['target_type']} "
            f"| {m['text_preview']}...",
            flush=True,
        )


if __name__ == "__main__":
    main()
