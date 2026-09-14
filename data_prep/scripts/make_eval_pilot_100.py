import csv
import random
from collections import defaultdict
from pathlib import Path


# ============================================================
# 설정
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

GT_CSV = (
    PROJECT_ROOT
    / "data_prep"
    / "evaluation"
    / "ground_truth"
    / "gt_2876.csv"
)

DURATION_CSV = (
    PROJECT_ROOT
    / "data_prep"
    / "evaluation"
    / "ground_truth"
    / "audio_duration_2876.csv"
)

OUTPUT_CSV = (
    PROJECT_ROOT
    / "data_prep"
    / "evaluation"
    / "deepgram"
    / "pilot_100.csv"
)

RANDOM_SEED = 42


# ============================================================
# 목표 개수
# ============================================================

# 실제 데이터 분포를 어느 정도 유지하면서
# 소수 클래스도 충분히 포함되도록 구성
TARGET_COUNTS = {
    "(해당 없음)": 40,
    "신체학대": 20,
    "정서학대": 15,
    "성학대": 15,
    "방임": 10,
}


# ============================================================
# 메인
# ============================================================

def main():

    if not GT_CSV.exists():
        raise FileNotFoundError(
            f"GT CSV를 찾을 수 없습니다:\n{GT_CSV}"
        )

    if not DURATION_CSV.exists():
        raise FileNotFoundError(
            f"Duration CSV를 찾을 수 없습니다:\n{DURATION_CSV}"
        )

    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)

    # --------------------------------------------------------
    # duration 읽기
    # --------------------------------------------------------

    duration_map = {}

    with DURATION_CSV.open(
        "r",
        encoding="utf-8-sig",
        newline=""
    ) as f:

        reader = csv.DictReader(f)

        for row in reader:

            sample_id = row["sample_id"].strip()

            duration_map[sample_id] = {
                "duration_seconds": row["duration_seconds"],
                "duration_hms": row["duration_hms"],
            }

    # --------------------------------------------------------
    # GT 읽기
    # --------------------------------------------------------

    groups = defaultdict(list)

    with GT_CSV.open(
        "r",
        encoding="utf-8-sig",
        newline=""
    ) as f:

        reader = csv.DictReader(f)

        for row in reader:

            sample_id = row["sample_id"].strip()
            label = row["abuse_label"].strip()

            if sample_id not in duration_map:
                continue

            row["duration_seconds"] = (
                duration_map[sample_id]["duration_seconds"]
            )

            row["duration_hms"] = (
                duration_map[sample_id]["duration_hms"]
            )

            groups[label].append(row)

    # --------------------------------------------------------
    # 랜덤 고정
    # --------------------------------------------------------

    random.seed(RANDOM_SEED)

    selected = []

    for label, target_count in TARGET_COUNTS.items():

        candidates = groups.get(label, [])

        if len(candidates) < target_count:

            raise ValueError(
                f"{label}: "
                f"필요 {target_count}, "
                f"가능 {len(candidates)}"
            )

        picked = random.sample(
            candidates,
            target_count
        )

        selected.extend(picked)

    # --------------------------------------------------------
    # 전체 순서 섞기
    # --------------------------------------------------------

    random.shuffle(selected)

    # --------------------------------------------------------
    # CSV 저장
    # --------------------------------------------------------

    fields = [
        "sample_id",
        "abuse_label",
        "risk_stage",
        "gender",
        "age",
        "grade",
        "subject_type",
        "tension_level",
        "behavior_characteristic",
        "duration_seconds",
        "duration_hms",
    ]

    with OUTPUT_CSV.open(
        "w",
        encoding="utf-8-sig",
        newline=""
    ) as f:

        writer = csv.DictWriter(
            f,
            fieldnames=fields
        )

        writer.writeheader()

        for row in selected:

            writer.writerow(
                {
                    field: row.get(field, "")
                    for field in fields
                }
            )

    # --------------------------------------------------------
    # 결과 출력
    # --------------------------------------------------------

    print("=" * 70)
    print("I-SPOT DEEPGRAM PILOT 100")
    print("=" * 70)

    print(f"선택된 파일 수: {len(selected)}")
    print()

    for label in TARGET_COUNTS:

        count = sum(
            1
            for row in selected
            if row["abuse_label"] == label
        )

        print(
            f"{label}: "
            f"{count}"
        )

    total_seconds = sum(
        float(row["duration_seconds"])
        for row in selected
    )

    total_minutes = total_seconds / 60
    total_hours = total_seconds / 3600

    estimated_cost = total_minutes * 0.0043

    print()
    print(
        f"총 길이: "
        f"{total_minutes:.2f}분 "
        f"({total_hours:.2f}시간)"
    )

    print(
        f"Nova-2 단순 예상 비용 "
        f"@$0.0043/min: "
        f"${estimated_cost:.2f}"
    )

    print()
    print(f"저장 완료:")
    print(OUTPUT_CSV)


if __name__ == "__main__":
    main()