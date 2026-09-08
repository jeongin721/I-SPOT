import requests
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from experiments.test_single_speaker_recovery_1786 import (
    recover_chunks,
)


API_URL = "http://127.0.0.1:8000/api/v1/analyze"

AUDIO_PATH = (
    PROJECT_ROOT
    / "test_sample"
    / "1786.mp3"
)


def main():

    print("=" * 100)
    print("1786 FULL SINGLE-SPEAKER RECOVERY TEST")
    print("=" * 100)

    print()
    print("API 호출 중...")

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

    print(
        f"HTTP: {response.status_code}"
    )

    response.raise_for_status()

    data = response.json()

    segments = (
        data.get("stt_data", {})
        .get("segments", [])
    )

    print(
        f"전체 Deepgram segment: "
        f"{len(segments)}"
    )

    print()

    speakers = sorted(
        {
            segment.get("speaker")
            for segment in segments
            if segment.get("speaker")
        }
    )

    print(
        f"발견된 speaker: {speakers}"
    )

    print()

    child_candidates = []

    counselor_candidates = []

    for index, segment in enumerate(
        segments,
        start=1,
    ):

        text = (
            segment.get("text")
            or ""
        ).strip()

        if not text:
            continue

        recovered = recover_chunks(text)

        print("=" * 100)

        print(
            f"[SEGMENT {index:03d}] "
            f"{text}"
        )

        for item in recovered:

            role = item["role"]
            recovered_text = item["text"]

            print(
                f"    {role:16} | "
                f"{recovered_text}"
            )

            if role == "CHILD_CANDIDATE":

                child_candidates.append(
                    recovered_text
                )

            elif role == "COUNSELOR":

                counselor_candidates.append(
                    recovered_text
                )

    child_text = " ".join(
        child_candidates
    )

    print()
    print("=" * 100)
    print("RESULT")
    print("=" * 100)

    print(
        f"원본 segment 수      : "
        f"{len(segments)}"
    )

    print(
        f"COUNSELOR 후보 수    : "
        f"{len(counselor_candidates)}"
    )

    print(
        f"CHILD 후보 수        : "
        f"{len(child_candidates)}"
    )

    print(
        f"CHILD text 글자 수   : "
        f"{len(child_text)}"
    )

    print()
    print("=" * 100)
    print("FINAL CHILD CANDIDATE TEXT")
    print("=" * 100)

    print(child_text)


if __name__ == "__main__":
    main()