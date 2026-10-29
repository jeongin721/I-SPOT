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
- session_change_notes: 네이티브 출력이 List[str]인데 Contract는
  {text, segment_ids} 객체 목록을 받는다(나중에 근거 번호를 붙여도
  모양이 안 바뀌게 Mingyu가 이렇게 정했다) — 문자열마다 segment_ids는
  빈 배열로 두고 감싼다. session_change.py는 LLM 없이 원문을 그대로
  나란히 보여주는 기계적 비교라, 근거 발화를 따로 짚을 필요가 없다고
  보고 segment_ids는 아직 안 채운다.
- followup_check_points: 2026-10-26부터 followup_check_llm.py가
  네이티브로 {text, segment_ids} 객체를 돌려준다(민규 PR #82 리뷰 —
  "증거 위치 표시"를 막는 지점이라고 지적받아 추가). protective_factors
  처럼 그대로 옮기면 된다.

[2026-10-27: 발화별 관련 조문(risk_utterances[].legal_references)]

STT 검수 화면(10/27 디자인)의 "관련 조문"용이다. infer_audio_session 이
legal_reference_adapter 로 위험 신호마다 아동복지법 제17조의 해당 호를
붙이고(_attach_legal_references), 여기서는 다섯 키만 옮긴다
(_legal_references). 법령 데이터를 못 쓰면 빈 배열 + warnings 한 줄.

[2026-10-27: 상담 요약 4칸(summary.assessment)]

10/27 디자인의 상담 요약은 사정 관점 4칸이다. 파이프라인이 이미 만들던
강점·위험 문단(narrative_summary)과 session_change_notes, 새로 추가한
desired_change_llm.py 결과를 summary.assessment 로 옮긴다
(_summary_assessment 참고).

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


LEGAL_REFERENCES_UNAVAILABLE_WARNING = (
    "법령 데이터를 불러오지 못해 관련 조문을 붙이지 못했습니다."
)

_LEGAL_REFERENCE_KEYS = ("law_name", "article", "item_label", "text", "portal_url")


def _legal_references(value: Any) -> List[Dict[str, str]]:
    """
    risk_utterances[].legal_references(2026-10-27) — 발화마다 관련 조문.
    legal_reference_adapter 출력에서 화면이 쓰는 다섯 키만 문자열로 옮긴다
    (short_label 은 화면이 abuse_type 으로 붙인다). 법 위반을 확정하는
    값이 아니라 해당 금지행위 조문을 가리키는 참고 링크다.
    """

    if not isinstance(value, list):
        return []

    references = []

    for item in value:
        if not isinstance(item, dict):
            continue

        references.append(
            {
                key: item.get(key) if isinstance(item.get(key), str) else ""
                for key in _LEGAL_REFERENCE_KEYS
            }
        )

    return references


def _assessment_field(text: Any, segment_ids: Any) -> Dict[str, Any]:
    # 목록이 아닌 근거 번호(숫자 · dict 등)는 버린다 — 여기서 TypeError 가 나면 분석 전체가 실패한다.
    ids = segment_ids if isinstance(segment_ids, list) else []

    return {
        "text": text.strip() if isinstance(text, str) else "",
        "segment_ids": [
            str(sid) for sid in ids if isinstance(sid, (str, int)) and not isinstance(sid, bool)
        ],
    }


def _summary_assessment(result: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """
    상담 요약 사정 관점 4칸(2026-10-27, 10/27 디자인 NoteWrite.dc.html).
    새로 분석하지 않고 파이프라인이 이미 만든 값을 옮긴다:

    - safety_changes(조사 후 변화된 사항) ← session_change_notes. 이전
      회차가 case_store 에 있어야 생기는 값이라 서버 경로(case_id 없음)
      에서는 빈 문자열이다 — 상담원이 쓴다.
    - strengths_resources(강점과 자원) · safety_risks(위험요인)
      ← record_draft.narrative_summary 의 두 문단과 근거 번호.
    - desired_changes(원하는 변화 · 서비스/지원) ← desired_change_llm.py.
    """

    # 변환 경계라 모양을 믿지 않는다 — dict 가 아니면 빈 칸으로 둔다(.get 에서 AttributeError 로
    # 분석 전체가 실패하지 않게, 2026-10-27 민규 교차검증).
    record_draft = result.get("record_draft")
    narrative = record_draft.get("narrative_summary") if isinstance(record_draft, dict) else None
    narrative = narrative if isinstance(narrative, dict) else {}
    desired = result.get("desired_changes")
    desired = desired if isinstance(desired, dict) else {}
    change_notes = [
        note for note in result.get("session_change_notes") or [] if isinstance(note, str)
    ]

    return {
        "safety_changes": _assessment_field("\n".join(change_notes), []),
        "strengths_resources": _assessment_field(
            narrative.get("strengths_narrative"),
            narrative.get("strengths_citations"),
        ),
        "safety_risks": _assessment_field(
            narrative.get("risks_narrative"),
            narrative.get("risks_citations"),
        ),
        "desired_changes": _assessment_field(
            desired.get("text"), desired.get("segment_ids")
        ),
    }


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
            "legal_references": _legal_references(
                point.get("legal_references")
            ),
        }
        for point in risk_signal_points
    ]

    if result.get("legal_references_unavailable"):
        warnings.append(LEGAL_REFERENCES_UNAVAILABLE_WARNING)

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

    # 예전 모양(List[str], 2026-10-26 이전 followup_check_llm.py 출력과
    # backend 시험의 가짜 모듈 결과)도 받는다 — session_change_notes처럼
    # segment_ids는 빈 배열로 감싼다.
    followup_check_points = [
        {"text": point, "segment_ids": []}
        if isinstance(point, str)
        else {
            "text": point.get("text", ""),
            "segment_ids": point.get("segment_ids", []),
            # 근거가 지난 회차 확정 요약뿐인 메모(2026-10-28, #100 §7 답 3). 있을 때만 키를 둔다.
            **(
                {"previous_session_label": point["previous_session_label"]}
                if isinstance(point.get("previous_session_label"), str) and point["previous_session_label"]
                else {}
            ),
        }
        for point in result.get("followup_check_points") or []
    ]

    # '추가 질문' AI 초안(followup_question_llm.py, 2026-10-29 C-1). 모듈이 이미 검사한 값이라 모양만 옮긴다.
    followup_questions = [
        {
            "text": question.get("text", ""),
            "kind": "OPEN",
            "segment_ids": question.get("segment_ids", []),
            "reason": question.get("reason", ""),
        }
        for question in result.get("followup_questions") or []
        if isinstance(question, dict)
    ]

    summary = {**summary, "assessment": _summary_assessment(result)}

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
        "followup_questions": followup_questions,
    }

    return contract, summary_evidence, _model_name(result)


