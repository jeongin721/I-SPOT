"""
종결 검토 요약 LLM 모듈(2026-10-30). 종결 검토 ① '핵심 요약' 과 ② 종결보고서(서식 29)의 '초기상황' · '종결상황' AI 초안.

[입력 — 새로 분석하지 않는다]
사례의 **승인 완료 회차 요약**(상담원이 확정한 사정 4칸 문장)과 회차별 AI 관련 신호(유형 이름)만 쓴다. 원문 · 메모 ·
사례 실명은 넣지 않는다. 글은 privacy_gateway.mask_for_outbound 로 가린 뒤 보내고, 답은 restore_pii 로 되돌린다.

[출력]
{
  "groups": [{"title": 묶음 이름(GROUP_TITLES), "items": [{"text", "sessions": [회차 번호]}]}],
  "report": {"initial_situation": {"text", "sessions"}, "closing_situation": {"text", "sessions"}},
}

[코드 검사(clean_output)]
- 묶음 이름은 GROUP_TITLES 만, 문장 1~MAX_ITEM_CHARS 자, 묶음마다 MAX_ITEMS_PER_GROUP 개. 다른 나라 문자가 섞인 문장은 버림.
- sessions 는 입력에 있던 승인 회차 번호만 남기고, 하나도 안 남으면 그 문장을 버린다(근거 없는 문장 금지).
- 보고서 칸도 같은 규칙. 남는 것이 하나도 없으면 ClosureSummaryOutputError.

[LLM 없이(rule_based_summary)]
AI_PROVIDER 가 modeling 이 아니면(시험 · 데모 mock) LLM 을 부르지 않고 승인 요약 4칸을 그대로 묶는다 — 상담원 확정 문장
모음이고 AI 생성이 아니다(source "APPROVED_SUMMARIES"). 보고서 초안은 첫 승인 회차 위험요인 · 마지막 승인 회차 조사 후 변화.

openai · privacy_gateway(NER 모델)는 CI 에 없다. 검사 함수를 backend/tests 에서 시험할 수 있게 그 import 는 함수 안에 둔다.
"""

from typing import TYPE_CHECKING, Any, Dict, List, Optional

from ai.modeling.abuse.text_script import has_foreign_script

if TYPE_CHECKING:  # pragma: no cover
    from openai import OpenAI

DEFAULT_MODEL = "gpt-5.6-luna"

#: ① 핵심 요약 묶음(10/30 디자인 순서). '아이 연계' 는 아이 앱 자료가 서버에 없어 넣지 않는다.
GROUP_TITLES = ("학대 관련 진술", "아동 정서 · 행동", "보호자(사례관리대상자) 변화", "안전 자원 · 강점")
MAX_ITEMS_PER_GROUP = 3
MAX_ITEM_CHARS = 200
MAX_REPORT_CHARS = 500
#: 입력 글 상한(승인 회차가 아주 많을 때 앞 회차를 줄인다).
MAX_INPUT_CHARS = 16000

ASSESSMENT_FIELDS = (
    ("safety_risks", "위험요인"),
    ("strengths_resources", "강점과 자원"),
    ("safety_changes", "조사 후 변화"),
    ("desired_changes", "원하는 변화"),
)


class ClosureSummaryOutputError(Exception):
    """LLM 응답에 쓸 문장이 하나도 남지 않음."""


SYSTEM_PROMPT = """너는 아동보호전문기관 상담사가 사례를 종결하기 전에 전체 상담을 돌아보도록 돕는 도우미다.
아래는 상담원이 회차마다 확정(승인)한 사정 요약과, 회차별 AI 관련 신호 목록이다. 이것만 근거로 쓴다.

[원칙]
1. 입력에 없는 사실 · 사람 · 사건을 만들지 않는다. 짐작하지 않는다.
2. 학대 여부를 판정하거나 '학대 확정' 같은 말을 쓰지 않는다. 변화 · 진술 · 자원을 담담하게 적는다.
3. 문장마다 근거가 된 회차 번호(sessions)를 적는다. 입력에 있는 회차 번호만 쓴다. 근거가 없으면 그 문장은 쓰지 않는다.
4. 묶음은 아래 이름만 쓴다. 묶음마다 문장 0~{max_items}개, 문장은 {max_chars}자 이내.
{group_titles}
5. 종결보고서 초안 두 칸: initial_situation(처음 개입할 때 상황 — 앞 회차 근거), closing_situation(지금 종결 시점 상황 —
   뒤 회차 근거). 각 {max_report}자 이내.
6. 상담원 문장에 있는 표지([이름1] 같은 것)는 그대로 둔다.

[입력]
{case_input}

문장은 한국어로만 쓴다(다른 나라 글자를 섞지 않는다).
반드시 아래 JSON 형식으로만 답한다:
{{
  "groups": [{{"title": "학대 관련 진술", "items": [{{"text": "...", "sessions": [1, 3]}}]}}],
  "report": {{
    "initial_situation": {{"text": "...", "sessions": [1]}},
    "closing_situation": {{"text": "...", "sessions": [5]}}
  }}
}}
"""


def format_case_input(sessions: List[Dict[str, Any]]) -> str:
    """
    sessions: [{"number": int, "date": "YYYY-MM-DD"|"", "assessment": {4칸 키: 글}, "signals": ["신체", ...]}] (회차 순).
    LLM 입력 글(마스킹 전). MAX_INPUT_CHARS 를 넘으면 앞 회차부터 뺀다(최근 회차가 종결 판단에 더 중요).
    """

    blocks: List[str] = []

    for session in sessions:
        lines = [f"## {session['number']}회차" + (f" ({session['date']})" if session.get("date") else "")]
        assessment = session.get("assessment") or {}
        for key, label in ASSESSMENT_FIELDS:
            text = " ".join(str(assessment.get(key) or "").split())
            if text:
                lines.append(f"- {label}: {text}")
        signals = [str(label) for label in session.get("signals") or [] if str(label).strip()]
        lines.append(f"- AI 관련 신호: {' · '.join(signals) if signals else '없음'}")
        blocks.append("\n".join(lines))

    while len(blocks) > 1 and len("\n\n".join(blocks)) > MAX_INPUT_CHARS:
        blocks.pop(0)

    return "\n\n".join(blocks)


