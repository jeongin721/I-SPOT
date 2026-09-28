import requests
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

API_URL = "http://127.0.0.1:8000/api/v1/analyze"
AUDIO_PATH = PROJECT_ROOT / "test_sample" / "1786.mp3"


def main():
    print("1786 API 호출 중...")

    with open(AUDIO_PATH, "rb") as f:
        response = requests.post(
            API_URL,
            files={
                "file": (
                    "1786.mp3",
                    f,
                    "audio/mpeg",
                )
            },
            timeout=1800,
        )

    print(f"HTTP: {response.status_code}")

    response.raise_for_status()

    data = response.json()

    segments = (
        data.get("stt_data", {})
        .get("segments", [])
    )

    print()
    print("=" * 100)
    print(f"전체 segment 수: {len(segments)}")
    print("앞 30개 segment")
    print("=" * 100)

    for i, segment in enumerate(segments[:30], start=1):

        speaker = segment.get("speaker")
        text = segment.get("text", "")

        print(
            f"{i:02d} | "
            f"{speaker} | "
            f"{text}"
        )


if __name__ == "__main__":
    main()