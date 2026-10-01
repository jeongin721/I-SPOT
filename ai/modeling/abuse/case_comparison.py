"""
같은 사례(case)의 승인된 회기들을 시간순으로 비교해서
회기별로 새로 나타난/반복되는/사라진 체크리스트 항목(Risk Factor)을 계산한다.

새 LLM 호출이나 재분석 없이, case_store에 이미 저장된
final_checklist만 비교하는 순수 데이터 작업이다.
"""

import json
from typing import Any, Dict, List, Optional, Set, Tuple

from ai.modeling.abuse import case_store


def _suggested_item_keys(
    checklist_json: str,
) -> Set[Tuple[str, str]]:
    checklist = json.loads(
        checklist_json or "{}"
    )

    return {
        (
            item["category"],
            item["item"],
        )
        for item in checklist.get(
            "checklist",
            [],
        )
        if item.get("suggested")
    }


def compare_case_sessions(
    case_id: str,
) -> List[Dict[str, Any]]:
    """
    승인된 회기만 시간순으로 비교한다.

    각 회기에 대해 "직전 승인된 회기" 대비:
    - new_items: 새로 나타난 항목
    - recurring_items: 이전에도 있었고 이번에도 있는 항목
    - resolved_items: 이전엔 있었는데 이번엔 사라진 항목

    첫 승인 회기는 비교 대상이 없으므로 전부 new_items로 표시한다.
    """

    approved_sessions = [
        session
        for session in case_store.list_sessions_for_case(
            case_id
        )
        if session["status"] == "approved"
    ]

    results: List[Dict[str, Any]] = []

    previous_keys: Set[Tuple[str, str]] = None

    for session in approved_sessions:
        current_keys = _suggested_item_keys(
            session["final_checklist"]
        )

        if previous_keys is None:
            new_items = current_keys
            recurring_items: Set[Tuple[str, str]] = set()
            resolved_items: Set[Tuple[str, str]] = set()
        else:
            new_items = current_keys - previous_keys
            recurring_items = current_keys & previous_keys
            resolved_items = previous_keys - current_keys

        results.append(
            {
                "session_id": session["session_id"],
                "created_at": session["created_at"],
                "approved_at": session["approved_at"],
                "new_items": sorted(new_items),
                "recurring_items": sorted(recurring_items),
                "resolved_items": sorted(resolved_items),
            }
        )

        previous_keys = current_keys

    return results


# ============================================================
# 종결 검토 참고자료 (LLM 없이 순수 데이터 요약)
# ============================================================
# "종결해도 되는가"는 AI가 판단할 문제가 아니라 상담사/사례회의가
# 공식 절차로 결정해야 하는 문제다(2026-10-01 범위 확정). 이 함수는
# 그 논의에 참고할 사실만 정리해서 보여준다 — LLM을 거치지 않고
# compare_case_sessions()가 이미 계산한 값만 그대로 집계하므로,
# 모든 문장이 DB에 저장된 사실과 1:1로 대응되고 환각 위험이 없다.

def summarize_case_trend(
    case_id: str,
) -> Optional[Dict[str, Any]]:
    """
    승인된 회기들의 추세를 요약한다. 승인된 회기가 없으면 None을 반환한다.

    consecutive_clean_sessions: 가장 최근 회기부터 거슬러 올라가며
    new_items/recurring_items가 둘 다 없는 회기가 몇 번 연속됐는지.
    active_items: 가장 최근 회기 기준으로 아직 남아 있는 항목
    (new_items + recurring_items).
    """

    comparisons = compare_case_sessions(
        case_id
    )

    if not comparisons:
        return None

    latest = comparisons[-1]

    active_items = sorted(
        set(latest["new_items"]) | set(latest["recurring_items"])
    )

    consecutive_clean_sessions = 0

    for entry in reversed(comparisons):
        if entry["new_items"] or entry["recurring_items"]:
            break
        consecutive_clean_sessions += 1

    if active_items:
        items_str = ", ".join(
            f"{category}::{item}"
            for category, item in active_items
        )
        summary_text = (
            f"총 {len(comparisons)}회기 중 가장 최근 회기(#{latest['session_id']})"
            f" 기준으로 아직 활성 상태인 항목이 있습니다: {items_str}."
        )
    elif consecutive_clean_sessions >= 1:
        summary_text = (
            f"총 {len(comparisons)}회기 중 최근 {consecutive_clean_sessions}회기"
            f" 연속으로 신규·반복 위험요인이 없습니다."
        )
    else:
        summary_text = (
            f"총 {len(comparisons)}회기 기록이 있습니다."
        )

    return {
        "case_id": case_id,
        "total_sessions": len(comparisons),
        "latest_session_id": latest["session_id"],
        "consecutive_clean_sessions": consecutive_clean_sessions,
        "active_items": active_items,
        "summary_text": summary_text,
        "disclaimer": (
            "이 요약은 종결 검토를 위한 참고 자료일 뿐이며, "
            "종결 여부는 상담사와 사례회의가 공식 절차에 따라 판단해야 합니다."
        ),
    }


# ============================================================
# 데모
# ============================================================

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print(
            "사용법: python3 case_comparison.py <case_id>"
        )
        sys.exit(1)

    case_id = sys.argv[1]

    comparisons = compare_case_sessions(
        case_id
    )

    if not comparisons:
        print(
            f"'{case_id}'에 승인된 회기가 없습니다."
        )
        sys.exit(0)

    for entry in comparisons:
        print(
            f"--- 회기 #{entry['session_id']} "
            f"(승인: {entry['approved_at']}) ---"
        )

        print(
            "  새로 나타남:",
            entry["new_items"] or "없음",
        )

        print(
            "  반복됨:",
            entry["recurring_items"] or "없음",
        )

        print(
            "  사라짐:",
            entry["resolved_items"] or "없음",
        )

        print()
