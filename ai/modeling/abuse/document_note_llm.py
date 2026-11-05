"""
상담 기록 문서 → 3단계(상담 요약 · 상담 일지) 칸 채우기와 4단계(확인 사항 · 추가 질문) 초안(2026-11-02).

녹취 · 자료 올리기에서 **상담사가 이미 쓴 상담 기록 문서**를 올리면 1(기록 확인) · 2(학대 신호 확인)는 건너뛰고,
이 모듈이 그 글을 3단계 칸에 나눠 옮긴다. 새로 분석하거나 요약하지 않는다 — 상담사 문장을 **그대로 옮긴다**.

[3단계 — fill_note]
입력: 문서 글. 출력:
{
  "assessment": {safety_changes, strengths_resources, safety_risks, desired_changes},   # 상담 요약 사정 4칸
  "note": {statement, attitude, environment, signals, opinion},                        # 상담 일지 칸
  "overview": "...",
}
코드 검사(clean_note): 칸 이름은 위 키만, 글 길이 상한, 다른 나라 문자 섞이면 버림,
**원문 문장과 통째로 같지 않은 문장은 버림**(keep_copied — 공백 · 문장 부호만 빼고 원문 덩어리 하나와 같아야 한다. 앞부분만 자른 것도 버린다.
덩어리는 마침표 · 빈 줄 · 새 항목 사이 — 마침표 없이 바뀐 줄 · 쪽은 이어 본다. 줄 머리 칸 이름은 실제 칸 이름 · 별칭만 뗀다).
LLM 이 지어내거나 뜻을 바꾼 문장('방문하지 않음' → '방문함')이 상담 일지에 들어가지 않게 하는 장치다(민규 #137 R1 — 전에는
글자 두 개 조각 60% 겹침이라 부정어가 빠진 문장도 통과했다). 문서에 없는 칸은 빈 칸으로 둔다.

[4단계 — draft_followups]
입력: 상담사가 3단계에서 확정 · 저장한 칸(요약 4칸 + 일지). 출력: {"checks": [{text}], "questions": [{text, reason}]}.
추가 질문은 followup_question_llm 의 유도 질문 검사(열린 질문 · 입력에 없는 인물 · 행위 낱말 금지)를 그대로 쓴다.
근거 위치(segment_ids)는 없다 — 문서 회차에는 전사본이 없다.

[LLM 없이 — rule_based_note]
AI_PROVIDER 가 modeling 이 아니면(시험 · 데모 mock) '[칸 이름]' · '칸 이름:' 머리줄로 나눈 글만 옮긴다(AI 아님).

개인정보: 글은 privacy_gateway.mask_for_outbound 로 가린 뒤 보내고, 답은 restore_pii 로 되돌린다.
openai · privacy_gateway(NER 모델)는 CI 에 없어 그 import 는 함수 안에 둔다(검사 함수는 backend/tests 에서 시험).
"""

import re
from typing import Any, Dict, List, Optional

from ai.modeling.abuse.followup_question_llm import _introduces_new_word, _is_open_question
from ai.modeling.abuse.text_script import has_foreign_script

DEFAULT_MODEL = "gpt-5.6-luna"

ASSESSMENT_FIELDS = (
    ("safety_changes", "조사 후 변화된 사항"),
    ("strengths_resources", "강점과 자원"),
    ("safety_risks", "위험요인"),
    ("desired_changes", "원하는 변화"),
)
NOTE_FIELDS = (
    ("statement", "아동 진술"),
    ("attitude", "대상자 태도"),
    ("environment", "물리적 환경"),
    ("signals", "위험 신호 검토 결과"),
    ("opinion", "소견"),
)
#: 머리줄로 칸을 찾을 때 같은 칸으로 보는 다른 이름(rule_based_note).
HEADING_ALIASES = {
    "safety_changes": ("조사 후 변화", "변화된 사항"),
    "strengths_resources": ("강점", "자원"),
    "safety_risks": ("위험요인", "위험 요인"),
    "desired_changes": ("원하는 변화", "원하는 서비스"),
    "statement": ("아동 진술", "아동진술", "진술"),
    "attitude": ("대상자 태도", "태도"),
    "environment": ("물리적 환경", "환경"),
    "signals": ("위험 신호", "위험신호", "위험 신호 검토 결과", "위험신호 검토 결과"),
    "opinion": ("소견", "상담자 소견", "상담원 소견"),
    "overview": ("개요", "상담 개요", "요약"),
}

