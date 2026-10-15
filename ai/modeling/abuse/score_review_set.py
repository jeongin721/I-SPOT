"""검수 세트(datasets/subtype_review_v1.json)로 2차 세부유형 평가 결과를 채점한다.

기준은 docs/subtype_rubric_v1.md(판례집 기반)이며 정답 라벨이 아니라 전문가 검수 전
초안이다. 케이스마다 must(반드시 있어야 함)와 may(있어도 없어도 됨)가 있고,
must + may 밖의 세부유형은 근거가 없는 것으로 본다.

사용: python score_review_set.py 결과1.json [결과2.json ...] [--fails]
결과 JSON은 eval_subtype_llm 계열이 저장한 파일(results_log 포함)이다.
"""

import json
import sys
from pathlib import Path

REVIEW_PATH = Path(__file__).parent / "datasets" / "subtype_review_v1.json"

# 세부유형이 14개로 합쳐지기 전 결과에 남아 있을 수 있는 이름
MERGED_INTO = {"유기": "기본적 보호·양육 방임"}


def load_review():
    return {(r["major"], r["case_id"]): r for r in json.load(open(REVIEW_PATH, encoding="utf-8"))}


def score(result_path, review, show_fails=False):
    log = json.load(open(result_path, encoding="utf-8"))["results_log"]
    pred_by_case = {
        (x["major_type"], x["case_id"]): {MERGED_INTO.get(p, p) for p in x["predicted_raw"]}
        for x in log
    }

    groups = {
        "전체": lambda r: True,
        "새 케이스(규칙 작성 전 미열람)": lambda r: not r["seen_before_rules"],
        "규칙 작성 전에 본 케이스": lambda r: r["seen_before_rules"],
        "확실": lambda r: r["conf"] == "확실",
        "애매": lambda r: r["conf"] == "애매",
    }
    fails = []
    stats = {g: {"pass": 0, "n": 0, "tp": 0, "fp": 0, "fn": 0} for g in groups}

    for key, r in review.items():
        if key not in pred_by_case:
            continue
        pred = pred_by_case[key]
        must, may = set(r["must"]), set(r["may"])
        missed = must - pred
        extra = pred - must - may
        ok = not missed and not extra
        if not ok:
            fails.append((key, sorted(pred), sorted(must), sorted(may), sorted(missed), sorted(extra)))
        for g, cond in groups.items():
            if cond(r):
                s = stats[g]
                s["n"] += 1
                s["pass"] += ok
                s["tp"] += len(pred & must)
                s["fp"] += len(extra)
                s["fn"] += len(missed)

    print(f"\n=== {Path(result_path).name}")
    for g, s in stats.items():
        p = s["tp"] / (s["tp"] + s["fp"]) if s["tp"] + s["fp"] else 0.0
        rc = s["tp"] / (s["tp"] + s["fn"]) if s["tp"] + s["fn"] else 0.0
        f1 = 2 * p * rc / (p + rc) if p + rc else 0.0
        print(f"  {g:<26} 통과 {s['pass']:>2}/{s['n']:<2}  P={p:.2f} R={rc:.2f} F1={f1:.2f}"
              f"  (오탐 {s['fp']}, 미탐 {s['fn']})")
    if show_fails:
        for (major, cid), pred, must, may, missed, extra in fails:
            print(f"  ✗ {major} {cid}: 예측={pred} 필수={must} 허용={may} | 미탐={missed} 오탐={extra}")
    return stats


if __name__ == "__main__":
    paths = [a for a in sys.argv[1:] if not a.startswith("--")]
    review = load_review()
    for p in paths:
        score(p, review, show_fails="--fails" in sys.argv)
