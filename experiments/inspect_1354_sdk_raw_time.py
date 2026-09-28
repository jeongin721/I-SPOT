import json
from pathlib import Path

RAW_PATH = Path(
    "test_sample/1354_deepgram_sdk_raw.json"
)

TARGET_START = 275.543
TARGET_END = 284.025
MARGIN = 5.0


def walk(obj):
    """
    JSON 전체를 재귀 탐색하면서
    start/end가 있는 dict를 찾는다.
    """
    if isinstance(obj, dict):

        start = obj.get("start")
        end = obj.get("end")

        if (
            isinstance(start, (int, float))
            and isinstance(end, (int, float))
        ):
            if (
                end >= TARGET_START - MARGIN
                and start <= TARGET_END + MARGIN
            ):
                yield obj

        for value in obj.values():
            yield from walk(value)

    elif isinstance(obj, list):

        for item in obj:
            yield from walk(item)


with open(
    RAW_PATH,
    "r",
    encoding="utf-8",
) as f:
    data = json.load(f)


print("=" * 80)
print("1354 Deepgram SDK RAW 시간대 확인")
print(
    f"대상 구간: "
    f"{TARGET_START:.3f} ~ {TARGET_END:.3f} sec"
)
print("=" * 80)


matches = list(
    walk(data)
)

print(
    f"시간 겹침 객체 수: {len(matches)}"
)


for index, item in enumerate(
    matches,
    start=1,
):

    print()
    print(
        f"[{index}]"
    )

    print(
        "start   :",
        item.get("start")
    )

    print(
        "end     :",
        item.get("end")
    )

    if "speaker" in item:
        print(
            "speaker :",
            item.get("speaker")
        )

    if "word" in item:
        print(
            "word    :",
            item.get("word")
        )

    if "punctuated_word" in item:
        print(
            "punctuated_word :",
            item.get("punctuated_word")
        )

    if "transcript" in item:
        print(
            "transcript :",
            item.get("transcript")
        )