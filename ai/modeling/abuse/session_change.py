"""
같은 사례(case_id)의 "바로 이전 승인 회기"와 이번 회기를 비교해서,
세부유형별로 진술이 달라진 지점만 뽑는다("상담 요약" 화면의
"(안전관련) 조사 후 변화된 사항").

LLM을 쓰지 않는다 — 기계적인 텍스트 비교이고, 요약·해석이 아니라
"두 회차의 원문을 그대로 나란히 보여주는" 목적이라 LLM이 끼어들
이유가 없다(새 사실을 추가하거나 표현을 바꿔 쓸 위험만 생긴다).

세부유형(major_type, subtype) 조합마다 "대표 진술 1개"만 비교한다
(evidence_strength가 가장 높은 것 — 동률이면 먼저 나온 것). 같은
세부유형 안에 근거가 여러 개 있어도 전부 비교하면 소음이 너무 커진다.

"회차" 표시는 case_store에 아직 정식 회차 번호 필드가 없어서, 그
사례의 "승인된" 세션 개수로 근사한다(1번째 승인=1회차, 2번째=2회차,
...). 실제 상담 회차(오프라인 상담 등 음성 분석을 거치지 않은 회차
포함)와 다를 수 있다 — 그래서 화면에는 "근사치"임을 숨기지 않는다.
"""

import json
from typing import Any, Dict, List, Optional, Tuple


_STRENGTH_RANK = {"높음": 3, "중간": 2, "낮음": 1}


def _top_evidence_by_subtype(
    subtype_analysis: Optional[Dict[str, Any]],
) -> Dict[Tuple[str, str], str]:
    best: Dict[Tuple[str, str], Tuple[str, int]] = {}

    for major_result in (subtype_analysis or {}).get(
        "results", []
    ):
        major_type = major_result.get("major_type")

        for subtype_entry in major_result.get(
            "subtypes", []
        ):
            subtype_name = subtype_entry.get("type")
            key = (major_type, subtype_name)

            for evidence in subtype_entry.get(
                "evidences", []
            ):
                text = (
                    evidence.get("evidence") or ""
                ).strip()

                if not text:
                    continue

                rank = _STRENGTH_RANK.get(
                    evidence.get("evidence_strength"), 0
                )

                current = best.get(key)

                if current is None or rank > current[1]:
                    best[key] = (text, rank)

    return {
        key: text
        for key, (text, rank) in best.items()
    }


def build_session_change_notes(
    current_subtype_analysis: Optional[Dict[str, Any]],
    previous_session_row: Optional[Dict[str, Any]],
    previous_round_label: str,
    current_round_label: str,
) -> List[str]:
    """
    previous_session_row: case_store.list_sessions_for_case()가 돌려주는
    sqlite Row(dict)를 그대로 받는다 — subtype_analysis 컬럼은 JSON
    문자열로 저장돼 있어 여기서 파싱한다.
    """

    if not previous_session_row:
        return []

    try:
        previous_subtype_analysis = json.loads(
            previous_session_row.get("subtype_analysis")
            or "{}"
        )
    except (TypeError, ValueError):
        return []

    current_map = _top_evidence_by_subtype(
        current_subtype_analysis
    )
    previous_map = _top_evidence_by_subtype(
        previous_subtype_analysis
    )

    notes = []

    for key, current_text in current_map.items():
        previous_text = previous_map.get(key)

        if previous_text is None:
            continue

        if previous_text == current_text:
            continue

        notes.append(
            f'{previous_round_label} "{previous_text}"였던 '
            f'진술이 {current_round_label}에 "{current_text}"로 '
            f"바뀜. 두 진술 모두 원문대로 남김."
        )

    return notes
