import json
from ispot_postprocess import STTPostProcessor

# 파이프라인 흐름 예시 테스트
mock_stt_output = {
    "schema_version": "1.0",
    "segments": [
        {"segment_id": "seg_001", "speaker": "SPEAKER_0", "start_ms": 399, "end_ms": 3060, "text": "같은 경우는 저희가 그러니까 종사자분들", "confidence": 0.72},
        {"segment_id": "seg_002", "speaker": "SPEAKER_0", "start_ms": 3520, "end_ms": 8260, "text": "관계 법령 근거해서 이제 범죄 전력을 의뢰하는 게 있거든요", "confidence": 0.86},
        {"segment_id": "seg_003", "speaker": "SPEAKER_1", "start_ms": 8960, "end_ms": 11620, "text": "네 확인했습니다.", "confidence": 0.55},
    ]
}

processor = STTPostProcessor(low_confidence_threshold=0.70)
processed_result = processor.process(mock_stt_output)

print("[+] 후처리 결과 (동일 화자 병합 및 low_confidence 산출):")
print(json.dumps(processed_result, indent=2, ensure_ascii=False))