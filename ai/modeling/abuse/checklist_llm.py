"""
상담 원문을 바탕으로 공식 서식(초기면접지/사정기록지 등)의 일부 항목을
AI가 초안(제안)으로 채운다.

[원칙]

1. 원문에 직접적인 근거가 있는 항목만 제안한다. 근거가 없으면 제안하지 않는다.
2. 높음/보통/낮음, 0~3점 같은 전문적 위험 판단·점수는 AI가 확정하지 않는다.
   안전영역 항목은 관련될 수 있는 원문 근거만 제안하고, 실제 등급 판단은
   상담사가 한다.
3. 모든 제안에는 원문 근거를 함께 붙이며, 상담사가 확인하기 전까지는
   "AI 제안 / 상담사 확인 필요" 상태로 취급한다.
"""

import os
from typing import Any, Dict, List, Optional

from openai import OpenAI

from ai.modeling.abuse.feedback_analysis import (
    build_correction_hint_text,
)
from ai.modeling.abuse.second_stage_llm import (
    _call_llm_with_retry,
    verify_evidence,
)


# ============================================================
# 1. 체크리스트 후보 항목 (서식4 초기면접지 / 서식6 사정기록지 기준)
# ============================================================

CHECKLIST_DEFINITIONS: Dict[str, List[str]] = {
    "가정상황": [
        "성격및기질문제", "어릴적학대경험", "알콜남용", "약물남용",
        "신체질환및장애", "정신질환및장애", "원치않은아동", "부적절한양육태도",
        "양육지식및기술부족", "부부및가족갈등", "성문제", "스트레스",
        "사회적고립", "경제적어려움", "배우자폭력", "존속학대",
        "전과력", "종교문제", "도박,게임중독",
    ],
    "아동 특성": [
        "거짓말", "반항,충동,공격성", "약물", "흡연", "도벽", "가출",
        "성문제", "주의산만", "음주", "인터넷(게임)중독",
        "불건전한또래관계", "대인관계기피(은둔형외톨이)", "과잉행동", "늦은귀가",
        "잦은결석", "학교폭력가해자", "학교부적응",
        "불안", "애착문제", "학교폭력피해자(왕따)",
        "낮은자존감", "신체발달지연", "무력감", "우울",
        "대소변문제", "성격및기질문제", "언어문제", "학습문제",
        "급(만)성질병", "영양결핍", "위생문제", "틱(음성/신체/투렛)",
        "탐식및결식",
    ],
}


# ============================================================
# 2. 안전영역 개입 사정 항목 (서식6/서식29 기준)
# ============================================================
# 높음/보통/낮음 등급 자체는 AI가 판단하지 않는다.
# 각 항목과 관련될 수 있는 원문 근거만 후보로 제안한다.

SAFETY_ASSESSMENT_DIMENSIONS: Dict[str, List[str]] = {
    "피해아동": [
        "아동의 위험상황 인지 및 대처능력",
        "아동의 연령, 장애 등 집중적 보호가 요구되는 특성 보유",
        "피해아동과 가족과의 관계 친밀성",
    ],
    "가족구성원": [
        "가족구성원의 아동 안전 보호 및 양육 의지",
        "가정 내 가정폭력 문제",
        "아동보호전문기관의 개입에 대한 태도",
        "가족기능과 가정환경에 대한 평가",
        "주양육자의 양육역량",
    ],
    "사례관리대상자": [
        "학대행위에 대한 잘못 인지 및 개선 의지",
        "스스로 자신을 통제하기 어려운 특성(중독, 성격장애 등)",
        "가정 내 위기상황(실직, 가정폭력 등)으로 인한 만성적 스트레스",
    ],
}

ENVIRONMENT_ITEM = "조부모, 친구, 이웃 등 신뢰할만한 주위 사람(Key Person)"


DEFAULT_MODEL = os.getenv(
    "CHECKLIST_MODEL",
    "gpt-5.6-luna",
)


# ============================================================
# 3. 프롬프트
# ============================================================

