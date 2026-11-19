"""
학대 신호 확인(2단계) 화면의 '안전 플래그 · 재학대 요인' 카드에 쓸 LLM 모듈(2026-11-05).

**AI 확인 후보다.** 판정이 아니다 — 상담원이 근거 발화를 보고 판단한다(05_RULES §1). 점수 · 등급으로 바꾸지 않는다.

[기준 — 팀 확인 2026-11-05, 문서 '재학대 요인 · 안전 플래그 기준안']
- 안전 플래그 S1~S10 은 "지금 이 아이가 안전한가" 를 본다. 근거: 미국 캘리포니아 SDM 안전평가 서식의 안전위협 항목
  구조(문구는 옮기지 않고 우리 말로 다시 썼다 — 서식이 © NCCD), 교육부 · 보건복지부 「유치원 · 어린이집 아동학대
  조기발견 및 관리 · 대응 매뉴얼」(2016) 신고의무자용 점검표.
- 재학대 요인 R2~R10 은 "앞으로 다시 일어날 가능성" 을 본다. 근거: 이상균 · 이봉주 외(2017, 사회복지연구 48(3)) 표 6
  (R2~R6, 통계 근거), 「아동학대 재학대 사례 심층 분석」(한국사회복지학 77(4))(R7~R10, 질적 14건).
- R1(중복학대)은 이 모듈이 찾지 않는다 — 2차 세부유형 분석의 유형 수로 화면이 센다.
- 아동 · 행위자 성별 · 나이 같은 바꿀 수 없는 특성은 넣지 않는다(편견을 심을 수 있다).

[설계 — 보호요인(protective_factor_llm.py)과 같은 방식]
마스킹한 축어록(record_draft_llm.build_transcript_citation_text)을 받아 LLM 이 segment_id 를 직접 인용하고, 실제 segment
목록에 없는 번호는 버린다. 근거 발화가 하나도 남지 않은 항목은 버린다. 위험 신호 분석 프롬프트(second_stage_llm)에 끼워 넣지
않고 따로 부른다 — 이미 튜닝된 위험 신호 탐지를 흔들지 않으려고(보호요인 모듈 docstring 과 같은 이유).

[실패]
LLM 실패 · 형식 오류면 None 을 돌려준다. 분석 전체는 실패시키지 않는다. 계약에서는 두 칸 모두 null(만들지 못함)이 되고,
빈 목록([] — 찾았지만 해당 없음)과 구분된다. "언급 없음 ≠ 위험 없음" 이므로 화면은 null 을 '없음' 으로 보이면 안 된다.

[가상 축어록 실측 2026-11-05] 한 번 부르는 데 10~12초(보호요인과 비슷) — 기록 초안 · 보호요인과 병렬이라 2단계가 뜨는
시점은 거의 그대로다. 첫 판에서 '부모가 맨날 싸운다' 만으로 S10 을 잡아 S10 정의를 좁혔다(말다툼은 R3).
"""

import threading
from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:  # pragma: no cover
    from openai import OpenAI

DEFAULT_MODEL = "gpt-5.6-luna"


# ============================================================
# 1. 기준(팀 확인 2026-11-05)
# ============================================================

SAFETY_FLAG_DEFINITIONS: Dict[str, str] = {
    "S1": "심각한 신체 피해가 있었거나, 그런 피해를 주겠다는 구체적인 위협이 있었다(사고로 보기 어려운 상처 · 가학적 행위 · 감금 포함).",
    "S2": "말하면 더 혼난다 · 가만두지 않겠다처럼 보복하거나 입을 막는 위협이 있었다.",
    "S3": "아동이 행위자와 지금 함께 살고 있고, 행위자로부터 막아 줄 다른 보호자가 없거나 막지 못한다.",
    "S4": "상처나 다친 일에 대한 아동 · 보호자의 설명이 없거나 앞뒤가 맞지 않는다.",
    "S5": "성학대가 의심되고, 지금도 그 상황에 노출될 수 있다.",
    "S6": "당장 필요한 돌봄(음식 · 감독 · 치료)이 없거나, 사는 곳이 당장 위험하다.",
    "S7": "아동이 보호자를 두려워하거나 집에 돌아가는 것을 두려워한다.",
    "S8": "자해 · 자살 언급, 극단적인 위축 · 공포처럼 심한 정서 반응이 있다.",
    "S9": "아동을 만나지 못하게 하거나, 가족이 이사 · 잠적할 것으로 보인다.",
    "S10": (
        "보호자 사이의 신체 폭력(때림 · 물건 던짐 · 흉기 등)이 있고 아동이 그 자리에서 다칠 수 있다. 말다툼 · 싸움이 잦다는 "
        "말만 있으면 S10 이 아니라 재학대 요인 R3 이다. 아동에게 직접 한 폭력은 S10 이 아니라 S1 이다."
    ),
}

