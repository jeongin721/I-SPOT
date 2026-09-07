import json
import subprocess
import tempfile
from pathlib import Path

from ispot_stt import (
    SelectiveFallbackDetector,
    WhisperLargeV3FallbackProvider,
)


AUDIO_PATH = Path("test_sample/1354.mp3")
STT_PATH = Path("test_sample/1354_stt.json")

# gap 자체만 자르지 않고 앞뒤 문맥도 Whisper에 제공
PRE_MARGIN_MS = 3000
POST_MARGIN_MS = 1000


# --------------------------------------------------
# 1. 기존 Deepgram 결과 읽기
# --------------------------------------------------

with open(
    STT_PATH,
    "r",
    encoding="utf-8",
) as f:
    data = json.load(f)

segments = data["stt_data"]["segments"]


# --------------------------------------------------
# 2. fallback 후보 자동 탐지
# --------------------------------------------------

detector = SelectiveFallbackDetector()

candidates = detector.detect(segments)

print("=" * 70)
print("Selective Whisper Fallback Test")
print("=" * 70)

print("fallback 후보:", len(candidates))


if not candidates:
    print("재전사가 필요한 구간이 없습니다.")
    raise SystemExit


# --------------------------------------------------
# 3. Whisper large-v3 준비
# --------------------------------------------------

whisper_provider = WhisperLargeV3FallbackProvider()


# --------------------------------------------------
# 4. 탐지된 구간만 자동 재전사
# --------------------------------------------------

for index, candidate in enumerate(
    candidates,
    start=1,
):

    gap_start = candidate["gap_start_ms"]
    gap_end = candidate["gap_end_ms"]

    # 앞뒤 문맥 포함
    clip_start_ms = max(
        0,
        gap_start - PRE_MARGIN_MS,
    )

    clip_end_ms = (
        gap_end + POST_MARGIN_MS
    )

    duration_ms = (
        clip_end_ms - clip_start_ms
    )

    print()
    print("-" * 70)
    print(f"[Fallback {index}]")
    print(
        "critical gap:",
        gap_start,
        "→",
        gap_end,
    )

    print(
        "Whisper 입력:",
        clip_start_ms,
        "→",
        clip_end_ms,
    )

    print(
        "길이:",
        round(duration_ms / 1000, 3),
        "초",
    )

    print(
        "Deepgram 직전:",
        candidate["prev_text"],
    )

    print(
        "Deepgram 다음:",
        candidate["next_text"],
    )

    # 임시 wav 생성
    with tempfile.NamedTemporaryFile(
        suffix=".wav",
        delete=False,
    ) as tmp:

        clip_path = Path(tmp.name)

    try:

        subprocess.run(
            [
                "ffmpeg",
                "-y",

                "-ss",
                str(clip_start_ms / 1000),

                "-i",
                str(AUDIO_PATH),

                "-t",
                str(duration_ms / 1000),

                "-ac",
                "1",

                "-ar",
                "16000",

                str(clip_path),
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        print()
        print(
            "[Fallback] Whisper large-v3 재전사 중..."
        )

        result = whisper_provider.transcribe(
            str(clip_path)
        )

        print()
        print(
            "Whisper 복원 결과:"
        )

        print(
            result.get("text", "")
        )

    finally:

        if clip_path.exists():
            clip_path.unlink()