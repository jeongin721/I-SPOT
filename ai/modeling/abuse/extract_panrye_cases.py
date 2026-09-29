"""판례집('2020-2022 아동학대 사건 판례연구') 텍스트에서 사건별 사실관계를 뽑는다.

입력: data/ref_text/panrye.txt (PDF 추출본)
출력: datasets/panrye_cases_v1.json  (part/chapter/no/title/court/facts/conclusion/type_hint)

type_hint는 결론 문장에서 키워드로 뽑은 참고값이다. 정답 라벨이 아니라 검수 출발점이다.
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "data/ref_text/panrye.txt"
OUT = Path(__file__).resolve().parent / "datasets/panrye_cases_v1.json"

PART_RE = re.compile(r"^제([123])부\s{2}")
COURT_RE = re.compile(r"^\((.*(?:법원|지원).*판결)\)$")
HEAD_MARKERS = ("빦사실관계", "빦소송경과", "빦결론", "빦양형", "판결의 의의")


def clean(lines):
    out = []
    for l in lines:
        s = l.strip()
        if not s or s.startswith("=====[PAGE") or s == "2020-2022 아동학대 사건 판례연구":
            continue
        if PART_RE.match(s) or s in {"Ⅰ", "Ⅱ", "Ⅲ", "Ⅳ", "신", "체", "학", "대", "정", "서", "유", "기,", "방", "임", "사", "망", "건"}:
            continue
        if re.fullmatch(r"\d{1,3}", s):  # 쪽번호
            continue
        out.append(s)
    return " ".join(out)


def section(block, start, ends):
    m = re.search(start + r"(.*?)(?=" + "|".join(ends) + r"|$)", block, re.S)
    return re.sub(r"\s+", " ", m.group(1)).strip() if m else ""


def type_hint(text):
    hits = []
    for key, pat in [("신체학대", r"신체적[,·\s]*(?:정신적|정서적)?\s*학대|신체의 건강"), ("정서학대", r"정서적|정신적|정신 건강"),
                     ("성학대", r"성적 학대|성적 폭력|성적 수치심"), ("방임", "방임|보호, 양육"), ("유기", "유기"), ("무죄", "무죄")]:
        if re.search(pat, text):
            hits.append(key)
    return hits


def main():
    lines = SRC.read_text(encoding="utf8").split("\n")
    starts = [i for i, l in enumerate(lines) if l.strip() == "빦사실관계"]
    cases, part, prev_no, chapter = [], 1, 0, 0
    for n, i in enumerate(starts):
        # 앞쪽 12줄에서 번호/제목/법원 찾기
        head = [l.strip() for l in lines[max(0, i - 12):i]]
        court_idx = max((k for k, l in enumerate(head) if COURT_RE.match(l)), default=None)
        if court_idx is None:
            continue
        court = COURT_RE.match(head[court_idx]).group(1)
        # 제목은 법원줄 바로 앞(여러 줄일 수 있음), 번호는 그 앞 숫자 한 줄
        k = court_idx - 1
        title_parts = []
        while k >= 0 and not re.fullmatch(r"\d{1,3}", head[k]):
            title_parts.insert(0, head[k]); k -= 1
        no = int(head[k]) if k >= 0 else None
        title = " ".join(title_parts)
        for l in reversed(head[:court_idx]):
            m = PART_RE.match(l)
            if m:
                part = int(m.group(1)); break
        # 사건 번호는 장(章)마다 1부터 다시 시작하므로 (부, 번호)는 고유하지 않다 → 순번 id를 따로 둔다
        if no is not None and no <= prev_no:
            chapter += 1
        if chapter == 0:
            chapter = 1
        prev_no = no or prev_no
        end = starts[n + 1] - 12 if n + 1 < len(starts) else len(lines)
        block = clean(lines[i:end])
        facts = section(block, r"빦사실관계", ["빦소송경과", "빦결론"])
        concl = section(block, r"빦결론", ["빦양형", "판결의 의의", "빦판결"])
        cases.append({"id": len(cases) + 1, "part": part, "chapter": chapter, "no": no, "title": title, "court": court,
                      "facts": facts, "conclusion": concl, "type_hint": type_hint(concl + " " + title),
                      # 학대 성립을 인정한 형사 사례만 평가에 쓴다(3부 무죄·행정소송·절차 사건 제외)
                      "usable": part in (1, 2) and bool(facts) and "무죄" not in concl[:80]})
    OUT.write_text(json.dumps(cases, ensure_ascii=False, indent=1), encoding="utf8")
    print("cases:", len(cases), "usable:", sum(c["usable"] for c in cases))


if __name__ == "__main__":
    main()
