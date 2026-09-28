# AI-HUB 아동 상담 원본 JSON을 I-SPOT 공통 Transcript 형식으로 변환한다.
# Q/A 화자 구분, 시간(ms) 변환, segment_id 생성을 담당한다.

from typing import Dict, List

from ai.schemas.aihub_consultation import AIHubConsultation
from ai.schemas.analysis import Transcript, TranscriptSegment


SPEAKER_MAP: Dict[str, str] = {
    "Q": "COUNSELOR",
    "A": "CHILD",
}


def timestamp_to_ms(value: str) -> int:
    """
    AI-HUB timestamp 예:
    00:03.680 -> 3680 ms
    01:02.500 -> 62500 ms
    """
    minute_second, millisecond = value.split(".")
    minute, second = minute_second.split(":")

    return (
        int(minute) * 60_000
        + int(second) * 1_000
        + int(millisecond.ljust(3, "0")[:3])
    )


def aihub_to_transcript(raw: dict) -> Transcript:
    """
    AI-HUB 상담 JSON을
    I-SPOT Transcript Contract로 변환한다.

    Q -> COUNSELOR
    A -> CHILD
    """
    source = AIHubConsultation(**raw)

    segments: List[TranscriptSegment] = []
    segment_index = 1

    for section in source.list:
        for item in section.list:
            for audio in item.audio:
                text = audio.text.strip()

                if not text:
                    continue

                speaker = SPEAKER_MAP.get(
                    audio.type,
                    "UNKNOWN",
                )

                segment = TranscriptSegment(
                    segment_id=f"seg_{segment_index:03d}",
                    speaker=speaker,
                    start_ms=timestamp_to_ms(audio.start),
                    end_ms=timestamp_to_ms(audio.end),
                    text=text,

                    # AI-HUB 원본 JSON에는
                    # STT confidence가 없으므로 임시값 사용
                    confidence=1.0,
                )

                segments.append(segment)
                segment_index += 1

    return Transcript(
        schema_version="1.0",
        segments=segments,
    )