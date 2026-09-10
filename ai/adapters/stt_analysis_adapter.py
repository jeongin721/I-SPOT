"""
I-SPOT STT 결과를 1차·2차 학대 분석 모델 입력으로 변환하는 Adapter다.
STT segment를 보존하면서 CHILD 중심 입력과 COUNSELOR+CHILD 문맥 입력을 생성한다.
"""

# ============================================================
# 1. Import
# ============================================================

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


# ============================================================
# 2. 설정
# ============================================================

VALID_SPEAKERS = {
    "COUNSELOR",
    "CHILD",
    "GUARDIAN",
    "OTHER",
    "UNKNOWN",
}

# 모델 입력이 지나치게 길어지는 것을 막기 위한
# 1차적인 문자 수 기준.
#
# 실제 tokenizer의 MAX_LENGTH와 완전히 동일한 개념은 아니며,
# segment를 안전하게 묶기 위한 Adapter 단계의 제한이다.
DEFAULT_MAX_CHARS = 1000


# ============================================================
# 3. Chunk 구조
# ============================================================

@dataclass
class AnalysisChunk:
    """
    모델에 전달할 하나의 상담 분석 단위다.

    chunk_id:
        Adapter가 생성한 chunk 식별자

    text:
        실제 모델 입력 문자열

    segment_ids:
        이 chunk를 구성한 원본 STT segment ID

    has_low_confidence:
        포함된 STT 발화 중 저신뢰 구간 존재 여부

    start_ms / end_ms:
        원본 음성에서 해당 chunk의 시간 범위
    """

    chunk_id: str
    text: str
    segment_ids: List[str]
    has_low_confidence: bool
    start_ms: int
    end_ms: int

    def to_dict(self) -> Dict[str, Any]:
        """Backend/테스트에서 사용하기 쉬운 dict 형태로 변환한다."""

        return {
            "chunk_id": self.chunk_id,
            "text": self.text,
            "segment_ids": self.segment_ids,
            "has_low_confidence": self.has_low_confidence,
            "start_ms": self.start_ms,
            "end_ms": self.end_ms,
        }


# ============================================================
# 4. STT Contract 검증
# ============================================================

