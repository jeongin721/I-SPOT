"""
고령자 생활 · 정서 영역 변화(2026-11-16, 멘토 정리 '학대 분석 → 영역별 이전 대비 변화', API_CONTRACT 27절).

회차 녹취에서 식사 · 수면 · 외출 · 사회활동 · 정서 다섯 영역의 이번 상태를 뽑고, 담당자가 앞 회차에서 확정한 기록과 견준
초안을 만든다. 초안은 늘 다섯 줄(영역 순서 고정)이고 담당자가 검토 · 확정한다(PUT /sessions/{id}/care-domains).

[입력] data["segments"](STT), data["previous_domains"] = [{"domain", "text", "session_number", "date"}]
       — 영역마다 가장 최근에 확정한(이야기 있던) 기록. 없으면 그 영역은 처음 기록.
[출력 한 줄] {"domain", "text" | None, "change": SIMILAR|CHANGED|NEW|NOT_MENTIONED | None, "change_note" | None,
             "segment_ids": [...], "source": "RULE" | "AI"}
  change 가 None 이면 '이전 기록과 같은지 담당자가 견줘 주세요'(규칙은 뜻을 비교하지 못한다).

[하지 않는 것] 좋아짐 · 나빠짐 평가, 우울 · 치매 같은 판정(senior_brief_llm.FORBIDDEN), 근거 발화 없는 상태 글.
"""

import re
from typing import Any, Dict, List, Optional

from ai.modeling.senior.senior_brief_llm import _usable

DOMAINS = ("MEAL", "SLEEP", "OUTING", "SOCIAL", "MOOD")
DOMAIN_LABELS = {"MEAL": "식사", "SLEEP": "수면", "OUTING": "외출", "SOCIAL": "사회활동", "MOOD": "정서"}
CHANGES = ("SIMILAR", "CHANGED", "NEW", "NOT_MENTIONED")

MAX_TEXT_CHARS = 200
MAX_NOTE_CHARS = 200
MAX_SEGMENTS = 3
COUNSELOR = "COUNSELOR"

#: 규칙 초안의 영역 낱말(어르신 쪽 발화만). 판정이 아니라 '이 영역 이야기가 나온 발화' 를 찾는 데만 쓴다.
DOMAIN_PATTERNS = {
    "MEAL": tuple(
        re.compile(p)
        for p in (r"밥", r"식사", r"끼니", r"입맛", r"반찬", r"굶", r"배고", r"먹(었|어|고|는|을|기)", r"드셨|드시")
    ),
    "SLEEP": tuple(
        re.compile(p)
        for p in (r"잠", r"잤", r"수면", r"낮잠", r"졸려|졸리", r"(밤|새벽)에?\s*.{0,6}깨", r"(잠을?|밤에)\s*자|자다가|자려고")
    ),
    "OUTING": tuple(
        re.compile(p)
        for p in (r"산책", r"외출", r"나가(서|고|요|기|지|는)?", r"나갔", r"밖에", r"걸어", r"시장", r"집에만", r"바깥")
    ),
    "SOCIAL": tuple(
        re.compile(p)
        for p in (
            r"친구", r"이웃", r"경로당", r"복지관", r"노인정", r"자식", r"아들", r"딸", r"손주|손자|손녀", r"모임",
            r"교회|성당|절에", r"만나", r"찾아(오|와)", r"전화(가|를|도)?\s*(오|와|했|안)",
        )
    ),
    "MOOD": tuple(
        re.compile(p)
        for p in (
            r"외로|외롭", r"쓸쓸", r"심심", r"기분", r"우울", r"슬퍼|슬프", r"눈물", r"걱정", r"답답", r"힘들|힘든",
            r"즐거|재미", r"좋아(요|서|했)", r"짜증|화가", r"무서|불안",
        )
    ),
}


