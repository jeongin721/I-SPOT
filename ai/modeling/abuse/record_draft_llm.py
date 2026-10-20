"""
축어록 기반 "기록 초안" 화면(상담사 웹 목업 2026-10-08 기준)을 만든다.

5개 섹션 중 지금 구현하는 건 4개뿐이다 — "향후 계획"(추천 질문)은
제외했다. 이유: 질문 추천은 자유 생성보다 검증된 질문 은행에서
RAG로 찾아 보여주는 쪽이 훨씬 안전한데(아동 면담 질문은 유도성 여부가
중요한 전문 영역이라 매번 LLM이 새로 문구를 만들면 검증하기 어렵다),
지금 그런 질문 은행이 없어서 RAG를 붙일 수 없다. 은행이 생기면 그때
별도로 추가한다(2026-10-08 논의).

이 모듈이 실제로 LLM을 불러 새로 만드는 건 "아동 진술 요지" 하나뿐이다.
나머지는 전부 이미 있는 걸 재사용한다:

- 상담 개요: 세션 메타데이터로 템플릿 조립(LLM 불필요)
- 위험 신호: second_stage_llm.analyze_subtypes가 이미 만든 근거+
  타임스탬프(subtype_analysis)를 그대로 재사용한다 — 새로 또 뽑으면
  같은 내용을 다른 말로 두 번 만드는 셈이고, 이미 evidence_verified로
  검증까지 끝난 데이터를 놔두고 새 LLM 호출을 추가하는 건 낭비다.
- 상담원 관찰: 상담사가 상담 직후 직접 쓰는 칸이다. AI가 만들지 않고
  빈 문자열로 둔다 — UI에서 입력받아 case_store에 저장하면 된다.

아동 진술 요지는 문장마다 축어록 segment_id를 인용하게 만든다. LLM이
실제로 없는 segment_id를 지어낼 수 있으므로(2026-10-01 qa 재검증
작업에서 LLM이 문자열 대신 엉뚱한 객체를 반환한 사례가 있었던 것과
같은 종류의 문제), 응답을 그대로 믿지 않고 실제 segments 목록에 있는
segment_id만 남기고 나머지는 버린다.
"""

import threading
from typing import Any, Dict, List, Optional

from openai import OpenAI

from ai.modeling.abuse.second_stage_llm import _call_llm_with_retry

DEFAULT_MODEL = "gpt-5.6-luna"

SYSTEM_PROMPT = """너는 아동 상담 축어록을 읽고 "기록 초안"의 "아동 진술 요지"
섹션을 작성하는 도우미다.

[공통 원칙]
1. 원문에 없는 사실을 추가하지 않는다.
2. 학대 여부나 학대 유형을 판단하지 않는다("학대 의심", "위험도가 높다" 같은
   판정 표현을 쓰지 않는다).
3. 상담사 질문 자체를 사실로 쓰지 않는다 — 아동/내담자의 실제 발화만 사용한다.
4. 문장마다 그 내용이 나온 축어록 줄의 segment_id를 정확히 인용한다.
   여러 줄에 걸쳐 있으면 segment_id를 여러 개 적어도 된다. 근거 없는
   문장은 만들지 않는다.

[아동 진술 요지]
- 아동이 상담에서 실제로 말한 내용을 짧은 문장(불릿) 여러 개로 정리한다.
- 일상적인 내용(학교, 친구, 취미)도 중요하면 포함한다.
- 이전 상담과 비교하거나 "달라졌다"/"줄었다" 같은 판단은 하지 않는다 —
  이번 상담에서 실제로 나온 말만 그대로 적는다.
- 문장마다 segment_id를 1개 이상 반드시 인용한다.

반드시 아래 JSON 형식으로만 답한다:
{
  "child_statement_points": [
    {"text": "...", "segment_ids": ["seg_001"]}
  ]
}
"""


def build_transcript_citation_text(
    segments: List[Dict[str, Any]],
) -> str:
    """
    세그먼트를 "[seg_001] 상담사: ..." 형식의 한 문자열로 합친다.

    마스킹(privacy_gateway.mask_for_outbound)은 호출부가 이 문자열
    전체에 대해 한 번에 적용한다 — segment_id/화자 태그는 PII가 아니라
    마스킹을 거쳐도 그대로 남는다.
    """

    lines = []

    for segment in segments:
        segment_id = segment.get("segment_id", "")
        speaker = segment.get("speaker", "UNKNOWN")
        text = (segment.get("text") or "").strip()

        if not text:
            continue

        lines.append(f"[{segment_id}] {speaker}: {text}")

    return "\n".join(lines)