REABUSE_FACTOR_DEFINITIONS: Dict[str, str] = {
    "R2": "행위자의 알코올 남용 · 음주 후 폭력.",
    "R3": "부부(배우자) 사이의 폭력이나 반복되는 심한 다툼.",
    "R4": "친부모가 행위자다.",
    "R5": "경제적 어려움(수급 · 생계 곤란).",
    "R6": "양육 기술 부족 · 양육 스트레스 · 체벌을 당연하게 여기는 양육 태도.",
    "R7": "행위자의 정신질환 · 지적장애(진단 · 치료 언급).",
    "R8": "아동에게 책임을 돌린다(아이가 말을 안 들어서 그렇다 등).",
    "R9": "행위자가 상담 · 교육 · 서비스를 거부하거나 형식적으로만 응한다.",
    "R10": "새 보호자 · 동거인이 생겼거나 행위자가 여럿이다.",
}

VALID_SAFETY_CODES = set(SAFETY_FLAG_DEFINITIONS)
VALID_REABUSE_CODES = set(REABUSE_FACTOR_DEFINITIONS)
VALID_CERTAINTY = {"CLEAR", "CHECK"}


# ============================================================
# 2. 프롬프트
# ============================================================

SYSTEM_PROMPT = """너는 아동 상담 축어록에서 '안전 플래그' 와 '재학대 요인' 후보를 찾는 보조 분석기다.
결과는 상담원이 확인할 후보일 뿐 판정이 아니다.

[원칙]
1. 축어록에 실제로 나온 진술만 근거로 삼는다. 상담원 질문에만 있고 아동 · 보호자가 확인하지 않은 내용은 근거가 아니다.
2. 원문에 없는 사실 · 정도를 보태지 않는다. 추측으로 항목을 만들지 않는다.
3. 항목마다 근거가 된 축어록 줄의 segment_id 를 정확히 인용한다. 근거가 없으면 그 항목을 만들지 않는다.
4. 같은 코드는 한 번만 낸다(근거 줄이 여러 개면 segment_ids 에 모두 적는다).
5. text 는 무엇이 있었는지 짧게 적는 한 문장이다. '위험하다' · '학대다' 같은 판정 · 단정을 쓰지 않는다.
6. 아동 · 행위자의 성별 · 나이만으로 항목을 만들지 않는다.

[안전 플래그 — 지금 이 아이가 안전한가]
{safety_definitions}

각 안전 플래그에 certainty 를 적는다.
- "CLEAR": 진술이 그 항목에 분명히 해당한다.
- "CHECK": 해당할 수 있지만 뜻이 둘로 읽혀 상담원 확인이 필요하다(예: '할머니 집에 가고 싶어요' 가 귀가 두려움인지 모호함).

[재학대 요인 — 앞으로 다시 일어날 가능성]
{reabuse_definitions}

[출력 형식 — 반드시 이 JSON 만]
{{
  "safety_flags": [
    {{"code": "S2", "text": "말하면 더 혼난다는 말을 들었다고 함", "certainty": "CLEAR", "segment_ids": ["seg_012"]}}
  ],
  "reabuse_factors": [
    {{"code": "R2", "text": "아빠가 술을 마시면 때린다고 함", "segment_ids": ["seg_004"]}}
  ]
}}

해당하는 내용이 없으면 빈 배열([])로 둔다.
"""


