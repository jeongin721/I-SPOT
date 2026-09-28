import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from child_analysis_text import ChildAnalysisTextBuilder


def main():
    stt_path = PROJECT_ROOT / "test_sample" / "1354_stt_latest.json"

    with open(
        stt_path,
        "r",
        encoding="utf-8",
    ) as f:
        data = json.load(f)

    stt_data = data.get("stt_data", {})

    builder = ChildAnalysisTextBuilder()
    result = builder.build(stt_data)

    print()
    print("=" * 80)
    print("1354 Child Analysis Text Test")
    print("=" * 80)

    print("status:", result.get("status"))
    print("child_speaker:", result.get("child_speaker"))

    print()
    print("role_mapping:")
    for speaker, info in result.get("role_mapping", {}).items():
        print(
            speaker,
            "→",
            info.get("role"),
            "| question_ratio=",
            round(info.get("question_ratio", 0), 3),
            "| confidence=",
            info.get("confidence"),
        )

    print()
    print("=" * 80)
    print("Timeline items")
    print("=" * 80)

    for item in result.get("items", []):
        print(
            item.get("start_ms"),
            "|",
            item.get("source"),
            "|",
            item.get("text"),
        )

    print()
    print("=" * 80)
    print("child_analysis_text")
    print("=" * 80)

    print(
        result.get(
            "child_analysis_text",
            "",
        )
    )


if __name__ == "__main__":
    main()