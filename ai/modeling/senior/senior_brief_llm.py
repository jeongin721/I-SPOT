"""
고령자 건강상담 '요약 · 다음 상담 확인사항' 모듈(2026-11-13, API_CONTRACT 27절).

[입력 — 서버가 만든다]
{
  "today": "YYYY-MM-DD",
  "profile": {"living_arrangement": str|None, "care_grade": str|None, "health_notes": str|None, "care_notes": str|None},
  "metrics": [{"metric", "label", "unit", "points": [{"id": 측정 id, "date": "YYYY-MM-DD", "value": float}]}],   # 오래된 것부터
  "sessions": [{"number": int, "date": "YYYY-MM-DD"|"", "overview": str, "key_points": [str]}],                   # 승인 회차, 오래된 것부터
}

[출력]
{"summary": str, "check_items": [{"text": str, "basis": [{"kind": "MEASUREMENT", "metric", "measurement_id"}
                                                          | {"kind": "SESSION", "session_number"} | {"kind": "PROFILE"}]}]}

[하지 않는 것 — 권장 범위 '제외']
질병 진단 · 정신질환 판정 · 치료 권고(약 늘리기 · 끊기 등)는 만들지 않는다. 측정값에 '정상 · 위험' 기준을 붙이지 않고
값과 변화만 말한다. LLM 답은 clean_output 이 이런 말이 든 문장을 버린다(FORBIDDEN). 판단은 담당자가 한다.

[LLM 없이(rule_based_brief)]
SENIOR_BRIEF_PROVIDER=rule(기본)이면 LLM 을 부르지 않고 값 변화 · 마지막 측정 날짜 · 지난 상담 핵심 내용을 규칙으로 묶는다
(source "RULE", AI 생성 아님). '눈에 띄는 변화' 폭(NOTABLE_CHANGE)은 지난번과 다르다는 표시일 뿐 의학 기준이 아니다.

openai · privacy_gateway(NER 모델)는 CI 에 없다. 규칙 · 검사 함수를 backend/tests 에서 시험할 수 있게 그 import 는 함수 안에 둔다.
"""

import re
from datetime import date
from typing import Any, Dict, Iterable, List, Optional, Tuple

from ai.modeling.abuse.text_script import has_foreign_script

DEFAULT_MODEL = "gpt-5.6-luna"

MAX_ITEMS = 6
MAX_ITEM_CHARS = 160
MAX_SUMMARY_CHARS = 400
#: LLM 에 넣는 최근 승인 회차 수 · 항목마다 최근 측정 수.
MAX_SESSIONS = 3
MAX_POINTS = 8
#: 마지막 측정이 이만큼 지났으면 측정을 다시 해 보자는 확인사항을 낸다.
STALE_DAYS = 30

#: 지난 측정과 이만큼 이상 다르면 확인사항으로 올린다(규칙). 의학 기준이 아니라 '지난번과 다름' 표시다.
NOTABLE_CHANGE = {
    "systolic": 15,
    "diastolic": 10,
    "pulse": 15,
    "blood_glucose_fasting": 30,
    "blood_glucose_post_meal": 40,
    "blood_glucose_random": 40,
    "weight_kg": 2,
    "body_temp_c": 1.0,
}

#: 진단 · 판정 · 치료 권고로 읽히는 말. 이 중 하나라도 든 문장은 버린다(요약은 규칙 요약으로 바꾼다).
FORBIDDEN = tuple(
    re.compile(pattern)
    for pattern in (
        r"진단",
        r"의심",
        r"판정",
        r"처방",
        r"소견",
        r"[고저]혈압(이|으로|입니다|증|일)",
        r"당뇨(병)?(이|로|입니다|일)",
        r"우울증",
        r"치매\s*(로|입니다|일|가\s*의심|증상)",
        r"질환(이|으로)\s*(보|있)",
        r"치료(가|를)?\s*(필요|권|받으셔야|시작)",
        r"(약|복용|투약).{0,8}(늘리|줄이|끊|중단|바꾸|변경)",
        r"정상\s*(범위|수치|입니다|이에요|이다)",
        r"(위험|이상)\s*(수치|군|합니다|해요|입니다)",
        r"(병원|진료).{0,6}(가야|가셔야|필요|받으셔야)",
    )
)

