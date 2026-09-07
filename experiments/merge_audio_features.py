import csv
from pathlib import Path


# ============================================================
# 1. 파일 경로
# ============================================================

AUDIO_FEATURES_CSV = Path(
    "audio_features_results.csv"
)

ROLE_MAPPING_CSV = Path(
    "speaker_role_mapping_results.csv"
)

OUTPUT_CSV = Path(
    "audio_features_with_roles.csv"
)


# ============================================================
# 2. CSV 읽기
# ============================================================

def read_csv(path):
    with open(
        path,
        "r",
        encoding="utf-8-sig",
    ) as f:
        return list(
            csv.DictReader(f)
        )


# ============================================================
# 3. Role Mapping Dictionary 생성
# ============================================================

def build_role_mapping(mapping_rows):
    """
    (file, speaker)를 key로 사용한다.

    예:
        ("0002", "SPEAKER_0")
            →
        {
            "role": "Q",
            "confidence": "0.9536"
        }
    """

    mapping = {}

    for row in mapping_rows:

        key = (
            row["file"],
            row["speaker"],
        )

        mapping[key] = {
            "role":
                row["role"],

            "mapping_confidence":
                row["confidence"],

            "q_overlap_ms":
                row["q_overlap_ms"],

            "a_overlap_ms":
                row["a_overlap_ms"],
        }

    return mapping


# ============================================================
# 4. Audio Feature + Role Mapping 결합
# ============================================================

def merge_features(
    audio_rows,
    role_mapping,
):

    merged_rows = []

    missing_count = 0

    for audio_row in audio_rows:

        key = (
            audio_row["file"],
            audio_row["speaker"],
        )

        role_info = role_mapping.get(
            key
        )

        # 매핑을 찾지 못한 경우
        if role_info is None:

            missing_count += 1

            role_info = {
                "role": "UNKNOWN",
                "mapping_confidence": "",
                "q_overlap_ms": "",
                "a_overlap_ms": "",
            }

        # 먼저 식별 정보
        merged_row = {
            "file":
                audio_row["file"],

            "speaker":
                audio_row["speaker"],

            "role":
                role_info["role"],

            "mapping_confidence":
                role_info[
                    "mapping_confidence"
                ],

            "q_overlap_ms":
                role_info["q_overlap_ms"],

            "a_overlap_ms":
                role_info["a_overlap_ms"],
        }

        # 기존 Audio Feature 추가
        for key_name, value in audio_row.items():

            if key_name in {
                "file",
                "speaker",
            }:
                continue

            merged_row[key_name] = value

        merged_rows.append(
            merged_row
        )

    return (
        merged_rows,
        missing_count,
    )


# ============================================================
# 5. CSV 저장
# ============================================================

def save_csv(rows):

    if not rows:
        return

    fieldnames = list(
        rows[0].keys()
    )

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

        writer.writerows(
            rows
        )


# ============================================================
# 6. Main
# ============================================================

def main():

    print()
    print("=" * 70)
    print("Audio Feature + Speaker Role Merge")
    print("=" * 70)

    # 파일 존재 확인
    if not AUDIO_FEATURES_CSV.exists():

        print(
            f"❌ 파일 없음: "
            f"{AUDIO_FEATURES_CSV}"
        )

        return

    if not ROLE_MAPPING_CSV.exists():

        print(
            f"❌ 파일 없음: "
            f"{ROLE_MAPPING_CSV}"
        )

        return

    # CSV 로드
    audio_rows = read_csv(
        AUDIO_FEATURES_CSV
    )

    mapping_rows = read_csv(
        ROLE_MAPPING_CSV
    )

    print(
        f"Audio Feature Row : "
        f"{len(audio_rows)}"
    )

    print(
        f"Role Mapping Row  : "
        f"{len(mapping_rows)}"
    )

    # Role mapping dictionary
    role_mapping = build_role_mapping(
        mapping_rows
    )

    # 결합
    merged_rows, missing_count = (
        merge_features(
            audio_rows,
            role_mapping,
        )
    )

    # 저장
    save_csv(
        merged_rows
    )

    # Role별 개수 확인
    role_counts = {}

    for row in merged_rows:

        role = row["role"]

        role_counts[role] = (
            role_counts.get(
                role,
                0,
            )
            + 1
        )

    print()
    print("-" * 70)

    print(
        f"결합 완료 Row    : "
        f"{len(merged_rows)}"
    )

    print(
        f"매핑 누락 Row    : "
        f"{missing_count}"
    )

    print()

    print("Role 분포")

    for role, count in sorted(
        role_counts.items()
    ):
        print(
            f"  {role:<8}: {count}"
        )

    print()

    print(
        f"CSV 저장 → "
        f"{OUTPUT_CSV}"
    )

    print("=" * 70)


if __name__ == "__main__":
    main()