SYSTEM_PROMPT_TEMPLATE = """
너는 아동학대 상담 원문을 보고 공식 상담 서식(초기면접지/사정기록지)의
일부 항목 초안을 제안하는 보조 도구다.

[중요 원칙]

1. 아래 제시된 후보 목록 안에서만 항목을 선택한다. 목록에 없는 항목을
   새로 만들지 않는다.
2. 원문에서 직접 확인 가능한 근거가 있는 항목만 포함한다.
   근거가 없으면 그 항목은 결과에 아예 포함하지 않는다.
3. evidence는 반드시 원문에 실제 존재하는 연속된 텍스트를 그대로 복사한다.
4. "안전영역 관련 근거"에는 높음/보통/낮음 등급을 절대 매기지 않는다.
   해당 항목과 관련될 수 있는 원문 근거만 제안한다.
5. 상담사의 질문에 관련 표현이 있어도 아동/가족이 명확히 부정한 경우
   근거로 사용하지 않는다.
6. 추측이나 일반화 없이, 원문에 실제로 서술된 사실만 사용한다.
7. problem_history_draft/counselor_opinion_draft에는 "학대 의심",
   "위험도가 높다"와 같은 판정 표현을 사용하지 않는다.
8. checklist의 category는 반드시 "가정상황" 또는 "아동 특성" 중
   하나를 정확히 그대로 적는다. "가정상황 또는 아동 특성"처럼
   두 값을 합쳐서 적지 않는다.
9. safety_assessment_evidence의 category는 반드시 "피해아동",
   "가족구성원", "사례관리대상자" 중 하나를 정확히 그대로 적는다.
   마찬가지로 값을 합쳐서 적지 않는다.

[가정상황 후보]

{household_items}

[아동 특성 후보]

{child_trait_items}

[안전영역 관련 근거 탐색 대상]

{safety_dimension_items}

[환경 - 신뢰할 만한 주위 사람 여부]

"{environment_item}" 항목과 관련해 원문에서 신뢰할 만한 주위 사람의
존재 여부가 언급되면 있음/없음 중 하나와 근거를 제시한다.
언급이 없으면 environment_key_person 필드를 결과에서 생략한다.

[문제력 초안]

원문에서 확인되는 현재 상황과 문제가 발생하게 된 배경을
객관적 사실 중심으로 3~5문장 정도로 작성한다.

[상담원 소견 초안]

원문에서 확인되는 관찰 사실을 중립적인 문체로 3~5문장 정리한다.
새로운 사실이나 결론을 추가하지 않는다.

반드시 아래 JSON 형식으로만 답한다.

{{
  "problem_history_draft": "...",
  "counselor_opinion_draft": "...",
  "checklist": [
    {{
      "category": "가정상황",
      "item": "가정상황 후보 목록에 있는 항목명 그대로",
      "evidence": ["원문에서 그대로 발췌한 근거"]
    }},
    {{
      "category": "아동 특성",
      "item": "아동 특성 후보 목록에 있는 항목명 그대로",
      "evidence": ["원문에서 그대로 발췌한 근거"]
    }}
  ],
  "safety_assessment_evidence": [
    {{
      "category": "피해아동",
      "item": "안전영역 후보 목록 중 피해아동 항목명 그대로",
      "evidence": ["원문에서 그대로 발췌한 근거"]
    }},
    {{
      "category": "가족구성원",
      "item": "안전영역 후보 목록 중 가족구성원 항목명 그대로",
      "evidence": ["원문에서 그대로 발췌한 근거"]
    }},
    {{
      "category": "사례관리대상자",
      "item": "안전영역 후보 목록 중 사례관리대상자 항목명 그대로",
      "evidence": ["원문에서 그대로 발췌한 근거"]
    }}
  ],
  "environment_key_person": {{
    "status": "있음 또는 없음",
    "evidence": ["원문에서 그대로 발췌한 근거"]
  }}
}}

근거 있는 항목이 하나도 없으면 checklist/safety_assessment_evidence는
빈 배열로 반환한다.
{correction_hint}"""

USER_PROMPT_TEMPLATE = """
[상담 원문]

{text}
"""


def _build_item_list_text(
    items: List[str],
) -> str:
    return "\n".join(
        f"- {item}"
        for item in items
    )


def _build_category_item_list_text(
    categories: Dict[str, List[str]],
) -> str:
    lines: List[str] = []

    for category, items in categories.items():
        lines.append(
            f"■ {category}"
        )

        for item in items:
            lines.append(
                f"  - {item}"
            )

    return "\n".join(lines)


