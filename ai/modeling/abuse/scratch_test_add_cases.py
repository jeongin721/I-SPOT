import os
import pandas as pd

from ai.modeling.abuse.infer_abuse_pipeline import analyze_abuse
from ai.modeling.abuse.eval_modelA_qa import _to_production_format

df = pd.read_csv(os.path.join(os.path.dirname(__file__), "datasets", "valid_qa_typeblock_v1.csv"))

CASES = [
    (1172, "방임"), (1392, "방임"), (1101, "정서학대"),
    # 회귀 확인용: 이미 성공했던 remove 케이스 2개도 같이 확인
    (748, "방임"), (417, "정서학대"),
]

for row_idx, label in CASES:
    text = _to_production_format(df.iloc[row_idx]["audio_text"])
    result = analyze_abuse(text=text, input_mode="qa")
    detected = result["major_types"][label]["detected"]
    corrected = result["major_types"][label].get("llm_corrected", False)
    supplementary = result["major_types"][label].get("llm_supplementary", False)
    print(
        f"row={row_idx} label={label} -> detected={detected} "
        f"(corrected={corrected}, supplementary={supplementary})",
        flush=True,
    )
