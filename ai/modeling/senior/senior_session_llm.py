"""
고령자 방문(회차) 통합 요약 모듈(2026-11-13, API_CONTRACT 27절 '회차 통합 요약', 개선안 ④).

고령자 사례(subject_type=SENIOR)의 회차는 STT 뒤 학대 분석 파이프라인 대신 이 모듈로 요약한다.
입력은 이번 녹취 + 이번 방문 측정값 + 이전 방문 이력(측정 추이 · 승인 요약)이고, 출력은 근거가 달린 통합 요약 ·
다음 상담 확인사항 초안 · 안전 관련 발화 표시다. 담당자가 검토 · 승인한다.

[입력 data]
{
  "today": "YYYY-MM-DD",
  "segments": [{"segment_id", "speaker", "text"}],                    # STT Contract. COUNSELOR 가 아니면 어르신 쪽으로 본다
  "visit_measurements": [{"id", "metric", "label", "unit", "value"}],  # 이번 방문(이 회차에 단) 측정
  "profile": {...}, "metrics": [...], "sessions": [...],             # senior_brief_llm 입력과 같은 모양(이전 이력)
}

[출력]
{
  "overview": str,
  "key_points": [{"text", "basis": [{"kind": "SEGMENT", "segment_ids"} | {"kind": "MEASUREMENT", "metric", "measurement_id"}]}],
  "check_points": [{"text", "basis": [...]}],          # 다음 상담 확인사항 초안(senior_brief_llm 근거 모양 + SEGMENT)
  "safety_mentions": [{"kind": "SELF_HARM" | "URGENT_HEALTH", "text", "segment_ids"}],
}

[하지 않는 것] 진단 · 정신질환 · 치매 판정 · 치료 권고(senior_brief_llm.FORBIDDEN 에 걸리는 문장은 버림), 근거 없는 문장.
안전 관련 발화는 '표시' 만 한다 — 긴급 여부는 담당자가 정한다. 낱말 찾기(SAFETY_PATTERNS)는 LLM 과 상관없이 늘 돌린다.

[LLM 없이(rule_based_session_summary)] SENIOR_AI_PROVIDER=rule(기본): 이번 측정값 한 줄 + 어르신 발화 앞 3개를 핵심 내용으로 옮기고,
확인사항은 senior_brief_llm 규칙(측정 변화 · 지난 상담), 안전 발화는 낱말 찾기만.

openai · privacy_gateway 는 CI 에 없어 import 는 함수 안에 둔다.
"""

import re
from typing import Any, Dict, Iterable, List, Optional, Tuple

from ai.modeling.senior.senior_brief_llm import (
    MAX_ITEMS as MAX_CHECK_POINTS,
    _fmt,
    _usable,
    format_input as format_history,
    rule_based_brief,
)

DEFAULT_MODEL = "gpt-5.6-luna"

MAX_OVERVIEW_CHARS = 500
MAX_POINT_CHARS = 200
MAX_KEY_POINTS = 8
MAX_SAFETY = 10
#: LLM 에 넣는 발화 글 상한. 넘으면 뒤를 자르고 '(이하 생략)' 을 붙인다.
MAX_INPUT_CHARS = 24000
RULE_KEY_POINTS = 3

COUNSELOR = "COUNSELOR"

#: 안전 관련 발화 낱말(어르신 쪽 발화만). 걸리면 담당자에게 바로 보이게 표시한다 — 판정이 아니다.
SAFETY_PATTERNS = {
    "SELF_HARM": tuple(
        re.compile(p)
        for p in (
            r"죽고\s*싶", r"죽어야", r"죽어\s*버리", r"자살", r"목숨을?\s*끊", r"살기\s*싫", r"살고\s*싶지\s*않",
            r"사라지고\s*싶", r"뛰어\s*내리", r"약을?\s*(모아|한꺼번에)", r"없어지(면|는\s*게)\s*나",
        )
    ),
    "URGENT_HEALTH": tuple(
        re.compile(p)
        for p in (
            r"가슴이?\s*(너무\s*)?(아파|아프|답답|조이|조여)", r"숨이?\s*(차|막혀|안\s*쉬어)", r"쓰러(졌|지|질)",
            r"정신을?\s*잃", r"의식이?\s*(없|흐려)", r"(한쪽|팔|다리|얼굴).{0,4}(마비|저려서\s*못|안\s*움직)",
            r"말이?\s*(어눌|안\s*나와)", r"피를?\s*(토|쏟)", r"(며칠|이틀|사흘).{0,6}(못\s*먹|굶)",
        )
    ),
}
SAFETY_LABELS = {"SELF_HARM": "자해 · 자살 관련 발화", "URGENT_HEALTH": "급한 건강 문제 관련 발화"}