MAX_FIELD_CHARS = 2000
MAX_OVERVIEW_CHARS = 500
#: 문서 글 상한(업로드 서버도 같은 값으로 막는다).
MAX_DOCUMENT_CHARS = 30000

MAX_CHECKS = 5
MAX_QUESTIONS = 5
MAX_ITEM_CHARS = 300


class DocumentNoteOutputError(Exception):
    """LLM 응답에 쓸 칸이 하나도 남지 않음."""


# ------------------------------------------------------------
# 코드 검사
# ------------------------------------------------------------


def _squash(value: Any, limit: int) -> str:
    if not isinstance(value, str):
        return ""
    text = "\n".join(" ".join(line.split()) for line in value.strip().splitlines() if line.strip())
    if not text or len(text) > limit or has_foreign_script(text):
        return ""
    return text


#: 옮겨 적은 문장을 원문과 맞출 때 빼는 것 — 공백 · 문장 부호(줄 바꿈 · 띄어쓰기 · 마침표 정리는 바꿔 쓰기가 아니다).
#: '~' · '-' 는 빼지 않는다 — '주 3~4회' 가 '주 34회' 와 같아지면 안 된다(민규 #137 보완). 줄 앞 글머리표만 따로 뗀다.
_IGNORED = re.compile(r"[\s.,!?;:·•‧∙*'\"“”‘’()\[\]{}<>「」『』…]+")
_BULLET = re.compile(r"^[\s\-–—•·*]+")
#: 원문 줄 머리의 '[칸 이름]' · '칸 이름:' — 이름이 **실제 칸 이름 · 별칭일 때만** 떼고 그 뒤 글만 옮긴 것도 그 문장으로 본다.
#: 아무 말이나 떼면 '다음 문장은 사실이 아님: 보호자가 방문함.' 에서 '보호자가 방문함.' 만 통과한다(민규 #137 교차검증 11/05).
_HEADING = re.compile(r"^\s*(?:\[([^\]\n]{1,30})\]|([^:：\n\[\]]{1,20})[:：])\s*")
#: 문장 경계(마침표 · 물음표 · 느낌표 뒤 공백, 줄 바꿈) — 옮긴 글을 나눌 때.
_SENTENCE_END = re.compile(r"(?<=[.!?。])\s+|\n+")
#: 문장이 끝난 조각(끝 따옴표 · 괄호는 넘어서 본다).
_CLOSED = re.compile(r"[.!?。][\"'”’)\]」』]*$")
#: 다음 줄이 새 항목으로 시작하는가(글머리표 · 번호 · '[칸]' · '이름:') — 그러면 앞 줄은 거기서 끝난 것으로 본다.
_ITEM_START = re.compile(r"\s*(?:[-–—•·∙*▪◦○●■□◆◇▶►※→]|\(?\d{1,3}[.)]|\[|[^\s:：\[\]][^:：\[\]]{0,19}[:：])")
#: 옮긴 글 조각을 이어 원문 덩어리 하나와 맞춰 보는 최대 조각 수(마침표 없는 목록 · 여러 줄 문장).
_MAX_JOIN = 12


def _key(piece: str) -> str:
    return _IGNORED.sub("", _BULLET.sub("", piece))


_HEADING_KEYS = {
    _key(name)
    for name in [label for _, label in ASSESSMENT_FIELDS + NOTE_FIELDS]
    + [alias for aliases in HEADING_ALIASES.values() for alias in aliases]
}


def _strip_heading(text: str) -> str:
    matched = _HEADING.match(text)
    if matched and _key(matched.group(1) or matched.group(2) or "") in _HEADING_KEYS:
        return text[matched.end():]
    return text


