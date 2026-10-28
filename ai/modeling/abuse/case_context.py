"""
분석 입력 case_context(사례 정보)를 LLM 프롬프트 입력 글로 바꾼다(2026-10-28).

설계: I-SPOT_DOCS/docs/PROPOSAL_case_context_analysis.md §3(합의) ·
PROPOSAL_ai_suggestions_case_context.md §1. Backend(analysis_service)가 받는 어댑터에만
`analyze(payload, case_context=…)` 로 넘기고, contract_adapter → infer_audio_session 으로 내려온다.

```jsonc
{
  "child_age_band": "만 10~13세",       // 정확한 나이 · 생년월일은 오지 않는다
  "child_gender": "F",
  "guardian_type": "FATHER",            // backend GuardianType
  "intake_child_traits": ["불안"],      // 서식 4 목록 단어
  "intake_family_situations": ["알콜남용"],
  "previous_session": {                 // 직전 '승인 완료' 회차, 없으면 null
    "session_label": "7회차", "consulted_on": "2026-10-20",
    "assessment": {"safety_changes": "…", "strengths_resources": "…", "safety_risks": "…", "desired_changes": "…"}
  }
}
```

[원칙]
- 이름 · 생년월일 · 연락처 · 사건번호 · 메모는 애초에 오지 않는다(Backend 가 고르지 않음). 여기서도
  알려진 키만 읽고 나머지는 버린다.
- `previous_session.assessment` 는 상담원이 쓴 글이라 이름이 섞일 수 있다 → 이 함수가 만든 글은
  부르는 쪽이 원문과 같은 `mask_for_outbound` 를 거쳐 보낸다(여기서는 가리지 않는다).
- 모양이 틀린 값은 조용히 버린다(분석을 멈추지 않는다). 아무것도 없으면 "없음".
"""

from typing import Any, Dict, List, Optional

#: 프롬프트에 쓰는 성별 · 보호자 유형 이름. 모르는 값은 쓰지 않는다.
GENDER_LABELS = {"F": "여", "M": "남", "여": "여", "남": "남"}

GUARDIAN_LABELS = {
    "PARENTS": "부모",
    "FATHER": "부",
    "MOTHER": "모",
    "GRANDPARENTS": "조부모",
    "RELATIVE": "친인척",
    "FOSTER": "위탁",
    "FACILITY": "시설",
    "OTHER": "기타",
}

#: 지난 회차 요약 4칸 이름(#86 summary.assessment).
ASSESSMENT_LABELS = {
    "safety_changes": "조사 후 변화된 사항",
    "strengths_resources": "강점과 자원",
    "safety_risks": "위험요인",
    "desired_changes": "원하는 변화 · 서비스",
}

#: 칸 하나 · 목록 하나의 최대 길이(프롬프트가 지나치게 길어지지 않게).
MAX_TEXT_CHARS = 600
MAX_ITEMS = 40

EMPTY = "없음"


def _text(value: Any, limit: int = MAX_TEXT_CHARS) -> str:
    return value.strip()[:limit] if isinstance(value, str) else ""


def _words(value: Any) -> List[str]:
    if not isinstance(value, list):
        return []

    words: List[str] = []

    for item in value[:MAX_ITEMS]:
        word = _text(item, 60)
        if word and word not in words:
            words.append(word)

    return words


def normalize_case_context(case_context: Any) -> Optional[Dict[str, Any]]:
    """알려진 키만 남긴 dict. 쓸 값이 하나도 없으면 None."""

    if not isinstance(case_context, dict):
        return None

    previous = case_context.get("previous_session")
    previous_view: Optional[Dict[str, Any]] = None

    if isinstance(previous, dict):
        assessment = previous.get("assessment")
        texts = {
            key: _text(assessment.get(key)) for key in ASSESSMENT_LABELS
        } if isinstance(assessment, dict) else {}
        texts = {key: text for key, text in texts.items() if text}
        label = _text(previous.get("session_label"), 20)

        if texts or label:
            previous_view = {
                "session_label": label,
                "consulted_on": _text(previous.get("consulted_on"), 20),
                "assessment": texts,
            }

    view = {
        "child_age_band": _text(case_context.get("child_age_band"), 20),
        "child_gender": GENDER_LABELS.get(case_context.get("child_gender"), ""),
        "guardian_type": GUARDIAN_LABELS.get(case_context.get("guardian_type"), ""),
        "intake_child_traits": _words(case_context.get("intake_child_traits")),
        "intake_family_situations": _words(case_context.get("intake_family_situations")),
        "previous_session": previous_view,
    }

    if not any(view.values()):
        return None

    return view


def previous_session_label(case_context: Any) -> Optional[str]:
    """직전 승인 회차 이름("7회차"). 없으면 None. 확인 메모의 '근거 · 7회차 확정 요약' 에 쓴다."""

    view = normalize_case_context(case_context)
    previous = view["previous_session"] if view else None
    label = previous["session_label"] if previous else ""

    return label or None


def format_case_context(case_context: Any) -> str:
    """
    프롬프트에 넣을 사례 정보 글. 마스킹 전 글이다 — 부르는 쪽이 mask_for_outbound 를 거쳐 보낸다.
    값이 없으면 "없음".
    """

    view = normalize_case_context(case_context)

    if view is None:
        return EMPTY

    lines: List[str] = []

    child = " · ".join(
        part for part in (view["child_age_band"], view["child_gender"]) if part
    )
    if child:
        lines.append(f"- 아동: {child}")
    if view["guardian_type"]:
        lines.append(f"- 보호자 유형: {view['guardian_type']}")
    if view["intake_child_traits"]:
        lines.append(f"- 초기면접 아동 특성: {', '.join(view['intake_child_traits'])}")
    if view["intake_family_situations"]:
        lines.append(f"- 초기면접 가정상황: {', '.join(view['intake_family_situations'])}")

    previous = view["previous_session"]
    if previous:
        head = " · ".join(
            part for part in (previous["session_label"], previous["consulted_on"]) if part
        )
        lines.append(f"- 지난 회차 확정 요약{f'({head})' if head else ''}:")
        for key, text in previous["assessment"].items():
            lines.append(f"  - {ASSESSMENT_LABELS[key]}: {text}")

    return "\n".join(lines) if lines else EMPTY