def _call_llm(**kwargs: Any) -> Any:
    # openai · second_stage_llm 은 CI 에 없을 수 있어 부를 때 불러온다(topic_tag_llm 과 같은 방식). 시험은 이 함수를 바꾼다.
    from ai.modeling.abuse.second_stage_llm import _call_llm_with_retry

    return _call_llm_with_retry(**kwargs)


def _definition_text(definitions: Dict[str, str]) -> str:
    return "\n".join(f"- {code}: {text}" for code, text in definitions.items())


# ============================================================
# 3. 검증 및 정리
# ============================================================

def _clean(
    raw: Any,
    valid_codes: set,
    valid_segment_ids: set,
    with_certainty: bool,
) -> List[Dict[str, Any]]:
    if not isinstance(raw, list):
        return []

    # 같은 코드가 여러 번 오면 하나로 합친다(첫 문장 · 근거 줄은 모두). 코드 순서는 처음 나온 순서.
    merged: Dict[str, Dict[str, Any]] = {}

    for item in raw:
        if not isinstance(item, dict):
            continue

        code = item.get("code")
        text = item.get("text")

        if code not in valid_codes or not isinstance(text, str) or not text.strip():
            continue

        segment_ids = [
            str(sid)
            for sid in (item.get("segment_ids") or [])
            if isinstance(sid, (str, int)) and str(sid) in valid_segment_ids
        ]

        if not segment_ids:
            # 근거 발화가 없는 후보는 버린다(보호요인과 같은 규칙) — 화면이 근거 없이 '플래그' 를 띄우면 안 된다.
            continue

        if code in merged:
            for sid in segment_ids:
                if sid not in merged[code]["segment_ids"]:
                    merged[code]["segment_ids"].append(sid)
            if with_certainty and item.get("certainty") == "CLEAR":
                merged[code]["certainty"] = "CLEAR"
            continue

        entry: Dict[str, Any] = {"code": code, "text": text.strip(), "segment_ids": segment_ids}

        if with_certainty:
            certainty = item.get("certainty")
            # 모르는 값이면 확인 필요로 둔다 — 근거가 약할 때 '분명함' 으로 올리지 않는다.
            entry["certainty"] = certainty if certainty in VALID_CERTAINTY else "CHECK"

        merged[code] = entry

    return list(merged.values())


# ============================================================
# 4. 진입점
# ============================================================

def generate_safety_flags(
    client: "OpenAI",
    model: str,
    masked_transcript_text: str,
    segments: List[Dict[str, Any]],
    deadline: Optional[float] = None,
    stop_event: Optional[threading.Event] = None,
) -> Optional[Dict[str, List[Dict[str, Any]]]]:
    """
    masked_transcript_text: 보호요인과 같은 마스킹된 인용 축어록(호출부가 mask_for_outbound 로 가린 것)을 그대로 쓴다.
    segments: 원본 segment 목록 — segment_id 검증에만 쓴다.

    반환: {"safety_flags": [...], "reabuse_factors": [...]}. LLM 실패 · 형식 오류면 None(분석은 실패시키지 않는다).
    축어록이 비었으면 찾을 것이 없으므로 두 칸 모두 빈 배열이다.
    """

    valid_segment_ids = {str(segment.get("segment_id", "")) for segment in segments}

    if not masked_transcript_text.strip():
        return {"safety_flags": [], "reabuse_factors": []}

    system_prompt = SYSTEM_PROMPT.format(
        safety_definitions=_definition_text(SAFETY_FLAG_DEFINITIONS),
        reabuse_definitions=_definition_text(REABUSE_FACTOR_DEFINITIONS),
    )
    user_prompt = f"[축어록]\n\n{masked_transcript_text}"

    try:
        parsed = _call_llm(
            client=client,
            model=model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_retries=2,
            timeout_seconds=180.0,
            deadline=deadline,
            stop_event=stop_event,
        )
    except Exception:
        return None

    if not isinstance(parsed, dict):
        return None

    return {
        "safety_flags": _clean(parsed.get("safety_flags"), VALID_SAFETY_CODES, valid_segment_ids, True),
        "reabuse_factors": _clean(parsed.get("reabuse_factors"), VALID_REABUSE_CODES, valid_segment_ids, False),
    }
