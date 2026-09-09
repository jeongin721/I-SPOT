"""
I-SPOT 한 회기 전체 STT 상담을 1차·2차 모델로 분석하는 통합 추론 모듈이다.
긴 상담을 chunk별로 추론한 뒤 회기 전체의 학대유형 및 세부유형 탐지 결과를 통합한다.
"""

# ============================================================
# 1. Import
# ============================================================

from typing import Any, Dict, List

from tqdm import tqdm

from ai.adapters.stt_analysis_adapter import (
    AnalysisChunk,
    STTAnalysisAdapter,
    validate_stt_result,
)

from ai.modeling.abuse.infer_abuse import (
    predict_abuse,
)

from ai.modeling.abuse.infer_subtype import (
    LABEL_DISPLAY_NAMES,
    predict_subtype,
)

from ai.modeling.abuse.explain_subtype import (
    explain_single_subtype,
)

# ============================================================
# 2. 1차 학대유형 설정
# ============================================================

ABUSE_LABELS = [
    "신체학대",
    "정서학대",
    "성학대",
    "방임",
]


# ============================================================
# 3. 세부유형 → 1차 학대유형 매핑
# ============================================================

SUBTYPE_TO_ABUSE = {
    # --------------------------------------------------------
    # 신체학대
    # --------------------------------------------------------
    "physical_direct": "신체학대",
    "physical_object": "신체학대",
    "physical_force": "신체학대",

    # --------------------------------------------------------
    # 정서학대
    # --------------------------------------------------------
    "emotional_verbal": "정서학대",
    "emotional_threat": "정서학대",
    "emotional_restriction": "정서학대",
    "emotional_discrimination": "정서학대",
    "emotional_dv_exposure": "정서학대",
    "emotional_cruelty": "정서학대",

    # --------------------------------------------------------
    # 성학대
    # --------------------------------------------------------
    "sexual_exposure": "성학대",
    "sexual_molestation": "성학대",
    "sexual_intercourse": "성학대",

    # --------------------------------------------------------
    # 방임
    # --------------------------------------------------------
    "neglect_physical": "방임",
    "neglect_education": "방임",
    "neglect_medical": "방임",
}


# ============================================================
# 4. Chunk → Dict 변환
# ============================================================

def _chunk_to_dict(
    chunk: AnalysisChunk,
) -> Dict[str, Any]:
    """AnalysisChunk의 추적 정보를 dict 형태로 변환한다."""

    return {
        "chunk_id": chunk.chunk_id,
        "segment_ids": chunk.segment_ids,
        "start_ms": chunk.start_ms,
        "end_ms": chunk.end_ms,
        "has_low_confidence": (
            chunk.has_low_confidence
        ),
    }

# ============================================================
# XAI 근거 표현 → 원본 STT Segment 연결
# ============================================================

