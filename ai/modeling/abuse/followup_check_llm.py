"""
"유형별 위험도" 화면의 "다음 상담에서 확인할 것" 카드를 채우는 LLM
모듈(2026-10-14 추가).

[FollowupQ 화면의 "질문 은행"과 다른 범위다]

FollowupQ("추가 확인 · 질문" 단계)는 아동에게 실제로 건넬 질문 문구를
다루는 화면이라 범위 밖으로 남겨뒀다 — 아동 면담 질문은 유도성 여부가
중요한 전문 영역이라, 검증된 질문 은행에서 RAG로 가져오는 쪽이
안전하고 아직 그 은행이 없다(record_draft_llm.py 모듈 docstring 참고).

이 모듈은 질문을 만들지 않는다. "무엇이 불확실하거나 확인이 안 됐는지"
짧게 서술만 한다 — 상담사가 그걸 보고 실제 질문은 직접 설계한다. 그래서
유도질문 위험이 사실상 없어서 질문 은행 없이 바로 LLM을 써도 된다고
판단했다.

[입력 — 전부 이미 계산된 데이터 재사용]

- 신뢰도가 낮거나 화자가 불확실한 발화(segments의 is_low_confidence/
  speaker=='UNKNOWN') — 새로 분석하지 않고 STT 결과를 그대로 재사용.
- 근거 강도가 약한 위험 신호(record_draft.risk_signal_points 중
  evidence_strength=='낮음' 또는 evidence_verified==False) — 이미
  second_stage_llm이 판단해 둔 강도를 그대로 재사용.

회차 간 진술 변화(session_change.py가 만드는 문장)는 이미 완성된
문장이라 이 모듈을 거치지 않고 호출부가 결과 리스트에 그대로
덧붙인다(infer_audio_session.py 참고) — LLM이 다시 쓰면서 원문을
바꿀 위험만 생긴다.
"""

from typing import Any, Dict, List, Optional

from openai import OpenAI

from ai.modeling.abuse.second_stage_llm import _call_llm_with_retry

DEFAULT_MODEL = "gpt-5.6-luna"


SYSTEM_PROMPT = """너는 아동 상담 기록에서 "다음 상담에서 확인할 것"
목록을 만드는 도우미다.

[절대 원칙]
1. 질문 문장을 만들지 않는다("~물어보세요", "~인지 확인해 보세요" 같은
   표현 금지). 아동 면담에서 유도 질문은 심각한 문제라 실제 질문
   문구는 상담사가 직접 설계해야 한다. 너는 "무엇이 불확실하거나
   확인이 안 됐는지"만 짧게 서술한다 — 질문이 아니라 상태 설명이다.
2. 입력에 없는 사실을 추가하거나 추측·해석하지 않는다.
3. "신뢰도가 0.59라서 불명확하다" 같이 신뢰도 수치나 "화자가
   불확실하다"는 말 자체를 반복하지 않는다 — 그건 상담사가 이미 화면
   다른 곳에서 보고 있는 정보라 그대로 되풀이하면 아무 도움이 안
   된다. 대신 그 발화가 "무엇에 대한 내용인지", "누구에게 일어난
   일인지"처럼 실제로 다음 상담에서 무엇을 더 들어봐야 하는지를
   적어라. 예를 들어 "08:54의 발화는 신뢰도가 낮다"(X, 반복일 뿐) 대신
   "08:54 '그만해' 발화가 어떤 상황에서 나온 말인지 확인 필요"(O,
   구체적 내용) 처럼 쓴다.
4. "네"/"아니요"/"응" 같은 한두 단어짜리 단답은 그 자체로 확인할
   내용이 없다 — 결과에 포함하지 않는다. 실제로 더 들어볼 만한
   내용이 있는 발화만 고른다.
5. 항목마다 1문장, 간결하게. 입력에 있는 시간(mm:ss)이나 발화 내용은
   그대로 인용해도 된다.
6. 입력 항목이 비어 있거나, 전부 4번 기준으로 걸러진다면 빈 리스트를
   반환한다 — 억지로 만들지 않는다.
7. 입력에 없는 항목(예: 치료 여부, 보호자 반응 등)을 스스로 지어내지
   않는다 — 오직 주어진 입력 항목에 실제로 담긴 내용만 다룬다.

[입력 — 신뢰도가 낮거나 화자가 불확실한 발화]
{low_confidence_input}

[입력 — 근거가 약한 위험 신호]
{weak_evidence_input}

반드시 아래 JSON 형식으로만 답한다:
{{
  "check_points": ["...", "..."]
}}
"""


#: "네"/"아니요" 같은 한두 단어 단답은 신뢰도가 낮아도 그 자체로는
#: 확인할 내용이 없다 — 프롬프트에도 걸러내라고 적었지만(SYSTEM_PROMPT
#: 4번), 애초에 입력에서부터 빼서 LLM이 그걸로 억지 문장을 만들
#: 여지를 줄인다. 공백 뺀 길이로 대충 "한두 단어"를 가른다.
_MIN_SUBSTANTIVE_LENGTH = 5