LIVING_LABELS = {
    "ALONE": "혼자 사심",
    "COUPLE": "배우자와 두 분",
    "WITH_FAMILY": "가족과 함께",
    "FACILITY": "시설 · 공동생활",
    "OTHER": "그 밖",
}
CARE_GRADE_LABELS = {
    **{f"GRADE_{n}": f"장기요양 {n}등급" for n in range(1, 6)},
    "COGNITIVE_SUPPORT": "장기요양 인지지원등급",
    "NONE": "장기요양 등급 없음",
    "UNKNOWN": "장기요양 등급 모름",
}


class SeniorBriefOutputError(ValueError):
    """LLM 답에서 쓸 문장이 하나도 남지 않음."""


def _fmt(value: float) -> str:
    return str(int(value)) if float(value).is_integer() else f"{value:.1f}"


def is_forbidden(text: str) -> bool:
    return any(pattern.search(text) for pattern in FORBIDDEN)


_HANGUL = re.compile("[가-힣]")


def _usable(text: str, limit: int) -> bool:
    """한글 문장(영어만 쓴 답은 버림) · 길이 · 금지 말 · 다른 나라 문자 검사."""

    return bool(text) and len(text) <= limit and bool(_HANGUL.search(text)) and not is_forbidden(text) and not has_foreign_script(text)


# ---------------------------------------------------------------- 규칙


