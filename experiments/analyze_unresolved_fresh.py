import requests
from pathlib import Path
import json
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TEST_SAMPLE_DIR = PROJECT_ROOT / "test_sample"

API_URL = "http://127.0.0.1:8000/api/v1/analyze"

TARGET_FILES = [
    "1786",
    "5113",
    "2315",
    "5194",
]


def main():
    all_results = []

    for file_id in TARGET_FILES:
        mp3_path = TEST_SAMPLE_DIR / f"{file_id}.mp3"

        print()
        print("=" * 80)
        print(f"FILE: {file_id}")
        print("=" * 80)

        if not mp3_path.exists():
            print(f"[ERROR] MP3 없음: {mp3_path}")
            continue

        with open(mp3_path, "rb") as f:
            files = {
                "file": (
                    mp3_path.name,
                    f,
                    "audio/mpeg",
                )
            }

            response = requests.post(
                API_URL,
                files=files,
                timeout=1800,
            )

        print(f"HTTP: {response.status_code}")

        if response.status_code != 200:
            print(response.text)
            continue

        data = response.json()

        result = {
            "file": file_id,
            "child_status": data.get(
                "child_analysis_status"
            ),
            "child_speaker": data.get(
                "child_speaker"
            ),
            "speaker_roles": data.get(
                "speaker_roles",
                {},
            ),
            "fallback_used": (
                data.get("stt_data", {})
                .get("fallback_used", False)
            ),
        }

        all_results.append(result)

        print(
            f"child_status : "
            f"{result['child_status']}"
        )

        print(
            f"child_speaker: "
            f"{result['child_speaker']}"
        )

        print(
            f"fallback_used: "
            f"{result['fallback_used']}"
        )

        print()

        speaker_roles = result["speaker_roles"]

        if not speaker_roles:
            print("[WARNING] speaker_roles 없음")
            continue

        for speaker, info in speaker_roles.items():

            print(f"[{speaker}]")

            print(
                f"  role               : "
                f"{info.get('role')}"
            )

            print(
                f"  confidence         : "
                f"{info.get('confidence')}"
            )

            print(
                f"  utterance_count    : "
                f"{info.get('utterance_count')}"
            )

            print(
                f"  question_count     : "
                f"{info.get('question_count')}"
            )

            print(
                f"  question_ratio     : "
                f"{info.get('question_ratio')}"
            )

            print(
                f"  short_answer_ratio : "
                f"{info.get('short_answer_ratio')}"
            )

            print(
                f"  avg_chars          : "
                f"{info.get('avg_chars')}"
            )

            print()

    output_path = (
        PROJECT_ROOT
        / "results"
        / "unresolved_fresh_analysis.json"
    )

    output_path.parent.mkdir(
        exist_ok=True
    )

    with open(
        output_path,
        "w",
        encoding="utf-8",
    ) as f:
        json.dump(
            all_results,
            f,
            ensure_ascii=False,
            indent=2,
        )

    print()
    print("=" * 80)
    print(f"SAVED: {output_path}")
    print("=" * 80)


if __name__ == "__main__":
    main()