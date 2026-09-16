"""
승인된 회기의 AI 체크리스트 초안(ai_checklist)과 상담사 최종본
(final_checklist)을 비교해서 상담사 피드백을 모델 개선에 활용한다.

지금 단계에서는 재학습할 만큼 데이터가 쌓이지 않았으므로,
두 가지 형태로 우선 활용한다.

1. 항목별 과다제안(false_positive)/과소제안(false_negative) 통계
   -> checklist_llm.py 프롬프트/후보 목록 튜닝 참고자료
2. 실제 교정 사례를 few-shot 힌트로 만들어 checklist_llm.py의
   시스템 프롬프트에 주입 -> 재학습 없이 즉시 반영되는
   in-context correction

데이터가 충분히 쌓이면(예: 항목당 수십 건 이상) 이 교정 데이터를
그대로 파인튜닝/프롬프트 최적화용 학습셋으로 전환할 수 있다.
"""

import json
from collections import defaultdict
from typing import Any, Dict, List

from ai.modeling.abuse import case_store


# ============================================================
# 1. 승인된 회기 로드
# ============================================================

def _load_approved_sessions() -> List[Dict[str, Any]]:
    conn = case_store._get_connection()

    rows = conn.execute(
        "SELECT * FROM sessions WHERE status = 'approved'"
    ).fetchall()

    conn.close()

    return [
        dict(row)
        for row in rows
    ]


# ============================================================
# 2. AI 초안 vs 최종본 교정 사례 수집
# ============================================================

def collect_checklist_corrections() -> List[Dict[str, Any]]:
    """
    승인된 회기마다 체크리스트 항목별로 AI 제안(suggested)과
    상담사 최종 확정이 다른 경우만 뽑는다.
    """

    corrections: List[Dict[str, Any]] = []

    for session in _load_approved_sessions():
        ai_checklist = json.loads(
            session["ai_checklist"] or "{}"
        )

        final_checklist = json.loads(
            session["final_checklist"] or "{}"
        )

        ai_items = {
            (
                item["category"],
                item["item"],
            ): item
            for item in ai_checklist.get(
                "checklist",
                [],
            )
        }

        final_items = {
            (
                item["category"],
                item["item"],
            ): item
            for item in final_checklist.get(
                "checklist",
                [],
            )
        }

        for key, final_item in final_items.items():
            ai_item = ai_items.get(key)

            if ai_item is None:
                continue

            ai_suggested = bool(
                ai_item.get("suggested")
            )

            final_suggested = bool(
                final_item.get("suggested")
            )

            if ai_suggested == final_suggested:
                continue

            correction_type = (
                "false_positive"
                if ai_suggested and not final_suggested
                else "false_negative"
            )

            corrections.append(
                {
                    "session_id": session["session_id"],
                    "case_id": session["case_id"],
                    "category": key[0],
                    "item": key[1],
                    "correction_type": correction_type,
                    "ai_evidence": ai_item.get(
                        "evidence",
                        [],
                    ),
                    "raw_text": session["raw_text"],
                }
            )

    return corrections


# ============================================================
# 3. 항목별 정확도 통계
# ============================================================

def summarize_item_accuracy() -> Dict[str, Dict[str, int]]:
    """
    (category::item) -> {"false_positive": n, "false_negative": n}
    """

    corrections = collect_checklist_corrections()

    stats: Dict[str, Dict[str, int]] = defaultdict(
        lambda: {
            "false_positive": 0,
            "false_negative": 0,
        }
    )

    for correction in corrections:
        key = (
            f"{correction['category']}::"
            f"{correction['item']}"
        )

        stats[key][
            correction["correction_type"]
        ] += 1

    return dict(stats)


# ============================================================
# 4. few-shot 교정 예시 추출
# ============================================================

def build_few_shot_correction_examples(
    max_examples: int = 5,
) -> List[Dict[str, Any]]:
    """
    checklist_llm.py 프롬프트에 넣을 최근 교정 사례를 뽑는다.
    같은 (category, item)은 최신 사례 하나만 남긴다.
    """

    corrections = collect_checklist_corrections()

    seen_keys = set()
    examples: List[Dict[str, Any]] = []

    for correction in sorted(
        corrections,
        key=lambda c: c["session_id"],
        reverse=True,
    ):
        key = (
            correction["category"],
            correction["item"],
        )

        if key in seen_keys:
            continue

        seen_keys.add(key)
        examples.append(correction)

        if len(examples) >= max_examples:
            break

    return examples


# ============================================================
# 5. 프롬프트 주입용 힌트 텍스트
# ============================================================

def build_correction_hint_text(
    max_examples: int = 5,
) -> str:
    """
    checklist_llm.py의 시스템 프롬프트에 그대로 삽입할 수 있는
    "과거 상담사 교정 이력" 힌트 텍스트를 만든다.

    교정 사례가 없으면 빈 문자열을 반환한다
    (프롬프트에 불필요한 섹션을 남기지 않기 위함).
    """

    examples = build_few_shot_correction_examples(
        max_examples
    )

    if not examples:
        return ""

    false_positive_lines = []
    false_negative_lines = []

    for example in examples:
        evidence_texts = [
            e.get("evidence", "")
            for e in example.get(
                "ai_evidence",
                [],
            )
        ]

        evidence_preview = (
            evidence_texts[0]
            if evidence_texts
            else "(근거 없음)"
        )

        line = (
            f"- {example['category']}::{example['item']} "
            f"(과거 근거 예: \"{evidence_preview}\")"
        )

        if example["correction_type"] == "false_positive":
            false_positive_lines.append(line)
        else:
            false_negative_lines.append(line)

    sections = []

    if false_positive_lines:
        sections.append(
            "다음 항목들은 과거 세션에서 AI가 제안했지만 "
            "상담사가 근거 부족으로 판단해 체크를 해제한 적이 있다. "
            "비슷한 수준으로 약하거나 간접적인 근거만으로는 "
            "섣불리 제안하지 않는다.\n"
            + "\n".join(false_positive_lines)
        )

    if false_negative_lines:
        sections.append(
            "다음 항목들은 과거 세션에서 AI가 놓쳤지만 "
            "상담사가 직접 추가한 적이 있다. "
            "비슷한 맥락의 원문 표현이 보이면 놓치지 않도록 "
            "주의 깊게 확인한다.\n"
            + "\n".join(false_negative_lines)
        )

    if not sections:
        return ""

    return (
        "\n[과거 상담사 교정 이력 참고]\n\n"
        + "\n\n".join(sections)
        + "\n"
    )


# ============================================================
# 6. 데모 / 리포트 출력
# ============================================================

if __name__ == "__main__":
    stats = summarize_item_accuracy()

    print("=" * 60)
    print("체크리스트 항목별 AI vs 상담사 교정 통계")
    print("=" * 60)

    if not stats:
        print(
            "승인된 회기 중 AI 초안을 수정한 사례가 없습니다."
        )
    else:
        for key, counts in sorted(
            stats.items(),
            key=lambda kv: sum(kv[1].values()),
            reverse=True,
        ):
            print(
                f"{key:<30} "
                f"과다제안(FP): {counts['false_positive']:>2}  "
                f"과소제안(FN): {counts['false_negative']:>2}"
            )

    print()
    print("=" * 60)
    print("프롬프트 주입용 힌트 텍스트")
    print("=" * 60)

    hint = build_correction_hint_text()

    print(
        hint
        if hint
        else "(교정 사례가 없어 힌트 없음)"
    )
