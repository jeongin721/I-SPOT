"""
같은 사례(case)의 승인된 회기들을 시간순으로 비교해서
회기별로 새로 나타난/반복되는/사라진 체크리스트 항목(Risk Factor)을 계산한다.

새 LLM 호출이나 재분석 없이, case_store에 이미 저장된
final_checklist만 비교하는 순수 데이터 작업이다.
"""

import json
from typing import Any, Dict, List, Set, Tuple

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