def analyze_audio_session_as_contract(
    stt_result: Dict[str, Any],
    client: Any = None,
    case_id: Optional[str] = None,
    deadline: Optional[float] = None,
    case_context: Optional[Dict[str, Any]] = None,
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

    case_context: 사례 정보(2026-10-28, case_context.py · PROPOSAL_case_context_analysis.md §3).
    Backend 가 받는 어댑터에만 키워드로 넘긴다. 없으면(None) 넘기지 않아 예전 판 모듈과도 맞는다.
    '다음 상담 전 확인할 사항'(followup_check_llm)이 쓰고, '추가 질문' 초안(followup_question_llm)은 나이대만 쓴다.
    """

    options: Dict[str, Any] = {}

    if case_context is not None:
        options["case_context"] = case_context

    result = analyze_audio_session(
        stt_result=stt_result,
        client=client,
        case_id=case_id,
        deadline=deadline,
        **options,
    )

    return to_ai_output_contract(result, transcript=stt_result)


# ============================================================
# STT 검수 '1차 임시 핵심 발화'(key_scan, 2026-10-28)
# ============================================================
# I-SPOT_DOCS/docs/PROPOSAL_stt_key_scan.md §8 합의. Backend(transcript_service.process_stt)가
# STT 결과를 저장한 같은 작업 끝에서 부르고, 시간 제한 · 설정으로 status(DONE · FAILED · SKIPPED)를
# 붙여 transcripts.key_scan 에 둔다. 판정이 아니라 '먼저 들어볼 곳' 이다(05_RULES §1).

#: 1차 분류기 이름(infer_abuse_qa_v3.py 의 roberta_abuse_qa_child_v3_best.pth).
KEY_SCAN_MODEL = "roberta_abuse_qa_child_v3"

#: 핵심 발화로 남기는 화자. 검출된 chunk 안의 상담원 · 보호자 · 기타 줄은 '다시 들어볼 아동 발화' 가
#: 아니라 뺀다. 화자 미확인 줄은 아동 발화일 수 있어 남긴다(저신뢰 보기와 겹쳐도 괜찮음).
KEY_SCAN_SPEAKERS = {"CHILD", "UNKNOWN"}


def key_scan_as_contract(stt_result: Dict[str, Any]) -> Dict[str, Any]:
    """
    원문 확정 전 1차 스캔. infer_audio_session.quick_risk_scan(1차 RoBERTa 만, LLM 없음, 로컬 —
    정식 분석과 같은 chunk 분할)의 {segment_id: [한글 대분류]} 를 Contract 모양으로 바꾼다.

    stt_result: 분석에 넘기는 것과 같은 STT Contract({"segments": [...]}).
    반환: {"model": KEY_SCAN_MODEL, "segments": [{"segment_id", "abuse_types": [영문 4종]}]} —
    원문 순서, 아동 · 화자 미확인 발화만, 없으면 빈 배열. 영문 4종 밖의 유형은 버린다.
    status 는 붙이지 않는다(Backend 가 정함). 모델 실패는 예외를 그대로 올린다.
    """

    # 지연 import: backend 시험은 infer_audio_session 을 가짜 모듈로 바꾸는데, 모듈 맨 위에서
    # 가져오면 그 가짜에 이 함수가 없을 때 contract_adapter import 자체가 깨진다.
    from ai.modeling.abuse.infer_audio_session import quick_risk_scan

    flagged = quick_risk_scan(stt_result) or {}
    segments = stt_result.get("segments") if isinstance(stt_result, dict) else None
    known = set(MAJOR_TYPE_TO_ENGLISH.values())
    picked: List[Dict[str, Any]] = []

    for segment in segments if isinstance(segments, list) else []:
        if not isinstance(segment, dict):
            continue

        segment_id = str(segment.get("segment_id", ""))
        speaker = segment.get("speaker")

        if not segment_id or segment_id not in flagged or speaker not in KEY_SCAN_SPEAKERS:
            continue

        abuse_types: List[str] = []

        for label in flagged.get(segment_id) or []:
            english = MAJOR_TYPE_TO_ENGLISH.get(label)
            if english in known and english not in abuse_types:
                abuse_types.append(english)

        if abuse_types:
            picked.append({"segment_id": segment_id, "abuse_types": abuse_types})

    return {"model": KEY_SCAN_MODEL, "segments": picked}
