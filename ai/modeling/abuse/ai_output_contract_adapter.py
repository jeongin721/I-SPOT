"""
ai/schemas/analysis.py의 AIAnalysisOutput 중 risk_utterances/abuse_signals/
risk_factors를 이 모듈(ai/modeling/abuse/)의 학대유형 탐지 결과로 채우는
번역 레이어.

지금(2026-10) ai/services/summary_service.py는 9월 MVP 범위로 이 세
필드를 항상 빈 배열로 고정해 두고 있다 — 요약 담당이 의도적으로 막아둔
것이라 지금 당장 그 파일을 고치지 않는다. 나중에 연결하기로 하면, 아래처럼
쓰면 된다(이 모듈이 바뀌는 게 아니라, summary_service.py 쪽에서 빈 배열
대신 이 함수를 호출하도록 한 줄만 바꾸면 된다):

    from ai.modeling.abuse.ai_output_contract_adapter import (
        analyze_transcript_for_risk_fields,
    )

    risk_fields = analyze_transcript_for_risk_fields(
        transcript.model_dump(), case_id=case_id,
    )
    analysis.risk_utterances = risk_fields["risk_utterances"]
    analysis.abuse_signals = risk_fields["abuse_signals"]
    analysis.risk_factors = risk_fields["risk_factors"]
    analysis.warnings = list(
        dict.fromkeys(analysis.warnings + risk_fields["warnings"])
    )

"표현 주의"(02_ARCHITECTURE.md) 원칙을 그대로 따른다 — 여기서 만드는 모든
문자열은 "참고", "확인 필요" 수준으로만 쓰고 "확정"/"판정" 표현을 쓰지
않는다.
"""

from typing import Any, Dict, List, Optional

from ai.modeling.abuse.infer_audio_session import analyze_audio_session

# 학대유형: 02_ARCHITECTURE.md §7 — 영문 enum은 PHYSICAL/EMOTIONAL/SEXUAL/
# NEGLECT로 고정돼 있다. 이 프로젝트(ai/modeling/abuse) 내부는 전부 한글
# 라벨을 쓰므로, 계약 경계에서만 이 매핑으로 변환한다.
MAJOR_TYPE_TO_ENGLISH = {
    "신체학대": "PHYSICAL",
    "정서학대": "EMOTIONAL",
    "성학대": "SEXUAL",
    "방임": "NEGLECT",
}