# ============================================================
# 4. Evidence 검증
# ============================================================

def _verify_evidence_list(
    evidence_list: Optional[List[Any]],
    source_text: str,
) -> List[Dict[str, Any]]:
    verified_entries: List[Dict[str, Any]] = []

    for evidence in evidence_list or []:
        if not isinstance(evidence, str) or not evidence.strip():
            continue

        result = verify_evidence(
            source_text=source_text,
            evidence=evidence,
        )

        verified_entries.append(
            {
                "evidence": evidence,
                "evidence_verified": result["evidence_verified"],
                "evidence_match_method": result["evidence_match_method"],
                "matched_evidence": result["matched_evidence"],
            }
        )

    return verified_entries


# ============================================================
# 5. LLM 출력 → 체크리스트 구조화
# ============================================================

def _empty_checklist() -> List[Dict[str, Any]]:
    result = []

    for category, items in CHECKLIST_DEFINITIONS.items():
        for item in items:
            result.append(
                {
                    "category": category,
                    "item": item,
                    "suggested": False,
                    "evidence": [],
                }
            )

    return result


def _empty_safety_assessment() -> List[Dict[str, Any]]:
    result = []

    for category, dimensions in SAFETY_ASSESSMENT_DIMENSIONS.items():
        for dimension in dimensions:
            result.append(
                {
                    "category": category,
                    "item": dimension,
                    "evidence": [],
                }
            )

    return result


def _build_checklist(
    raw_checklist: Any,
    source_text: str,
) -> List[Dict[str, Any]]:
    candidate_lookup = {
        (category, item)
        for category, items in CHECKLIST_DEFINITIONS.items()
        for item in items
    }

    evidence_map: Dict[Any, List[Dict[str, Any]]] = {}

    if isinstance(raw_checklist, list):
        for entry in raw_checklist:
            if not isinstance(entry, dict):
                continue

            key = (
                entry.get("category"),
                entry.get("item"),
            )

            if key not in candidate_lookup:
                continue

            verified_evidence = _verify_evidence_list(
                entry.get("evidence"),
                source_text,
            )

            has_verified_evidence = any(
                evidence["evidence_verified"]
                for evidence in verified_evidence
            )

            if not has_verified_evidence:
                continue

            evidence_map[key] = verified_evidence

    result = []

    for category, items in CHECKLIST_DEFINITIONS.items():
        for item in items:
            evidence = evidence_map.get(
                (category, item),
                [],
            )

            result.append(
                {
                    "category": category,
                    "item": item,
                    "suggested": bool(evidence),
                    "evidence": evidence,
                }
            )

    return result


def _build_safety_assessment(
    raw_list: Any,
    source_text: str,
) -> List[Dict[str, Any]]:
    candidate_lookup = {
        (category, item)
        for category, items in SAFETY_ASSESSMENT_DIMENSIONS.items()
        for item in items
    }

    evidence_map: Dict[Any, List[Dict[str, Any]]] = {}

    if isinstance(raw_list, list):
        for entry in raw_list:
            if not isinstance(entry, dict):
                continue

            key = (
                entry.get("category"),
                entry.get("item"),
            )

            if key not in candidate_lookup:
                continue

            verified_evidence = _verify_evidence_list(
                entry.get("evidence"),
                source_text,
            )

            verified_only = [
                evidence
                for evidence in verified_evidence
                if evidence["evidence_verified"]
            ]

            if verified_only:
                evidence_map[key] = verified_only

    result = []

    for category, items in SAFETY_ASSESSMENT_DIMENSIONS.items():
        for item in items:
            result.append(
                {
                    "category": category,
                    "item": item,
                    "evidence": evidence_map.get(
                        (category, item),
                        [],
                    ),
                }
            )

    return result


def _build_environment_key_person(
    raw: Any,
    source_text: str,
) -> Optional[Dict[str, Any]]:
    if not isinstance(raw, dict):
        return None

    status = raw.get("status")

    if status not in {"있음", "없음"}:
        return None

    verified_evidence = _verify_evidence_list(
        raw.get("evidence"),
        source_text,
    )

    verified_only = [
        evidence
        for evidence in verified_evidence
        if evidence["evidence_verified"]
    ]

    if not verified_only:
        return None

    return {
        "item": ENVIRONMENT_ITEM,
        "status": status,
        "evidence": verified_only,
    }