def _client(segments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [s for s in segments if s.get("speaker") != COUNSELOR and (s.get("text") or "").strip()]


def _cut(text: str, limit: int) -> str:
    text = text.strip()
    return text if len(text) <= limit else text[: limit - 1] + "…"


def previous_by_domain(data: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    return {
        item["domain"]: item
        for item in data.get("previous_domains") or []
        if isinstance(item, dict) and item.get("domain") in DOMAINS and (item.get("text") or "").strip()
    }


def _not_mentioned(domain: str, source: str) -> Dict[str, Any]:
    return {"domain": domain, "text": None, "change": "NOT_MENTIONED", "change_note": None, "segment_ids": [], "source": source}


def rule_domain(domain: str, segments: List[Dict[str, Any]], has_previous: bool) -> Dict[str, Any]:
    hits = [s for s in _client(segments) if any(p.search(s["text"]) for p in DOMAIN_PATTERNS[domain])][:MAX_SEGMENTS]
    if not hits:
        return _not_mentioned(domain, "RULE")
    return {
        "domain": domain,
        "text": _cut(hits[0]["text"], MAX_TEXT_CHARS),
        "change": None if has_previous else "NEW",
        "change_note": None,
        "segment_ids": [str(s.get("segment_id")) for s in hits],
        "source": "RULE",
    }


def rule_based_domains(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """영역 낱말이 나온 어르신 발화를 그대로 옮긴다. 이전과 같은지는 담당자가 견준다(change None)."""

    segments = data.get("segments") or []
    previous = previous_by_domain(data)
    return [rule_domain(domain, segments, domain in previous) for domain in DOMAINS]


# ---------------------------------------------------------------- LLM 프롬프트 · 답 검사


PROMPT_SECTION = """
[생활 · 정서 영역 — 앞 회차에 담당자가 확정한 기록]
{previous}

[영역 변화 — domains]
식사(MEAL) · 수면(SLEEP) · 외출(OUTING) · 사회활동(SOCIAL) · 정서(MOOD) 다섯 영역마다 한 줄씩 쓴다.
- text: 이번 녹취에서 그 영역에 대해 어르신이 말씀하신 이번 상태(사실만, {max_text}자 이내). refs 에 발화 번호를 꼭 단다.
- change: 위 앞 회차 기록과 견줘 SIMILAR(비슷함) · CHANGED(달라짐). 앞 기록이 없으면 NEW. 이번에 그 영역 이야기가 없으면 NOT_MENTIONED(text · refs 비움).
- change_note: CHANGED 일 때 무엇이 어떻게 달라졌는지 '이전 → 이번' 사실로({max_note}자 이내). 좋아짐 · 나빠짐 · 위험 같은 평가, 우울 · 치매 같은 판정은 쓰지 않는다.
"""

#: 출력 JSON 안내에 그대로 끼우는 줄(format 값으로 들어가므로 중괄호를 겹치지 않는다).
PROMPT_OUTPUT = """  "domains": [{"domain": "MEAL", "text": "...", "change": "CHANGED", "change_note": "...", "refs": ["s4"]}]"""


def format_previous(data: Dict[str, Any]) -> str:
    previous = previous_by_domain(data)
    lines = []
    for domain in DOMAINS:
        item = previous.get(domain)
        label = f"{DOMAIN_LABELS[domain]}({domain})"
        if item is None:
            lines.append(f"- {label}: 앞 기록 없음")
        else:
            lines.append(f"- {label}, {item.get('session_number')}회차 {item.get('date') or ''}: {item['text'].strip()}")
    return "\n".join(lines)


def prompt_section(data: Dict[str, Any]) -> str:
    return PROMPT_SECTION.format(previous=format_previous(data), max_text=MAX_TEXT_CHARS, max_note=MAX_NOTE_CHARS)


def _clean_one(item: Dict[str, Any], segment_ids: set, has_previous: bool) -> Optional[Dict[str, Any]]:
    change = item.get("change")
    if change not in CHANGES:
        return None
    domain = item["domain"]
    if change == "NOT_MENTIONED":
        return _not_mentioned(domain, "AI")

    text = item.get("text")
    if not isinstance(text, str) or not _usable(text.strip(), MAX_TEXT_CHARS):
        return None
    segs = list(dict.fromkeys(str(ref).strip() for ref in item.get("refs") or [] if str(ref).strip() in segment_ids))
    if not segs:  # 근거 없는 상태 글은 버린다
        return None

    # 앞 기록이 있고 없음에 맞춘다(LLM 이 앞 기록을 잘못 읽었을 때).
    if not has_previous:
        change = "NEW"
    elif change == "NEW":
        change = None

    note = item.get("change_note")
    note = note.strip() if isinstance(note, str) else ""
    if change != "CHANGED" or not _usable(note, MAX_NOTE_CHARS):
        note = ""

    return {
        "domain": domain,
        "text": text.strip(),
        "change": change,
        "change_note": note or None,
        "segment_ids": segs[:MAX_SEGMENTS],
        "source": "AI",
    }


def clean_domains(raw: Any, data: Dict[str, Any], segment_ids: set) -> List[Dict[str, Any]]:
    """LLM 답을 다섯 줄로. 빠지거나 못 쓰는 영역은 규칙 초안으로 채운다(source RULE)."""

    segments = data.get("segments") or []
    previous = previous_by_domain(data)
    given: Dict[str, Dict[str, Any]] = {}
    for item in raw if isinstance(raw, list) else []:
        if isinstance(item, dict) and item.get("domain") in DOMAINS and item["domain"] not in given:
            given[item["domain"]] = item

    result = []
    for domain in DOMAINS:
        cleaned = None
        if domain in given:
            cleaned = _clean_one(given[domain], segment_ids, domain in previous)
        result.append(cleaned or rule_domain(domain, segments, domain in previous))
    return result