def _build_abuse_signals(
    audio_analysis_result: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """major_types 중 detected=True인 것만 abuse_signals로 변환한다."""

    signals = []

    for label, prediction in audio_analysis_result.get(
        "major_types", {}
    ).items():
        if not prediction.get("detected"):
            continue

        english_type = MAJOR_TYPE_TO_ENGLISH.get(label)

        if english_type is None:
            continue

        subtypes = [
            entry.get("type")
            for entry in next(
                (
                    r.get("subtypes", [])
                    for r in audio_analysis_result.get(
                        "subtype_analysis", {}
                    ).get("results", [])
                    if r.get("major_type") == label
                ),
                [],
            )
        ]

        signals.append(
            {
                "type": english_type,
                "type_ko": label,
                "subtypes": subtypes,
                "llm_supplementary": bool(
                    prediction.get("llm_supplementary")
                ),
            }
        )

    return signals


def _build_risk_utterances(
    audio_analysis_result: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """2차 세부유형 분석의 근거 발화를 segment_id와 함께 평탄화한다."""

    utterances = []

    for major_result in audio_analysis_result.get(
        "subtype_analysis", {}
    ).get("results", []):
        major_type_ko = major_result.get("major_type")
        english_type = MAJOR_TYPE_TO_ENGLISH.get(major_type_ko)

        for subtype_entry in major_result.get("subtypes", []):
            for evidence in subtype_entry.get("evidences", []):
                timestamps = evidence.get("timestamps") or {}

                utterances.append(
                    {
                        "text": evidence.get("evidence", ""),
                        "segment_ids": timestamps.get(
                            "segment_ids", []
                        ),
                        "type": english_type,
                        "subtype": subtype_entry.get("type"),
                        "strength": evidence.get(
                            "evidence_strength"
                        ),
                        "verified": bool(
                            evidence.get("evidence_verified")
                        ),
                        "needs_review": bool(
                            evidence.get("needs_review")
                        ),
                    }
                )

    return utterances


def _build_risk_factors(
    audio_analysis_result: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """체크리스트 초안(AI 제안) 중 suggested 항목 + 안전영역 근거를 모은다."""

    checklist_draft = (
        audio_analysis_result.get("checklist_draft") or {}
    )
    factors = []

    for item in checklist_draft.get("checklist", []):
        if not item.get("suggested"):
            continue

        factors.append(
            {
                "category": item.get("category"),
                "item": item.get("item"),
                "evidence": [
                    {"text": e.get("evidence", "")}
                    for e in item.get("evidence", [])
                ],
            }
        )

    for entry in checklist_draft.get(
        "safety_assessment_evidence", []
    ):
        if not entry.get("evidence"):
            continue

        factors.append(
            {
                "category": entry.get("category"),
                "item": entry.get("item"),
                "evidence": [
                    {"text": e.get("evidence", "")}
                    for e in entry.get("evidence", [])
                ],
            }
        )

    return factors


def _build_warnings(
    audio_analysis_result: Dict[str, Any],
) -> List[str]:
    """
    "표현 주의" 원칙에 맞춰 "확정"/"판정" 대신 "참고"/"확인 필요"로만
    문구를 만든다.
    """

    warnings = []

    detected = audio_analysis_result.get(
        "detected_major_types", []
    )

    if detected:
        warnings.append(
            "AI가 확인이 필요한 발화를 찾았습니다. 근거 발화를 직접 "
            "확인하고 상담사가 최종 판단해 주세요."
        )

    needs_review_count = sum(
        1
        for major_result in audio_analysis_result.get(
            "subtype_analysis", {}
        ).get("results", [])
        for subtype_entry in major_result.get("subtypes", [])
        for evidence in subtype_entry.get("evidences", [])
        if evidence.get("needs_review")
    )

    if needs_review_count:
        warnings.append(
            f"추가 확인이 필요한 근거가 {needs_review_count}건 있습니다."
        )

    low_confidence_chunks = sum(
        1
        for chunk in audio_analysis_result.get(
            "chunk_results", []
        )
        if chunk.get("has_low_confidence")
    )

    if low_confidence_chunks:
        warnings.append(
            f"STT 신뢰도가 낮은 구간이 포함된 청크가 {low_confidence_chunks}개 "
            "있어 원문 검수가 필요합니다."
        )

    return warnings


def build_risk_fields(
    audio_analysis_result: Dict[str, Any],
) -> Dict[str, Any]:
    """
    infer_audio_session.analyze_audio_session()의 결과를 AIAnalysisOutput의
    risk_utterances/abuse_signals/risk_factors/warnings 모양으로 바꾼다.
    이미 분석을 끝낸 결과가 있을 때(재분석 없이) 쓴다.
    """

    return {
        "abuse_signals": _build_abuse_signals(audio_analysis_result),
        "risk_utterances": _build_risk_utterances(audio_analysis_result),
        "risk_factors": _build_risk_factors(audio_analysis_result),
        "warnings": _build_warnings(audio_analysis_result),
    }


def analyze_transcript_for_risk_fields(
    transcript_dict: Dict[str, Any],
    case_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Transcript(STT Contract v1.0 dict, 예: Transcript.model_dump())를 받아
    analyze_audio_session을 직접 돌리고 risk 필드까지 한 번에 만든다.

    run_analysis_pipeline에서 이미 다른 이유로 analyze_audio_session을
    호출했다면(예: 상담요약도 이 파이프라인에서 만들 계획이라면) 그 결과를
    build_risk_fields()에 바로 넘기는 쪽이 중복 분석을 피할 수 있다 —
    이 함수는 risk 필드만 단독으로 필요할 때 쓰는 편의 함수다.

    analyze_audio_session이 던지는 예외(PrivacyGatewayBlocked, RuntimeError,
    ValueError)를 그대로 전파한다 — 호출부가 summary_service.py의 기존
    SummaryTimeoutError 등으로 변환해야 한다면 여기서 잡지 않고 그 변환
    로직에서 처리하는 게 일관성 있다(한 곳에서만 매핑).
    """

    result = analyze_audio_session(
        stt_result=transcript_dict,
        case_id=case_id,
    )

    return build_risk_fields(result)
