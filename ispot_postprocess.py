"""I-SPOT STT Post-processing Module.

STT 결과(Contract v1.0)를 전달받아 다음 작업을 수행한다:
1. 연속된 동일 화자의 세그먼트를 문맥 단위로 재병합 (타임스탬프 재계산)
2. 신뢰도(Confidence) 재검증 및 낮은 신뢰도 구간 플래그 부여
3. 텍스트 불필요 공백 정제
"""

from typing import Any, Dict, List, Optional

# 공부용 설명:
# 이 파일은 STT 결과를 '다음 단계에서 다루기 좋게 정리하는 후처리 모듈'이다.
#
# STT는 종종 다음과 같은 문제가 있다:
# - 같은 화자의 짧은 발화가 여러 segment로 나뉜다.
# - 공백, 문장 부호, 신뢰도 값이 불안정하다.
# - 시간 타임스탬프가 segment 단위로 흩어져 있다.
#
# 그래서 여기서는 다음 작업을 수행한다:
# 1) 같은 화자의 연속 발화를 병합한다.
# 2) 텍스트 공백을 정리한다.
# 3) 신뢰도 낮은 발화 구간을 표시한다.
#
# 결과적으로 downstream AI 분석 단계가 훨씬 편하게 데이터를 받아볼 수 있다.
class STTPostProcessor:
    def __init__(self, low_confidence_threshold: float = 0.70, merge_silence_gap_ms: int = 1500):
        # 공부용 설명:
        # threshold: 신뢰도가 이 값보다 낮으면 '낮은 신뢰도'라는 표시를 붙인다.
        # max_gap_ms: 같은 화자의 발화를 병합할 때 허용할 최대 시간 간격이다.
        # 예를 들어 1.5초 정도의 짧은 공백이면 같은 문맥으로 묶을 수 있다고 판단한다.
        self.threshold = low_confidence_threshold
        self.max_gap_ms = merge_silence_gap_ms  # 동일 화자 간 병합 허용 최대 무음 시간

    def clean_text(self, text: str) -> str:
        """텍스트 공백 정제"""
        if not text:
            return ""
        return " ".join(text.split())

    def merge_same_speaker_segments(self, segments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """동일 화자의 연속 발화 병합 로직"""
        # 공부용 설명:
        # STT는 말을 끊어 여러 segment로 나누는 경우가 많다.
        # 예를 들어 같은 사람이 한 문장 안에서 짧게 쪼개지면
        # 실제로는 하나의 문장처럼 보여야 한다.
        #
        # 이 메서드는 다음 조건을 보고 병합 여부를 결정한다:
        # - 화자가 동일한가?
        # - 이전 발화 끝과 다음 발화 시작 사이 간격이 너무 큰가?
        # - 같은 문맥으로 묶어도 되는가?
        #
        # 조건이 맞으면 두 발화를 하나로 합쳐서 더 자연스러운 transcript를 만든다.
        if not segments:
            return []

        merged: List[Dict[str, Any]] = []
        current = None

        for seg in segments:
            cleaned_text = self.clean_text(seg.get("text", ""))
            if not cleaned_text:
                continue

            seg_info = {
                "speaker": seg.get("speaker", "UNKNOWN"),
                "start_ms": seg.get("start_ms", 0),
                "end_ms": seg.get("end_ms", 0),
                "text": cleaned_text,
                "confidence": seg.get("confidence", 0.0),
            }

            if current is None:
                current = seg_info
                continue

            # 동일 화자이고, 이전 발화 끝과 다음 발화 시작 사이 간격이 임계값 이내인 경우 병합
            is_same_speaker = current["speaker"] == seg_info["speaker"]
            gap = seg_info["start_ms"] - current["end_ms"]

            if is_same_speaker and gap <= self.max_gap_ms:
                current["end_ms"] = seg_info["end_ms"]
                current["text"] = f"{current['text']} {seg_info['text']}"
                # 신뢰도는 두 세그먼트의 평균치로 계산
                current["confidence"] = round((current["confidence"] + seg_info["confidence"]) / 2, 2)
            else:
                merged.append(current)
                current = seg_info

        if current:
            merged.append(current)

        # ID 재할당 및 신뢰도 플래그 계산
        final_segments = []
        for idx, seg in enumerate(merged, start=1):
            conf = seg["confidence"]
            final_segments.append(
                {
                    "segment_id": f"seg_{idx:03d}",
                    "speaker": seg["speaker"],
                    "start_ms": seg["start_ms"],
                    "end_ms": seg["end_ms"],
                    "text": seg["text"],
                    "confidence": conf,
                    "is_low_confidence": conf < self.threshold,
                }
            )

        return final_segments

    def process(self, stt_result: Dict[str, Any]) -> Dict[str, Any]:
        """후처리 실행 메인 메서드"""
        # 공부용 설명:
        # 실제 사용 시에는 전체 STT JSON 하나를 받아서,
        # 여기서 segments만 뽑아 merge_same_speaker_segments()를 실행한다.
        #
        # 이후 최종 결과는 이렇게 반환된다:
        # {
        #   "schema_version": "1.0",
        #   "segments": [ ... ]
        # }
        #
        # 이 JSON은 이후 분석 단계에서 더 쉽게 사용된다.
        raw_segments = stt_result.get("segments", [])
        processed_segments = self.merge_same_speaker_segments(raw_segments)

        return {
            "schema_version": stt_result.get("schema_version", "1.0"),
            "segments": processed_segments,
        }