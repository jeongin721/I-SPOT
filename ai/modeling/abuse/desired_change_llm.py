"""
"상담 요약" 화면의 "앞으로 원하는 변화 · 원하는 서비스/지원" 칸을 채우는
LLM 모듈(2026-10-27 추가).

[왜 필요한가]

10/27 디자인(counselor-design/screens/NoteWrite.dc.html)의 상담 요약은
사정 관점 4칸이다 — (안전관련) 조사 후 변화된 사항 · 아동안전과 관련된
강점과 자원 · 아동안전과 관련된 위험요인 · 앞으로 원하는 변화 · 원하는
서비스/지원. 앞의 셋은 이미 만들던 값이 있다(session_change.py,
narrative_summary_llm.py의 강점·위험 문단). 네 번째만 만드는 곳이 없어서
이 모듈을 추가했다.

[입력 — 이미 만든 값 재사용]

record_draft_llm.build_transcript_citation_text()로 만들고 호출부가
mask_for_outbound()로 마스킹한 축어록을 그대로 받는다
(protective_factor_llm.py와 같은 입력). 아동이 바람을 말한 줄은 핵심
진술 요지(child_statement_points)에 안 들어갈 때가 많아서("할머니 집에
가고 싶어요") 요지가 아니라 축어록 전체를 본다.

[설계 결정]

- 별도 호출이다 — 위험신호 탐지 프롬프트를 건드리지 않는다
  (protective_factor_llm.py · narrative_summary_llm.py와 같은 원칙).
- 항목마다 segment_id를 인용하게 하고, 실제 segment에 없는 번호는
  버린다. 근거 없는 항목은 뺀다(followup_check_llm._clean_points와 같은
  정책). 화면에는 항목을 한 문단으로 이어 붙여 보인다(join_points).
- 서비스/지원은 아동 · 보호자가 직접 말한 바람이나, 진술에서 바로
  드러나는 필요(다쳤다고 말함 → 의료 확인)까지만 쓴다. 입력에 없는
  사실을 지어내지 않는다.
"""

import threading
from typing import Any, Dict, List, Optional

from openai import OpenAI

from ai.modeling.abuse.second_stage_llm import _call_llm_with_retry

DEFAULT_MODEL = "gpt-5.6-luna"

#: 근거 있는 항목이 하나도 없을 때 칸에 들어가는 문구.
#: narrative_summary_llm.py의 강점·위험 문단과 같은 문구를 쓴다.
EMPTY_TEXT = "확인된 내용 없음"


SYSTEM_PROMPT = """너는 아동 상담 사례관리 문서의 "상담 요약"에서
"앞으로 원하는 변화 · 원하는 서비스/지원" 칸을 쓰는 도우미다.

[원칙]
1. 아동(또는 보호자)이 축어록에서 직접 말한 바람·원하는 변화만 쓴다
   (예: "할머니 집에 가고 싶어요" → 조모 집에 가고 싶다고 말함).
2. 서비스/지원은 진술에서 바로 드러나는 필요만 쓴다(예: 다친 곳이
   아프다고 말했는데 치료 이야기가 없음 → 통증 부위 의료 확인 필요).
   입력에 없는 사실, 원인, 정도를 추가하거나 추측하지 않는다.
3. "학대 의심", "위험도가 높다" 같은 판정 표현을 쓰지 않는다.
4. 상담사 질문에 들어 있는 내용을 아동이 확인하지 않았으면 근거가
   아니다.
5. 항목마다 1문장, 간결하게. 최대 4개.
6. 항목마다 그 내용이 나온 축어록 줄의 segment_id를 정확히 인용한다.
   근거 없는 segment_id는 지어내지 않는다. 인용할 segment_id가 없으면
   그 항목을 넣지 않는다.
7. 해당하는 내용이 없으면 빈 리스트를 반환한다 — 억지로 만들지 않는다.

[출력 형식]

반드시 아래 JSON 형식으로만 답한다:
{
  "desired_change_points": [
    {"text": "...", "segment_ids": ["seg_001"]}
  ]
}
"""


def _clean_points(
    raw_points: Any,
    valid_segment_ids: set,
) -> List[Dict[str, Any]]:
    """followup_check_llm._clean_points와 같은 검증 — 실제 segment에 있는
    번호만 남기고, 근거가 하나도 없는 항목은 뺀다."""

    if not isinstance(raw_points, list):
        return []

    cleaned: List[Dict[str, Any]] = []

    for item in raw_points:
        if not isinstance(item, dict):
            continue

        text = item.get("text")

        if not isinstance(text, str) or not text.strip():
            continue

        segment_ids = [
            str(sid)
            for sid in (item.get("segment_ids") or [])
            if isinstance(sid, (str, int))
            and str(sid) in valid_segment_ids
        ]

        if not segment_ids:
            continue

        cleaned.append({"text": text.strip(), "segment_ids": segment_ids})

    return cleaned


def join_points(points: List[Dict[str, Any]]) -> Dict[str, Any]:
    """항목 목록 → 칸 하나({text, segment_ids}). 근거 번호는 처음 나온
    순서대로 중복 없이 모은다. 항목이 없으면 EMPTY_TEXT."""

    texts = [p["text"] for p in points if p.get("text")]
    segment_ids: List[str] = []

    for p in points:
        for sid in p.get("segment_ids") or []:
            if sid not in segment_ids:
                segment_ids.append(sid)

    return {
        "text": " ".join(texts) if texts else EMPTY_TEXT,
        "segment_ids": segment_ids,
    }


def generate_desired_changes(
    client: OpenAI,
    model: str,
    masked_transcript_text: str,
    segments: List[Dict[str, Any]],
    deadline: Optional[float] = None,
    stop_event: Optional[threading.Event] = None,
) -> List[Dict[str, Any]]:
    """
    masked_transcript_text: protective_factor_llm.generate_protective_factors와
    같은 마스킹된 축어록. 반환값도 마스킹된 상태라 호출부가 restore_pii()를
    적용해야 한다.
    segments: 원본 segment 목록 — segment_id 검증에만 쓴다.

    LLM 호출이 실패해도 예외를 던지지 않고 빈 리스트를 준다(보호요인과
    같은 정책 — 이 칸 하나 때문에 분석 전체가 실패하지 않게).
    """

    valid_segment_ids = {
        str(segment.get("segment_id", "")) for segment in segments
    }

    if not masked_transcript_text.strip():
        return []

    try:
        parsed = _call_llm_with_retry(
            client=client,
            model=model,
            system_prompt=SYSTEM_PROMPT,
            user_prompt=f"[축어록]\n\n{masked_transcript_text}",
            max_retries=2,
            timeout_seconds=180.0,
            deadline=deadline,
            stop_event=stop_event,
        )
    except Exception:
        parsed = {}

    if not isinstance(parsed, dict):
        parsed = {}

    return _clean_points(
        parsed.get("desired_change_points"),
        valid_segment_ids,
    )