class SeniorSessionOutputError(ValueError):
    """LLM 답에서 쓸 핵심 내용이 하나도 남지 않음."""


def _client_segments(segments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [
        segment
        for segment in segments
        if segment.get("speaker") != COUNSELOR and (segment.get("text") or "").strip()
    ]


def _cut(text: str, limit: int) -> str:
    text = text.strip()
    return text if len(text) <= limit else text[: limit - 1] + "…"


# ---------------------------------------------------------------- 안전 관련 발화(낱말)


def find_safety_mentions(segments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    found = []
    for segment in _client_segments(segments):
        text = segment["text"]
        for kind, patterns in SAFETY_PATTERNS.items():
            if any(pattern.search(text) for pattern in patterns):
                found.append({"kind": kind, "text": _cut(text, MAX_POINT_CHARS), "segment_ids": [str(segment.get("segment_id"))]})
                break
        if len(found) >= MAX_SAFETY:
            break
    return found


def _merge_safety(*groups: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen, merged = set(), []
    for group in groups:
        for item in group:
            key = (item["kind"], tuple(item["segment_ids"]))
            if key in seen:
                continue
            seen.add(key)
            merged.append(item)
    return merged[:MAX_SAFETY]


# ---------------------------------------------------------------- 규칙


def _visit_line(visit: List[Dict[str, Any]]) -> Optional[str]:
    if not visit:
        return None
    by_metric = {item["metric"]: item for item in visit}
    parts = []
    if "systolic" in by_metric and "diastolic" in by_metric:
        parts.append(f"혈압 {_fmt(by_metric['systolic']['value'])}/{_fmt(by_metric['diastolic']['value'])}mmHg")
    for item in visit:
        if item["metric"] in ("systolic", "diastolic"):
            continue
        parts.append(f"{item['label']} {_fmt(item['value'])}{item['unit']}")
    return "이번 측정: " + ", ".join(parts) + "."


def _visit_basis(visit: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [{"kind": "MEASUREMENT", "metric": item["metric"], "measurement_id": item["id"]} for item in visit]


def rule_overview(data: Dict[str, Any]) -> str:
    segments = data.get("segments") or []
    client = len(_client_segments(segments))
    parts = [f"상담 발화 {len(segments)}건(담당자 외 {client}건)."]
    line = _visit_line(data.get("visit_measurements") or [])
    if line:
        parts.append(line)
    parts.append("규칙으로 옮긴 내용이라 담당자가 요약을 고쳐 써 주세요.")
    return " ".join(parts)


def rule_based_session_summary(data: Dict[str, Any]) -> Dict[str, Any]:
    segments = data.get("segments") or []
    visit = data.get("visit_measurements") or []
    points = []
    line = _visit_line(visit)
    if line:
        points.append({"text": line, "basis": _visit_basis(visit)})
    for segment in _client_segments(segments)[:RULE_KEY_POINTS]:
        points.append(
            {
                "text": _cut(segment["text"], MAX_POINT_CHARS),
                "basis": [{"kind": "SEGMENT", "segment_ids": [str(segment.get("segment_id"))]}],
            }
        )
    checks = [item for item in rule_based_brief(data)["check_items"] if item["basis"]]
    return {
        "overview": rule_overview(data),
        "key_points": points,
        "check_points": checks[:MAX_CHECK_POINTS],
        "safety_mentions": find_safety_mentions(segments),
    }


# ---------------------------------------------------------------- LLM


SYSTEM_PROMPT = """너는 고령자 건강상담 담당자를 돕는 보조 도구다. 이번 방문의 건강측정 결과와 상담 녹취, 이전 방문 이력을 함께 읽고
담당자가 상담 기록에 옮길 '통합 요약' 초안과 '다음 상담 확인사항' 초안을 쓴다. 판단은 담당자가 한다.

[꼭 지킬 것]
1. 질병 이름을 붙이거나 진단 · 의심 · 판정하지 않는다("고혈압", "우울증으로 보임", "치매 의심" 금지). 어르신이 직접 말한 병명은 "~라고 말씀하심"으로만 옮긴다.
2. 측정값을 정상 · 위험으로 나누지 않는다. 값과 지난번과의 차이만 말한다.
3. 치료 · 약 조절 · 병원 진료를 권하지 않는다. 대신 다음에 다시 재거나 여쭤 볼 것으로 쓴다.
4. 기억 · 복약과 관련된 말(깜빡함, 약 먹은 걸 잊음, 같은 말 반복 등)은 판정 없이 그대로 빠뜨리지 말고 옮긴다.
5. 녹취 · 입력에 없는 사실을 지어내지 않는다. 모든 문장에 근거 ref 를 1개 이상 단다: 발화 번호(s..), 측정(M..), 이전 상담(S..), 기본정보(P).
6. 자해 · 자살과 관련된 말이나 급한 건강 문제(가슴 통증 · 숨참 · 쓰러짐 등)를 어르신이 말했으면 safety_mentions 에 그 발화 번호와 함께 적는다. 긴급한지는 정하지 않는다.
7. 담당자에게 쓰는 쉬운 존댓말. 이름 토큰은 그대로 둔다.

[출력 JSON]
{{"overview": "{max_overview}자 이내",
  "key_points": [{{"text": "{max_chars}자 이내", "refs": ["s3", "M1"]}}],          # 최대 {max_points}개
  "check_points": [{{"text": "...", "refs": ["M2", "s7"]}}],                     # 최대 {max_checks}개
  "safety_mentions": [{{"kind": "SELF_HARM" 또는 "URGENT_HEALTH", "text": "...", "refs": ["s9"]}}]}}

[이번 방문 측정]
{visit}

[이전 이력]
{history}

[이번 녹취]
{transcript}
"""


def format_transcript(segments: List[Dict[str, Any]]) -> Tuple[List[str], List[str]]:
    """(발화 줄 목록, 넣은 발화 id). 줄마다 따로 가리려고 목록으로 돌려준다."""

    lines, ids, total = [], [], 0
    for segment in segments:
        text = (segment.get("text") or "").strip()
        if not text:
            continue
        who = "담당자" if segment.get("speaker") == COUNSELOR else "어르신"
        line = f"[{segment.get('segment_id')}] {who}: {text}"
        if total + len(line) > MAX_INPUT_CHARS:
            lines.append("(이하 생략)")
            break
        lines.append(line)
        ids.append(str(segment.get("segment_id")))
        total += len(line) + 1
    return lines, ids


def format_visit(visit: List[Dict[str, Any]], refs: Dict[str, Dict[str, Any]]) -> str:
    """이번 방문 측정을 'V..' ref 로 적는다(이전 이력의 M.. 과 겹치지 않게)."""

    lines = []
    for number, item in enumerate(visit, start=1):
        ref = f"V{number}"
        refs[ref] = {"kind": "MEASUREMENT", "metric": item["metric"], "measurement_id": item["id"]}
        lines.append(f"- {ref} {item['label']} {_fmt(item['value'])}{item['unit']}")
    return "\n".join(lines) or "- 없음"


def _clean_items(raw: Any, refs: Dict[str, Dict[str, Any]], segment_ids: set, limit: int) -> List[Dict[str, Any]]:
    result = []
    for item in raw if isinstance(raw, list) else []:
        if not isinstance(item, dict) or not isinstance(item.get("text"), str):
            continue
        text = item["text"].strip()
        if not _usable(text, MAX_POINT_CHARS):
            continue
        basis: List[Dict[str, Any]] = []
        segs: List[str] = []
        for ref in item.get("refs") or []:
            ref = str(ref).strip()
            if ref in segment_ids and ref not in segs:
                segs.append(ref)
            elif ref in refs and refs[ref] not in basis:
                basis.append(refs[ref])
        if segs:
            basis.insert(0, {"kind": "SEGMENT", "segment_ids": segs})
        if not basis:  # 근거 없는 문장은 버린다
            continue
        result.append({"text": text, "basis": basis})
        if len(result) >= limit:
            break
    return result


def _clean_safety(raw: Any, segment_ids: set) -> List[Dict[str, Any]]:
    result = []
    for item in raw if isinstance(raw, list) else []:
        if not isinstance(item, dict) or item.get("kind") not in SAFETY_LABELS or not isinstance(item.get("text"), str):
            continue
        segs = [str(ref).strip() for ref in item.get("refs") or [] if str(ref).strip() in segment_ids]
        text = item["text"].strip()
        if not segs or not text or len(text) > MAX_POINT_CHARS:
            continue
        result.append({"kind": item["kind"], "text": text, "segment_ids": list(dict.fromkeys(segs))})
    return result[:MAX_SAFETY]


def clean_output(
    raw: Any, refs: Dict[str, Dict[str, Any]], segment_ids: Iterable[str], fallback_overview: str
) -> Dict[str, Any]:
    if not isinstance(raw, dict):
        raise SeniorSessionOutputError("JSON 객체가 아님")

    segs = set(segment_ids)
    overview = raw.get("overview")
    if not isinstance(overview, str) or not _usable(overview.strip(), MAX_OVERVIEW_CHARS):
        overview = fallback_overview

    key_points = _clean_items(raw.get("key_points"), refs, segs, MAX_KEY_POINTS)
    if not key_points:
        raise SeniorSessionOutputError("남은 핵심 내용이 없음")

    return {
        "overview": overview.strip(),
        "key_points": key_points,
        "check_points": _clean_items(raw.get("check_points"), refs, segs, MAX_CHECK_POINTS),
        "safety_mentions": _clean_safety(raw.get("safety_mentions"), segs),
    }


def summarize_senior_session(
    data: Dict[str, Any],
    known_identifiers: Optional[Iterable[str]] = None,
    model: Optional[str] = None,
    deadline: Optional[float] = None,
) -> Dict[str, Any]:
    """입력 → 줄마다 가리기 → LLM → 검사 → 이름 되돌리기 → 낱말 찾기와 합치기. 반환에 "model" 을 붙인다."""

    from ai.modeling.abuse.llm_backend import build_openai_client_and_model
    from ai.modeling.abuse.pii_masking import restore_pii
    from ai.modeling.abuse.privacy_gateway import review
    from ai.modeling.abuse.second_stage_llm import _call_llm_with_retry

    segments = data.get("segments") or []
    lines, ids = format_transcript(segments)
    if not ids:
        raise SeniorSessionOutputError("요약할 발화가 없음")

    history, refs = format_history(data)
    visit = format_visit(data.get("visit_measurements") or [], refs)
    masked = review({"lines": lines, "history": [history]}, known_identifiers=list(known_identifiers or []))
    client, model_name = build_openai_client_and_model(model or DEFAULT_MODEL)
    prompt = SYSTEM_PROMPT.format(
        max_overview=MAX_OVERVIEW_CHARS,
        max_points=MAX_KEY_POINTS,
        max_checks=MAX_CHECK_POINTS,
        max_chars=MAX_POINT_CHARS,
        visit=visit,
        history=masked.payload["history"][0],
        transcript="\n".join(masked.payload["lines"]),
    )
    parsed = _call_llm_with_retry(
        client=client,
        model=model_name,
        system_prompt=prompt,
        user_prompt="위 입력으로 통합 요약과 다음 상담 확인사항 초안을 만들어.",
        max_retries=2,
        timeout_seconds=120.0,
        deadline=deadline,
    )
    cleaned = clean_output(parsed, refs, ids, rule_overview(data))
    restored = restore_pii(cleaned, masked.entity_map)
    restored["safety_mentions"] = _merge_safety(find_safety_mentions(segments), restored["safety_mentions"])

    return {**restored, "model": model_name}
