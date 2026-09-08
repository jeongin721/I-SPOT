import requests
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from experiments.test_single_speaker_recovery_1786 import (
    recover_chunks,
)


API_URL = "http://127.0.0.1:8000/api/v1/analyze"

TARGET_FILES = [
    "1786",
    "5113",
    "2315",
    "5194",
]


def analyze_file(file_id: str):

    audio_path = (
        PROJECT_ROOT
        / "test_sample"
        / f"{file_id}.mp3"
    )

    print()
    print("=" * 100)
    print(f"FILE: {file_id}")
    print("=" * 100)

    with open(audio_path, "rb") as f:

        response = requests.post(
            API_URL,
            files={
                "file": (
                    f"{file_id}.mp3",
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

    speakers = sorted(
        {
            segment.get("speaker")
            for segment in segments
            if segment.get("speaker")
        }
    )

    print(f"Deepgram speakers : {speakers}")
    print(f"원본 segment 수   : {len(segments)}")

    # 이번 호출에서는 화자 분리가 정상적으로 됐다면
    # single-speaker recovery 실험 대상에서 제외
    if len(speakers) != 1:

        print()
        print(
            "[SKIP] 이번 Deepgram 호출에서는 "
            "single-speaker 상태가 아님"
        )

        return

    child_candidates = []
    counselor_candidates = []

    for segment in segments:

        text = (
            segment.get("text")
            or ""
        ).strip()

        if not text:
            continue

        recovered = recover_chunks(text)

        for item in recovered:

            role = item["role"]
            recovered_text = item["text"]

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

    print(
        f"COUNSELOR 후보 수 : "
        f"{len(counselor_candidates)}"
    )

    print(
        f"CHILD 후보 수     : "
        f"{len(child_candidates)}"
    )

    print(
        f"CHILD text 글자 수: "
        f"{len(child_text)}"
    )

    print()
    print("-" * 100)
    print("FINAL CHILD CANDIDATE TEXT")
    print("-" * 100)

    print(child_text)


def main():

    print("=" * 100)
    print("SINGLE-SPEAKER RECOVERY CROSS-FILE TEST")
    print("=" * 100)

    for file_id in TARGET_FILES:

        try:

            analyze_file(
                file_id
            )

        except Exception as e:

            print(
                f"[ERROR] {file_id}: {e}"
            )


if __name__ == "__main__":
    main()