def _build_risk_signal_points(
    subtype_analysis: Optional[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    새 LLM 호출 없이, 이미 검증된 2차 세부유형 분석 근거를 그대로
    "위험 신호" 섹션 모양으로 재사용한다.
    """

    points = []

    for major_result in (subtype_analysis or {}).get("results", []):
        major_type = major_result.get("major_type")

        for subtype_entry in major_result.get("subtypes", []):
            subtype_name = subtype_entry.get("type")

            for evidence in subtype_entry.get("evidences", []):
                timestamps = evidence.get("timestamps") or {}
                segment_ids = [
                    str(sid)
                    for sid in (timestamps.get("segment_ids") or [])
                ]

                points.append(
                    {
                        "text": evidence.get("evidence", ""),
                        "major_type": major_type,
                        "subtype": subtype_name,
                        "evidence_strength": evidence.get(
                            "evidence_strength"
                        ),
                        # 2026-10-13: SignalReview 화면의 "근거" 칸이
                        # 지금까지 이 둘을 안 받아서 "AI 추출 근거"라는
                        # 의미 없는 placeholder만 보여주고 있었다.
                        # strength_reason은 이미 2차 분석이 만들어 둔
                        # "왜 이 강도로 판단했는지" 설명이고,
                        # evidence_verified는 원문 대조 결과다 — 둘 다
                        # 새로 만들 필요 없이 그대로 넘기면 된다.
                        "strength_reason": evidence.get(
                            "strength_reason"
                        ),
                        "evidence_verified": evidence.get(
                            "evidence_verified", False
                        ),
                        "segment_ids": segment_ids,
                    }
                )

    return points


def _clean_points(
    raw_points: Any,
    valid_segment_ids: set,
) -> List[Dict[str, Any]]:
    if not isinstance(raw_points, list):
        return []

    cleaned = []

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

        cleaned.append(
            {
                "text": text.strip(),
                "segment_ids": segment_ids,
            }
        )

    return cleaned


def generate_record_draft(
    client: OpenAI,
    model: str,
    masked_transcript_text: str,
    segments: List[Dict[str, Any]],
    subtype_analysis: Optional[Dict[str, Any]],
    session_overview: str = "",
    deadline: Optional[float] = None,
    stop_event: Optional[threading.Event] = None,
) -> Dict[str, Any]:
    """
    기록 초안 필드를 만든다("향후 계획"은 제외 — 모듈 docstring 참고,
    질문 은행이 생기면 RAG로 별도 추가할 예정).

    masked_transcript_text: build_transcript_citation_text()로 만든
    문자열을 호출부가 이미 mask_for_outbound()로 마스킹한 것.
    segments: 원본(비식별화 전) segment 목록 — segment_id 검증에만
    쓰고 텍스트 내용은 쓰지 않는다(LLM에는 마스킹된 텍스트만 전달됨).
    """

    valid_segment_ids = {
        str(segment.get("segment_id", "")) for segment in segments
    }

    if not masked_transcript_text.strip():
        return {
            "session_overview": session_overview,
            "child_statement_points": [],
            "risk_signal_points": _build_risk_signal_points(
                subtype_analysis
            ),
            "counselor_observation": "",
        }

    user_prompt = f"[축어록]\n\n{masked_transcript_text}"

    try:
        parsed = _call_llm_with_retry(
            client=client,
            model=model,
            system_prompt=SYSTEM_PROMPT,
            user_prompt=user_prompt,
            max_retries=2,
            timeout_seconds=180.0,
            deadline=deadline,
            stop_event=stop_event,
        )
    except Exception:
        parsed = {}

    if not isinstance(parsed, dict):
        parsed = {}

    return {
        "session_overview": session_overview,
        "child_statement_points": _clean_points(
            parsed.get("child_statement_points"),
            valid_segment_ids,
        ),
        "risk_signal_points": _build_risk_signal_points(
            subtype_analysis
        ),
        "counselor_observation": "",
    }