def _measurement_basis(metric: str, *points: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [{"kind": "MEASUREMENT", "metric": metric, "measurement_id": point["id"]} for point in points]


def _metric_items(metric: Dict[str, Any]) -> List[Dict[str, Any]]:
    points = metric.get("points") or []
    if len(points) < 2:
        return []

    name, label, unit = metric["metric"], metric["label"], metric["unit"]
    prev, last = points[-2], points[-1]
    change = last["value"] - prev["value"]
    if abs(change) >= NOTABLE_CHANGE.get(name, float("inf")):
        way = "올랐어요" if change > 0 else "내려갔어요"
        return [
            {
                "text": f"{label}이 지난 측정({prev['date']}, {_fmt(prev['value'])}{unit})보다 {_fmt(abs(change))}{unit} {way}"
                f"({_fmt(last['value'])}{unit}). 잴 때 상황(시간 · 식사 · 약 드신 때)이 같았는지 확인해 보세요.",
                "basis": _measurement_basis(name, prev, last),
            }
        ]

    if len(points) >= 3:
        a, b, c = points[-3:]
        if a["value"] < b["value"] < c["value"] or a["value"] > b["value"] > c["value"]:
            way = "올랐어요" if c["value"] > a["value"] else "내려갔어요"
            path = " → ".join(_fmt(point["value"]) for point in (a, b, c))
            return [
                {
                    "text": f"{label}이 최근 3번 이어서 {way}({path}{unit}). 요즘 생활에 달라진 점이 있는지 여쭤 보세요.",
                    "basis": _measurement_basis(name, a, b, c),
                }
            ]
    return []


def _last_measured(metrics: List[Dict[str, Any]]) -> Optional[str]:
    dates = [point["date"] for metric in metrics for point in metric.get("points") or []]
    return max(dates) if dates else None


def rule_summary(data: Dict[str, Any]) -> str:
    metrics = data.get("metrics") or []
    sessions = data.get("sessions") or []
    profile = data.get("profile") or {}
    parts = []

    facts = [LIVING_LABELS.get(profile.get("living_arrangement") or ""), CARE_GRADE_LABELS.get(profile.get("care_grade") or "")]
    facts = [fact for fact in facts if fact]
    if facts:
        parts.append(" · ".join(facts) + ".")

    count = len({point["id"] for metric in metrics for point in metric.get("points") or []})
    last = _last_measured(metrics)
    if count:
        latest = [
            f"{metric['label']} {_fmt(metric['points'][-1]['value'])}{metric['unit']}"
            for metric in metrics
            if metric.get("points")
        ]
        parts.append(f"건강측정 {count}번(마지막 {last}) — 최근 값: {', '.join(latest[:4])}.")
    else:
        parts.append("건강측정 기록이 아직 없습니다.")

    if sessions:
        recent = sessions[-1]
        overview = (recent.get("overview") or "").strip()
        when = f", {recent['date']}" if recent.get("date") else ""
        if overview:
            if len(overview) > 160:
                overview = overview[:159] + "…"
            parts.append(f"최근 상담({recent['number']}회차{when}): {overview}")
        else:
            parts.append(f"최근 상담은 {recent['number']}회차{when}입니다.")
    else:
        parts.append("승인한 상담 기록이 아직 없습니다.")

    return " ".join(parts)


def rule_based_brief(data: Dict[str, Any]) -> Dict[str, Any]:
    """LLM 없이 묶는다. 같은 입력이면 늘 같은 답."""

    metrics = data.get("metrics") or []
    sessions = data.get("sessions") or []
    items: List[Dict[str, Any]] = []

    for metric in metrics:
        items.extend(_metric_items(metric))

    last = _last_measured(metrics)
    today = data.get("today")
    if last is None:
        items.append({"text": "아직 건강측정 기록이 없어요. 이번 상담 때 혈압 등을 재서 남겨 보세요.", "basis": []})
    elif today:
        gap = (date.fromisoformat(today) - date.fromisoformat(last)).days
        if gap >= STALE_DAYS:
            items.append({"text": f"마지막 측정이 {gap}일 전({last})이에요. 이번 상담 때 다시 재 보세요.", "basis": []})

    if sessions:
        recent = sessions[-1]
        for point in (recent.get("key_points") or [])[:2]:
            point = (point or "").strip()
            if not point:
                continue
            if len(point) > 80:
                point = point[:79] + "…"
            items.append(
                {
                    "text": f"지난 상담({recent['number']}회차)에서 나온 이야기 — {point} 그 뒤 어떻게 지내시는지 이어서 여쭤 보세요.",
                    "basis": [{"kind": "SESSION", "session_number": recent["number"]}],
                }
            )

    return {"summary": rule_summary(data), "check_items": items[:MAX_ITEMS]}


# ---------------------------------------------------------------- LLM


SYSTEM_PROMPT = """너는 고령자 건강상담 담당자를 돕는 보조 도구다. 어르신의 건강측정 기록과 지난 상담 요약을 보고,
담당자가 다음 상담 전에 읽을 짧은 요약과 '다음 상담 때 확인해 볼 점'을 쓴다. 판단은 담당자가 한다.

[꼭 지킬 것]
1. 질병 이름을 붙이거나 진단 · 의심 · 판정하지 않는다("고혈압으로 보임", "우울증 의심" 금지).
2. 측정값을 정상 · 위험으로 나누지 않는다. 값과 그 변화(지난번보다 얼마나 올랐는지 · 내렸는지)만 말한다.
3. 치료 · 약 조절(늘리기 · 줄이기 · 끊기) · 병원 진료를 권하지 않는다. 대신 담당자가 어르신께 여쭤 볼 점으로 쓴다.
4. 입력에 없는 사실을 지어내지 않는다. 확인해 볼 점마다 근거 ref(M숫자 = 측정, S숫자 = 상담 회차, P = 기본정보)를 1개 이상 단다.
5. 담당자에게 쓰는 말이다. 쉬운 존댓말, 한 항목에 한 가지만.

[출력 JSON]
{{"summary": "{max_summary}자 이내 요약", "check_items": [{{"text": "{max_chars}자 이내", "refs": ["M1", "S3"]}}]}}
check_items 는 최대 {max_items}개. 없으면 빈 목록.

[입력]
{case_input}
"""


def format_input(data: Dict[str, Any]) -> Tuple[str, Dict[str, Dict[str, Any]]]:
    """LLM 입력 글과 ref → 근거. 측정은 항목마다 최근 MAX_POINTS 개, 상담은 최근 MAX_SESSIONS 회차만."""

    refs: Dict[str, Dict[str, Any]] = {"P": {"kind": "PROFILE"}}
    lines = [f"오늘: {data.get('today') or ''}"]

    profile = data.get("profile") or {}
    lines.append("[P 기본정보]")
    lines.append(f"- 거주: {LIVING_LABELS.get(profile.get('living_arrangement') or '', '모름')}")
    lines.append(f"- {CARE_GRADE_LABELS.get(profile.get('care_grade') or '', '장기요양 등급 모름')}")
    if profile.get("health_notes"):
        lines.append(f"- 담당자가 적은 건강 메모: {profile['health_notes'].strip()}")
    if profile.get("care_notes"):
        lines.append(f"- 생활 · 돌봄 메모: {profile['care_notes'].strip()}")

    lines.append("[건강측정]")
    counter = 0
    for metric in data.get("metrics") or []:
        cells = []
        for point in (metric.get("points") or [])[-MAX_POINTS:]:
            counter += 1
            ref = f"M{counter}"
            refs[ref] = {"kind": "MEASUREMENT", "metric": metric["metric"], "measurement_id": point["id"]}
            cells.append(f"{ref} {point['date']} {_fmt(point['value'])}")
        if cells:
            lines.append(f"- {metric['label']}({metric['unit']}): " + " / ".join(cells))
    if counter == 0:
        lines.append("- 없음")

    lines.append("[지난 상담 — 담당자가 승인한 요약]")
    sessions = (data.get("sessions") or [])[-MAX_SESSIONS:]
    for session in sessions:
        ref = f"S{session['number']}"
        refs[ref] = {"kind": "SESSION", "session_number": session["number"]}
        lines.append(f"{ref} ({session.get('date') or '날짜 없음'}) {(session.get('overview') or '').strip()}")
        for point in session.get("key_points") or []:
            lines.append(f"  · {point}")
    if not sessions:
        lines.append("- 없음")

    return "\n".join(lines), refs


def clean_output(raw: Any, refs: Dict[str, Dict[str, Any]], fallback_summary: str) -> Dict[str, Any]:
    if not isinstance(raw, dict):
        raise SeniorBriefOutputError("JSON 객체가 아님")

    summary = raw.get("summary")
    if not isinstance(summary, str) or not _usable(summary.strip(), MAX_SUMMARY_CHARS):
        summary = fallback_summary

    items = []
    for item in raw.get("check_items") or []:
        if not isinstance(item, dict):
            continue
        text = item.get("text")
        if not isinstance(text, str):
            continue
        text = text.strip()
        if not _usable(text, MAX_ITEM_CHARS):
            continue
        basis = []
        for ref in item.get("refs") or []:
            if isinstance(ref, str) and ref.strip() in refs and refs[ref.strip()] not in basis:
                basis.append(refs[ref.strip()])
        if not basis:  # 근거 없는 문장은 버린다
            continue
        items.append({"text": text, "basis": basis})
        if len(items) >= MAX_ITEMS:
            break

    if not items:
        raise SeniorBriefOutputError("남은 확인사항이 없음")

    return {"summary": summary.strip(), "check_items": items}


def generate_senior_brief(
    data: Dict[str, Any],
    known_identifiers: Optional[Iterable[str]] = None,
    model: Optional[str] = None,
    deadline: Optional[float] = None,
) -> Dict[str, Any]:
    """입력 → 마스킹 → LLM → 검사 → 이름 되돌리기. 반환에 "model" 을 붙인다. 실패는 예외 그대로(서버가 코드로 바꾼다)."""

    from ai.modeling.abuse.llm_backend import build_openai_client_and_model
    from ai.modeling.abuse.pii_masking import restore_pii
    from ai.modeling.abuse.privacy_gateway import review
    from ai.modeling.abuse.second_stage_llm import _call_llm_with_retry

    names = list(known_identifiers or [])
    text, refs = format_input(data)
    masked = review({"input": [text]}, known_identifiers=names)
    client, model_name = build_openai_client_and_model(model or DEFAULT_MODEL)
    prompt = SYSTEM_PROMPT.format(
        max_summary=MAX_SUMMARY_CHARS,
        max_chars=MAX_ITEM_CHARS,
        max_items=MAX_ITEMS,
        case_input=masked.payload["input"][0],
    )
    parsed = _call_llm_with_retry(
        client=client,
        model=model_name,
        system_prompt=prompt,
        user_prompt="위 입력으로 요약과 다음 상담 확인사항을 만들어.",
        max_retries=2,
        timeout_seconds=90.0,
        deadline=deadline,
    )
    cleaned = clean_output(parsed, refs, rule_summary(data))
    restored = restore_pii(cleaned, masked.entity_map)

    return {**restored, "model": model_name}
