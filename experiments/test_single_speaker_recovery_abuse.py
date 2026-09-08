import requests
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from experiments.test_single_speaker_recovery_1786 import (
    recover_chunks,
)

from abuse_model.infer_abuse import (
    predict_abuse,
)


API_URL = "http://127.0.0.1:8000/api/v1/analyze"

TARGET_FILES = [
    "1786",
    "5113",
    "2315",
    "5194",
]


def build_recovered_child_text(
    segments: list[dict],
) -> str:

    child_candidates = []

    for segment in segments:

        text = (
            segment.get("text")
            or ""
        ).strip()

        if not text:
            continue

        recovered = recover_chunks(
            text
        )

        for item in recovered:

            if (
                item.get("role")
                == "CHILD_CANDIDATE"
            ):
                child_candidates.append(
                    item["text"]
                )

    return " ".join(
        child_candidates
    ).strip()


def print_prediction(
    prediction: dict,
):

    for label, info in prediction.items():

        if isinstance(info, dict):

            probability = info.get(
                "probability"
            )

            detected = info.get(
                "detected"
            )

            threshold = info.get(
                "threshold"
            )

            print(
                f"{label:8} | "
                f"prob={probability} | "
                f"threshold={threshold} | "
                f"detected={detected}"
            )

        else:

            print(
                f"{label:8} | {info}"
            )


def analyze_file(
    file_id: str,
):

    audio_path = (
        PROJECT_ROOT
        / "test_sample"
        / f"{file_id}.mp3"
    )

    print()
    print("=" * 100)
    print(f"FILE: {file_id}")
    print("=" * 100)

    with open(
        audio_path,
        "rb",
    ) as f:

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

    print(
        f"HTTP: {response.status_code}"
    )

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

    print(
        f"Deepgram speakers: "
        f"{speakers}"
    )

    if len(speakers) != 1:

        print(
            "[SKIP] 이번 호출에서는 "
            "single-speaker가 아님"
        )

        return

    recovered_text = (
        build_recovered_child_text(
            segments
        )
    )

    print(
        f"Recovered text length: "
        f"{len(recovered_text)}"
    )

    if not recovered_text:

        print(
            "[ERROR] 복구된 CHILD text 없음"
        )

        return

    print()
    print(
        "RoBERTa prediction:"
    )
    print("-" * 100)

    prediction = predict_abuse(
        recovered_text
    )

    print_prediction(
        prediction
    )


def main():

    print("=" * 100)
    print(
        "SINGLE-SPEAKER RECOVERY "
        "→ ABUSE CLASSIFIER TEST"
    )
    print("=" * 100)

    for file_id in TARGET_FILES:

        try:

            analyze_file(
                file_id
            )

        except Exception as e:

            print()
            print(
                f"[ERROR] {file_id}: {e}"
            )


if __name__ == "__main__":
    main()