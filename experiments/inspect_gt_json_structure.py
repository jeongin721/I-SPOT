import json
from pathlib import Path
from pprint import pprint


PROJECT_ROOT = Path(__file__).resolve().parent.parent

JSON_PATH = (
    PROJECT_ROOT
    / "test_sample"
    / "1786.json"
)


def find_first_audio(obj):
    """
    JSON 전체를 탐색해서
    첫 번째 audio 값을 찾는다.
    """

    if isinstance(obj, dict):

        for key, value in obj.items():

            if key == "audio":
                return value

            result = find_first_audio(value)

            if result is not None:
                return result

    elif isinstance(obj, list):

        for item in obj:

            result = find_first_audio(item)

            if result is not None:
                return result

    return None


def main():

    with open(
        JSON_PATH,
        "r",
        encoding="utf-8",
    ) as f:
        data = json.load(f)

    audio = find_first_audio(data)

    print("=" * 100)
    print("FIRST AUDIO STRUCTURE")
    print("=" * 100)

    print(
        f"type: {type(audio).__name__}"
    )

    if isinstance(audio, list):

        print(
            f"length: {len(audio)}"
        )

        print()

        for index, item in enumerate(
            audio[:5]
        ):

            print("-" * 100)
            print(f"AUDIO ITEM [{index}]")
            print("-" * 100)

            pprint(
                item,
                width=120,
                sort_dicts=False,
            )

    else:

        pprint(
            audio,
            width=120,
            sort_dicts=False,
        )


if __name__ == "__main__":
    main()