def _link_evidence_to_segments(
    evidence_phrases: List[str],
    chunk: AnalysisChunk,
    stt_segments: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    XAI가 추출한 근거 표현을 실제 CHILD STT segment와 연결한다.

    근거 표현이 실제로 포함된 CHILD 발화만 사용하며,
    원본 segment_id / timestamp / confidence 정보를 보존한다.

    하나의 근거 표현이 여러 segment에 존재하면
    해당되는 모든 segment를 반환한다.
    """

    linked_evidence = []

    # 현재 chunk에 포함된 segment만 검색
    chunk_segment_ids = set(
        chunk.segment_ids
    )

    for phrase in evidence_phrases:

        normalized_phrase = (
            phrase.strip()
        )

        if not normalized_phrase:
            continue

        for segment in stt_segments:

            # -----------------------------------------------
            # 현재 chunk 밖의 segment 제외
            # -----------------------------------------------

            if (
                segment["segment_id"]
                not in chunk_segment_ids
            ):
                continue

            # -----------------------------------------------
            # XAI 근거는 CHILD 발화에서만 연결
            # -----------------------------------------------

            if (
                segment["speaker"]
                != "CHILD"
            ):
                continue

            source_text = (
                segment["text"]
            )

            # -----------------------------------------------
            # 근거 표현이 실제 원문에 존재하는지 확인
            # -----------------------------------------------

            if (
                normalized_phrase
                not in source_text
            ):
                continue

            linked_evidence.append(
                {
                    "evidence_text": (
                        normalized_phrase
                    ),
                    "segment_id": (
                        segment[
                            "segment_id"
                        ]
                    ),
                    "source_text": (
                        source_text
                    ),
                    "start_ms": (
                        segment[
                            "start_ms"
                        ]
                    ),
                    "end_ms": (
                        segment[
                            "end_ms"
                        ]
                    ),
                    "confidence": (
                        segment[
                            "confidence"
                        ]
                    ),
                    "is_low_confidence": (
                        segment[
                            "is_low_confidence"
                        ]
                    ),
                }
            )

    return linked_evidence


# ============================================================
# 5. 1차 회기 분석
# ============================================================

def _analyze_abuse_chunks(
    chunks: List[AnalysisChunk],
) -> Dict[str, Dict[str, Any]]:
    """
    CHILD 중심 chunk를 각각 1차 모델로 분석한다.

    하나의 chunk에서라도 detected=True이면
    회기 전체에서도 해당 학대유형을 탐지된 것으로 통합한다.

    확률값은 외부 결과에 노출하지 않는다.
    """

    # --------------------------------------------------------
    # 회기 전체 결과 초기화
    # --------------------------------------------------------

    session_result = {
        label: {
            "detected": False,
            "evidence_chunks": [],
        }
        for label in ABUSE_LABELS
    }

    # --------------------------------------------------------
    # Chunk별 추론
    # --------------------------------------------------------

    for chunk in tqdm(
        chunks,
        desc="1차 회기 분석",
    ):

        predictions = predict_abuse(
            chunk.text
        )

        for label in ABUSE_LABELS:

            prediction = predictions.get(
                label,
                {
                    "detected": False,
                },
            )

            if not prediction.get(
                "detected",
                False,
            ):
                continue

            # 하나라도 탐지되면 회기 전체에서 탐지
            session_result[
                label
            ][
                "detected"
            ] = True

            session_result[
                label
            ][
                "evidence_chunks"
            ].append(
                _chunk_to_dict(
                    chunk
                )
            )

    return session_result


# ============================================================
# 2차 회기 분석 + XAI + Segment 연결
# ============================================================

def _analyze_subtype_chunks(
    chunks: List[AnalysisChunk],
    stt_segments: List[Dict[str, Any]],
) -> Dict[str, Dict[str, Any]]:
    """
    COUNSELOR + CHILD 문맥 chunk를 각각
    2차 세부유형 모델로 분석한다.

    탐지된 subtype에 대해서만 Phrase Occlusion XAI를 수행하고,
    XAI 근거 표현을 실제 CHILD STT segment_id와 연결한다.

    하나의 chunk에서라도 탐지된 subtype은
    회기 전체에서 detected=True로 통합한다.
    """

    session_result: Dict[
        str,
        Dict[str, Any],
    ] = {}

    # --------------------------------------------------------
    # Chunk별 2차 추론
    # --------------------------------------------------------

    for chunk in tqdm(
        chunks,
        desc="2차 회기 분석",
    ):

        predictions = predict_subtype(
            chunk.text
        )

        # ----------------------------------------------------
        # 탐지된 Subtype만 처리
        # ----------------------------------------------------

        for (
            subtype,
            prediction,
        ) in predictions.items():

            if not prediction.get(
                "detected",
                False,
            ):
                continue

            # ------------------------------------------------
            # XAI 실행
            #
            # 전체 Q+A는 모델 문맥으로 유지하고,
            # explain_subtype.py 내부에서 CHILD 발화만
            # Phrase Occlusion 대상으로 사용한다.
            # ------------------------------------------------

            evidence_phrases = (
                explain_single_subtype(
                    text=chunk.text,
                    label=subtype,
                )
            )

            # ------------------------------------------------
            # XAI 근거 → 실제 STT Segment 연결
            # ------------------------------------------------

            linked_evidence = (
                _link_evidence_to_segments(
                    evidence_phrases=(
                        evidence_phrases
                    ),
                    chunk=chunk,
                    stt_segments=(
                        stt_segments
                    ),
                )
            )

            # ------------------------------------------------
            # Subtype 최초 탐지
            # ------------------------------------------------

            if subtype not in session_result:

                session_result[
                    subtype
                ] = {
                    "detected": True,
                    "display_name": (
                        LABEL_DISPLAY_NAMES.get(
                            subtype,
                            subtype,
                        )
                    ),
                    "parent_abuse": (
                        SUBTYPE_TO_ABUSE.get(
                            subtype
                        )
                    ),
                    "evidence_chunks": [],
                    "evidence": [],
                }

            # ------------------------------------------------
            # 탐지된 Chunk 기록
            # ------------------------------------------------

            session_result[
                subtype
            ][
                "evidence_chunks"
            ].append(
                _chunk_to_dict(
                    chunk
                )
            )

            # ------------------------------------------------
            # Segment 단위 실제 근거 기록
            # ------------------------------------------------

            session_result[
                subtype
            ][
                "evidence"
            ].extend(
                linked_evidence
            )

    return session_result


# ============================================================
# 7. 1차 결과 기준 2차 결과 필터
# ============================================================

def _filter_subtypes_by_abuse(
    abuse_result: Dict[
        str,
        Dict[str, Any],
    ],
    subtype_result: Dict[
        str,
        Dict[str, Any],
    ],
) -> Dict[str, Dict[str, Any]]:
    """
    1차에서 탐지된 상위 학대유형에 속하는
    2차 세부유형만 최종 결과에 남긴다.

    예:
        1차 신체학대 = False
        → physical_* 세부유형은 최종 결과에서 제외
    """

    detected_abuse = {
        label
        for label, result
        in abuse_result.items()
        if result.get(
            "detected",
            False,
        )
    }

    filtered_result = {}

    for (
        subtype,
        result,
    ) in subtype_result.items():

        parent_abuse = result.get(
            "parent_abuse"
        )

        if parent_abuse not in detected_abuse:
            continue

        filtered_result[
            subtype
        ] = result

    return filtered_result


# ============================================================
# 8. 저신뢰 STT Warning 생성
# ============================================================

def _build_warnings(
    abuse_result: Dict[
        str,
        Dict[str, Any],
    ],
    subtype_result: Dict[
        str,
        Dict[str, Any],
    ],
) -> List[str]:
    """
    탐지 결과에 사용된 chunk 중
    STT 저신뢰 segment가 포함된 경우 warning을 생성한다.
    """

    has_low_confidence = False

    # --------------------------------------------------------
    # 1차 확인
    # --------------------------------------------------------

    for result in abuse_result.values():

        for chunk in result.get(
            "evidence_chunks",
            [],
        ):

            if chunk.get(
                "has_low_confidence",
                False,
            ):
                has_low_confidence = True
                break

        if has_low_confidence:
            break

    # --------------------------------------------------------
    # 2차 확인
    # --------------------------------------------------------

    if not has_low_confidence:

        for result in subtype_result.values():

            for chunk in result.get(
                "evidence_chunks",
                [],
            ):

                if chunk.get(
                    "has_low_confidence",
                    False,
                ):
                    has_low_confidence = True
                    break

            if has_low_confidence:
                break

    warnings = []

    if has_low_confidence:

        warnings.append(
            "탐지 결과에 STT 저신뢰 발화가 포함되어 "
            "원본 음성 확인이 필요합니다."
        )

    return warnings


# ============================================================
# 9. 전체 회기 분석
# ============================================================

def analyze_stt_session(
    stt_result: Dict[str, Any],
    max_chars: int = 1000,
) -> Dict[str, Any]:
    """
    하나의 상담 회기 STT 결과 전체를 분석한다.

    처리 흐름:
        STT Contract
        → Adapter
        → 1차 CHILD chunk
        → 1차 모델
        → 2차 Q+A chunk
        → 2차 모델
        → 회기 전체 결과 통합
    """

    # --------------------------------------------------------
    # STT Contract 검증 및 원본 Segment 확보
    # --------------------------------------------------------

    stt_segments = (
        validate_stt_result(
            stt_result
        )
    )

    # --------------------------------------------------------
    # Adapter 준비
    # --------------------------------------------------------

    adapter = STTAnalysisAdapter(
        max_chars=max_chars
    )

    # --------------------------------------------------------
    # 1차 입력 생성
    # --------------------------------------------------------

    abuse_chunks = (
        adapter.build_abuse_inputs(
            stt_result
        )
    )

    # --------------------------------------------------------
    # 2차 입력 생성
    # --------------------------------------------------------

    subtype_chunks = (
        adapter.build_subtype_inputs(
            stt_result
        )
    )

    # --------------------------------------------------------
    # 1차 분석
    # --------------------------------------------------------

    abuse_result = (
        _analyze_abuse_chunks(
            abuse_chunks
        )
    )

    # --------------------------------------------------------
    # 2차 분석
    # --------------------------------------------------------

    subtype_result = (
        _analyze_subtype_chunks(
            chunks=subtype_chunks,
            stt_segments=stt_segments,
        )
    )

    # --------------------------------------------------------
    # 1차 결과 기준 2차 필터
    # --------------------------------------------------------

    subtype_result = (
        _filter_subtypes_by_abuse(
            abuse_result=abuse_result,
            subtype_result=subtype_result,
        )
    )

    # --------------------------------------------------------
    # Warning
    # --------------------------------------------------------

    warnings = _build_warnings(
        abuse_result=abuse_result,
        subtype_result=subtype_result,
    )

    # --------------------------------------------------------
    # 최종 반환
    # --------------------------------------------------------

    return {
        "schema_version": "1.0",
        "abuse_signals": (
            abuse_result
        ),
        "subtype_signals": (
            subtype_result
        ),
        "warnings": warnings,
    }


# ============================================================
# 10. Mock STT 테스트
# ============================================================

def main() -> None:
    """
    실제 STT 연결 전 전체 회기 분석을
    Mock STT 데이터로 테스트한다.
    """

    mock_stt_result = {
        "schema_version": "1.0",
        "segments": [
            {
                "segment_id": "seg_001",
                "speaker": "COUNSELOR",
                "start_ms": 1000,
                "end_ms": 3000,
                "text": (
                    "집에서 무슨 일이 있었는지 "
                    "이야기해 줄 수 있나요?"
                ),
                "confidence": 0.95,
                "is_low_confidence": False,
            },
            {
                "segment_id": "seg_002",
                "speaker": "CHILD",
                "start_ms": 3100,
                "end_ms": 6000,
                "text": (
                    "아빠가 저한테 욕하면서 "
                    "집에서 나가라고 했어요."
                ),
                "confidence": 0.91,
                "is_low_confidence": False,
            },
            {
                "segment_id": "seg_003",
                "speaker": "COUNSELOR",
                "start_ms": 6100,
                "end_ms": 8000,
                "text": (
                    "그 다음에는 무슨 일이 있었나요?"
                ),
                "confidence": 0.94,
                "is_low_confidence": False,
            },
            {
                "segment_id": "seg_004",
                "speaker": "CHILD",
                "start_ms": 8100,
                "end_ms": 11000,
                "text": (
                    "막대기로 제 다리를 "
                    "여러 번 때렸어요."
                ),
                "confidence": 0.88,
                "is_low_confidence": False,
            },
        ],
    }

    result = analyze_stt_session(
        mock_stt_result
    )

    print()
    print("=" * 70)
    print("I-SPOT 상담 회기 통합 분석 결과")
    print("=" * 70)

    print()

    # --------------------------------------------------------
    # 1차 출력
    # --------------------------------------------------------

    print("[1차 학대유형]")

    for (
        label,
        analysis,
    ) in result[
        "abuse_signals"
    ].items():

        status = (
            "탐지 있음"
            if analysis[
                "detected"
            ]
            else "탐지 없음"
        )

        print(
            f"- {label}: {status}"
        )

    # --------------------------------------------------------
    # 2차 출력
    # --------------------------------------------------------

    print()
    print("[2차 세부유형]")

    if not result[
        "subtype_signals"
    ]:

        print(
            "- 탐지된 세부유형 없음"
        )

    else:

        for (
            subtype,
            analysis,
        ) in result[
            "subtype_signals"
        ].items():

            print(
                f"- "
                f"{analysis['display_name']} "
                f"({subtype})"
            )

            print(
                "  탐지 chunk: "
                f"{analysis['evidence_chunks']}"
            )

            evidence_items = (
                analysis.get(
                    "evidence",
                    [],
                )
            )

            if evidence_items:

                print(
                    "  XAI 근거:"
                )

                for evidence in evidence_items:

                    print(
                        f"    - "
                        f"{evidence['evidence_text']}"
                    )

                    print(
                        f"      segment_id: "
                        f"{evidence['segment_id']}"
                    )

                    print(
                        f"      원문: "
                        f"{evidence['source_text']}"
                    )

                    print(
                        f"      시간: "
                        f"{evidence['start_ms']}ms"
                        f" ~ "
                        f"{evidence['end_ms']}ms"
                    )

                    if evidence[
                        "is_low_confidence"
                    ]:

                        print(
                            "      ⚠ STT 저신뢰 구간"
                        )

    # --------------------------------------------------------
    # Warning
    # --------------------------------------------------------

    if result[
        "warnings"
    ]:

        print()
        print("[Warnings]")

        for warning in result[
            "warnings"
        ]:

            print(
                f"- {warning}"
            )


# ============================================================
# 11. Entry Point
# ============================================================

if __name__ == "__main__":
    main()