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

[2026-10-22: PROPOSAL_risk_fields.md §7 확정안 반영]

- risk_utterances에 reason(strength_reason 그대로)·evidence_verified를
  추가했다. 둘 다 record_draft_llm.py가 이미 만들어 두던 값이라 새
  LLM 호출 없이 옮기기만 했다 — record_draft는 restore_pii를 거친
  뒤라(infer_audio_session.py) 실명이 복원된 값이다. needs_review는
  record_draft_llm.py 어디에도 없어 Mingyu에게 출처를 다시 확인
  요청했고, 답 오기 전까지는 넣지 않는다.
- abuse_signals에 detection_source(MODEL|FILTERED)·filtered_reason을
  추가했다. 세션 단위 major_types는 chunk별 1차 판정을 detected만
  남기고 OR로 합치면서 filtered_reason을 버리고 있어서(기존 코드),
  chunk_results를 다시 훑어 복원한다 — 어느 chunk든 1차가
  detected=True면 MODEL, 전부 아니고 filtered_reason 있는 chunk가
  있으면 FILTERED(그 사유를 옮긴다), 둘 다 아니면 둘 다 None(Mingyu
  제안 규칙). 오디오 경로(analyze_audio_session)는 note 모드 전용인
  _screen_missed_major_types를 타지 않아 llm_supplementary가 생길
  일이 없으므로 LLM_SUPPLEMENTARY는 이번 판에서 쓰지 않는다(예약값).
- confidence/threshold는 이번 판에서 뺐다 — 1차가 session_detected로
  합쳐지는 시점에 이미 확률이 버려져 있고(chunk 값만 남음), 세션
  단위로 어떻게 합칠지(chunk 최댓값 등) 설계가 따로 필요하다. 지금
  Agent·Backend 관문·화면 모두 detected만 보므로 당장 급하지 않다.

[2026-10-22: Mingyu — 위험 3필드의 유형 · 근거 강도를 영문 대문자로]

- 확정안(PROPOSAL_risk_fields.md §7, 10/22 합의)대로 risk_utterances ·
  abuse_signals 의 유형 키를 major_type(한글) 대신 abuse_type(영문
  PHYSICAL|EMOTIONAL|SEXUAL|NEGLECT)으로, evidence_strength 를
  높음|중간|낮음 대신 HIGH|MEDIUM|LOW 로 내보낸다(02_ARCHITECTURE.md §7
  "한글 표기는 화면에서만"). 변환은 이 Contract 경계에서만 하고
  파이프라인 안(record_draft · subtype_analysis)은 한글 그대로다.
  severity_ratings[].major_type 은 #49 로 따로 합의한 선택 필드라
  여기서 바꾸지 않는다(API_CONTRACT.md 8절). subtype 은 2차 세부유형명
  (한글)을 그대로 둔다.
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


# 학대유형 대분류: 02_ARCHITECTURE.md §7 의 영문 enum. 파이프라인 안은
# 한글 라벨(ABUSE_LABELS)이라 Contract 경계(여기)에서만 바꾼다.
MAJOR_TYPE_TO_ENGLISH = {
    "신체학대": "PHYSICAL",
    "정서학대": "EMOTIONAL",
    "성학대": "SEXUAL",
    "방임": "NEGLECT",
}

# 근거 강도: second_stage_llm 이 내는 높음|중간|낮음(확률이 아니라 근거의
# 직접성). second_stage_llm 은 셋 밖의 값을 "낮음"으로 고정하므로 여기서도
# 모르는 값은 LOW 로 둔다.
EVIDENCE_STRENGTH_TO_ENGLISH = {
    "높음": "HIGH",
    "중간": "MEDIUM",
    "낮음": "LOW",
}


def _abuse_type(label: Any) -> Any:
    """한글 대분류 → 영문 대문자. 모르는 값은 그대로 둔다(정보를 잃지 않게)."""

    return MAJOR_TYPE_TO_ENGLISH.get(label, label)


def _evidence_strength(value: Any) -> str:
    return EVIDENCE_STRENGTH_TO_ENGLISH.get(value, "LOW")


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
    risk_signal_points = record_draft.get("risk_signal_points", [])

    risk_utterances = [
        {
            "text": point.get("text", ""),
            "segment_ids": point.get("segment_ids", []),
            "abuse_type": _abuse_type(point.get("major_type")),
            "subtype": point.get("subtype"),
            "evidence_strength": _evidence_strength(
                point.get("evidence_strength")
            ),
            # second_stage_llm 은 비거나 문자열이 아닌 이유를 None 으로 정리해
            # 넘기므로(_clean_optional_string) 키가 있어도 None 일 수 있다.
            # Contract 의 reason 은 문자열(없으면 "")이라 여기서 맞춘다
            # (Codex 교차검증 R1, 2026-10-23).
            "reason": point.get("strength_reason") or "",
            "evidence_verified": bool(
                point.get("evidence_verified", False)
            ),
        }
        for point in risk_signal_points
    ]

    # major_type(한글)별 근거 segment_id — 같은 유형 risk_signal_points
    # 에서 모은다. abuse_signals 는 major_types 의 한글 키로 찾으므로
    # 변환 전 라벨로 묶는다.
    segment_ids_by_type: Dict[str, List[str]] = {}

    for point in risk_signal_points:
        major_type = point.get("major_type")

        if not major_type:
            continue

        bucket = segment_ids_by_type.setdefault(major_type, [])

        for segment_id in point.get("segment_ids") or []:
            if segment_id not in bucket:
                bucket.append(segment_id)

    chunk_results = result.get("chunk_results") or []

    def _detection_source(
        major_type: str,
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        chunk별 1차 판정을 훑어 이 유형이 왜 detected인지/아닌지 찾는다.
        세션 major_types는 chunk 판정을 detected만 남기고 OR로 합치면서
        filtered_reason을 버리므로(위에서 다시 만듦), 여기서 chunk_results를
        다시 본다. 어느 chunk든 1차가 detected=True면 MODEL, 전부 아니고
        filtered_reason 있는 chunk가 있으면 FILTERED, 둘 다 아니면
        (None, None) — PROPOSAL_risk_fields.md §7 2026-10-22 확정안.
        """

        filtered_reason = None

        for chunk in chunk_results:
            chunk_info = (
                chunk.get("major_types") or {}
            ).get(major_type) or {}

            if chunk_info.get("detected"):
                return "MODEL", None

            if (
                filtered_reason is None
                and chunk_info.get("filtered_reason")
            ):
                filtered_reason = chunk_info["filtered_reason"]

        if filtered_reason is not None:
            return "FILTERED", filtered_reason

        return None, None

    abuse_signals = []

    for major_type, info in (
        result.get("major_types") or {}
    ).items():
        detection_source, filtered_reason = _detection_source(
            major_type
        )

        # 안전망(2026-10-23, 이경진 님 요청): chunk_results 가 없거나 세션
        # 판정과 어긋나도 detected=True 인 신호가 출처 없이(null) 나가지
        # 않게 한다. 지금 파이프라인은 같은 루프에서 둘을 함께 채우므로
        # 실제로는 걸리지 않고, 구조가 바뀌거나 손으로 만든 결과를 넣을
        # 때만 작동한다.
        if detection_source is None and info.get("detected", False):
            detection_source = "MODEL"

        abuse_signals.append(
            {
                "abuse_type": _abuse_type(major_type),
                "detected": info.get("detected", False),
                "segment_ids": segment_ids_by_type.get(
                    major_type, []
                ),
                "detection_source": detection_source,
                "filtered_reason": filtered_reason,
            }
        )

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