def validate_stt_result(
    stt_result: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """
    STT 결과가 AI Adapter에서 사용할 수 있는 형태인지 확인한다.

    STT 담당자의 후처리가 끝난 Contract v1.0을 기준으로 한다.
    """

    if not isinstance(stt_result, dict):
        raise ValueError(
            "STT 결과는 dict 형식이어야 합니다."
        )

    if stt_result.get("schema_version") != "1.0":
        raise ValueError(
            "지원하지 않는 STT schema_version입니다."
        )

    segments = stt_result.get("segments")

    if not isinstance(segments, list):
        raise ValueError(
            "STT 결과에 segments 배열이 필요합니다."
        )

    validated_segments = []

    for index, segment in enumerate(
        segments,
        start=1,
    ):

        if not isinstance(segment, dict):
            raise ValueError(
                f"{index}번째 segment가 dict 형식이 아닙니다."
            )

        segment_id = str(
            segment.get(
                "segment_id",
                "",
            )
        ).strip()

        speaker = str(
            segment.get(
                "speaker",
                "UNKNOWN",
            )
        ).strip().upper()

        text = str(
            segment.get(
                "text",
                "",
            )
        ).strip()

        if not segment_id:
            raise ValueError(
                f"{index}번째 segment에 segment_id가 없습니다."
            )

        if speaker not in VALID_SPEAKERS:
            speaker = "UNKNOWN"

        # 빈 발화는 분석 대상에서 제외
        if not text:
            continue

        start_ms = int(
            segment.get(
                "start_ms",
                0,
            )
        )

        end_ms = int(
            segment.get(
                "end_ms",
                start_ms,
            )
        )

        confidence = float(
            segment.get(
                "confidence",
                0.0,
            )
        )

        is_low_confidence = bool(
            segment.get(
                "is_low_confidence",
                confidence < 0.70,
            )
        )

        validated_segments.append(
            {
                "segment_id": segment_id,
                "speaker": speaker,
                "start_ms": max(
                    0,
                    start_ms,
                ),
                "end_ms": max(
                    start_ms,
                    end_ms,
                ),
                "text": text,
                "confidence": max(
                    0.0,
                    min(
                        1.0,
                        confidence,
                    ),
                ),
                "is_low_confidence": (
                    is_low_confidence
                ),
            }
        )

    return validated_segments


# ============================================================
# 5. 공통 Chunk 생성
# ============================================================

def _build_chunk(
    chunk_index: int,
    segments: List[Dict[str, Any]],
    text: str,
) -> AnalysisChunk:
    """
    여러 STT segment 정보를 하나의 AnalysisChunk로 묶는다.
    """

    if not segments:
        raise ValueError(
            "빈 segment로 chunk를 생성할 수 없습니다."
        )

    return AnalysisChunk(
        chunk_id=f"chunk_{chunk_index:03d}",
        text=text.strip(),
        segment_ids=[
            segment["segment_id"]
            for segment in segments
        ],
        has_low_confidence=any(
            segment[
                "is_low_confidence"
            ]
            for segment in segments
        ),
        start_ms=min(
            segment["start_ms"]
            for segment in segments
        ),
        end_ms=max(
            segment["end_ms"]
            for segment in segments
        ),
    )


# ============================================================
# 6. 1차 모델용 CHILD Chunk 생성
# ============================================================

def build_abuse_chunks(
    stt_result,
    max_chars=DEFAULT_MAX_CHARS,
):
    """
    팀 공용 Transcript에서 CHILD 발화만 추출하여
    현재 A-only 1차 학대유형 모델 입력 chunk를 생성한다.
    """

    # ============================================================
    # 1. 팀 공용 Transcript 검증
    # ============================================================

    segments = validate_stt_result(stt_result)

    # ============================================================
    # 2. CHILD 발화만 추출
    # ============================================================

    child_segments = [
        segment
        for segment in segments
        if (
            segment["speaker"] == "CHILD"
            and segment["text"].strip()
        )
    ]

    if not child_segments:
        return []

    # ============================================================
    # 3. CHILD 발화를 모델 입력 길이에 맞게 묶기
    # ============================================================

    chunks = []

    current_segments = []
    current_texts = []
    current_length = 0

    for segment in child_segments:

        text = segment["text"].strip()

        additional_length = len(text)

        if current_texts:
            additional_length += 1

        if (
            current_segments
            and current_length + additional_length > max_chars
        ):
            chunks.append(
                _build_chunk(
                    chunk_index=len(chunks) + 1,
                    segments=current_segments,
                    text=" ".join(current_texts),
                )
            )

            current_segments = []
            current_texts = []
            current_length = 0

        current_segments.append(segment)
        current_texts.append(text)

        current_length += additional_length

    # ============================================================
    # 4. 마지막 chunk 저장
    # ============================================================

    if current_segments:
        chunks.append(
            _build_chunk(
                chunk_index=len(chunks) + 1,
                segments=current_segments,
                text=" ".join(current_texts),
            )
        )

    return chunks

# ============================================================
# 7. COUNSELOR + CHILD 문맥 그룹 생성
# ============================================================

def _build_qa_groups(
    segments: List[Dict[str, Any]],
) -> List[List[Dict[str, Any]]]:
    """
    2차 모델용 상담 문맥 단위를 생성한다.

    기본 구조:
        COUNSELOR
        → CHILD
        → CHILD

    다음 COUNSELOR 발화가 등장하면
    새로운 문맥 그룹을 시작한다.

    GUARDIAN / OTHER / UNKNOWN은 현재 2차 모델 입력에서 제외한다.
    """

    qa_groups = []

    current_group = []

    for segment in segments:

        speaker = segment[
            "speaker"
        ]

        # ----------------------------------------------------
        # 상담사 발화
        # ----------------------------------------------------

        if speaker == "COUNSELOR":

            # 기존 그룹에 CHILD 답변까지 존재한다면 저장
            if (
                current_group
                and any(
                    item["speaker"] == "CHILD"
                    for item in current_group
                )
            ):

                qa_groups.append(
                    current_group
                )

            # 새로운 질문 문맥 시작
            current_group = [
                segment
            ]

        # ----------------------------------------------------
        # 아동 발화
        # ----------------------------------------------------

        elif speaker == "CHILD":

            # 앞에 COUNSELOR 질문이 없어도
            # CHILD 발화 자체는 분석 대상이므로 보존한다.
            current_group.append(
                segment
            )

        # ----------------------------------------------------
        # 나머지 화자
        # ----------------------------------------------------

        else:
            continue

    # 마지막 그룹 저장
    if (
        current_group
        and any(
            item["speaker"] == "CHILD"
            for item in current_group
        )
    ):

        qa_groups.append(
            current_group
        )

    return qa_groups


# ============================================================
# 8. Q+A 그룹 → 텍스트 변환
# ============================================================

def _qa_group_to_text(
    group: List[Dict[str, Any]],
) -> str:
    """
    Q+A segment 그룹을 현재 2차 모델이 사용하는
    화자 태그 문자열로 변환한다.

    예:
        [COUNSELOR] 무슨 일이 있었나요?
        [CHILD] 아빠가 막대기로 때렸어요.
    """

    lines = []

    for segment in group:

        speaker = segment[
            "speaker"
        ]

        text = segment[
            "text"
        ]

        lines.append(
            f"[{speaker}] {text}"
        )

    return " ".join(
        lines
    )


# ============================================================
# 9. 2차 모델용 Q+A Chunk 생성
# ============================================================

def build_subtype_chunks(
    stt_result: Dict[str, Any],
    max_chars: int = DEFAULT_MAX_CHARS,
) -> List[AnalysisChunk]:
    """
    2차 세부유형 모델 입력을 CHILD 발화만 사용해 생성한다.

    COUNSELOR 발화는 모델 입력에서 제외하고,
    CHILD segment 하나를 하나의 분석 chunk로 사용한다.
    """

    # ========================================================
    # 1. STT 결과 검증
    # ========================================================

    segments = validate_stt_result(
        stt_result
    )

    # ========================================================
    # 2. CHILD 발화만 추출
    # ========================================================

    child_segments = [
        segment
        for segment in segments
        if (
            segment["speaker"] == "CHILD"
            and segment["text"].strip()
        )
    ]

    if not child_segments:
        return []

    # ========================================================
    # 3. CHILD segment 하나당 하나의 Chunk 생성
    # ========================================================

    chunks: List[AnalysisChunk] = []

    for segment in child_segments:

        child_text = segment[
            "text"
        ].strip()

        # XAI의 CHILD 범위 추출 로직과 호환되도록
        # [CHILD] 태그만 붙인다.
        chunk_text = (
            f"[CHILD] {child_text}"
        )

        chunks.append(
            _build_chunk(
                chunk_index=len(chunks) + 1,
                segments=[segment],
                text=chunk_text,
            )
        )

    return chunks
    
# ============================================================
# 10. 전체 Adapter
# ============================================================

class STTAnalysisAdapter:
    """
    STT Contract v1.0 결과를
    I-SPOT AI 모델 입력으로 변환하는 Adapter다.
    """

    def __init__(
        self,
        max_chars: int = DEFAULT_MAX_CHARS,
    ) -> None:

        if max_chars <= 0:
            raise ValueError(
                "max_chars는 1 이상이어야 합니다."
            )

        self.max_chars = max_chars

    def build_abuse_inputs(
        self,
        stt_result: Dict[str, Any],
    ) -> List[AnalysisChunk]:
        """
        1차 4대 학대유형 모델 입력 생성.
        """

        return build_abuse_chunks(
            stt_result=stt_result,
            max_chars=self.max_chars,
        )

    def build_subtype_inputs(
        self,
        stt_result: Dict[str, Any],
    ) -> List[AnalysisChunk]:
        """
        2차 세부유형 모델 입력 생성.
        """

        return build_subtype_chunks(
            stt_result=stt_result,
            max_chars=self.max_chars,
        )

    def build_all_inputs(
        self,
        stt_result: Dict[str, Any],
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        하나의 STT 결과에서
        1차와 2차 모델 입력을 동시에 생성한다.
        """

        abuse_chunks = (
            self.build_abuse_inputs(
                stt_result
            )
        )

        subtype_chunks = (
            self.build_subtype_inputs(
                stt_result
            )
        )

        return {
            "abuse_chunks": [
                chunk.to_dict()
                for chunk
                in abuse_chunks
            ],
            "subtype_chunks": [
                chunk.to_dict()
                for chunk
                in subtype_chunks
            ],
        }


# ============================================================
# 11. 간단한 Mock 테스트
# ============================================================

def main() -> None:
    """
    실제 STT 연결 전 Adapter 동작을 확인하기 위한 Mock 테스트다.
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
                    "아빠가 막대기로 "
                    "제 다리를 때렸어요."
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
                    "그런 일이 자주 있었나요?"
                ),
                "confidence": 0.94,
                "is_low_confidence": False,
            },
            {
                "segment_id": "seg_004",
                "speaker": "CHILD",
                "start_ms": 8100,
                "end_ms": 10000,
                "text": (
                    "일주일에 두세 번 정도 그래요."
                ),
                "confidence": 0.55,
                "is_low_confidence": True,
            },
        ],
    }

    adapter = STTAnalysisAdapter(
        max_chars=1000
    )

    result = adapter.build_all_inputs(
        mock_stt_result
    )

    print()
    print("=" * 70)
    print("I-SPOT STT → AI Adapter 테스트")
    print("=" * 70)

    print()
    print("[1차 학대유형 모델 입력]")

    for chunk in result[
        "abuse_chunks"
    ]:

        print()
        print(chunk)

    print()
    print("[2차 세부유형 모델 입력]")

    for chunk in result[
        "subtype_chunks"
    ]:

        print()
        print(chunk)


# ============================================================
# 12. Entry Point
# ============================================================

if __name__ == "__main__":
    main()