def _is_trivial_utterance(text: str) -> bool:
    stripped = text.strip().rstrip(".!?,")
    compact = stripped.replace(" ", "")
    return len(compact) < _MIN_SUBSTANTIVE_LENGTH


def _format_low_confidence(
    segments: List[Dict[str, Any]],
) -> str:
    items = [
        segment
        for segment in segments
        if (
            segment.get("is_low_confidence")
            or segment.get("speaker") == "UNKNOWN"
        )
        and not _is_trivial_utterance(segment.get("text", ""))
    ]

    if not items:
        return "없음"

    lines = []

    for segment in items:
        ms = segment.get("start_ms", 0) or 0
        t = int(ms // 1000)
        ts = f"{t // 60:02d}:{t % 60:02d}"
        reason = (
            "화자 불확실"
            if segment.get("speaker") == "UNKNOWN"
            else f"신뢰도 {segment.get('confidence', 0):.2f}"
        )
        lines.append(
            f"- {ts} \"{segment.get('text', '')}\" ({reason})"
        )

    return "\n".join(lines)


def _format_weak_evidence(
    risk_signal_points: List[Dict[str, Any]],
) -> str:
    items = [
        p
        for p in risk_signal_points
        if p.get("evidence_strength") == "낮음"
        or p.get("evidence_verified") is False
    ]

    if not items:
        return "없음"

    lines = []

    for p in items:
        label = f"{p.get('major_type', '')} · {p.get('subtype', '')}"
        lines.append(
            f"- ({label}) \"{p.get('text', '')}\""
        )

    return "\n".join(lines)


#: narrative_summary_llm.py와 같은 이유로 쓰는 구분자.
SPLIT_MARKER = "\n===I-SPOT-FOLLOWUP-SPLIT===\n"


def format_inputs_for_masking(
    segments: List[Dict[str, Any]],
    risk_signal_points: List[Dict[str, Any]],
) -> str:
    return (
        _format_low_confidence(segments)
        + SPLIT_MARKER
        + _format_weak_evidence(risk_signal_points)
    )


def generate_followup_check_points_from_masked_text(
    client: OpenAI,
    model: str,
    masked_combined_text: str,
) -> List[str]:
    parts = masked_combined_text.split(SPLIT_MARKER)
    low_confidence_input = parts[0] if parts else "없음"
    weak_evidence_input = parts[1] if len(parts) > 1 else "없음"

    if (
        low_confidence_input.strip() == "없음"
        and weak_evidence_input.strip() == "없음"
    ):
        return []

    system_prompt = SYSTEM_PROMPT.format(
        low_confidence_input=low_confidence_input,
        weak_evidence_input=weak_evidence_input,
    )

    try:
        parsed = _call_llm_with_retry(
            client=client,
            model=model,
            system_prompt=system_prompt,
            user_prompt="위 입력을 바탕으로 목록을 만들어.",
            max_retries=2,
            timeout_seconds=180.0,
        )
    except Exception:
        parsed = {}

    if not isinstance(parsed, dict):
        parsed = {}

    points = parsed.get("check_points")

    if not isinstance(points, list):
        return []

    return [
        point.strip()
        for point in points
        if isinstance(point, str) and point.strip()
    ]


def generate_followup_check_points(
    client: OpenAI,
    model: str,
    segments: List[Dict[str, Any]],
    risk_signal_points: List[Dict[str, Any]],
) -> List[str]:
    """**독립 테스트/데모 전용** — 마스킹 없이 바로 LLM을 부른다.
    실제 서비스 경로(infer_audio_session.py)는 format_inputs_for_masking
    → mask_for_outbound → generate_followup_check_points_from_masked_text
    → restore_pii 순서를 쓴다(narrative_summary_llm.py와 같은 이유)."""

    combined = format_inputs_for_masking(
        segments, risk_signal_points
    )

    return generate_followup_check_points_from_masked_text(
        client, model, combined
    )


# ============================================================
# 데모
# ============================================================

if __name__ == "__main__":
    import json

    from ai.modeling.abuse.llm_backend import build_openai_client_and_model

    segments = [
        {"segment_id": "seg_020", "start_ms": 135000, "speaker": "UNKNOWN", "text": "밥도 안 줄 때가 있어요.", "confidence": 0.70, "is_low_confidence": True},
    ]
    risk_signal_points = [
        {"major_type": "신체학대", "subtype": "직접 신체 가해", "text": "등이랑 팔이요.", "evidence_strength": "낮음", "evidence_verified": False},
    ]

    client, model = build_openai_client_and_model(DEFAULT_MODEL)
    result = generate_followup_check_points(
        client=client,
        model=model,
        segments=segments,
        risk_signal_points=risk_signal_points,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
