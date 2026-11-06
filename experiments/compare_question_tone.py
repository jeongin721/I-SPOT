"""다음 상담 질문 말투 비교 — 순화 전(말투 원칙을 넣기 전 커밋) vs 지금 코드.

같은 사례 기록 · 확인할 사항 · 공식 근거를 두 버전의 질문 생성(generate_validated_questions)에 넣고,
버전마다 여러 번 돌려 통과한 질문과 탈락한 초안(사유)을 확인할 사항별로 나란히 보여 준다.

실행(OPENAI_API_KEY 필요, RAG_ANALYZER_MODEL 로 부른다):
    python experiments/compare_question_tone.py --runs 3 --out /tmp/question_tone.md
    python experiments/compare_question_tone.py --samples my_samples.json   # 실제 전사본(비식별한 뒤 보낸다)
    python experiments/compare_question_tone.py --dry-run                   # LLM 없이 입력만 확인

--samples JSON 은 POST /api/v1/rag/analyze 와 같은 칸을 쓴다:
    [{"name": "사례 A", "transcript": {"segments": [...]}, "session_no": 8,
      "previous_sessions": [...], "child_app_responses": [...]}]

- 내장 샘플은 지어낸 문장이라 비식별 없이 보낸다. --samples 는 rag.pipeline 과 같은 비식별(privacy_gateway)을
  거친 뒤에만 보내고, 비식별을 쓸 수 없으면 멈춘다.
- 확인할 사항 프롬프트는 두 버전이 같아서 샘플마다 한 번만 뽑아 두 버전에 같이 넣는다.
- 공식 근거: 벡터 색인이 있으면 업무 매뉴얼 면담 지침(load_interview_guidance), 없으면 아래 고정 문구.
- 보고서에 사례 원문이 들어갈 수 있다. 실제 전사본으로 만든 보고서는 저장소에 올리지 않는다.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path
from statistics import mean
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import rag.checklist_builder as after_module
from rag.case_context import build_case_records
from rag.config import ANALYZER_MODEL, VECTOR_DB_DIR

# 말투 순화(feat(rag): 다음 상담 질문을 아이에게 돌려 묻는 말투로 순화) 바로 전 커밋.
DEFAULT_BEFORE_REV = "ffcb17e"

FALLBACK_GUIDANCE = [
    {
        "content": (
            "아동 면담 시에는 개방형 질문을 먼저 사용하고, 특정 답을 암시하는 질문은 피한다. "
            "아동이 사용한 표현을 그대로 사용해 되묻고, 한 번에 한 가지만 묻는다."
        ),
        "metadata": {"source": "비교용 고정 문구", "screen_section": "상담·조사·사정", "chunk_id": "fixed-1"},
    }
]


def _segments(*rows: tuple[str, str, int, str]) -> dict[str, Any]:
    return {
        "segments": [
            {"segment_id": segment_id, "speaker": speaker, "start_ms": start_ms, "text": text}
            for segment_id, speaker, start_ms, text in rows
        ]
    }


# 지어낸 사례(실제 사례 아님). 유형별로 하나씩.
BUILTIN_SAMPLES: list[dict[str, Any]] = [
    {
        "name": "신체 — 통증 · 안전 계획",
        "session_no": 8,
        "transcript": _segments(
            ("s1", "CHILD", 3_000, "아빠가 때렸어요."),
            ("s2", "CHILD", 68_000, "등이랑 팔이 아파요."),
            ("s3", "CHILD", 160_000, "할머니한테는 아직 전화 안 했어요."),
        ),
        "previous_sessions": [
            {
                "session_no": 7,
                "summary": "아동이 학교 생활을 이야기함",
                "safety_plan": "위험할 때 할머니에게 연락하기로 함",
                "check_items": [{"item": "할머니 연락처를 아는지", "status": "open"}],
                "transcript": _segments(("p1", "CHILD", 10_000, "집에 가기 싫어요.")),
            }
        ],
        "child_app_responses": [
            {"response_id": "r1", "question": "요즘 기분은 어때?", "answer": "조금 무서워요", "answered_at": "2026-10-07"}
        ],
    },
    {
        "name": "방임 — 식사 · 혼자 있는 시간",
        "session_no": 3,
        "transcript": _segments(
            ("s1", "CHILD", 5_000, "어제 저녁은 안 먹었어요."),
            ("s2", "CHILD", 42_000, "밤에는 집에 혼자 있어요. 엄마는 늦게 와요."),
            ("s3", "CHILD", 95_000, "배고프면 라면 끓여 먹어요."),
        ),
        "previous_sessions": [
            {
                "session_no": 2,
                "summary": "아동이 학교 급식은 잘 먹는다고 함",
                "check_items": [{"item": "주말 식사를 어떻게 하는지", "status": "open"}],
                "transcript": _segments(("p1", "CHILD", 20_000, "주말이 제일 싫어요.")),
            }
        ],
        "child_app_responses": [],
    },
    {
        "name": "정서 — 소리 지름 · 등교 거부",
        "session_no": 5,
        "transcript": _segments(
            ("s1", "CHILD", 8_000, "엄마가 소리 질러요."),
            ("s2", "CHILD", 51_000, "나는 쓸모없다고 했어요."),
            ("s3", "CHILD", 120_000, "학교 가기 싫어요. 방에 혼자 있으면 괜찮아요."),
        ),
        "previous_sessions": [],
        "child_app_responses": [
            {"response_id": "r1", "question": "요즘 잠은 잘 자?", "answer": "잘 못 자요", "answered_at": "2026-10-20"}
        ],
    },
]


# ---------------------------------------------------------------------------
# 순화 전 모듈 불러오기
# ---------------------------------------------------------------------------


def load_before_module(rev: str):
    """git 의 rev 시점 rag/checklist_builder.py 를 rag 패키지 안 모듈로 불러온다(상대 import 그대로 쓴다)."""
    source = subprocess.run(
        ["git", "show", f"{rev}:rag/checklist_builder.py"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    name = "rag._checklist_builder_before"
    spec = importlib.util.spec_from_loader(name, loader=None)
    module = importlib.util.module_from_spec(spec)
    module.__package__ = "rag"
    sys.modules[name] = module  # pydantic 이 문자열 주석을 풀 때 모듈을 찾는다
    exec(compile(source, f"{rev}:rag/checklist_builder.py", "exec"), module.__dict__)  # noqa: S102
    return module


# ---------------------------------------------------------------------------
# 입력 준비
# ---------------------------------------------------------------------------


def prepare_inputs(sample: dict[str, Any], *, mask: bool) -> tuple[list[dict[str, Any]], dict[str, str]]:
    records = build_case_records(
        sample.get("transcript"),
        session_no=sample.get("session_no"),
        previous_sessions=sample.get("previous_sessions"),
        child_app_responses=sample.get("child_app_responses"),
    )
    records = [record for record in records if str(record.get("text") or "").strip()]
    if not mask:
        return records, {}
    from rag.privacy import mask_payload  # torch · transformers(NER) 필요

    masked, entity_map = mask_payload({"case": {record["ref"]: record.get("text", "") for record in records}})
    return [{**record, "text": masked["case"][record["ref"]]} for record in records], entity_map


def official_knowledge() -> tuple[list[dict[str, Any]], str]:
    # 색인 폴더가 없으면 검색을 부르지 않는다(Chroma 가 빈 폴더를 만들고, 임베딩 호출이 헛돈다).
    if VECTOR_DB_DIR.exists():
        guidance = after_module.load_interview_guidance()
        if guidance:
            return after_module.build_knowledge_entries([], [], guidance, []), "업무 매뉴얼 면담 지침(벡터 색인)"
    return after_module.build_knowledge_entries([], [], FALLBACK_GUIDANCE, []), "비교용 고정 문구(색인 없음)"


# ---------------------------------------------------------------------------
# 한 번 돌리기
# ---------------------------------------------------------------------------

_REVIEW_LINE = re.compile(r"^\[(\d+)\] \((\w+)\) (.*)$")
_REVIEW_FLAGS = ("leading", "presupposes", "age_inappropriate", "judgmental", "too_direct")


def run_once(module, check_items, records, knowledge) -> dict[str, Any]:
    """질문 생성 한 번. 통과한 질문 · 통계 · 초안마다 결과(통과 / 규칙 탈락 사유 / 검토 탈락 기준)."""
    calls: list[tuple[str, str, Any]] = []
    original = module._invoke

    def recording_invoke(schema, system_prompt, human_prompt):
        result = original(schema, system_prompt, human_prompt)
        calls.append((schema.__name__, human_prompt, result))
        return result

    module._invoke = recording_invoke
    try:
        accepted, stats = module.generate_validated_questions(check_items, records, knowledge)
    finally:
        module._invoke = original

    record_by_ref = {record["ref"]: record for record in records}
    knowledge_refs = {entry["ref"] for entry in knowledge}
    check_ids = {item["id"] for item in check_items}
    accepted_texts = {item["question"] for item in accepted}

    # 검토 결과: 검토 프롬프트의 "[번호] (대상) 질문" 줄로 번호 → 질문을 잇는다.
    review_flags: dict[str, list[str]] = {}
    for schema_name, human_prompt, result in calls:
        if schema_name != "QuestionReviews":
            continue
        numbered = {
            int(match.group(1)): match.group(3)
            for line in human_prompt.splitlines()
            if (match := _REVIEW_LINE.match(line))
        }
        for review in result.reviews:
            flags = [flag for flag in _REVIEW_FLAGS if getattr(review, flag, False)]
            if review.question_id in numbered and flags:
                review_flags[numbered[review.question_id]] = flags + ([review.reason] if review.reason else [])

    drafts = []
    for schema_name, _, result in calls:
        if schema_name != "QuestionDrafts":
            continue
        for draft in result.items:
            item = module._clean_draft(draft, set(record_by_ref), knowledge_refs, check_ids)
            text = draft.question.strip()
            if item is None:
                outcome = "탈락 · 근거 ID 부족"
            elif text in accepted_texts:
                outcome = "통과"
            elif text in review_flags:
                outcome = "검토 탈락 · " + ", ".join(review_flags[text])
            else:
                cited = " ".join(record_by_ref[ref].get("text", "") for ref in item["case_refs"])
                reason = module.rule_check(item, cited)
                outcome = f"규칙 탈락 · {reason}" if reason else "탈락 · 개수 초과 · 중복 · 검토 누락"
            drafts.append(
                {
                    "question": text,
                    "audience": draft.audience,
                    "check_item_id": draft.check_item_id if draft.check_item_id in check_ids else None,
                    "outcome": outcome,
                }
            )
    return {"accepted": accepted, "stats": stats, "drafts": drafts}


# ---------------------------------------------------------------------------
# 보고서
# ---------------------------------------------------------------------------


def _summary(runs: list[dict[str, Any]]) -> dict[str, float]:
    counselor = [[item for item in run["accepted"] if item["audience"] == "counselor"] for run in runs]
    lengths = [len(item["question"]) for items in counselor for item in items]
    return {
        "상담사용 통과(평균)": mean(len(items) for items in counselor),
        "규칙 탈락(평균)": mean(run["stats"]["rule_rejected"] for run in runs),
        "검토 탈락(평균)": mean(run["stats"]["review_rejected"] for run in runs),
        "생성 횟수(평균)": mean(run["stats"]["rounds"] for run in runs),
        "상담사용 질문 길이(평균 글자)": mean(lengths) if lengths else 0,
    }


def render_sample(sample, check_items, results, entity_map, restore) -> str:
    def show(text: str) -> str:
        return restore(text, entity_map) if entity_map else text

    lines = [f"## {sample['name']}", "", "### 확인할 사항(두 버전 공통)", ""]
    lines += [f"- `{item['id']}` {show(item['item'])}" for item in check_items] or ["- (없음)"]

    lines += ["", "### 요약", "", "| | 순화 전 | 순화 후 |", "|---|---|---|"]
    before, after = _summary(results["before"]), _summary(results["after"])
    lines += [f"| {key} | {before[key]:.1f} | {after[key]:.1f} |" for key in before]

    groups = [(item["id"], show(item["item"])) for item in check_items] + [(None, "확인할 사항 없음 · 아이 앱")]
    lines += ["", "### 통과한 질문(확인할 사항별, 모든 회차)", ""]
    for check_id, title in groups:
        lines += [f"**{check_id or '-'} {title}**", ""]
        for version, label in (("before", "순화 전"), ("after", "순화 후")):
            questions = [
                f"{show(item['question'])} `{item['audience']}`"
                for run in results[version]
                for item in run["accepted"]
                if item.get("check_item_id") == check_id
            ]
            lines.append(f"- {label}: " + (" / ".join(questions) if questions else "(없음)"))
        lines.append("")

    lines += ["### 탈락한 초안", ""]
    for version, label in (("before", "순화 전"), ("after", "순화 후")):
        rejected = [
            f"  - {show(draft['question'])} — {draft['outcome']}"
            for run in results[version]
            for draft in run["drafts"]
            if draft["outcome"] != "통과"
        ]
        lines += [f"- {label}"] + (rejected or ["  - (없음)"])
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 진입점
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--samples", type=Path, help="비교할 전사본 JSON(없으면 내장 샘플 3개)")
    parser.add_argument("--runs", type=int, default=3, help="버전마다 질문 생성을 돌릴 횟수")
    parser.add_argument("--before-rev", default=DEFAULT_BEFORE_REV, help="순화 전 코드의 git 커밋")
    parser.add_argument("--out", type=Path, help="보고서(Markdown)를 쓸 파일. 없으면 화면에만 출력")
    parser.add_argument("--dry-run", action="store_true", help="LLM 을 부르지 않고 입력만 출력")
    args = parser.parse_args()

    samples = json.loads(args.samples.read_text(encoding="utf-8")) if args.samples else BUILTIN_SAMPLES
    for index, sample in enumerate(samples, start=1):
        sample.setdefault("name", f"샘플 {index}")
    mask = args.samples is not None

    before_module = load_before_module(args.before_rev)
    if before_module.CHECK_ITEM_SYSTEM_PROMPT != after_module.CHECK_ITEM_SYSTEM_PROMPT:
        sys.exit("확인할 사항 프롬프트가 두 버전에서 다릅니다. 이 스크립트는 같은 확인할 사항을 두 버전에 넣습니다.")

    knowledge, knowledge_source = official_knowledge()
    from rag.privacy import restore

    report = [
        "# 다음 상담 질문 말투 비교",
        "",
        f"- 순화 전: `{args.before_rev}` · 순화 후: 지금 작업 트리",
        f"- 모델: `{ANALYZER_MODEL}` · 버전마다 {args.runs}회",
        f"- 공식 근거: {knowledge_source}",
        f"- 샘플: {'--samples ' + str(args.samples) + ' (비식별 후 전송)' if mask else '내장 샘플(지어낸 사례)'}",
        "",
    ]

    for sample in samples:
        records, entity_map = prepare_inputs(sample, mask=mask)
        if args.dry_run:
            print(f"== {sample['name']}")
            print(after_module._case_text(records))
            print(after_module._knowledge_text(knowledge))
            continue

        try:
            check_items, _ = after_module.extract_check_items(records, knowledge)
        except Exception as error:  # noqa: BLE001 — 확인할 사항 없이도 질문은 비교한다
            print(f"[{sample['name']}] 확인할 사항 추출 실패: {type(error).__name__}", file=sys.stderr)
            check_items = []

        results: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for version, module in (("before", before_module), ("after", after_module)):
            for run in range(1, args.runs + 1):
                print(f"[{sample['name']}] {version} {run}/{args.runs}", file=sys.stderr)
                try:
                    results[version].append(run_once(module, check_items, records, knowledge))
                except Exception as error:  # noqa: BLE001 — 한 회차가 실패해도 나머지로 비교한다
                    print(f"  실패: {type(error).__name__}: {error}", file=sys.stderr)
            if not results[version]:
                sys.exit(f"[{sample['name']}] {version} 질문 생성이 모두 실패했습니다(OPENAI_API_KEY · 네트워크 확인).")

        report += [render_sample(sample, check_items, results, entity_map, restore), ""]

    if args.dry_run:
        return
    text = "\n".join(report)
    print(text)
    if args.out:
        args.out.write_text(text, encoding="utf-8")
        print(f"\n보고서: {args.out}", file=sys.stderr)


if __name__ == "__main__":
    main()
