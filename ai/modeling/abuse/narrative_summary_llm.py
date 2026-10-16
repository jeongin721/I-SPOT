"""
"상담 요약" 화면의 "강점과 자원" / "위험요인" 섹션을 자연스러운 문단으로
종합하는 LLM 모듈 초안(2026-10-13).

[왜 필요한가]

protective_factor_llm.py(보호 요인)와 record_draft_llm.py의 위험 신호
재사용 로직은 각각 "범주 태그 + 불릿 목록" 형태로 구조화된 근거를
만든다 — 상담사가 하나씩 검수하기엔 이 구조화된 형태가 유용하지만,
기관에 제출하는 "상담 요약" 문서에는 사람이 쓴 것 같은 자연스러운
문단이 필요하다는 요청(2026-10-13)에 따라 이 모듈을 추가했다.

이미 검증된 구조화 데이터(보호요인/위험신호)를 입력으로 받아 문단으로
"다시 쓰기"만 한다 — 새로운 사실을 추가하거나 추론하지 않는다.

[범위 — 지금은 세션 1개 분량만]

예시로 받은 화면은 "6회차+8회차"처럼 여러 회차를 가로지르는 근거를
한 문단에 종합하고 있었다. 그건 case_store에 회차별 보호요인/위험신호를
저장하고 모아오는 작업이 먼저 있어야 해서(아직 없음) 범위 밖으로 미뤘고,
이 모듈은 "이번 세션 하나 분량의 보호요인/위험신호를 문단으로 종합"하는
것까지만 한다(2026-10-13 논의).

[설계 결정 — 왜 분리된 호출인가]

protective_factor_llm.py/second_stage_llm.py와 마찬가지로 완전히 별도
호출이다. 위험신호 탐지 자체의 튜닝된 프롬프트에는 영향이 없다.

[PII 마스킹 — 2026-10-13 수정]

처음 만들 때는 protective_factors/risk_signal_points를 그대로 받아
바로 LLM에 보내게 짰는데, infer_audio_session.py에서 이 둘을 넘기는
시점엔 이미 restore_pii로 실명이 복원된 뒤라는 걸 나중에 발견했다 —
그대로 쓰면 마스킹 없이 실명이 외부(OpenAI)로 나간다. 그래서
format_points_for_masking() → (호출부가) mask_for_outbound() →
generate_narrative_summary_from_masked_text() → (호출부가)
restore_pii() 순서로 나눴다. generate_narrative_summary()는 이
순서를 안 거치는 독립 테스트/데모 전용이고, 실제 서비스 경로
(infer_audio_session.py)는 반드시 마스킹 경유 버전을 써야 한다.
"""

from typing import Any, Dict, List, Optional

from openai import OpenAI

from ai.modeling.abuse.second_stage_llm import _call_llm_with_retry

DEFAULT_MODEL = "gpt-5.6-luna"


SYSTEM_PROMPT = """너는 아동 상담 사례관리 문서의 "상담 요약"에서
"강점과 자원" 문단과 "위험요인" 문단을 쓰는 도우미다.

[공통 원칙]

1. 입력으로 주어진 보호 요인/위험 신호 항목에 있는 사실만 쓴다. 새로운
   사실, 원인, 정도를 추가하거나 추측하지 않는다.
2. "학대 의심", "위험도가 높다" 같은 판정 표현을 쓰지 않는다 — 있는
   그대로 사실을 서술한다.
3. 강점과 자원 문단이 위험요인을 상쇄하는 것처럼 읽히게 쓰지 않는다 —
   이 둘은 서로 다른 축이다(2026-10-12 보호요인 모듈 설계 원칙과 동일).
4. 입력 항목의 범주 이름("지지적 관계", "직접 신체 가해" 등)을 본문에
   그대로 나열하지 않는다 — 사람이 보고서를 쓰듯 자연스러운 문장으로
   풀어 쓴다. 단, 아동이 실제로 한 말은 따옴표로 직접 인용해도 된다.
5. 각 문단은 1~3문장으로 간결하게 쓴다. 입력 항목이 여러 개면 자연스럽게
   이어 쓰되, 서로 다른 사실을 하나로 합쳐서 왜곡하지 않는다.
6. 입력에 항목이 아예 없으면("없음") 그 문단은 "확인된 내용 없음"이라고
   만 쓴다 — 억지로 문장을 만들지 않는다.

[강점과 자원 — 입력 항목]
{strengths_input}

[위험요인 — 입력 항목]
{risks_input}

[출력 형식]

반드시 아래 JSON 형식으로만 답한다:
{{
  "strengths_narrative": "...",
  "risks_narrative": "..."
}}
"""


def _format_points(points: List[Dict[str, Any]], kind: str) -> str:
    if not points:
        return "없음"

    lines = []

    for p in points:
        if kind == "strength":
            label = p.get("category", "")
        else:
            label = f"{p.get('major_type', '')} · {p.get('subtype', '')}"

        lines.append(f"- ({label}) {p.get('text', '')}")

    return "\n".join(lines)


def _collect_segment_ids(points: List[Dict[str, Any]]) -> List[str]:
    seen = []

    for p in points:
        for sid in p.get("segment_ids", []) or []:
            sid = str(sid)

            if sid not in seen:
                seen.append(sid)

    return seen


#: 마스킹된 두 텍스트 블록을 안전하게 나눠 담기 위한 구분자. 실명이
#: 여기 그대로 들어올 일이 없는 고정 문자열이라 mask_for_outbound를
#: 거쳐도 안 바뀐다 — 호출부가 "두 섹션을 합쳐서 한 번에 마스킹 →
#: 이 구분자로 다시 분리"하는 패턴에 쓴다(아래 docstring 참고).
SPLIT_MARKER = "\n===I-SPOT-NARRATIVE-SPLIT===\n"


