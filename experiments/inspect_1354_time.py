import json
from pathlib import Path

STT_PATH = Path("test_sample/1354_stt.json")

TARGET_START = 275_543
TARGET_END = 284_025
MARGIN = 5_000

with open(STT_PATH, "r", encoding="utf-8") as f:
    data = json.load(f)

segments = data["stt_data"]["segments"]

print("=" * 80)
print("1354 핵심 발화 시간대 STT 확인")
print(f"GT 핵심 구간: {TARGET_START} ~ {TARGET_END} ms")
print("=" * 80)

for seg in segments:
    start = seg.get("start_ms", 0)
    end = seg.get("end_ms", 0)

    # 핵심 구간 전후 5초까지 표시
    if end >= TARGET_START - MARGIN and start <= TARGET_END + MARGIN:
        print()
        print("ID      :", seg.get("id"))
        print("Speaker :", seg.get("speaker"))
        print("Time    :", start, "~", end)
        print("Text    :", seg.get("text"))

        words = seg.get("words", [])

        if words:
            print("Words:")
            for word in words:
                print(
                    f"  {word.get('start_ms')}~{word.get('end_ms')} "
                    f"{word.get('speaker')} "
                    f"{word.get('word')}"
                )