def _source_runs(source: str) -> set:
    """원문을 '확실한 경계' 사이 덩어리로 나눈 비교 열쇠(와 실제 칸 이름을 뗀 열쇠).

    확실한 경계: 마침표 · 물음표 · 느낌표, 빈 줄, 글 끝, 다음 줄이 새 항목(글머리표 · 번호 · 칸 이름), 칸 이름만 있는 줄.
    마침표 없이 바뀐 줄(PDF 줄 · 쪽 꺾임 '아동은 맞았다⏎고 말하지 않았다.', 마침표 없는 목록)은 경계로 보지 않고 다음 줄과
    한 덩어리로 묶는다 — 덩어리 앞부분만 옮긴 조각('아동은 맞았다.')은 통과하지 않고, 덩어리를 통째로 옮기면(여러 줄로
    나눠 옮겨도) 통과한다(민규 #137 교차검증 11/05 — 전에는 줄 바꿈을 문장 경계로 믿어 조각이 201, 온 문장이 502).
    """

    lines = source.split("\n")
    segments: List[tuple] = []  # (열쇠, 확실히 끝남, 줄 첫 조각, 글)
    for index, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            if segments:
                segments[-1] = (*segments[-1][:1], True, *segments[-1][2:])
            continue
        following = next((later for later in lines[index + 1:] if later.strip()), None)
        heading_only = bool(re.fullmatch(r"\[[^\]\n]{1,30}\]|[^\n]{1,20}[:：]", stripped))
        line_closed = (
            following is None
            or heading_only
            or bool(_ITEM_START.match(following))
            or not lines[index + 1].strip()
        )
        pieces = [piece for piece in re.split(r"(?<=[.!?。])\s+", stripped) if _key(piece)]
        for position, piece in enumerate(pieces):
            last = position == len(pieces) - 1
            closed = bool(_CLOSED.search(piece)) or (last and line_closed)
            segments.append((_key(piece), closed, position == 0, piece))

    runs = set()
    for start in range(len(segments)):
        if start and not segments[start - 1][1]:
            continue
        end = start
        while end < len(segments) - 1 and not segments[end][1]:
            end += 1
        tail = "".join(segment[0] for segment in segments[start + 1:end + 1])
        runs.add(segments[start][0] + tail)
        if segments[start][2]:
            runs.add(_key(_strip_heading(segments[start][3])) + tail)
    runs.discard("")
    return runs


def _kept_pieces(text: str, source: str) -> tuple:
    """옮긴 글을 조각으로 나눠, 이어 붙이면 원문 덩어리 하나와 통째로 같은 조각들만 남긴다 → (모든 조각, 남긴 조각)."""

    runs = _source_runs(source)
    pieces = [piece.strip() for piece in _SENTENCE_END.split(text) if _key(piece)]
    kept: List[str] = []
    index = 0
    while index < len(pieces):
        joined = ""
        hit = None
        for end in range(index, min(len(pieces), index + _MAX_JOIN)):
            joined += _key(pieces[end])
            if joined in runs:
                hit = end
                break
        if hit is None:
            index += 1
            continue
        kept.extend(pieces[index:hit + 1])
        index = hit + 1
    return pieces, kept


def keep_copied(text: str, source: str) -> str:
    """text 에서 원문(source)의 **덩어리 하나와 통째로 같은** 문장(들)만 남긴다(공백 · 문장 부호만 보지 않는다).

    낱말 하나라도 다르거나, 원문 덩어리의 앞부분만 잘라 옮긴 것('맞았다고 말하지 않았다' → '맞았다')도 버린다 — 한국어는
    부정이 문장 끝에 와서 자르기만 해도 뜻이 뒤집힌다(민규 #137 R1 · 보완). 덩어리는 _source_runs 참고."""

    pieces, kept = _kept_pieces(text, source)
    # 다 맞으면 줄 바꿈까지 그대로 둔다.
    return text if kept and len(kept) == len(pieces) else " ".join(kept)


def copied_from_source(text: str, source: str) -> bool:
    """text 의 모든 문장이 원문 덩어리와 통째로 같은가."""

    pieces, kept = _kept_pieces(text, source)
    return bool(pieces) and len(kept) == len(pieces)


def clean_note(raw: Any, source: str) -> Dict[str, Any]:
    """LLM 답을 모듈 docstring 의 검사로 거른다. 남는 칸이 하나도 없으면 DocumentNoteOutputError."""

    raw = raw if isinstance(raw, dict) else {}

    def pick(group: Any, fields) -> Dict[str, str]:
        group = group if isinstance(group, dict) else {}
        out = {}
        for key, _label in fields:
            text = _squash(group.get(key), MAX_FIELD_CHARS)
            out[key] = keep_copied(text, source) if text else ""
        return out

    assessment = pick(raw.get("assessment"), ASSESSMENT_FIELDS)
    note = pick(raw.get("note"), NOTE_FIELDS)
    overview = _squash(raw.get("overview"), MAX_OVERVIEW_CHARS)
    overview = keep_copied(overview, source) if overview else ""

    if not any(assessment.values()) and not any(note.values()) and not overview:
        raise DocumentNoteOutputError("남는 칸이 없습니다.")

    return {"assessment": assessment, "note": note, "overview": overview}


