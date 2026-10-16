"""
ai/modeling/abuse 파이프라인 결과를 backend의 AI Output Contract
(backend/app/schemas/contracts.py의 AIAnalysisResult, ai/schemas/
analysis.py의 AIAnalysisOutput과 동일 형태)로 변환한다.

[왜 필요한가]

analyze_audio_session()의 출력은 이 프로젝트가 실제로 화면에 쓰는
전체 분석 결과(record_draft, severity_ratings, protective_factors,
session_change_notes, followup_check_points 포함)라, backend
Contract보다 필드가 훨씬 많다. 지금 Contract는 다섯 필드만 받는다:
summary(overview/key_points), risk_utterances, abuse_signals,
risk_factors, warnings. 이 모듈은 그 다섯 필드에 맞는 부분만 골라
채우는 "번역기" 역할만 한다 — 새로 분석하거나 판단하지 않는다.

[지금 Contract에 정식 자리가 없어서 risk_factors에 임시로 담는 필드]

- severity_ratings(유형별 1~5단계 심각도, 검수 전 초안)
- protective_factors(보호요인 범주)
- session_change_notes(회차 간 진술 변화)
- followup_check_points(다음 상담에서 확인할 것)

risk_factors는 타입이 느슨한 List[Dict[str, Any]]라 당장은 동작하지만,
Contract에 정식 필드가 생기면 여기서 분리해서 옮겨야 한다(임시방편임을
"kind" 키로 표시해 둔다). 정식 필드 추가는 backend 쪽과 상의가 필요
하다 — contracts.py 주석: "Backend 단독으로 이 구조를 변경하지
않는다."

[2026-10-15: 아직 못 채운 것]

- 백엔드 adapter의 analyze(transcript_payload)는 case_id를 안 받는다
  (analysis_service가 session.id만 넘긴다). 그래서 Privacy Gateway
  Tier 2(case_store에 등록된 실명 정확매칭)는 이 경로에서는 못 쓴다
  — NER(Tier 1)만 적용된다. case_id까지 넘기려면 backend 쪽
  analysis_service.py도 같이 바꿔야 한다.
"""

from typing import Any, Dict, List, Optional

from openai import OpenAI

from ai.modeling.abuse.infer_audio_session import analyze_audio_session


def to_ai_output_contract(
    result: Dict[str, Any],
) -> Dict[str, Any]:
    """analyze_audio_session()의 반환값을 AI Output Contract 모양으로 바꾼다."""

    record_draft = result.get("record_draft") or {}
    narrative_summary = (
        record_draft.get("narrative_summary") or {}
    )

    overview = (
        narrative_summary.get("risks_narrative")
        or result.get("counseling_summary", "")
        or ""
    )

    key_points = [
        point.get("text", "")
        for point in record_draft.get(
            "child_statement_points", []
        )
        if point.get("text")
    ]

    risk_utterances = [
        {
            "text": point.get("text", ""),
            "segment_ids": point.get("segment_ids", []),
            "major_type": point.get("major_type"),
            "subtype": point.get("subtype"),
            "evidence_strength": point.get(
                "evidence_strength"
            ),
        }
        for point in record_draft.get(
            "risk_signal_points", []
        )
    ]

    abuse_signals = [
        {
            "major_type": major_type,
            "detected": info.get("detected", False),
        }
        for major_type, info in (
            result.get("major_types") or {}
        ).items()
    ]

    # Contract에 아직 정식 자리가 없는 필드들을 risk_factors에 임시로
    # 담는다(모듈 docstring 참고) — "kind"로 구분해서 나중에 분리하기
    # 쉽게 해 둔다.
    risk_factors: List[Dict[str, Any]] = []

    for factor in result.get("protective_factors") or []:
        risk_factors.append(
            {"kind": "protective_factor", **factor}
        )

    for rating in result.get("severity_ratings") or []:
        risk_factors.append(
            {"kind": "severity_rating", **rating}
        )

    for note in result.get("session_change_notes") or []:
        risk_factors.append(
            {"kind": "session_change_note", "text": note}
        )

    for point in result.get("followup_check_points") or []:
        risk_factors.append(
            {"kind": "followup_check_point", "text": point}
        )

    return {
        "schema_version": "1.0",
        "summary": {
            "overview": overview,
            "key_points": key_points,
        },
        "risk_utterances": risk_utterances,
        "abuse_signals": abuse_signals,
        "risk_factors": risk_factors,
        "warnings": [],
    }


def analyze_audio_session_as_contract(
    stt_result: Dict[str, Any],
    client: Any = None,
    case_id: Optional[str] = None,
    deadline: Optional[float] = None,
) -> Dict[str, Any]:
    """
    backend/app/adapters/ai_adapter.py가 부를 진입점.

    PipelineAIAdapter(ai/services/analysis_pipeline.run_analysis_pipeline)와
    같은 자리에 꽂을 수 있도록, 반환값을 처음부터 Contract 모양으로
    맞춰서 돌려준다 — 호출부는 추가 변환 없이 바로
    AIAnalysisResult.model_validate()에 넘기면 된다.

    deadline: time.monotonic() 기준 마감 시각. analyze_audio_session으로
    그대로 전달한다(2026-10-16, backend AI_TIMEOUT_SECONDS 대응).
    """

    result = analyze_audio_session(
        stt_result=stt_result,
        client=client,
        case_id=case_id,
        deadline=deadline,
    )

    return to_ai_output_contract(result)