def _clean_sessions(raw: Any, allowed: set) -> List[int]:
    if not isinstance(raw, list):
        return []
    picked: List[int] = []
    for number in raw:
        if isinstance(number, bool) or not isinstance(number, int):
            continue
        if number in allowed and number not in picked:
            picked.append(number)
    return sorted(picked)


def _clean_text(raw: Any, limit: int) -> str:
    if not isinstance(raw, str):
        return ""
    text = " ".join(raw.split())
    # 다른 나라 문자가 섞인 문장은 버린다(2026-10-30, text_script).
    return text if 0 < len(text) <= limit and not has_foreign_script(text) else ""


def clean_output(raw: Any, session_numbers: List[int]) -> Dict[str, Any]:
    """LLM 답을 모듈 docstring 의 검사로 거른다. 남는 문장이 없으면 ClosureSummaryOutputError."""

    allowed = set(session_numbers)
    raw = raw if isinstance(raw, dict) else {}
    by_title: Dict[str, List[Dict[str, Any]]] = {title: [] for title in GROUP_TITLES}

    for group in raw.get("groups") or []:
        if not isinstance(group, dict) or group.get("title") not in by_title:
            continue
        items = by_title[group["title"]]
        for item in group.get("items") or []:
            if len(items) >= MAX_ITEMS_PER_GROUP or not isinstance(item, dict):
                continue
            text = _clean_text(item.get("text"), MAX_ITEM_CHARS)
            sessions = _clean_sessions(item.get("sessions"), allowed)
            if text and sessions and all(text != other["text"] for other in items):
                items.append({"text": text, "sessions": sessions})

    report_raw = raw.get("report") if isinstance(raw.get("report"), dict) else {}
    report: Dict[str, Optional[Dict[str, Any]]] = {}
    for key in ("initial_situation", "closing_situation"):
        field = report_raw.get(key) if isinstance(report_raw.get(key), dict) else {}
        text = _clean_text(field.get("text"), MAX_REPORT_CHARS)
        sessions = _clean_sessions(field.get("sessions"), allowed)
        report[key] = {"text": text, "sessions": sessions} if text and sessions else None

    groups = [{"title": title, "items": by_title[title]} for title in GROUP_TITLES]

    if not any(group["items"] for group in groups) and not any(report.values()):
        raise ClosureSummaryOutputError("남는 문장이 없습니다.")

    return {"groups": groups, "report": report}


def rule_based_summary(sessions: List[Dict[str, Any]]) -> Dict[str, Any]:
    """LLM 없이 승인 요약 4칸을 묶는다(상담원 확정 문장 모음, AI 생성 아님). 묶음 이름은 4칸 이름."""

    groups = []
    for key, label in ASSESSMENT_FIELDS:
        items = []
        for session in sessions:
            text = _clean_text((session.get("assessment") or {}).get(key), MAX_ITEM_CHARS)
            if text:
                items.append({"text": text, "sessions": [session["number"]]})
        groups.append({"title": label, "items": items})

    def pick(order: List[Dict[str, Any]], key: str) -> Optional[Dict[str, Any]]:
        for session in order:
            text = _clean_text((session.get("assessment") or {}).get(key), MAX_REPORT_CHARS)
            if text:
                return {"text": text, "sessions": [session["number"]]}
        return None

    return {
        "groups": groups,
        "report": {
            "initial_situation": pick(sessions, "safety_risks"),
            "closing_situation": pick(list(reversed(sessions)), "safety_changes"),
        },
    }


def generate_closure_summary(
    sessions: List[Dict[str, Any]],
    known_identifiers: Optional[List[str]] = None,
    model: Optional[str] = None,
    deadline: Optional[float] = None,
) -> Dict[str, Any]:
    """승인 회차 → 마스킹 → LLM → 검사 → 이름 되돌리기. 반환에 "model" 을 붙인다. 실패는 예외 그대로(서버가 코드로 바꾼다)."""

    from ai.modeling.abuse.llm_backend import build_openai_client_and_model
    from ai.modeling.abuse.pii_masking import restore_pii
    from ai.modeling.abuse.privacy_gateway import mask_for_outbound
    from ai.modeling.abuse.second_stage_llm import _call_llm_with_retry

    masked, entity_map = mask_for_outbound(format_case_input(sessions), known_identifiers=known_identifiers or [])
    client, model_name = build_openai_client_and_model(model or DEFAULT_MODEL)
    prompt = SYSTEM_PROMPT.format(
        max_items=MAX_ITEMS_PER_GROUP,
        max_chars=MAX_ITEM_CHARS,
        max_report=MAX_REPORT_CHARS,
        group_titles="\n".join(f"   - {title}" for title in GROUP_TITLES),
        case_input=masked,
    )
    parsed = _call_llm_with_retry(
        client=client,
        model=model_name,
        system_prompt=prompt,
        user_prompt="위 입력으로 종결 검토 핵심 요약과 종결보고서 초안을 만들어.",
        max_retries=2,
        timeout_seconds=120.0,
        deadline=deadline,
    )
    cleaned = clean_output(parsed, [session["number"] for session in sessions])
    restored = restore_pii(cleaned, entity_map)

    return {**restored, "model": model_name}
