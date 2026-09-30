"""판례집 사례(115건)를 모델 B 개선 실험용으로 분할한다: 최종 테스트 + 5-fold 개발.

규칙(먼저 정하고 나중에 바꾸지 않는다)
- 정답은 판례집 '결론' 문장이 인정한 유형이다(유기는 방임에 합침). AI가 사실관계에서 더 찾은 유형은
  별도 컬럼(ai_review)에 보관만 하고 채점의 정답으로 쓰지 않는다.
- test(약 30건)는 개선 방법을 고르는 동안 절대 보지 않고, 최종 1회만 채점한다.
- dev(나머지)는 5-fold 교차검증으로 방법을 고른다. 학습과 임계값 조정은 fold 안에서만 한다.
- 텍스트 유사도(문자 n-gram TF-IDF)로 확인했을 때 최근접 사례 유사도가 최대 0.18이라 거의 같은 사건은 없다.
  대신 사건 상황(가정/영유아시설/학교·학원/복지시설/기타)이 test와 각 fold에 고르게 들어가도록 분할한다.

출력: datasets/panrye_split_v1.json
"""
import json
import re
from pathlib import Path

import numpy as np

BASE = Path(__file__).resolve().parent
CASES = BASE / "datasets/panrye_cases_v1.json"
REVIEW_XLSX = BASE / "analysis_output/panrye_label_review_검수완료.xlsx"
OUT = BASE / "datasets/panrye_split_v1.json"

LABELS = ["신체학대", "정서학대", "성학대", "방임"]
TEST_SIZE = 30
N_FOLDS = 5
SEED = 20260928
TRIALS = 30000

# 결론 문장을 읽고 확인해서 키워드 규칙이 틀린 사건만 고친다.
COURT_OVERRIDES = {
    22: {"정서학대"},  # '성적 수치심'은 정서적 학대의 결과 표현
    49: {"신체학대"},  # 결론에 유형 표시가 없고 신체 압박 사망 사건
    58: {"정서학대"},  # '정 서적'처럼 띄어 쓴 표기
}

# 법원 결론 문장은 그 사건에서 "유죄로 다투는 죄명"만 담아서, 사실관계에
# 분명히 적힌 신체적 접촉인데도 결론에는 안 나오는 경우가 있다. 실제 상담
# 맥락에서는 "이 재판에서 누가 유죄인지"가 아니라 "이 아동이 보호자에게
# 맞았는지"가 중요하므로, 사실관계를 다시 읽고 신체학대를 추가한다(사람이
# 직접 읽고 판단 — LLM으로 만들면 같은 LLM을 평가하는 순환 문제가 생긴다).
# 추가하지 않은 예외: P012(맞은 사람이 아동이 아니라 배우자), P102(때린
# 주체가 보호자가 아니라 또래 아동이고, 시설장의 책임은 방임임)는 그대로 둔다.
BODY_ABUSE_ADDITIONS = {
    17: "친모 본인이 A, B를 직접 때림(C는 목격만이라 정서학대도 별도로 유지)",
    40: "친부 본인이 꼬집고 폭행하고 깨묾(이 사건 유죄는 친모의 방임이지만 행위 자체는 존재)",
    57: "팔을 잡아끌고 연구실로 데려감",
    64: "원장 본인이 밀고, 뒷머리를 들어 밀어 고꾸라뜨리고, 턱을 강하게 잡아당김",
    65: "교사 본인이 엉덩이·얼굴·팔을 밀치고 잡아당김",
    69: "교사 본인이 리모컨으로 머리를 때림",
    85: "가해자 본인이 멱살·가슴을 잡고 흔듦",
    111: "발등으로 엉덩이를 걷어참",
}


def court_labels(case):
    t = re.sub(r"\s+", "", case["conclusion"])
    s = set()
    if re.search(r"신체적(?:,|·)?(?:정신적|정서적)?학대", t):
        s.add("신체학대")
    if re.search(r"정서적|정신적|정신건강", t):
        s.add("정서학대")
    if "성적학대" in t:
        s.add("성학대")
    if re.search(r"방임|유기", t):
        s.add("방임")
    s = COURT_OVERRIDES.get(case["id"], s)
    if case["id"] in BODY_ABUSE_ADDITIONS:
        s = s | {"신체학대"}
    return s


