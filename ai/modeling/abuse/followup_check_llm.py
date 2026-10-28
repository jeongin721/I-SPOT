"""
"유형별 위험도" 화면의 "다음 상담에서 확인할 것" 카드를 채우는 LLM
모듈(2026-10-14 추가, 2026-10-14 재설계).

[FollowupQ 화면의 "질문 은행"과 다른 범위다]

FollowupQ("추가 확인 · 질문" 단계)는 아동에게 실제로 건넬 질문 문구를
다루는 화면이라 범위 밖으로 남겨뒀다 — 아동 면담 질문은 유도성 여부가
중요한 전문 영역이라, 검증된 질문 은행에서 RAG로 가져오는 쪽이
안전하고 아직 그 은행이 없다(record_draft_llm.py 모듈 docstring 참고).

이 모듈은 질문을 만들지 않는다. "무엇이 불확실하거나 확인이 안 됐는지"
짧게 서술만 한다 — 상담사가 그걸 보고 실제 질문은 직접 설계한다. 그래서
유도질문 위험이 사실상 없어서 질문 은행 없이 바로 LLM을 써도 된다고
판단했다.

[2026-10-14 재설계 — 왜 바꿨나]

1차 버전은 "신뢰도 낮은 발화 + 근거 약한 위험 신호"만 입력으로 줬다.
실사용 테스트에서 두 가지 문제가 나왔다:

- "네"/"아니요" 같은 단답까지 전부 "신뢰도 X라 불명확함"으로 기계적
  나열돼서 쓸모가 없었다 → 단답은 입력에서부터 제외(_is_trivial_utterance).
- 회차 간 진술 변화(session_change.py 결과)를 이 카드에 그대로
  덧붙였었는데, 그건 이미 "상담 요약" 화면의 "(안전관련) 조사 후
  변화된 사항"에 따로 나오는 내용이라 중복이었다 → 호출부
  (infer_audio_session.py)에서 더 이상 합치지 않는다.
- 더 근본적으로, 원래 목업이 보여준 "확인할 것"(예: "등 · 팔 통증
  이후 치료 여부")은 저신뢰도 발화 나열이 아니라 "상담 내용 안에서
  언급은 됐는데 후속 결과가 안 나온 것"을 찾아내는 추론이었다. 그래서
  입력을 "저신뢰도 발화"뿐 아니라 "이번 상담에서 확인된 아동 진술 +
  위험 신호 요지" 전체로 넓히고, "언급은 됐지만 결과가 안 나온 것"을
  찾으라고 프롬프트를 바꿨다 — 단, 입력에 없는 사실 자체를 지어내는
  건 여전히 금지한다(원칙 2).

[입력 — 전부 이미 계산된 데이터 재사용, 새로 분석하지 않는다]

- 아동 진술 요지(record_draft.child_statement_points) + 위험 신호
  (record_draft.risk_signal_points) 전체 — "언급됐지만 후속이 안 된
  것"을 찾으려면 근거 강도와 무관하게 전체 맥락이 필요하다.
- 신뢰도가 낮거나 화자가 불확실한 발화(segments) — 별도 카테고리로
  남겨서 "화자/의미가 불확실하다" 종류는 계속 잡아낸다.

[2026-10-26 segment_ids 추가 — 왜 지금까지 비어 있었나]

민규(Backend) 리뷰(PR #82)에서 지적된 지점이다: 이 카드의 각 항목이
어느 발화에서 나온 건지 화면에서 보여주려면(README 원칙 3,
API_CONTRACT §8의 증거 위치 표시 요구) segment_ids가 있어야 하는데,
지금까지는 contract_adapter.py가 무조건 빈 배열을 채워 넣고 있었다
(이 모듈이 plain string 목록만 반환했기 때문). protective_factor_llm.py·
record_draft_llm.py와 같은 패턴(LLM이 segment_id를 직접 인용 → 실제
segment 목록에 있는 id만 남기고 나머지는 버림)을 그대로 가져왔다 —
근거 없는 항목은 protective_factor_llm.py처럼 엄격하게 제외한다(이
카드도 "증거 위치"가 핵심 요구사항이라 느슨하게 둘 이유가 없다).
"""

