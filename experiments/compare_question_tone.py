"""다음 상담 질문 말투 비교 — 순화 전(main, 말투 원칙을 넣기 전) vs 지금 코드.

같은 입력을 두 버전의 질문 생성기에 넣고, 버전마다 여러 번 돌려 통과한 질문과 탈락한 초안을 나란히 보여 준다.

비교 대상(--target):
- screen(기본): 화면 '추가 질문' AI 초안 — ai/modeling/abuse/followup_question_llm.py(#118). Backend 가 실제로 쓰는 경로.
  입력은 이번 회차 아동 발화를 '아동 진술' 줄로 그대로 넣는다(실제 분석은 진술 요지를 LLM 이 먼저 정리한다).
- rag: rag 다음 상담 체크리스트 질문 — rag/checklist_builder.py(with_questions=True 일 때만. Backend 는 끈다).
  같은 사례 기록 · 확인할 사항 · 공식 근거를 두 버전에 넣는다. 확인할 사항은 샘플마다 한 번만 뽑는다.
- all: 둘 다.

실행(OPENAI_API_KEY 필요):
    python experiments/compare_question_tone.py --runs 3 --out /tmp/question_tone.md
    python experiments/compare_question_tone.py --target all --runs 3
    python experiments/compare_question_tone.py --samples my_samples.json   # 실제 전사본(비식별한 뒤 보낸다)
    python experiments/compare_question_tone.py --dry-run                   # LLM 없이 입력만 확인

--samples JSON 은 POST /api/v1/rag/analyze 와 같은 칸에 나이대를 더한다:
    [{"name": "사례 A", "child_age_band": "만 10~13세", "transcript": {"segments": [...]}, "session_no": 8,
      "previous_sessions": [...], "child_app_responses": [...]}]

- 내장 샘플은 지어낸 문장이라 비식별 없이 보낸다. --samples 는 서비스와 같은 비식별(screen: mask_for_outbound,
  rag: rag.privacy.mask_payload)을 거친 뒤에만 보내고, 비식별을 쓸 수 없으면 멈춘다(torch · transformers 필요).
- rag 의 공식 근거: 벡터 색인이 있으면 업무 매뉴얼 면담 지침(load_interview_guidance), 없으면 아래 고정 문구.
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
from functools import partial
from pathlib import Path
from statistics import mean
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# 말투 순화를 넣기 전 main 머리(Merge pull request #156).
DEFAULT_BEFORE_REV = "f777dcd"

SCREEN_MODULE_PATH = "ai/modeling/abuse/followup_question_llm.py"
RAG_MODULE_PATH = "rag/checklist_builder.py"

FALLBACK_GUIDANCE = [
    {
        "content": (
            "아동 면담 시에는 개방형 질문을 먼저 사용하고, 특정 답을 암시하는 질문은 피한다. "
            "아동이 사용한 표현을 그대로 사용해 되묻고, 한 번에 한 가지만 묻는다."
        ),
        "metadata": {"source": "비교용 고정 문구", "screen_section": "상담·조사·사정", "chunk_id": "fixed-1"},
    }
]

VERSIONS = (("before", "순화 전"), ("after", "순화 후"))


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
        "child_age_band": "만 10~13세",
        "session_no": 8,
        "transcript": _segments(
            ("seg_001", "CHILD", 3_000, "아빠가 때렸어요."),
            ("seg_002", "CHILD", 68_000, "등이랑 팔이 아파요."),
            ("seg_003", "CHILD", 160_000, "할머니한테는 아직 전화 안 했어요."),
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
        "child_age_band": "만 6~9세",
        "session_no": 3,
        "transcript": _segments(
            ("seg_001", "CHILD", 5_000, "어제 저녁은 안 먹었어요."),
            ("seg_002", "CHILD", 42_000, "밤에는 집에 혼자 있어요. 엄마는 늦게 와요."),
            ("seg_003", "CHILD", 95_000, "배고프면 라면 끓여 먹어요."),
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
        "child_age_band": "만 10~13세",
        "session_no": 5,
        "transcript": _segments(
            ("seg_001", "CHILD", 8_000, "엄마가 소리 질러요."),
            ("seg_002", "CHILD", 51_000, "나는 쓸모없다고 했어요."),
            ("seg_003", "CHILD", 120_000, "학교 가기 싫어요. 방에 혼자 있으면 괜찮아요."),
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


def load_module_at_rev(rev: str, path: str, package: str):
    """git 의 rev 시점 파일을 package 안 모듈로 불러온다(상대 · 절대 import 를 그대로 쓴다)."""
    source = subprocess.run(
        ["git", "show", f"{rev}:{path}"], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout
    name = f"{package}._before_{Path(path).stem}"
    spec = importlib.util.spec_from_loader(name, loader=None)
    module = importlib.util.module_from_spec(spec)
    module.__package__ = package
    sys.modules[name] = module  # pydantic 이 문자열 주석을 풀 때 모듈을 찾는다
    exec(compile(source, f"{rev}:{path}", "exec"), module.__dict__)  # noqa: S102
    return module


# ---------------------------------------------------------------------------
# screen — 화면 추가 질문(#118)
# ---------------------------------------------------------------------------


def screen_input(sample: dict[str, Any], *, mask: bool) -> tuple[str, list[dict[str, Any]], dict[str, str]]:
    """(마스킹한 입력 글, 원본 발화 목록, 되돌릴 표). 이번 회차 아동 발화를 '아동 진술' 줄로 넣는다."""
    from ai.modeling.abuse.followup_question_llm import SPLIT_MARKER

    segments = [segment for segment in (sample.get("transcript") or {}).get("segments", []) if segment.get("text")]
    lines = [
        f"- [{segment['segment_id']}] (아동 진술) {segment['text']}"
        for segment in segments
        if segment.get("speaker") == "CHILD"
    ]
    text = ("\n".join(lines) or "없음") + SPLIT_MARKER + "없음" + SPLIT_MARKER + "없음"
    if not mask:
        return text, segments, {}
    # torch · transformers(NER) 필요
    from ai.modeling.abuse.privacy_gateway import mask_for_outbound

    masked, entity_map = mask_for_outbound(text)
    return masked, segments, entity_map


def run_screen_once(module, client, model: str, text: str, segments, age_band: str) -> dict[str, Any]:
    """질문 생성 한 번. LLM 이 낸 초안 그대로(raw)와 코드 검사를 통과한 질문(accepted)."""
    import ai.modeling.abuse.second_stage_llm as llm

    raw: list[Any] = []
    original = llm._call_llm_with_retry

    def recording_call(**kwargs):
        result = original(**kwargs)
        if isinstance(result, dict) and isinstance(result.get("questions"), list):
            raw.extend(result["questions"])
        return result

    llm._call_llm_with_retry = recording_call
    try:
        accepted = module.generate_followup_questions_from_masked_text(
            client=client, model=model, masked_combined_text=text, segments=segments, age_band=age_band
        )
    finally:
        llm._call_llm_with_retry = original

    kept = {item["text"] for item in accepted}
    drafts = []
    for item in raw:
        question = " ".join(str(item.get("text") or "").split()) if isinstance(item, dict) else ""
        if question:
            drafts.append({"question": question, "outcome": "통과" if question in kept else "코드 검사 탈락"})
    return {"accepted": accepted, "drafts": drafts}


def render_screen(results: dict[str, list[dict[str, Any]]], show) -> list[str]:
    lines = ["### 화면 추가 질문(#118)", "", "| | 순화 전 | 순화 후 |", "|---|---|---|"]
    summary = {}
    for version, _ in VERSIONS:
        runs = results[version]
        lengths = [len(item["text"]) for run in runs for item in run["accepted"]]
        summary[version] = {
            "통과(평균)": mean(len(run["accepted"]) for run in runs),
            "코드 검사 탈락(평균)": mean(
                sum(draft["outcome"] != "통과" for draft in run["drafts"]) for run in runs
            ),
            "질문 길이(평균 글자)": mean(lengths) if lengths else 0,
        }
    lines += [f"| {key} | {summary['before'][key]:.1f} | {summary['after'][key]:.1f} |" for key in summary["before"]]
    for version, label in VERSIONS:
        lines += ["", f"**{label}**", ""]
        for index, run in enumerate(results[version], start=1):
            lines.append(f"- {index}회차")
            lines += [f"  - {show(item['text'])}" for item in run["accepted"]] or ["  - (통과한 질문 없음)"]
            lines += [
                f"  - ~~{show(draft['question'])}~~ — {draft['outcome']}"
                for draft in run["drafts"]
                if draft["outcome"] != "통과"
            ]
    return lines


# ---------------------------------------------------------------------------
# rag — 다음 상담 체크리스트 질문
# ---------------------------------------------------------------------------


def rag_input(sample: dict[str, Any], *, mask: bool) -> tuple[list[dict[str, Any]], dict[str, str]]:
    from rag.case_context import build_case_records

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


def rag_knowledge(rag_module) -> tuple[list[dict[str, Any]], str]:
    from rag.config import VECTOR_DB_DIR

    # 색인 폴더가 없으면 검색을 부르지 않는다(Chroma 가 빈 폴더를 만들고, 임베딩 호출이 헛돈다).
    if VECTOR_DB_DIR.exists():
        guidance = rag_module.load_interview_guidance()
        if guidance:
            return rag_module.build_knowledge_entries([], [], guidance, []), "업무 매뉴얼 면담 지침(벡터 색인)"
    return rag_module.build_knowledge_entries([], [], FALLBACK_GUIDANCE, []), "비교용 고정 문구(색인 없음)"


_REVIEW_LINE = re.compile(r"^\[(\d+)\] \((\w+)\) (.*)$")
_REVIEW_FLAGS = ("leading", "presupposes", "age_inappropriate", "judgmental", "too_direct")


def run_rag_once(module, check_items, records, knowledge) -> dict[str, Any]:
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
            drafts.append({"question": text, "outcome": outcome})
    return {"accepted": accepted, "stats": stats, "drafts": drafts}


def _rag_summary(runs: list[dict[str, Any]]) -> dict[str, float]:
    counselor = [[item for item in run["accepted"] if item["audience"] == "counselor"] for run in runs]
    lengths = [len(item["question"]) for items in counselor for item in items]
    return {
        "상담사용 통과(평균)": mean(len(items) for items in counselor),
        "규칙 탈락(평균)": mean(run["stats"]["rule_rejected"] for run in runs),
        "검토 탈락(평균)": mean(run["stats"]["review_rejected"] for run in runs),
        "생성 횟수(평균)": mean(run["stats"]["rounds"] for run in runs),
        "상담사용 질문 길이(평균 글자)": mean(lengths) if lengths else 0,
    }


def render_rag(check_items, results, show) -> list[str]:
    lines = ["### rag 다음 상담 체크리스트 질문", "", "확인할 사항(두 버전 공통):", ""]
    lines += [f"- `{item['id']}` {show(item['item'])}" for item in check_items] or ["- (없음)"]

    lines += ["", "| | 순화 전 | 순화 후 |", "|---|---|---|"]
    before, after = _rag_summary(results["before"]), _rag_summary(results["after"])
    lines += [f"| {key} | {before[key]:.1f} | {after[key]:.1f} |" for key in before]

    groups = [(item["id"], show(item["item"])) for item in check_items] + [(None, "확인할 사항 없음 · 아이 앱")]
    lines += ["", "통과한 질문(확인할 사항별, 모든 회차):", ""]
    for check_id, title in groups:
        lines += [f"**{check_id or '-'} {title}**", ""]
        for version, label in VERSIONS:
            questions = [
                f"{show(item['question'])} `{item['audience']}`"
                for run in results[version]
                for item in run["accepted"]
                if item.get("check_item_id") == check_id
            ]
            lines.append(f"- {label}: " + (" / ".join(questions) if questions else "(없음)"))
        lines.append("")

    lines += ["탈락한 초안:", ""]
    for version, label in VERSIONS:
        rejected = [
            f"  - {show(draft['question'])} — {draft['outcome']}"
            for run in results[version]
            for draft in run["drafts"]
            if draft["outcome"] != "통과"
        ]
        lines += [f"- {label}"] + (rejected or ["  - (없음)"])
    return lines


# ---------------------------------------------------------------------------
# 진입점
# ---------------------------------------------------------------------------


def _repeat(name: str, runs: int, call) -> list[dict[str, Any]]:
    results = []
    for run in range(1, runs + 1):
        print(f"[{name}] {run}/{runs}", file=sys.stderr)
        try:
            results.append(call())
        except Exception as error:  # noqa: BLE001 — 한 회차가 실패해도 나머지로 비교한다
            print(f"  실패: {type(error).__name__}: {error}", file=sys.stderr)
    if not results:
        sys.exit(f"[{name}] 모두 실패했습니다(OPENAI_API_KEY · 네트워크 확인).")
    return results


def _restorer(entity_map: dict[str, str]):
    """보고서에 쓸 때 비식별 토큰을 원문으로 되돌리는 함수."""
    if not entity_map:
        return lambda value: value
    from ai.modeling.abuse.pii_masking import restore_pii

    return lambda value: restore_pii(value, entity_map)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--target", choices=("screen", "rag", "all"), default="screen", help="비교할 질문 생성기")
    parser.add_argument("--samples", type=Path, help="비교할 전사본 JSON(없으면 내장 샘플 3개)")
    parser.add_argument("--runs", type=int, default=3, help="버전마다 질문 생성을 돌릴 횟수")
    parser.add_argument("--before-rev", default=DEFAULT_BEFORE_REV, help="순화 전 코드의 git 커밋")
    parser.add_argument("--model", help="screen 질문 생성 모델(기본: followup_question_llm.DEFAULT_MODEL)")
    parser.add_argument("--out", type=Path, help="보고서(Markdown)를 쓸 파일. 없으면 화면에만 출력")
    parser.add_argument("--dry-run", action="store_true", help="LLM 을 부르지 않고 입력만 출력")
    args = parser.parse_args()

    samples = json.loads(args.samples.read_text(encoding="utf-8")) if args.samples else BUILTIN_SAMPLES
    for index, sample in enumerate(samples, start=1):
        sample.setdefault("name", f"샘플 {index}")
    mask = args.samples is not None
    targets = ("screen", "rag") if args.target == "all" else (args.target,)

    header = [
        "# 다음 상담 질문 말투 비교",
        "",
        f"- 순화 전: `{args.before_rev}` · 순화 후: 지금 작업 트리 · 버전마다 {args.runs}회",
        f"- 샘플: {'--samples ' + str(args.samples) + ' (비식별 후 전송)' if mask else '내장 샘플(지어낸 사례)'}",
    ]

    if "screen" in targets:
        import ai.modeling.abuse.followup_question_llm as screen_after

        screen_before = load_module_at_rev(args.before_rev, SCREEN_MODULE_PATH, "ai.modeling.abuse")
        screen_model = args.model or screen_after.DEFAULT_MODEL
        header.append(f"- 화면 추가 질문(#118) 모델: `{screen_model}` — 입력은 아동 발화를 '아동 진술' 줄로 그대로 넣음")
    if "rag" in targets:
        import rag.checklist_builder as rag_after
        from rag.config import ANALYZER_MODEL

        rag_before = load_module_at_rev(args.before_rev, RAG_MODULE_PATH, "rag")
        if rag_before.CHECK_ITEM_SYSTEM_PROMPT != rag_after.CHECK_ITEM_SYSTEM_PROMPT:
            sys.exit("확인할 사항 프롬프트가 두 버전에서 다릅니다. 이 스크립트는 같은 확인할 사항을 두 버전에 넣습니다.")
        knowledge, knowledge_source = rag_knowledge(rag_after)
        header.append(f"- rag 모델: `{ANALYZER_MODEL}` · 공식 근거: {knowledge_source}")

    client = None
    if "screen" in targets and not args.dry_run:
        from openai import OpenAI

        client = OpenAI()

    report = [*header, ""]
    for sample in samples:
        section = [f"## {sample['name']}", ""]
        # screen 과 rag 는 따로 가린다(같은 토큰이 다른 원문일 수 있어 표를 나눠 둔다).
        entity_maps: dict[str, dict[str, str]] = {"screen": {}, "rag": {}}

        if "screen" in targets:
            text, segments, entity_maps["screen"] = screen_input(sample, mask=mask)
            age_band = sample.get("child_age_band") or "알 수 없음"
            if args.dry_run:
                print(f"== {sample['name']} · screen ({age_band})\n{text.split(screen_after.SPLIT_MARKER)[0]}")
            else:
                screen_results = {
                    version: _repeat(
                        f"{sample['name']} · screen · {version}",
                        args.runs,
                        partial(run_screen_once, module, client, screen_model, text, segments, age_band),
                    )
                    for version, module in (("before", screen_before), ("after", screen_after))
                }

        if "rag" in targets:
            records, entity_maps["rag"] = rag_input(sample, mask=mask)
            if args.dry_run:
                print(f"== {sample['name']} · rag\n{rag_after._case_text(records)}\n{rag_after._knowledge_text(knowledge)}")
            else:
                try:
                    check_items, _ = rag_after.extract_check_items(records, knowledge)
                except Exception as error:  # noqa: BLE001 — 확인할 사항 없이도 질문은 비교한다
                    print(f"[{sample['name']}] 확인할 사항 추출 실패: {type(error).__name__}", file=sys.stderr)
                    check_items = []
                rag_results = defaultdict(list)
                for version, module in (("before", rag_before), ("after", rag_after)):
                    rag_results[version] = _repeat(
                        f"{sample['name']} · rag · {version}",
                        args.runs,
                        partial(run_rag_once, module, check_items, records, knowledge),
                    )

        if args.dry_run:
            continue

        if "screen" in targets:
            section += [*render_screen(screen_results, _restorer(entity_maps["screen"])), ""]
        if "rag" in targets:
            section += [*render_rag(check_items, rag_results, _restorer(entity_maps["rag"])), ""]
        report += section

    if args.dry_run:
        return
    text = "\n".join(report)
    print(text)
    if args.out:
        args.out.write_text(text, encoding="utf-8")
        print(f"\n보고서: {args.out}", file=sys.stderr)


if __name__ == "__main__":
    main()
