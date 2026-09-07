import json
from pathlib import Path

from dotenv import load_dotenv

from ispot_stt import DeepgramSTTProvider


BASE_DIR = Path(__file__).resolve().parent

AUDIO_PATH = (
    BASE_DIR
    / "test_sample"
    / "1354.mp3"
)

OUTPUT_PATH = (
    BASE_DIR
    / "test_sample"
    / "1354_raw_deepgram.json"
)

load_dotenv()


def main():

    print("=" * 80)
    print("1354 Deepgram RAW STT 저장")
    print("=" * 80)

    provider = DeepgramSTTProvider()

    raw_result = provider.transcribe(
        str(AUDIO_PATH)
    )

    print(
        "반환 타입:",
        type(raw_result)
    )

    with open(
        OUTPUT_PATH,
        "w",
        encoding="utf-8",
    ) as f:
        json.dump(
            raw_result,
            f,
            ensure_ascii=False,
            indent=2,
            default=str,
        )

    print()
    print(
        "저장 완료:",
        OUTPUT_PATH
    )


if __name__ == "__main__":
    main()