def rule_based_note(text: str) -> Dict[str, Any]:
    """LLM 없이 '[칸 이름]' · '칸 이름:' 머리줄로 나눈 글만 옮긴다. 머리줄이 없으면 모두 빈 칸(개요만 앞부분)."""

    sections: Dict[str, List[str]] = {}
    current: Optional[str] = None

    for line in text.splitlines():
        stripped = line.strip()
        match = re.match(r"^\[?\s*([^\]:：]{1,20}?)\s*[\]:：]\s*(.*)$", stripped)
        key = None
        if match:
            head = match.group(1).strip()
            for field, aliases in HEADING_ALIASES.items():
                if any(head == alias or head.endswith(alias) for alias in aliases):
                    key = field
                    break
        if key:
            current = key
            rest = match.group(2).strip()
            sections.setdefault(key, [])
            if rest:
                sections[key].append(rest)
        elif current and stripped:
            sections[current].append(stripped)

    def joined(key: str, limit: int) -> str:
        return _squash("\n".join(sections.get(key, [])), limit)

    overview = joined("overview", MAX_OVERVIEW_CHARS)
    if not sections:
        overview = _squash(" ".join(text.split())[:MAX_OVERVIEW_CHARS], MAX_OVERVIEW_CHARS)

    return {
        "assessment": {key: joined(key, MAX_FIELD_CHARS) for key, _ in ASSESSMENT_FIELDS},
        "note": {key: joined(key, MAX_FIELD_CHARS) for key, _ in NOTE_FIELDS},
        "overview": overview,
    }


def note_input_text(assessment: Dict[str, str], note: Dict[str, str]) -> str:
    """4단계 입력 글 — 3단계에서 상담사가 확정 · 저장한 칸을 이름표와 함께 묶는다(빈 칸은 뺀다)."""

    lines = []
    for key, label in ASSESSMENT_FIELDS:
        if (assessment.get(key) or "").strip():
            lines.append(f"- {label}: {' '.join(assessment[key].split())}")
    for key, label in NOTE_FIELDS:
        if (note.get(key) or "").strip():
            lines.append(f"- {label}: {' '.join(note[key].split())}")
    return "\n".join(lines)


def clean_followups(raw: Any, source: str) -> Dict[str, List[Dict[str, str]]]:
    """확인 사항: 길이 · 다른 나라 문자. 추가 질문: 거기에 열린 질문 · 입력에 없는 인물 · 행위 낱말 금지(followup_question_llm)."""

    raw = raw if isinstance(raw, dict) else {}
    checks: List[Dict[str, str]] = []
    for item in raw.get("checks") or []:
        text = _squash(item.get("text") if isinstance(item, dict) else item, MAX_ITEM_CHARS)
        if text and all(text != other["text"] for other in checks) and len(checks) < MAX_CHECKS:
            checks.append({"text": text})

    questions: List[Dict[str, str]] = []
    for item in raw.get("questions") or []:
        if not isinstance(item, dict):
            continue
        text = _squash(item.get("text"), MAX_ITEM_CHARS)
        reason = _squash(item.get("reason"), MAX_ITEM_CHARS)
        if not text or text.count("?") > 1 or not _is_open_question(text) or _introduces_new_word(text, source):
            continue
        if all(text != other["text"] for other in questions) and len(questions) < MAX_QUESTIONS:
            questions.append({"text": text, "reason": reason})

    return {"checks": checks, "questions": questions}


# ------------------------------------------------------------
# LLM
# ------------------------------------------------------------

NOTE_PROMPT = """너는 아동보호전문기관 상담사가 이미 쓴 상담 기록 문서를 기관 양식 칸에 나눠 옮기는 도우미다.

[원칙]
1. 문서의 문장을 **그대로 옮긴다.** 요약 · 바꿔 쓰기 · 덧붙이기를 하지 않는다. 여러 문장을 한 칸에 옮겨도 된다.
2. 문서에 없는 내용은 쓰지 않는다. 해당 내용이 없는 칸은 빈 글("")로 둔다. 짐작하지 않는다.
3. 학대 여부를 판정하지 않는다.
4. 문서 속 표지([이름1] 같은 것)는 그대로 둔다.

[칸]
assessment(상담 요약 사정 관점):
  safety_changes = (안전관련) 조사 후 변화된 사항
  strengths_resources = 아동안전과 관련된 강점과 자원
  safety_risks = 아동안전과 관련된 위험요인
  desired_changes = 앞으로 원하는 변화 · 원하는 서비스/지원
note(상담 일지):
  statement = 아동 진술(아동이 한 말)
  attitude = 대상자(보호자 · 사례관리대상자) 태도
  environment = 물리적 환경(집 · 방문 장소 상태)
  signals = 위험 신호 검토 결과
  opinion = 상담원 소견
overview = 상담 개요(문서 첫머리의 개요 문장, 없으면 "")

[문서]
{document}

문장은 한국어로만 쓴다(다른 나라 글자를 섞지 않는다).
반드시 아래 JSON 형식으로만 답한다:
{{"assessment": {{"safety_changes": "", "strengths_resources": "", "safety_risks": "", "desired_changes": ""}},
  "note": {{"statement": "", "attitude": "", "environment": "", "signals": "", "opinion": ""}},
  "overview": ""}}
"""