from typing import Any, Dict, List, Optional

from openai import OpenAI

from ai.modeling.abuse.case_context import format_case_context
from ai.modeling.abuse.second_stage_llm import _call_llm_with_retry

DEFAULT_MODEL = "gpt-5.6-luna"


SYSTEM_PROMPT = """너는 아동 상담 기록에서 "다음 상담에서 확인할 것"
목록을 만드는 도우미다.

[절대 원칙]
1. 질문 문장을 만들지 않는다("~물어보세요", "~인지 확인해 보세요" 같은
   표현 금지). 아동 면담에서 유도 질문은 심각한 문제라 실제 질문
   문구는 상담사가 직접 설계해야 한다. 너는 "무엇이 불확실하거나
   확인이 안 됐는지"만 짧게 서술한다 — 질문이 아니라 상태 설명이다.
2. 입력에 있는 내용 안에서 "언급은 됐지만 그 다음 결과나 후속 내용이
   안 나온 것"을 짚어내는 건 괜찮다 — 예를 들어 다친 걸 말했는데
   병원에 갔는지는 안 나왔다면 "치료 여부 확인 필요"라고 쓸 수 있다.
   하지만 입력 어디에도 없는 사실 자체(예: 실제로 언급 안 된 보호자
   반응, 사건 경위 등)를 지어내면 절대 안 된다 — 오직 입력에 실제로
   나온 내용을 근거로만 "뭐가 비어 있는지"를 말한다.
3. "신뢰도가 0.59라서 불명확하다" 같이 신뢰도 수치나 "화자가
   불확실하다"는 말 자체를 반복하지 않는다 — 그건 상담사가 이미 화면
   다른 곳에서 보고 있는 정보라 그대로 되풀이하면 아무 도움이 안
   된다. 대신 그 발화가 "무엇에 대한 내용인지", "누구에게 일어난
   일인지"처럼 실제로 다음 상담에서 무엇을 더 들어봐야 하는지를
   적어라.
4. "네"/"아니요"/"응" 같은 한두 단어짜리 단답은 그 자체로 확인할
   내용이 없다 — 결과에 포함하지 않는다.
5. 항목마다 1문장, 간결하게. 입력에 있는 시간(mm:ss)이나 발화 내용은
   그대로 인용해도 된다.
6. 입력 항목이 비어 있으면 빈 리스트를 반환한다 — 억지로 만들지 않는다.
7. 사소한 것까지 전부 나열하지 말고, 실제로 다음 상담에서 챙길 만한
   가치가 있는 것만 최대 5개까지 고른다.
8. 항목마다 그 내용이 나온 입력 줄의 segment_id를 정확히 인용한다.
   줄 앞에 [seg_001]처럼 적혀 있다 — 여러 줄에 걸쳐 있으면
   segment_id를 여러 개 적어도 된다. 근거 없는 segment_id는 지어내지
   않는다. 인용할 segment_id가 없으면 그 항목 자체를 결과에 넣지
   않는다.

[입력 — 이번 상담에서 확인된 아동 진술 · 위험 신호 요지]
{session_content_input}

[입력 — 신뢰도가 낮거나 화자가 불확실한 발화]
{low_confidence_input}

[입력 — 사례 정보(초기면접 · 지난 회차 확정 요약), 없으면 "없음"]
{case_context_input}

[사례 정보를 쓰는 법]
- 사례 정보는 이번 상담 내용을 읽는 **배경**으로만 쓴다. 예: 초기면접에 '알콜남용' 이 있고 이번에
  음주 뒤 체벌 진술이 나오면 "보호자 음주 빈도 · 음주 뒤 상황 확인 필요" 처럼 이어 짚을 수 있다.
- 지난 회차 요약에 있던 것(예: 안전 계획)이 이번 상담에 안 나왔으면 "유지 여부 확인 필요" 라고
  짚을 수 있다 — 단, 이번 상담의 관련 줄 segment_id 를 인용할 수 있을 때만.
- 사례 정보에만 있고 이번 상담에 근거 줄이 없는 항목은 만들지 않는다(segment_id 는 이번 상담 줄에서만).
- 사례 정보의 내용을 이번 상담에서 새로 확인된 사실처럼 쓰지 않는다.

반드시 아래 JSON 형식으로만 답한다:
{{
  "check_points": [
    {{"text": "...", "segment_ids": ["seg_001"]}}
  ]
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
        segment_id = segment.get("segment_id", "")
        lines.append(
            f"- [{segment_id}] {ts} \"{segment.get('text', '')}\" ({reason})"
        )

    return "\n".join(lines)


def _format_session_content(
    child_statement_points: List[Dict[str, Any]],
    risk_signal_points: List[Dict[str, Any]],
) -> str:
    lines = []

    for p in child_statement_points or []:
        text = (p.get("text") or "").strip()

        if not text:
            continue

        tag = ",".join(p.get("segment_ids") or [])
        lines.append(f"- [{tag}] (아동 진술) {text}")

    for p in risk_signal_points or []:
        text = (p.get("text") or "").strip()

        if not text:
            continue

        tag = ",".join(p.get("segment_ids") or [])
        label = f"{p.get('major_type', '')} · {p.get('subtype', '')}"
        lines.append(f"- [{tag}] ({label}) \"{text}\"")

    if not lines:
        return "없음"

    return "\n".join(lines)


#: narrative_summary_llm.py와 같은 이유로 쓰는 구분자.
SPLIT_MARKER = "\n===I-SPOT-FOLLOWUP-SPLIT===\n"


def format_inputs_for_masking(
    segments: List[Dict[str, Any]],
    child_statement_points: List[Dict[str, Any]],
    risk_signal_points: List[Dict[str, Any]],
    case_context: Any = None,
) -> str:
    """case_context(2026-10-28, case_context.py): 사례 정보. 없으면 세 번째 칸은 "없음".
    지난 회차 요약은 상담원 글이라 이름이 섞일 수 있어, 이 글 전체를 부르는 쪽이 한 번에 마스킹한다."""

    return (
        _format_session_content(
            child_statement_points, risk_signal_points
        )
        + SPLIT_MARKER
        + _format_low_confidence(segments)
        + SPLIT_MARKER
        + format_case_context(case_context)
    )


def _clean_points(
    raw_points: Any,
    valid_segment_ids: set,
) -> List[Dict[str, Any]]:
    """protective_factor_llm._clean_points와 같은 패턴 — LLM이 주장한
    segment_id를 실제 segment 목록과 대조해 검증한다. 근거(유효한
    segment_id) 없는 항목은 엄격하게 제외한다 — "증거 위치 표시"가
    이 카드의 핵심 요구사항이라 느슨하게 둘 이유가 없다(모듈
    docstring 2026-10-26 참고).

    [2026-10-27 민규 교차검증으로 발견]
    segment_ids가 list라고 그냥 믿고 돌았었다. LLM이
    "segment_ids": 5나 true처럼 list가 아닌 값을 보내면 `for sid in
    (... or [])`에서 TypeError가 나고, 이 호출은 _call_llm_with_retry의
    try/except 바깥이라 예외가 infer_audio_session까지 올라가 회차
    분석 전체가 AI_FAILED로 끝난다. {"seg_001": true} 같은 dict는
    돌면 키만 나와서 list인 것처럼 통과해 버린다 — 그래서 list인지
    먼저 확인하고, 아니면 그 항목만(전체가 아니라) 건너뛴다.
    """

    if not isinstance(raw_points, list):
        return []

    cleaned: List[Dict[str, Any]] = []

    for item in raw_points:
        if not isinstance(item, dict):
            continue

        text = item.get("text")

        if not isinstance(text, str) or not text.strip():
            continue

        raw_segment_ids = item.get("segment_ids")

        if not isinstance(raw_segment_ids, list):
            continue

        segment_ids = [
            str(sid)
            for sid in raw_segment_ids
            if isinstance(sid, (str, int)) and not isinstance(sid, bool)
            and str(sid) in valid_segment_ids
        ]

        if not segment_ids:
            continue

        cleaned.append({"text": text.strip(), "segment_ids": segment_ids})

    return cleaned


def generate_followup_check_points_from_masked_text(
    client: OpenAI,
    model: str,
    masked_combined_text: str,
    segments: List[Dict[str, Any]],
    deadline: Optional[float] = None,
) -> List[Dict[str, Any]]:
    """segments: 원본 segment 목록 — segment_id 검증에만 쓴다
    (protective_factor_llm.generate_protective_factors와 같은 이유).
    """

    valid_segment_ids = {
        str(segment.get("segment_id", "")) for segment in segments
    }

    parts = masked_combined_text.split(SPLIT_MARKER)
    session_content_input = parts[0] if parts else "없음"
    low_confidence_input = parts[1] if len(parts) > 1 else "없음"
    # 예전 판(두 칸)으로 만든 글도 받는다.
    case_context_input = parts[2] if len(parts) > 2 else "없음"

    if (
        session_content_input.strip() == "없음"
        and low_confidence_input.strip() == "없음"
    ):
        return []

    system_prompt = SYSTEM_PROMPT.format(
        session_content_input=session_content_input,
        low_confidence_input=low_confidence_input,
        case_context_input=case_context_input,
    )

    try:
        parsed = _call_llm_with_retry(
            client=client,
            model=model,
            system_prompt=system_prompt,
            user_prompt="위 입력을 바탕으로 목록을 만들어.",
            max_retries=2,
            timeout_seconds=180.0,
            deadline=deadline,
        )
    except Exception:
        parsed = {}

    if not isinstance(parsed, dict):
        parsed = {}

    return _clean_points(parsed.get("check_points"), valid_segment_ids)


def generate_followup_check_points(
    client: OpenAI,
    model: str,
    segments: List[Dict[str, Any]],
    child_statement_points: List[Dict[str, Any]],
    risk_signal_points: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """**독립 테스트/데모 전용** — 마스킹 없이 바로 LLM을 부른다.
    실제 서비스 경로(infer_audio_session.py)는 format_inputs_for_masking
    → mask_for_outbound → generate_followup_check_points_from_masked_text
    → restore_pii 순서를 쓴다(narrative_summary_llm.py와 같은 이유)."""

    combined = format_inputs_for_masking(
        segments, child_statement_points, risk_signal_points
    )

    return generate_followup_check_points_from_masked_text(
        client, model, combined, segments
    )


# ============================================================
# 데모
# ============================================================

if __name__ == "__main__":
    import json

    from ai.modeling.abuse.llm_backend import build_openai_client_and_model

    # segments는 데모용으로 축약했지만, 실제 서비스 경로(infer_audio_session.py)
    # 에서는 전체 축어록 segment 목록이 들어온다 — child_statement_points/
    # risk_signal_points의 segment_ids는 그 전체 목록을 가리키므로, 여기서도
    # seg_019·seg_020뿐 아니라 seg_050·seg_015까지 다 넣어둬야 검증을 통과한다.
    segments = [
        {"segment_id": "seg_015", "start_ms": 110000, "speaker": "CHILD", "text": "등이랑 팔이요.", "confidence": 0.95, "is_low_confidence": False},
        {"segment_id": "seg_019", "start_ms": 135000, "speaker": "UNKNOWN", "text": "밥도 안 줄 때가 있어요.", "confidence": 0.70, "is_low_confidence": True},
        {"segment_id": "seg_020", "start_ms": 383000, "speaker": "CHILD", "text": "아니요", "confidence": 0.59, "is_low_confidence": True},
        {"segment_id": "seg_050", "start_ms": 610000, "speaker": "CHILD", "text": "할머니 집에 가고 싶어요.", "confidence": 0.93, "is_low_confidence": False},
    ]
    child_statement_points = [
        {"text": "할머니 집에 가고 싶다고 말했다.", "segment_ids": ["seg_050"]},
    ]
    risk_signal_points = [
        {"major_type": "신체학대", "subtype": "직접 신체 가해", "text": "등이랑 팔이요.", "evidence_strength": "높음", "evidence_verified": True, "segment_ids": ["seg_015"]},
    ]

    client, model = build_openai_client_and_model(DEFAULT_MODEL)
    result = generate_followup_check_points(
        client=client,
        model=model,
        segments=segments,
        child_statement_points=child_statement_points,
        risk_signal_points=risk_signal_points,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
