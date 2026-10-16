"""
같은 사례(case_id)의 "바로 이전 승인 회기"와 이번 회기를 비교해서,
세부유형별로 진술이 달라진 지점만 뽑는다("상담 요약" 화면의
"(안전관련) 조사 후 변화된 사항").

LLM을 쓰지 않는다 — 기계적인 텍스트 비교이고, 요약·해석이 아니라
"두 회차의 원문을 그대로 나란히 보여주는" 목적이라 LLM이 끼어들
이유가 없다(새 사실을 추가하거나 표현을 바꿔 쓸 위험만 생긴다).

세부유형(major_type, subtype)별로 "대표 진술"(evidence_strength가
가장 높은 것 — 동률이면 먼저 나온 것)을 비교 문구에 쓰지만, "바뀌었다"
판정 자체는 그 세부유형의 근거 전체(여러 개일 수 있음)를 서로 비교해서
내린다. 2026-10-14 실사용 테스트에서 발견: 같은 녹취를 다시 분석해도
2차 LLM이 같은 발화를 매번 똑같이 끊어서 인용하지 않는다(예:
"...이불 들추고"까지 인용했다가 다음 회차엔 "..."만 인용). 대표 진술
하나만 정확히 문자열 비교하면 이런 재인용 차이를 "진술이 바뀜"으로
오탐한다 — 그래서 "이번 세부유형에 저번과 충분히 겹치는 근거가 하나도
없을 때만" 바뀐 걸로 본다(difflib 문자열 유사도, LLM 아님).

"회차" 표시는 case_store에 아직 정식 회차 번호 필드가 없어서, 그
사례의 "승인된" 세션 개수로 근사한다(1번째 승인=1회차, 2번째=2회차,
...). 실제 상담 회차(오프라인 상담 등 음성 분석을 거치지 않은 회차
포함)와 다를 수 있다 — 그래서 화면에는 "근사치"임을 숨기지 않는다.
"""

import json
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional, Tuple


_STRENGTH_RANK = {"높음": 3, "중간": 2, "낮음": 1}

# 이 미만이면 "다른 진술"로 본다. 재인용 때문에 한쪽이 다른 쪽의 부분
# 문자열이기만 해도(접두사가 잘리는 경우 등) 유사도가 높게 나오므로,
# 느슨하게 잡아도 "진짜 다른 내용"은 대부분 이 밑으로 떨어진다.
_SAME_STATEMENT_SIMILARITY = 0.5


def _evidence_by_subtype(
    subtype_analysis: Optional[Dict[str, Any]],
) -> Dict[Tuple[str, str], List[Tuple[str, int]]]:
    """
    {(major_type, subtype): [(evidence_text, strength_rank), ...]}
    세부유형 안의 근거를 전부 모은다(강도 높은 순 정렬) — "대표 진술
    1개만 문자열 비교"로는 재인용 차이를 걸러낼 수 없어서다(모듈
    docstring 참고).
    """

    grouped: Dict[Tuple[str, str], List[Tuple[str, int]]] = {}

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

                grouped.setdefault(key, []).append(
                    (text, rank)
                )

    for key, items in grouped.items():
        items.sort(key=lambda item: item[1], reverse=True)

    return grouped


def _max_similarity(
    current_texts: List[str],
    previous_texts: List[str],
) -> float:
    best = 0.0

    for current_text in current_texts:
        for previous_text in previous_texts:
            ratio = SequenceMatcher(
                None, current_text, previous_text
            ).ratio()

            if ratio > best:
                best = ratio

    return best


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

    current_grouped = _evidence_by_subtype(
        current_subtype_analysis
    )
    previous_grouped = _evidence_by_subtype(
        previous_subtype_analysis
    )

    notes = []

    for key, current_items in current_grouped.items():
        previous_items = previous_grouped.get(key)

        if not previous_items:
            continue

        current_texts = [
            text for text, _rank in current_items
        ]
        previous_texts = [
            text for text, _rank in previous_items
        ]

        if (
            _max_similarity(
                current_texts, previous_texts
            )
            >= _SAME_STATEMENT_SIMILARITY
        ):
            continue

        current_top = current_items[0][0]
        previous_top = previous_items[0][0]

        notes.append(
            f'{previous_round_label} "{previous_top}"였던 '
            f'진술이 {current_round_label}에 "{current_top}"로 '
            f"바뀜. 두 진술 모두 원문대로 남김."
        )

    return notes
