import json
from pathlib import Path
import sys

# 프로젝트 루트를 import 경로에 추가
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from speaker_role_runtime import RuntimeSpeakerRoleMapper


TARGET_FILES = [
    "1786",
    "5113",
    "2315",
    "5194",
]

TEST_SAMPLE_DIR = PROJECT_ROOT / "test_sample"


def main():
    mapper = RuntimeSpeakerRoleMapper()

    print("=" * 80)
    print("UNRESOLVED SPEAKER ANALYSIS")
    print("=" * 80)

    for file_id in TARGET_FILES:
        stt_path = TEST_SAMPLE_DIR / f"{file_id}_stt.json"

        print()
        print("=" * 80)
        print(f"FILE: {file_id}")
        print("=" * 80)

        if not stt_path.exists():
            print(f"[ERROR] 파일 없음: {stt_path}")
            continue

        with open(
            stt_path,
            "r",
            encoding="utf-8",
        ) as f:
            stt_data = json.load(f)

        segments = stt_data.get("segments", [])

        print(f"STT segments: {len(segments)}")
        print()

        role_mapping = mapper.map_roles(segments)

        if not role_mapping:
            print("[WARNING] role_mapping 결과 없음")
            continue

        for speaker, info in role_mapping.items():

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

        child_speakers = [
            speaker
            for speaker, info in role_mapping.items()
            if info.get("role") == "CHILD"
        ]

        print("-" * 80)

        if len(child_speakers) == 1:
            print(
                f"RESULT: CHILD = "
                f"{child_speakers[0]}"
            )
        else:
            print(
                "RESULT: UNRESOLVED "
                f"(CHILD count = {len(child_speakers)})"
            )


if __name__ == "__main__":
    main()