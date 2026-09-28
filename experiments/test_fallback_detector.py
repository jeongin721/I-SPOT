import json

from stt.ispot_stt import SelectiveFallbackDetector


with open(
    "test_sample/1354_stt.json",
    "r",
    encoding="utf-8",
) as f:
    data = json.load(f)


segments = data["stt_data"]["segments"]

detector = SelectiveFallbackDetector()

candidates = detector.detect(segments)


print("=" * 70)
print("Selective Fallback Detector v1")
print("=" * 70)

print("탐지 개수:", len(candidates))

for candidate in candidates:
    print()
    print("gap:", candidate["gap_start_ms"], "→", candidate["gap_end_ms"])
    print(
        "gap_sec:",
        candidate["gap_ms"] / 1000,
    )
    print(
        "speaker:",
        candidate["prev_speaker"],
        "→",
        candidate["next_speaker"],
    )
    print(
        "직전:",
        candidate["prev_text"],
    )
    print(
        "다음:",
        candidate["next_text"],
    )