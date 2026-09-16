"""
STT Contract v1.0 결과를 오늘 만든 신규 파이프라인(analyze_session 계열)으로
연결하는 진입점.

실제 음성 인식·화자분리 모델은 별도로 제공될 예정이며, 이 모듈은 그 결과가
Contract v1.0 형식(schema_version="1.0", segments[])만 지키면 그대로
연결되도록 만든 어댑터다. 구버전 세부유형 모델을 쓰는 infer_session.py는
그대로 두고 건드리지 않는다.

1차 RoBERTa는 512 토큰 제한이 있어 상담사/아동 대화를 일정 길이로 나눠
chunk 단위로 돌리고, 하나의 chunk에서라도 탐지되면 세션 전체에서
탐지된 것으로 통합한다. 2차 LLM/상담 요약·일지/체크리스트 초안은
토큰 제한이 훨씬 커서 세션 전체 transcript를 한 번에 사용한다.
"""

import os
from typing import Any, Dict, List, Tuple

from openai import OpenAI

from ai.adapters.stt_analysis_adapter import validate_stt_result

from ai.modeling.abuse.infer_abuse_v3_adapter import (
    predict_major_types,
)
from ai.modeling.abuse.second_stage_llm import (
    analyze_subtypes,
)
from ai.modeling.abuse.audio_to_counseling_note import (
    DEFAULT_MODEL as DEFAULT_NOTE_MODEL,
    generate_counseling_records,
)
from ai.modeling.abuse.checklist_llm import (
    DEFAULT_MODEL as DEFAULT_CHECKLIST_MODEL,
    generate_checklist_draft,
)


# ============================================================
# 1. 기본 설정
# ============================================================

ABUSE_LABELS = [
    "신체학대",
    "정서학대",
    "성학대",
    "방임",
]

# predict_major_types(input_mode="qa")의 화자 파싱 정규식과
# 맞추기 위해 STT speaker enum을 한국어 화자 표시로 매핑한다.
# GUARDIAN/OTHER/UNKNOWN은 1차/2차 모델이 학습된 형식에 없으므로 제외한다.
SPEAKER_LABEL_KO = {
    "COUNSELOR": "상담사",
    "CHILD": "아동",
}

# 1차 RoBERTa(512 토큰) chunk 분할 기준.
# stt_analysis_adapter.DEFAULT_MAX_CHARS와 같은 기준을 쓴다.
MAX_CHUNK_CHARS = 1000


# ============================================================
# 2. STT segment → transcript 변환
# ============================================================

def build_qa_transcript_lines(
    segments: List[Dict[str, Any]],
) -> List[Tuple[str, str, Dict[str, Any]]]:
    """
    검증된 STT segment를 (화자표시, 텍스트, 원본segment) 튜플 목록으로 만든다.
    """

    lines = []

    for segment in segments:

        speaker_ko = SPEAKER_LABEL_KO.get(
            segment["speaker"]
        )

        if not speaker_ko:
            continue

        text = segment["text"].strip()

        if not text:
            continue

        lines.append(
            (
                speaker_ko,
                text,
                segment,
            )
        )

    return lines


def build_full_transcript_text(
    lines: List[Tuple[str, str, Dict[str, Any]]],
) -> str:
    """
    세션 전체 transcript 텍스트를 만든다.
    2차 LLM/상담 요약·일지/체크리스트는 이 전체 텍스트를 그대로 쓴다.
    """

    return "\n".join(
        f"{speaker}: {text}"
        for speaker, text, _ in lines
    )


def build_qa_chunks(
    lines: List[Tuple[str, str, Dict[str, Any]]],
    max_chars: int = MAX_CHUNK_CHARS,
) -> List[List[Tuple[str, str, Dict[str, Any]]]]:
    """
    1차 RoBERTa 입력용으로 상담사/아동 줄을 max_chars 단위로 묶는다.
    """

    chunks: List[List[Tuple[str, str, Dict[str, Any]]]] = []

    current: List[Tuple[str, str, Dict[str, Any]]] = []
    current_length = 0

    for speaker, text, segment in lines:

        line = f"{speaker}: {text}"

        additional_length = len(line)

        if current:
            additional_length += 1

        if (
            current
            and current_length + additional_length > max_chars
        ):
            chunks.append(current)

            current = []
            current_length = 0

        current.append(
            (speaker, text, segment)
        )

        current_length += additional_length

    if current:
        chunks.append(current)

    return chunks