FOLLOWUP_PROMPT = """너는 아동보호전문기관 상담사가 다음 상담을 준비하도록 돕는 도우미다. 아래는 상담사가 확정한 이번 회차 상담 기록이다.

[만들 것]
1. checks — 다음 상담 전에 상담사가 확인할 사항(최대 {max_checks}개). 기록에서 언급됐지만 뒤가 안 나온 것
   (치료 여부, 지금의 안전, 약속한 연계 등)을 우선. 한 문장, "~ 확인 필요." 꼴.
2. questions — 다음 상담에서 아동에게 건넬 열린 질문 초안(최대 {max_questions}개)과 reason(왜 필요한지 상담사에게 한 문장).
   - 예/아니오로 답할 수 있는 질문 금지("~했어?" "~맞지?"). "무엇 · 어떻게 · 어디 · 언제 · 누구 · 어땠어 · 이야기해 줄래" 꼴만.
   - "왜 ~했어?" 금지. 기록에 없는 사람 · 행위 · 감정을 먼저 꺼내지 않는다. 질문 하나에 물음표 하나. 아이 눈높이 반말.
기록에 없는 사실을 지어내지 않는다. 학대 여부를 판정하지 않는다. 물을 것이 없으면 빈 리스트.

[기록]
{note}

문장은 한국어로만 쓴다(다른 나라 글자를 섞지 않는다).
반드시 아래 JSON 형식으로만 답한다:
{{"checks": [{{"text": "..."}}], "questions": [{{"text": "...", "reason": "..."}}]}}
"""


def _call(prompt: str, user_prompt: str, model: Optional[str], deadline: Optional[float]) -> Any:
    from ai.modeling.abuse.llm_backend import build_openai_client_and_model
    from ai.modeling.abuse.second_stage_llm import _call_llm_with_retry

    client, model_name = build_openai_client_and_model(model or DEFAULT_MODEL)
    parsed = _call_llm_with_retry(
        client=client,
        model=model_name,
        system_prompt=prompt,
        user_prompt=user_prompt,
        max_retries=2,
        timeout_seconds=120.0,
        deadline=deadline,
    )
    return parsed, model_name


def fill_note(
    text: str,
    known_identifiers: Optional[List[str]] = None,
    model: Optional[str] = None,
    deadline: Optional[float] = None,
) -> Dict[str, Any]:
    """문서 글 → 마스킹 → LLM → 검사(원문 복사 포함) → 이름 되돌리기. 반환에 "model" 을 붙인다."""

    from ai.modeling.abuse.pii_masking import restore_pii
    from ai.modeling.abuse.privacy_gateway import mask_for_outbound

    masked, entity_map = mask_for_outbound(text[:MAX_DOCUMENT_CHARS], known_identifiers=known_identifiers or [])
    parsed, model_name = _call(NOTE_PROMPT.format(document=masked), "위 문서를 칸에 나눠 옮겨.", model, deadline)
    # 원문 복사 검사는 가린 글끼리 한다(LLM 이 본 글이 가린 글이라서).
    cleaned = clean_note(parsed, masked)
    return {**restore_pii(cleaned, entity_map), "model": model_name}


def draft_followups(
    note_text: str,
    known_identifiers: Optional[List[str]] = None,
    model: Optional[str] = None,
    deadline: Optional[float] = None,
) -> Dict[str, Any]:
    """3단계 확정 칸(note_input_text) → 마스킹 → LLM → 검사 → 이름 되돌리기. 반환에 "model" 을 붙인다."""

    from ai.modeling.abuse.pii_masking import restore_pii
    from ai.modeling.abuse.privacy_gateway import mask_for_outbound

    masked, entity_map = mask_for_outbound(note_text, known_identifiers=known_identifiers or [])
    prompt = FOLLOWUP_PROMPT.format(max_checks=MAX_CHECKS, max_questions=MAX_QUESTIONS, note=masked)
    parsed, model_name = _call(prompt, "위 기록으로 확인 사항과 추가 질문 초안을 만들어.", model, deadline)
    cleaned = clean_followups(parsed, masked)
    return {**restore_pii(cleaned, entity_map), "model": model_name}
