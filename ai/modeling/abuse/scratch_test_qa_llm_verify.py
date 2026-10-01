import ast
import time

import pandas as pd

from ai.modeling.abuse.infer_abuse_pipeline import analyze_abuse
from ai.modeling.abuse.eval_modelA_qa import _to_production_format, LABELS

import os
df = pd.read_csv(os.path.join(os.path.dirname(__file__), "datasets", "valid_qa_typeblock_v1.csv"))

# 알려진 문제 케이스들: (row, label, 기대방향)
KNOWN_ISSUES = [
    # 방임 FP(모델이 과탐지, LLM이 지워야 함)
    (748, "방임", "remove"), (844, "방임", "remove"), (1048, "방임", "remove"),
    (1064, "방임", "remove"), (1120, "방임", "remove"), (1308, "방임", "remove"),
    # 신체학대 FP(remove)
    (35, "신체학대", "remove"), (86, "신체학대", "remove"),
    (382, "신체학대", "remove"), (1174, "신체학대", "remove"),
    # 정서학대 FP(remove) 중 명확한 것들(정상훈육/무시 등)
    (417, "정서학대", "remove"), (905, "정서학대", "remove"),
    (865, "정서학대", "remove"), (381, "정서학대", "remove"),
    (533, "정서학대", "remove"),
    # 방임 FN(모델이 놓침, LLM이 추가해야 함 -- 단 교육적방임 정의상
    # 학교행사 불참만으로는 해당 안 할 수 있어 결과가 갈릴 수 있음)
    (1172, "방임", "add"), (1392, "방임", "add"),
    # 정서학대 FN(add)
    (1101, "정서학대", "add"),
]

t0 = time.time()
results = []

for row_idx, label, expected in KNOWN_ISSUES:
    text = _to_production_format(df.iloc[row_idx]["audio_text"])
    call_t0 = time.time()
    result = analyze_abuse(text=text, input_mode="qa")
    elapsed = time.time() - call_t0

    detected = result["major_types"][label]["detected"]
    corrected = result["major_types"][label].get("llm_corrected", False)
    supplementary = result["major_types"][label].get("llm_supplementary", False)

    success = (not detected) if expected == "remove" else detected

    results.append(
        {
            "row": row_idx, "label": label, "expected": expected,
            "detected_final": detected, "corrected": corrected,
            "supplementary": supplementary, "success": success, "elapsed": elapsed,
        }
    )
    print(
        f"row={row_idx} label={label} 기대={expected} -> "
        f"최종={detected} (corrected={corrected}, supplementary={supplementary}) "
        f"{'OK' if success else 'FAIL'} ({elapsed:.1f}초)",
        flush=True,
    )

total_elapsed = time.time() - t0
success_count = sum(1 for r in results if r["success"])
print(f"\n=== 결과: {success_count}/{len(results)} 성공, 총 {total_elapsed:.1f}초 ===")