def format_points_for_masking(
    protective_factors: List[Dict[str, Any]],
    risk_signal_points: List[Dict[str, Any]],
) -> str:
    """
    마스킹 전 호출부가 쓸 합쳐진 텍스트를 만든다. 호출부는 이 결과를
    privacy_gateway.mask_for_outbound()로 한 번에 마스킹한 뒤
    SPLIT_MARKER로 다시 둘로 나눠
    generate_narrative_summary_from_masked_text()에 넘긴다 — 이 모듈이
    직접 외부로 나가는 마스킹되지 않은 실명 텍스트를 만들지 않도록
    하기 위함이다(2026-10-13, protective_factors/risk_signal_points가
    이 시점엔 이미 restore_pii로 실명 복원된 상태라는 걸 뒤늦게
    발견해서 추가한 안전장치).
    """

    return (
        _format_points(protective_factors, "strength")
        + SPLIT_MARKER
        + _format_points(risk_signal_points, "risk")
    )


def generate_narrative_summary_from_masked_text(
    client: OpenAI,
    model: str,
    masked_combined_text: str,
) -> Dict[str, str]:
    """
    masked_combined_text: format_points_for_masking()의 결과를
    mask_for_outbound()로 마스킹한 것 그대로(SPLIT_MARKER 포함).
    반환값도 마스킹된 상태이므로 호출부가 restore_pii()를 적용해야
    한다 — citations(segment_id)는 PII가 아니라 여기서 안 다룬다,
    호출부가 원본 구조화 데이터에서 직접 뽑는다.
    """

    parts = masked_combined_text.split(SPLIT_MARKER)
    strengths_input = parts[0] if parts else "없음"
    risks_input = parts[1] if len(parts) > 1 else "없음"

    if strengths_input.strip() == "없음" and risks_input.strip() == "없음":
        return {
            "strengths_narrative": "확인된 내용 없음",
            "risks_narrative": "확인된 내용 없음",
        }

    system_prompt = SYSTEM_PROMPT.format(
        strengths_input=strengths_input,
        risks_input=risks_input,
    )

    try:
        parsed = _call_llm_with_retry(
            client=client,
            model=model,
            system_prompt=system_prompt,
            user_prompt="위 입력을 바탕으로 두 문단을 써.",
            max_retries=2,
            timeout_seconds=180.0,
        )
    except Exception:
        parsed = {}

    if not isinstance(parsed, dict):
        parsed = {}

    strengths_narrative = parsed.get("strengths_narrative")
    risks_narrative = parsed.get("risks_narrative")

    if not isinstance(strengths_narrative, str) or not strengths_narrative.strip():
        strengths_narrative = "확인된 내용 없음"

    if not isinstance(risks_narrative, str) or not risks_narrative.strip():
        risks_narrative = "확인된 내용 없음"

    return {
        "strengths_narrative": strengths_narrative.strip(),
        "risks_narrative": risks_narrative.strip(),
    }


def generate_narrative_summary(
    client: OpenAI,
    model: str,
    protective_factors: List[Dict[str, Any]],
    risk_signal_points: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    **독립 테스트/데모 전용** — 마스킹 없이 바로 LLM을 부른다. 실제
    서비스 경로(infer_audio_session.py)는 이 함수를 쓰지 않는다 —
    protective_factors/risk_signal_points가 그 시점엔 이미 실명
    복원된 상태라 그대로 보내면 PII가 마스킹 없이 외부로 나간다.
    서비스 경로는 format_points_for_masking() →
    privacy_gateway.mask_for_outbound() →
    generate_narrative_summary_from_masked_text() → restore_pii()
    순서를 쓴다(아래 함수들 docstring 참고).

    citations(segment_id)는 PII가 아니므로 여기서는 그대로 모아
    반환한다 — 독립 테스트에서 호출부 따로 안 만들어도 바로 쓰라고
    남겨둔 편의 기능이다.
    """

    strengths_citations = _collect_segment_ids(protective_factors)
    risks_citations = _collect_segment_ids(risk_signal_points)

    if not protective_factors and not risk_signal_points:
        return {
            "strengths_narrative": "확인된 내용 없음",
            "risks_narrative": "확인된 내용 없음",
            "strengths_citations": [],
            "risks_citations": [],
        }

    combined = format_points_for_masking(
        protective_factors, risk_signal_points
    )
    narrative = generate_narrative_summary_from_masked_text(
        client, model, combined
    )

    return {
        **narrative,
        "strengths_citations": strengths_citations,
        "risks_citations": risks_citations,
    }


# ============================================================
# 데모
# ============================================================

if __name__ == "__main__":
    import json

    from ai.modeling.abuse.llm_backend import build_openai_client_and_model

    protective_factors = [
        {"category": "안전 자원", "text": "조모에게 연락하는 안전 계획을 알고 있다고 말했다.", "segment_ids": ["seg_050"]},
        {"category": "정서적 자원", "text": "할머니 집에 가고 싶다고 말했다.", "segment_ids": ["seg_050"]},
    ]
    risk_signal_points = [
        {"major_type": "신체학대", "subtype": "직접 신체 가해", "text": "아빠가 많이 때렸어요.", "segment_ids": ["seg_010"], "evidence_strength": "높음"},
        {"major_type": "정서학대", "subtype": "위협·공포 유발", "text": "말하면 더 혼난다고 했어요.", "segment_ids": ["seg_011"], "evidence_strength": "중간"},
    ]

    client, model = build_openai_client_and_model(DEFAULT_MODEL)
    result = generate_narrative_summary(
        client=client,
        model=model,
        protective_factors=protective_factors,
        risk_signal_points=risk_signal_points,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
