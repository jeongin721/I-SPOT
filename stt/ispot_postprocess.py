"""I-SPOT STT Post-processing Module.

STT 결과(Contract v1.0)를 전달받아 다음 작업을 수행한다:
1. 연속된 동일 화자의 세그먼트 병합
2. word-level 정보 보존
3. 잘못 잘린 화자 경계 일부 보정
4. confidence 재검증
5. 텍스트 공백 정제
"""

from typing import Any, Dict, List


class STTPostProcessor:
    def __init__(
        self,
        low_confidence_threshold: float = 0.70,
        merge_silence_gap_ms: int = 1500,
    ):
        self.threshold = low_confidence_threshold
        self.max_gap_ms = merge_silence_gap_ms

    # ============================================================
    # 1. 텍스트 정리
    # ============================================================

    def clean_text(self, text: str) -> str:
        """불필요한 공백 정리"""
        if not text:
            return ""

        return " ".join(text.split())

    # ============================================================
    # 2. 동일 화자의 연속 segment 병합
    # ============================================================

    def merge_same_speaker_segments(
        self,
        segments: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:

        if not segments:
            return []

        merged: List[Dict[str, Any]] = []
        current = None

        for seg in segments:

            cleaned_text = self.clean_text(
                seg.get("text", "")
            )

            if not cleaned_text:
                continue

            seg_info = {
                "speaker": seg.get(
                    "speaker",
                    "UNKNOWN",
                ),
                "start_ms": seg.get(
                    "start_ms",
                    0,
                ),
                "end_ms": seg.get(
                    "end_ms",
                    0,
                ),
                "text": cleaned_text,
                "confidence": seg.get(
                    "confidence",
                    0.0,
                ),

                # word-level 정보 유지
                "words": list(
                    seg.get("words", [])
                ),
            }

            # 첫 segment
            if current is None:
                current = seg_info
                continue

            is_same_speaker = (
                current["speaker"]
                == seg_info["speaker"]
            )

            gap = (
                seg_info["start_ms"]
                - current["end_ms"]
            )

            # 같은 화자 + 짧은 공백이면 병합
            if (
                is_same_speaker
                and gap <= self.max_gap_ms
            ):

                current["end_ms"] = (
                    seg_info["end_ms"]
                )

                current["text"] = (
                    f"{current['text']} "
                    f"{seg_info['text']}"
                ).strip()

                current["confidence"] = round(
                    (
                        current["confidence"]
                        + seg_info["confidence"]
                    )
                    / 2,
                    2,
                )

                # words도 같이 병합
                current["words"].extend(
                    seg_info["words"]
                )

            else:

                merged.append(current)
                current = seg_info

        if current:
            merged.append(current)

        return merged

    # ============================================================
    # 3. 화자 경계 보정
    # ============================================================

    def fix_speaker_boundary(
        self,
        segments: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Deepgram diarization이 문장의 마지막 질문 표현을
        다음 화자로 잘못 넘긴 경우를 일부 보정한다.

        예:

        SPEAKER_0
        "보통 일주일이면 몇 번 아픈 거"

        SPEAKER_1
        "같아? 일주일에 두 번 아픈 거 같아요."

        ↓

        SPEAKER_0
        "보통 일주일이면 몇 번 아픈 거 같아?"

        SPEAKER_1
        "일주일에 두 번 아픈 거 같아요."
        """

        if not segments or len(segments) < 2:
            return segments

        # --------------------------------------------------------
        # 앞 문장에 붙을 가능성이 높은 짧은 질문 종결 표현
        # --------------------------------------------------------

        question_endings = {
            "같아?",
            "어때?",
            "있어?",
            "했어?",
            "뭐야?",
            "왜?",
            "어떠셔?",
        }

        for i in range(len(segments) - 1):

            current = segments[i]
            next_seg = segments[i + 1]

            # 같은 화자라면 보정할 필요 없음
            if (
                current.get("speaker")
                == next_seg.get("speaker")
            ):
                continue

            current_words = current.get(
                "words",
                [],
            )

            next_words = next_seg.get(
                "words",
                [],
            )

            if not current_words:
                continue

            if not next_words:
                continue

            # 다음 segment의 첫 단어
            first_next_word = next_words[0]

            first_word_text = str(
                first_next_word.get(
                    "word",
                    "",
                )
            ).strip()

            # 우리가 지정한 질문형이 아니면 건드리지 않음
            if (
                first_word_text
                not in question_endings
            ):
                continue

            # ----------------------------------------------------
            # 시간 간격 확인
            # ----------------------------------------------------

            current_end = int(
                current.get(
                    "end_ms",
                    0,
                )
            )

            word_start = int(
                first_next_word.get(
                    "start_ms",
                    0,
                )
            )

            gap = word_start - current_end

            # 1.5초보다 멀리 떨어져 있으면
            # 같은 발화라고 보기 어려움
            if gap < 0 or gap > 1500:
                continue

            # ----------------------------------------------------
            # 다음 segment 첫 단어를 앞 segment로 이동
            # ----------------------------------------------------

            moved_word = next_words.pop(0)

            # word에 기록된 Deepgram speaker도
            # 이동된 화자로 수정
            moved_word["speaker"] = current.get(
                "speaker",
                "UNKNOWN",
            )

            current_words.append(
                moved_word
            )

            current["words"] = (
                current_words
            )

            next_seg["words"] = (
                next_words
            )

            # ----------------------------------------------------
            # 앞 segment text 수정
            # ----------------------------------------------------

            current_text = str(
                current.get(
                    "text",
                    "",
                )
            ).strip()

            current["text"] = (
                f"{current_text} "
                f"{first_word_text}"
            ).strip()

            # 앞 segment 종료시간도 이동된 단어까지 연장
            current["end_ms"] = (
                moved_word.get(
                    "end_ms",
                    current_end,
                )
            )

            # ----------------------------------------------------
            # 다음 segment text에서 이동한 단어 삭제
            # ----------------------------------------------------

            next_text = str(
                next_seg.get(
                    "text",
                    "",
                )
            ).strip()

            if next_text.startswith(
                first_word_text
            ):

                next_text = next_text[
                    len(first_word_text):
                ].strip()

            next_seg["text"] = (
                next_text
            )

            # 다음 segment의 시작시간 수정
            if next_words:

                next_seg["start_ms"] = (
                    next_words[0].get(
                        "start_ms",
                        next_seg.get(
                            "start_ms",
                            0,
                        ),
                    )
                )

        # --------------------------------------------------------
        # 혹시 text가 완전히 비어버린 segment가 있으면 제거
        # --------------------------------------------------------

        cleaned_segments = []

        for seg in segments:

            if str(
                seg.get(
                    "text",
                    "",
                )
            ).strip():

                cleaned_segments.append(
                    seg
                )

        return cleaned_segments

    # ============================================================
    # 4. 최종 segment_id / confidence 재계산
    # ============================================================

    def finalize_segments(
        self,
        segments: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:

        final_segments = []

        for idx, seg in enumerate(
            segments,
            start=1,
        ):

            conf = float(
                seg.get(
                    "confidence",
                    0.0,
                )
            )

            final_segments.append(
                {
                    "segment_id": (
                        f"seg_{idx:03d}"
                    ),
                    "speaker": seg.get(
                        "speaker",
                        "UNKNOWN",
                    ),
                    "start_ms": seg.get(
                        "start_ms",
                        0,
                    ),
                    "end_ms": seg.get(
                        "end_ms",
                        0,
                    ),
                    "text": seg.get(
                        "text",
                        "",
                    ),
                    "confidence": conf,
                    "is_low_confidence": (
                        conf < self.threshold
                    ),
                    "words": seg.get(
                        "words",
                        [],
                    ),
                }
            )

        return final_segments

    # ============================================================
    # 5. 전체 후처리 실행
    # ============================================================

    def process(
        self,
        stt_result: Dict[str, Any],
    ) -> Dict[str, Any]:

        raw_segments = stt_result.get(
            "segments",
            [],
        )

        # STEP 1
        # 동일 화자 연속 발화 병합
        merged_segments = (
            self.merge_same_speaker_segments(
                raw_segments
            )
        )

        # STEP 2
        # 잘못 잘린 화자 경계 보정
        corrected_segments = (
            self.fix_speaker_boundary(
                merged_segments
            )
        )

        # STEP 3
        # ID / confidence 최종 정리
        final_segments = (
            self.finalize_segments(
                corrected_segments
            )
        )

        return {
            "schema_version": stt_result.get(
                "schema_version",
                "1.0",
            ),
            "segments": final_segments,

            # Selective Whisper fallback 정보 보존
            "fallback_used": stt_result.get(
                "fallback_used",
                False,
            ),

            "fallback_evidence": stt_result.get(
                "fallback_evidence",
                [],
            ),
        }