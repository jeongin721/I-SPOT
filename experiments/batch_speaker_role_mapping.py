import csv
import json
from pathlib import Path

from evaluate_diarization import load_ground_truth
from speaker_role_mapping import map_speakers_to_roles


TEST_DIR = Path("test_sample")
OUTPUT_CSV = Path("speaker_role_mapping_results.csv")


def load_stt_segments(stt_json_path: Path):
    with open(
        stt_json_path,
        "r",
        encoding="utf-8",
    ) as f:
        data = json.load(f)

    return (
        data
        .get("stt_data", {})
        .get("segments", [])
    )


def main():

    rows = []

    gt_files = sorted(
        TEST_DIR.glob("*.json")
    )

    # *_stt.json은 GT가 아니므로 제외
    gt_files = [
        path
        for path in gt_files
        if not path.name.endswith("_stt.json")
    ]

    print()
    print("=" * 70)
    print("Speaker Role Mapping Batch")
    print("=" * 70)

    for gt_path in gt_files:

        file_id = gt_path.stem

        stt_path = (
            TEST_DIR
            / f"{file_id}_stt.json"
        )

        if not stt_path.exists():
            continue

        gt_segments = load_ground_truth(
            gt_path
        )

        stt_segments = load_stt_segments(
            stt_path
        )

        mapping = map_speakers_to_roles(
            gt_segments,
            stt_segments,
        )

        print()
        print(f"[{file_id}]")

        for speaker, info in sorted(
            mapping.items()
        ):

            print(
                f"{speaker} → "
                f"{info['role']} "
                f"(confidence={info['confidence']:.4f})"
            )

            rows.append(
                {
                    "file": file_id,
                    "speaker": speaker,
                    "role": info["role"],
                    "q_overlap_ms": info["q_overlap_ms"],
                    "a_overlap_ms": info["a_overlap_ms"],
                    "confidence": info["confidence"],
                }
            )

    if not rows:

        print(
            "❌ 매핑 결과가 없습니다."
        )
        return

    fieldnames = [
        "file",
        "speaker",
        "role",
        "q_overlap_ms",
        "a_overlap_ms",
        "confidence",
    ]

    with open(
        OUTPUT_CSV,
        "w",
        newline="",
        encoding="utf-8-sig",
    ) as f:

        writer = csv.DictWriter(
            f,
            fieldnames=fieldnames,
        )

        writer.writeheader()
        writer.writerows(rows)

    print()
    print("=" * 70)
    print("배치 매핑 완료")
    print("=" * 70)

    print(
        f"총 Row 수 : {len(rows)}"
    )

    print(
        f"CSV 저장  : {OUTPUT_CSV}"
    )

    print("=" * 70)


if __name__ == "__main__":
    main()