def _chunk_to_text(
    chunk: List[Tuple[str, str, Dict[str, Any]]],
) -> str:
    return "\n".join(
        f"{speaker}: {text}"
        for speaker, text, _ in chunk
    )


# ============================================================
# 2.5 근거(evidence) → 원본 음성 타임스탬프 역매핑
# ============================================================
# 2차 LLM의 evidence_start/evidence_end는 build_full_transcript_text가
# 만든 전체 텍스트 안에서의 문자 위치다. 그 문자 위치가 어떤 STT
# segment(들)에서 나왔는지 되짚어서 start_ms/end_ms를 붙여주면
# 근거 발화를 원본 음성 재생 위치와 연결할 수 있다.

def build_line_char_spans(
    lines: List[Tuple[str, str, Dict[str, Any]]],
) -> List[Dict[str, Any]]:
    """
    build_full_transcript_text와 완전히 동일한 조립 규칙
    ("화자: 텍스트"를 "\\n"으로 join)으로 각 줄의 문자 구간을 계산한다.
    """

    spans: List[Dict[str, Any]] = []

    cursor = 0

    for speaker, text, segment in lines:
        line_text = f"{speaker}: {text}"

        start_char = cursor
        end_char = cursor + len(line_text)

        spans.append(
            {
                "start_char": start_char,
                "end_char": end_char,
                "segment_id": segment["segment_id"],
                "start_ms": segment["start_ms"],
                "end_ms": segment["end_ms"],
            }
        )

        # build_full_transcript_text가 줄 사이에 "\n" 하나를 넣으므로
        # 다음 줄은 그만큼 뒤에서 시작한다.
        cursor = end_char + 1

    return spans


