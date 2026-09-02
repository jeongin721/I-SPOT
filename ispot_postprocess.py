"""I-SPOT STT Post-processing Module.

STT 결과(Contract v1.0)를 전달받아 다음 작업을 수행한다:
1. 연속된 동일 화자의 세그먼트를 문맥 단위로 재병합 (타임스탬프 재계산)
2. 신뢰도(Confidence) 재검증 및 낮은 신뢰도 구간 플래그 부여
3. 텍스트 불필요 공백 정제
"""

from typing import Any, Dict, List, Optional


class STTPostProcessor:
    def __init__(self, low_confidence_threshold: float = 0.70, merge_silence_gap_ms: int = 1500):
        self.threshold = low_confidence_threshold
        self.max_gap_ms = merge_silence_gap_ms  # 동일 화자 간 병합 허용 최대 무음 시간

    def clean_text(self, text: str) -> str:
        """텍스트 공백 정제"""
        if not text:
            return ""
        return " ".join(text.split())

    def merge_same_speaker_segments(self, segments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """동일 화자의 연속 발화 병합 로직"""
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
        raw_segments = stt_result.get("segments", [])
        processed_segments = self.merge_same_speaker_segments(raw_segments)

        return {
            "schema_version": stt_result.get("schema_version", "1.0"),
            "segments": processed_segments,
        }