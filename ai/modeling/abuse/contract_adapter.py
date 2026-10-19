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

[2026-10-16: Mingyu 리뷰 반영]

severity_ratings/protective_factors/session_change_notes/
followup_check_points를 risk_factors에 kind 태그로 욱여넣는 이전
방식은 보류했다 — risk_factors는 "위험 요인" 칸이라 보호요인이
섞이면 화면에서 위험 요인으로 보이고, 근거 발화 번호가 없는 항목은
서버 근거 검사에서 빠질 수 있다는 지적을 받았다. risk_factors는
계속 비워 둔다.

[2026-10-19: PR #49 머지 반영 — 4개 필드를 정식 선택 필드로 채움]

Mingyu가 Contract(backend/app/schemas/contracts.py)에 severity_ratings/
protective_factors/session_change_notes/followup_check_points를
정식 선택 필드로 추가했다(API_CONTRACT.md 8절). 이제 risk_factors가
아니라 이 필드들에 직접 채운다:

- severity_ratings: severity_llm.rate_severity_from_text()의 출력
  키(major_type/level/reason/matched_evidence/reviewed)가 Contract의
  SeverityRating과 이름이 같아 그대로 옮긴다. segment_ids는 아직
  없어서 Contract 기본값(빈 배열)으로 비워 둔다.
- protective_factors: protective_factor_llm.generate_protective_factors()의
  출력(category/text/segment_ids)이 이미 ProtectiveFactor와 모양이
  같아 그대로 옮긴다.
- session_change_notes/followup_check_points: 네이티브 출력이
  List[str]인데 Contract는 {text, segment_ids} 객체 목록을 받는다
  (나중에 근거 번호를 붙여도 모양이 안 바뀌게 Mingyu가 이렇게
  정했다) — 문자열마다 segment_ids는 빈 배열로 두고 감싼다.

summary(overview/key_points)는 더 이상 이 모듈이 직접 만들지 않고
agent/summary_converter.convert_summary()(Mingyu, PR #47 — 2026-10-16
main에 머지됨)를 그대로 쓴다 — 아동(CHILD) 발화만 근거로 남기고
원문 segment_id와 대조해 끊어진 인용을 걸러내는 처리가 이미 거기
있어서, 같은 처리를 여기서 다시 만들지 않는다.

[2026-10-16: fixture 리뷰 반영]

- abuse_signals에 segment_ids를 붙였다 — 같은 major_type의
  risk_signal_points(=risk_utterances) segment_ids를 모아 붙인 것이라,
  detected=False거나 해당 유형 근거가 risk_signal_points에 없으면 빈
  배열이다.
- model 이름은 더 이상 환경변수(OPENAI_MODEL, 애초에 이 파이프라인
  어디서도 읽지 않는 값이었다)로 꾸미지 않고, 실제로 쓰인 모델명을
  result에서 그대로 읽는다(_model_name 참고). 이 파이프라인은 단계마다
  별도 LLM 호출(second_stage_llm/record_draft_llm/...)이라 모델이
  이론상 달라질 수 있지만, 전부 같은 DEFAULT_MODEL(현재
  "gpt-5.6-luna")에서 시작해 보통은 같다 — 대표값으로 subtype_analysis
  단계의 모델명을 쓴다.

[아직 못 채운 것]

- 백엔드 adapter의 analyze(transcript_payload)는 case_id를 안 받는다
  (analysis_service가 session.id만 넘긴다). 그래서 Privacy Gateway
  Tier 2(case_store에 등록된 실명 정확매칭)는 이 경로에서는 못 쓴다
  — NER(Tier 1)만 적용된다. 실명 저장 여부가 팀 결정 대기 중이라
  (10/16 Mingyu 답변) 지금은 이 상태로 둔다.
"""

from typing import Any, Dict, List, Optional, Tuple

from openai import OpenAI

from agent.summary_converter import convert_summary

from ai.modeling.abuse.infer_audio_session import analyze_audio_session


def _model_name(result: Dict[str, Any]) -> Optional[str]:
    """실제로 쓰인 모델명을 result에서 읽는다(모듈 docstring 참고)."""

    return (
        (result.get("subtype_analysis") or {}).get("model")
        or result.get("counseling_record_model")
    )


def to_ai_output_contract(
    result: Dict[str, Any],
    transcript: Dict[str, Any],
) -> Tuple[Dict[str, Any], List[Dict[str, Any]], Optional[str]]:
    """
    analyze_audio_session()의 반환값을 AI Output Contract 모양으로 바꾼다.

    transcript: analyze_audio_session에 넘긴 STT Contract dict({"segments": [...]}).
                convert_summary()가 근거 발화의 화자를 다시 확인하는 데 쓴다.

    반환값은 (contract_dict, summary_evidence, model_name) 튜플이다.
    summary_evidence/model_name은 AIAnalysisResult에는 없는 별도 필드라
    호출부(ModelingAIAdapter)가 AIAnalysisBundle을 만들 때 따로 담아야 한다.
    """

    converted = convert_summary(result, transcript)
    summary = converted["summary"]
    summary_evidence = converted.get("summary_evidence", [])
    warnings = list(converted.get("warnings", []))

    record_draft = result.get("record_draft") or {}

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

    # major_type별 근거 segment_id — 같은 유형 risk_utterances에서 모은다.
    segment_ids_by_type: Dict[str, List[str]] = {}

    for utterance in risk_utterances:
        major_type = utterance.get("major_type")

        if not major_type:
            continue

        bucket = segment_ids_by_type.setdefault(major_type, [])

        for segment_id in utterance.get("segment_ids") or []:
            if segment_id not in bucket:
                bucket.append(segment_id)

    abuse_signals = [
        {
            "major_type": major_type,
            "detected": info.get("detected", False),
            "segment_ids": segment_ids_by_type.get(major_type, []),
        }
        for major_type, info in (
            result.get("major_types") or {}
        ).items()
    ]

    # risk_factors는 계속 비워 둔다 — 아래 4개 필드가 정식 자리를
    # 대신 받는다(모듈 docstring 참고).
    risk_factors: List[Dict[str, Any]] = []

    severity_ratings = [
        {
            "major_type": rating.get("major_type"),
            "level": rating.get("level"),
            "reason": rating.get("reason", ""),
            "matched_evidence": rating.get("matched_evidence", ""),
            "reviewed": rating.get("reviewed", False),
        }
        for rating in result.get("severity_ratings") or []
    ]

    protective_factors = [
        {
            "category": factor.get("category"),
            "text": factor.get("text", ""),
            "segment_ids": factor.get("segment_ids", []),
        }
        for factor in result.get("protective_factors") or []
    ]

    session_change_notes = [
        {"text": note, "segment_ids": []}
        for note in result.get("session_change_notes") or []
    ]

    followup_check_points = [
        {"text": point, "segment_ids": []}
        for point in result.get("followup_check_points") or []
    ]

    contract = {
        "schema_version": "1.0",
        "summary": summary,
        "risk_utterances": risk_utterances,
        "abuse_signals": abuse_signals,
        "risk_factors": risk_factors,
        "warnings": warnings,
        "severity_ratings": severity_ratings,
        "protective_factors": protective_factors,
        "session_change_notes": session_change_notes,
        "followup_check_points": followup_check_points,
    }

    return contract, summary_evidence, _model_name(result)


def analyze_audio_session_as_contract(
    stt_result: Dict[str, Any],
    client: Any = None,
    case_id: Optional[str] = None,
    deadline: Optional[float] = None,
) -> Tuple[Dict[str, Any], List[Dict[str, Any]], Optional[str]]:
    """
    backend/app/adapters/ai_adapter.py가 부를 진입점.

    PipelineAIAdapter(ai/services/analysis_pipeline.run_analysis_pipeline)와
    같은 자리에 꽂을 수 있도록, 반환값을 처음부터 Contract 모양으로
    맞춰서 돌려준다. (contract_dict, summary_evidence, model_name) 튜플을
    돌려주므로 호출부는 contract_dict만 AIAnalysisResult.model_validate()에
    넘기고, 나머지 둘은 AIAnalysisBundle에 따로 담으면 된다.

    deadline: time.monotonic() 기준 마감 시각. analyze_audio_session으로
    그대로 전달한다(2026-10-16, backend AI_TIMEOUT_SECONDS 대응).
    """

    result = analyze_audio_session(
        stt_result=stt_result,
        client=client,
        case_id=case_id,
        deadline=deadline,
    )

    return to_ai_output_contract(result, transcript=stt_result)