def _find_spans_for_char_range(
    start_char: int,
    end_char: int,
    line_spans: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    return [
        span
        for span in line_spans
        if span["start_char"] < end_char
        and span["end_char"] > start_char
    ]


def link_evidence_timestamps(
    subtype_analysis: Dict[str, Any],
    line_spans: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    subtype_analysis 안의 evidence마다 원본 음성 타임스탬프
    (start_ms/end_ms/segment_ids)를 timestamps 필드로 붙인다.

    evidence_verified가 False이거나 문자 위치가 없으면
    timestamps는 None으로 둔다 (근거 자체가 불확실한 상태에서
    잘못된 시간 구간을 링크하지 않기 위함).
    """

    for major_result in subtype_analysis.get(
        "results",
        [],
    ):
        for subtype in major_result.get(
            "subtypes",
            [],
        ):
            for evidence in subtype.get(
                "evidences",
                [],
            ):
                start_char = evidence.get(
                    "evidence_start"
                )

                end_char = evidence.get(
                    "evidence_end"
                )

                if (
                    not evidence.get(
                        "evidence_verified"
                    )
                    or start_char is None
                    or end_char is None
                ):
                    evidence["timestamps"] = None
                    continue

                matches = _find_spans_for_char_range(
                    start_char,
                    end_char,
                    line_spans,
                )

                if not matches:
                    evidence["timestamps"] = None
                    continue

                evidence["timestamps"] = {
                    "start_ms": min(
                        span["start_ms"]
                        for span in matches
                    ),
                    "end_ms": max(
                        span["end_ms"]
                        for span in matches
                    ),
                    "segment_ids": [
                        span["segment_id"]
                        for span in matches
                    ],
                }

    return subtype_analysis


# ============================================================
# 3. 세션 전체 분석
# ============================================================

def analyze_audio_session(
    stt_result: Dict[str, Any],
    client: Any = None,
    note_model: str = DEFAULT_NOTE_MODEL,
    checklist_model: str = DEFAULT_CHECKLIST_MODEL,
) -> Dict[str, Any]:
    """
    STT Contract v1.0 결과(한 세션)를 1차 → 2차 → 상담 요약·일지 →
    체크리스트 초안까지 오늘 만든 파이프라인으로 분석한다.
    """

    segments = validate_stt_result(
        stt_result
    )

    lines = build_qa_transcript_lines(
        segments
    )

    if not lines:
        raise ValueError(
            "분석 가능한 상담사/아동 발화가 없습니다."
        )

    full_text = build_full_transcript_text(
        lines
    )

    # --------------------------------------------------------
    # 1차: chunk 단위로 돌리고, 하나라도 탐지되면
    # 세션 전체에서 탐지된 것으로 통합한다.
    # --------------------------------------------------------

    chunks = build_qa_chunks(
        lines
    )

    session_detected = {
        label: False
        for label in ABUSE_LABELS
    }

    chunk_results = []

    for index, chunk in enumerate(
        chunks,
        start=1,
    ):
        chunk_prediction = predict_major_types(
            text=_chunk_to_text(chunk),
            input_mode="qa",
        )

        for label in ABUSE_LABELS:
            if chunk_prediction.get(
                label,
                {},
            ).get(
                "detected",
                False,
            ):
                session_detected[label] = True

        chunk_results.append(
            {
                "chunk_index": index,
                "segment_ids": [
                    segment["segment_id"]
                    for _, _, segment in chunk
                ],
                "has_low_confidence": any(
                    segment["is_low_confidence"]
                    for _, _, segment in chunk
                ),
                "major_types": chunk_prediction,
            }
        )

    major_types = {
        label: {"detected": session_detected[label]}
        for label in ABUSE_LABELS
    }

    detected_major_types = [
        label
        for label in ABUSE_LABELS
        if session_detected[label]
    ]

    # --------------------------------------------------------
    # 2차: 세션 전체 transcript로 한 번에 (LLM은 512 토큰 제한 없음)
    # --------------------------------------------------------

    if detected_major_types:
        subtype_result = analyze_subtypes(
            text=full_text,
            major_types=detected_major_types,
        )

        line_spans = build_line_char_spans(
            lines
        )

        subtype_result = link_evidence_timestamps(
            subtype_result,
            line_spans,
        )
    else:
        subtype_result = {
            "results": [],
            "note": "탐지된 대분류 없음",
        }

    # --------------------------------------------------------
    # 상담 요약/일지 + 체크리스트 초안 (세션 전체 transcript)
    # --------------------------------------------------------

    if client is None:
        api_key = os.environ.get(
            "OPENAI_API_KEY"
        )

        if not api_key:
            raise RuntimeError(
                "환경변수 OPENAI_API_KEY가 설정되어 있지 않습니다."
            )

        client = OpenAI(
            api_key=api_key
        )

    counseling_records = generate_counseling_records(
        client=client,
        transcript=full_text,
        model=note_model,
    )

    checklist_draft = generate_checklist_draft(
        text=full_text,
        client=client,
        model=checklist_model,
    )

    return {
        "full_text": full_text,
        "major_types": major_types,
        "detected_major_types": detected_major_types,
        "subtype_analysis": subtype_result,
        "counseling_summary": counseling_records[
            "counseling_summary"
        ],
        "counseling_note": counseling_records[
            "counseling_note"
        ],
        "counseling_record_model": note_model,
        "checklist_draft": checklist_draft,
        "chunk_results": chunk_results,
    }


# ============================================================
# 4. 데모
# ============================================================

if __name__ == "__main__":
    import json

    sample_stt_result = {
        "schema_version": "1.0",
        "segments": [
            {
                "segment_id": "seg_001",
                "speaker": "COUNSELOR",
                "text": "아빠가 어떻게 했어?",
                "start_ms": 0,
                "end_ms": 2000,
                "confidence": 0.95,
            },
            {
                "segment_id": "seg_002",
                "speaker": "CHILD",
                "text": "아빠가 막대기로 제 팔을 여러 번 때렸어요.",
                "start_ms": 2200,
                "end_ms": 5000,
                "confidence": 0.92,
            },
            {
                "segment_id": "seg_003",
                "speaker": "COUNSELOR",
                "text": "또 다른 일도 있었어?",
                "start_ms": 5200,
                "end_ms": 6500,
                "confidence": 0.96,
            },
            {
                "segment_id": "seg_004",
                "speaker": "CHILD",
                "text": "저번에는 벨트로 허벅지를 때렸어요.",
                "start_ms": 6700,
                "end_ms": 9000,
                "confidence": 0.60,
                "is_low_confidence": True,
            },
        ],
    }

    result = analyze_audio_session(
        stt_result=sample_stt_result
    )

    print(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2,
        )
    )
