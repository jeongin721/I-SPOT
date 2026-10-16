import sys

from transcript_builder import TranscriptBuilder

# Windows 한국어 콘솔(cp949)에는 이모지가 없어, 아래 성공 메시지의 ✅ 에서
# UnicodeEncodeError 가 난다. 검증은 모두 통과한 뒤라 결과는 정상인데
# traceback 만 보여 실패로 오해하기 쉬우므로 출력 인코딩을 고정한다.
try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass


ALLOWED_ROLES = {
    "COUNSELOR",
    "CHILD",
    "GUARDIAN",
    "OTHER",
    "UNKNOWN",
}

REQUIRED_FIELDS = {
    "segment_id",
    "speaker",
    "start_ms",
    "end_ms",
    "text",
    "confidence",
}


def main():
    # 실제 postprocess 결과와 같은 형태의 테스트용 STT 데이터
    stt_data = {
        "schema_version": "1.0",
        "segments": [
            {
                "segment_id": "seg_001",
                "speaker": "SPEAKER_0",
                "start_ms": 1000,
                "end_ms": 3000,
                "text": "오늘 기분은 어때?",
                "confidence": 0.98,
                "is_low_confidence": False,
                "words": [],
            },
            {
                "segment_id": "seg_002",
                "speaker": "SPEAKER_1",
                "start_ms": 3200,
                "end_ms": 5000,
                "text": "그냥 그래요.",
                "confidence": 0.96,
                "is_low_confidence": False,
                "words": [],
            },
        ],
    }

    # 실제 RuntimeSpeakerRoleMapper 결과 형태
    role_mapping = {
        "SPEAKER_0": {
            "role": "COUNSELOR",
            "confidence": 0.95,
        },
        "SPEAKER_1": {
            "role": "CHILD",
            "confidence": 0.92,
        },
    }

    builder = TranscriptBuilder()

    transcript = builder.build(
        stt_data=stt_data,
        role_mapping=role_mapping,
    )

    assert transcript["schema_version"] == "1.0"

    segments = transcript["segments"]

    assert len(segments) == 2

    for index, segment in enumerate(
        segments,
        start=1,
    ):
        # 필수 필드만 존재하는지
        assert set(segment.keys()) == REQUIRED_FIELDS, (
            f"{index}번째 segment 필드 불일치: "
            f"{set(segment.keys())}"
        )

        # 허용된 역할인지
        assert segment["speaker"] in ALLOWED_ROLES

        # SPEAKER_n이 남아 있지 않은지
        assert not segment["speaker"].startswith(
            "SPEAKER_"
        )

        # 시간값 검사
        assert segment["start_ms"] >= 0
        assert segment["end_ms"] >= segment["start_ms"]

        # confidence 검사
        assert 0.0 <= segment["confidence"] <= 1.0

        # ID 검사
        assert segment["segment_id"]

    assert segments[0]["speaker"] == "COUNSELOR"
    assert segments[1]["speaker"] == "CHILD"

    print("✅ TranscriptBuilder validation success")
    print("schema_version:", transcript["schema_version"])
    print("segment_count:", len(segments))
    print(
        "speakers:",
        sorted(
            set(
                segment["speaker"]
                for segment in segments
            )
        ),
    )

    print("\nconverted transcript:")

    for segment in segments:
        print(
            segment["segment_id"],
            "|",
            segment["speaker"],
            "|",
            segment["text"],
        )


if __name__ == "__main__":
    main()