def _clean_draft_text(
    value: Any,
) -> str:
    if not isinstance(value, str):
        return ""

    return value.strip()


# ============================================================
# 6. 공개 함수
# ============================================================

def generate_checklist_draft(
    text: str,
    client: Any = None,
    model: str = DEFAULT_MODEL,
    max_retries: int = 3,
    timeout_seconds: float = 180.0,
) -> Dict[str, Any]:
    """
    상담 원문을 바탕으로 서식 체크리스트 초안을 생성한다.

    반환값의 모든 제안 항목은 "AI 제안 / 상담사 확인 필요" 상태이며,
    안전영역 항목에는 등급(높음/보통/낮음)을 포함하지 않는다.

    timeout_seconds 기본값은 로컬 Ollama 호출(수십~백여 초) 기준으로
    잡았다 — 예전 OpenAI 전용(30초) 그대로 두면 응답 전에 타임아웃되어
    처음부터 재시도만 반복하다 실패하는 경우가 있었다.
    """

    if not text.strip():
        return {
            "problem_history_draft": "",
            "counselor_opinion_draft": "",
            "checklist": _empty_checklist(),
            "safety_assessment_evidence": _empty_safety_assessment(),
            "environment_key_person": None,
            "model": model,
        }

    if client is None:
        api_key = os.environ.get(
            "OPENAI_API_KEY"
        )

        if not api_key:
            raise RuntimeError(
                "환경변수 OPENAI_API_KEY가 설정되어 있지 않습니다."
            )

        client = OpenAI(
            api_key=api_key
        )

    try:
        correction_hint = build_correction_hint_text()
    except Exception:
        # 피드백 DB를 못 읽어도 체크리스트 생성 자체는 막지 않는다.
        correction_hint = ""

    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
        household_items=_build_item_list_text(
            CHECKLIST_DEFINITIONS["가정상황"]
        ),
        child_trait_items=_build_item_list_text(
            CHECKLIST_DEFINITIONS["아동 특성"]
        ),
        safety_dimension_items=_build_category_item_list_text(
            SAFETY_ASSESSMENT_DIMENSIONS
        ),
        environment_item=ENVIRONMENT_ITEM,
        correction_hint=correction_hint,
    )

    user_prompt = USER_PROMPT_TEMPLATE.format(
        text=text
    )

    parsed = _call_llm_with_retry(
        client=client,
        model=model,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        max_retries=max_retries,
        timeout_seconds=timeout_seconds,
    )

    return {
        "problem_history_draft": _clean_draft_text(
            parsed.get("problem_history_draft")
        ),
        "counselor_opinion_draft": _clean_draft_text(
            parsed.get("counselor_opinion_draft")
        ),
        "checklist": _build_checklist(
            parsed.get("checklist"),
            text,
        ),
        "safety_assessment_evidence": _build_safety_assessment(
            parsed.get("safety_assessment_evidence"),
            text,
        ),
        "environment_key_person": _build_environment_key_person(
            parsed.get("environment_key_person"),
            text,
        ),
        "model": model,
    }


# ============================================================
# 7. 데모
# ============================================================

if __name__ == "__main__":
    import json

    text = """
상담사: 아빠가 어떻게 했어?
아동: 아빠가 막대기로 제 팔을 여러 번 때렸어요.
상담사: 그럴 때 엄마는 뭐 하고 있었어?
아동: 엄마도 옆에서 아빠한테 맞는 걸 봤어요. 무서워서 방에 숨었어요.
상담사: 요즘 학교는 잘 다니고 있어?
아동: 학교 가는 게 무섭고 불안해요. 그리고 요즘 잠도 잘 못 자요.
상담사: 힘들 때 이야기할 수 있는 사람은 있어?
아동: 할머니한테는 가끔 얘기해요. 할머니는 저를 잘 챙겨주세요.
"""

    result = generate_checklist_draft(
        text=text
    )

    print(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2,
        )
    )