def setting_of(title):
    if re.search(r"어린이집|유치원|보육교사|아이돌보미|산후|신생아|산부인과", title):
        return "영유아시설"
    if re.search(r"학교|교사|학원|스포츠|축구|체육|코치|강사|감독|기숙사", title):
        return "학교·학원"
    if re.search(r"시설|보육원|공동생활|위탁", title):
        return "복지시설"
    if re.search(r"친모|친부|부모|계모|친언니|자녀|아동의 (?:어머니|아버지)|가정", title):
        return "가정"
    return "기타"


def load_ai_review():
    try:
        import openpyxl
    except ImportError:
        return {}
    if not REVIEW_XLSX.exists():
        return {}
    ws = openpyxl.load_workbook(REVIEW_XLSX)["검수표"]
    out = {}
    for r in ws.iter_rows(min_row=2, values_only=True):
        out[int(r[1][1:])] = [int(x) for x in r[4:8]]
    return out


def strata_matrix(rows):
    """분할 균형을 볼 특성: 4개 정답 + 복수유형 + 상황 5종."""
    settings = ["가정", "영유아시설", "학교·학원", "복지시설", "기타"]
    return np.array([[int(l in r["court"]) for l in LABELS]
                     + [int(len(r["court"]) > 1)]
                     + [int(r["setting"] == s) for s in settings] for r in rows], dtype=float)


def best_split(F, k_size, rng, trials):
    n = len(F)
    target = F.sum(0) * k_size / n
    best, best_cost = None, 1e9
    for _ in range(trials):
        idx = rng.choice(n, k_size, replace=False)
        cost = (np.abs(F[idx].sum(0) - target) / np.sqrt(target + 1)).sum()
        if cost < best_cost:
            best, best_cost = idx, cost
    return best


def main():
    cases = [c for c in json.load(open(CASES, encoding="utf-8")) if c["usable"]]
    review = load_ai_review()
    rows = []
    for c in cases:
        rows.append({
            "id": c["id"], "title": c["title"], "setting": setting_of(c["title"]),
            "court": sorted(court_labels(c), key=LABELS.index),
            "ai_review": [l for l, v in zip(LABELS, review.get(c["id"], [0] * 4)) if v],
        })
    rng = np.random.default_rng(SEED)
    F = strata_matrix(rows)
    test_idx = best_split(F, TEST_SIZE, rng, TRIALS)
    dev_idx = np.array([i for i in range(len(rows)) if i not in set(test_idx)])
    Fd = F[dev_idx]
    # dev를 5개 fold로: 남은 사례에서 fold 크기만큼씩 균형 있게 뽑는다.
    remaining = list(range(len(dev_idx)))
    folds = []
    for k in range(N_FOLDS):
        left = len(remaining)
        size = left // (N_FOLDS - k)
        sub = Fd[remaining]
        pick = best_split(sub, size, rng, 8000) if k < N_FOLDS - 1 else np.arange(left)
        chosen = [remaining[i] for i in pick]
        folds.append(chosen)
        remaining = [i for i in remaining if i not in set(chosen)]
    for i in test_idx:
        rows[i]["split"] = "test"
    for k, chosen in enumerate(folds):
        for j in chosen:
            rows[dev_idx[j]]["split"] = f"fold{k}"
    OUT.write_text(json.dumps({"seed": SEED, "labels": LABELS, "cases": rows}, ensure_ascii=False, indent=1), encoding="utf-8")

    def report(name, sel):
        sub = [rows[i] for i in sel]
        pos = [sum(l in r["court"] for r in sub) for l in LABELS]
        st = {s: sum(r["setting"] == s for r in sub) for s in ["가정", "영유아시설", "학교·학원", "복지시설", "기타"]}
        print(f"{name:6s} n={len(sub):3d} 양성 {dict(zip([l[:2] for l in LABELS], pos))} 복수 {sum(len(r['court'])>1 for r in sub)} {st}")
    report("전체", range(len(rows)))
    report("test", test_idx)
    for k, chosen in enumerate(folds):
        report(f"fold{k}", [dev_idx[j] for j in chosen])


if __name__ == "__main__":
    main()
