"""
1차가 잡은 유형에 '함께 나오기 쉬운 유형' 을 더해 2차에 묻는다(2026-11-11, 시연 전 김수아 5회차).

[왜] 2차 세부유형 분석(second_stage_llm.analyze_subtypes)은 1차가 잡은 유형만 본다. 1차가 '아빠가 화나서 컵을 던졌어요 ·
심장이 막 뛰었어요 · 아빠 올 시간쯤 배가 아파요' 를 신체학대로만 잡고 정서학대를 놓치자, 2차는 신체학대만 검토해 근거 0건
('벽에 던짐' 은 아이에게 직접 한 행위가 아니다 — 맞는 판단)을 냈고, 근거 없는 유형 빼기로 신체학대마저 빠져 학대 신호 확인이
네 유형 모두 비었다. 같은 화면의 안전 플래그(S7 · S8)는 원문 전체를 보는 별도 LLM 이라 잡았다.

[규칙] 1차가 신체학대를 잡으면 정서학대도 2차에 묻는다(신체 · 정서는 함께 나오는 경우가 많고, 정서가 가장 자주 빠진다).
더해 물은 정서학대는 **신체학대 근거를 2차가 찾지 못했고, 정서학대 근거가 원문 줄에 이어졌을 때만** 탐지로 올린다.
아니면 그 유형의 2차 결과를 버린다 — 1차 탐지가 아닌 유형을 근거 없이 띄우지 않는다(05_RULES §1).

[왜 좁혔나 — 2026-11-11 실측] AI-Hub 검증 360회차(1차 + 2차 근거, 1회)에서 '신체학대를 잡으면 늘 정서학대도 올림' 은
정서학대를 5회차 더했는데 정답은 1회차뿐이었고(Macro F1 0.8512 → 0.8497), 5회차 모두 신체학대 근거가 이미 찾아진
회차였다. 김수아 5회차처럼 '1차는 신체학대인데 2차가 신체 근거를 못 찾은' 경우에만 올리면 이 360회차에서 더해지는
회차는 0이다.

표준 라이브러리만 쓴다(backend/tests 에서 시험).
"""

from typing import Any, Dict, List, Tuple

#: 1차가 앞 유형을 잡으면 2차에 함께 묻는 유형.
COMPANIONS: Dict[str, List[str]] = {"신체학대": ["정서학대"]}

#: major_types 항목에 남기는 표시 — 1차가 아니라 2차 근거로 올린 유형.
CONFIRMED_BY = "2차 동반 확인"


def second_stage_types(detected: List[str], order: List[str]) -> List[str]:
    """1차 탐지 유형 + 함께 묻는 유형(중복 없이, order 순서)."""

    asked = set(detected)
    for label in detected:
        asked.update(COMPANIONS.get(label, []))
    return [label for label in order if label in asked]


def _has_linked_evidence(major_result: Dict[str, Any]) -> bool:
    for subtype in major_result.get("subtypes") or []:
        for evidence in subtype.get("evidences") or []:
            if ((evidence.get("timestamps") or {}).get("segment_ids")):
                return True
    return False


def confirm_companions(
    subtype_result: Dict[str, Any],
    detected: List[str],
    asked: List[str],
) -> Tuple[Dict[str, Any], List[str]]:
    """더해 물은 유형 가운데, 함께 묻게 한 1차 유형의 근거는 없고 자기 근거는 줄에 이어진 것만 남긴다 → (고친 2차 결과, 탐지로 올릴 유형)."""

    extra = [label for label in asked if label not in detected]
    if not extra:
        return subtype_result, []

    results = subtype_result.get("results") or []
    grounded = {result.get("major_type") for result in results if _has_linked_evidence(result)}

    confirmed: List[str] = []
    kept: List[Dict[str, Any]] = []
    for major_result in results:
        label = major_result.get("major_type")
        if label in extra:
            # 이 유형을 함께 묻게 한 1차 유형(신체학대)의 근거가 이미 찾아졌으면 올리지 않는다(위 '왜 좁혔나').
            triggers = [source for source in detected if label in COMPANIONS.get(source, [])]
            if any(source in grounded for source in triggers) or not _has_linked_evidence(major_result):
                continue
            if label not in confirmed:
                confirmed.append(label)
        kept.append(major_result)

    return {**subtype_result, "results": kept}, confirmed
