import csv
from collections import defaultdict
from pathlib import Path


# ============================================================
# 경로
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

INPUT_CSV = (
    PROJECT_ROOT
    / "data_prep"
    / "evaluation"
    / "elevenlabs"
    / "comparison_available.csv"
)

OUTPUT_CSV = (
    PROJECT_ROOT
    / "data_prep"
    / "evaluation"
    / "elevenlabs"
    / "comparison_18_detailed_analysis.csv"
)


# ============================================================
# 숫자 변환
# ============================================================

def to_float(value):

    try:
        return float(value)

    except (
        TypeError,
        ValueError
    ):
        return 0.0


# ============================================================
# 상태를 간단한 실패 유형으로 변환
# ============================================================

def failure_type(status):

    if status == "ROLE_MAPPING_OK":
        return "SUCCESS"

    if status == "SINGLE_SPEAKER_COLLAPSE":
        return "SINGLE_SPEAKER_COLLAPSE"

    if status == "MIXED_SPEAKER_COLLAPSE":
        return "MIXED_SPEAKER_COLLAPSE"

    if status == "ROLE_MISSING":
        return "ROLE_MISSING"

    if status == "AMBIGUOUS":
        return "AMBIGUOUS"

    return "OTHER"


# ============================================================
# main
# ============================================================

def main():

    if not INPUT_CSV.exists():

        print(
            f"입력 파일이 없습니다:\n"
            f"{INPUT_CSV}"
        )

        return

    with INPUT_CSV.open(
        "r",
        encoding="utf-8-sig",
        newline=""
    ) as f:

        rows = list(
            csv.DictReader(f)
        )

    print(
        "=" * 76
    )

    print(
        "I-SPOT Deepgram vs ElevenLabs "
        "18-sample 상세 분석"
    )

    print(
        "=" * 76
    )

    print(
        f"분석 샘플 수: "
        f"{len(rows)}"
    )

    # ========================================================
    # 기본 통계
    # ========================================================

    dg_status_counts = defaultdict(
        int
    )

    el_status_counts = defaultdict(
        int
    )

    transitions = defaultdict(
        int
    )

    detailed_rows = []

    dg_child_coverages = []
    el_child_coverages = []

    dg_counselor_coverages = []
    el_counselor_coverages = []

    improved_samples = []
    degraded_samples = []
    both_failed_samples = []
    both_ok_samples = []

    for row in rows:

        sample_id = row[
            "sample_id"
        ]

        dg_status = row[
            "deepgram_status"
        ]

        el_status = row[
            "elevenlabs_status"
        ]

        dg_status_counts[
            dg_status
        ] += 1

        el_status_counts[
            el_status
        ] += 1

        transitions[
            (
                dg_status,
                el_status
            )
        ] += 1

        dg_child = to_float(
            row.get(
                "deepgram_child_coverage"
            )
        )

        el_child = to_float(
            row.get(
                "elevenlabs_child_coverage"
            )
        )

        dg_counselor = to_float(
            row.get(
                "deepgram_counselor_coverage"
            )
        )

        el_counselor = to_float(
            row.get(
                "elevenlabs_counselor_coverage"
            )
        )

        dg_child_coverages.append(
            dg_child
        )

        el_child_coverages.append(
            el_child
        )

        dg_counselor_coverages.append(
            dg_counselor
        )

        el_counselor_coverages.append(
            el_counselor
        )

        dg_ok = (
            dg_status
            == "ROLE_MAPPING_OK"
        )

        el_ok = (
            el_status
            == "ROLE_MAPPING_OK"
        )

        if (
            not dg_ok
            and el_ok
        ):

            overall_change = (
                "ELEVENLABS_RECOVERED"
            )

            improved_samples.append(
                sample_id
            )

        elif (
            dg_ok
            and not el_ok
        ):

            overall_change = (
                "ELEVENLABS_DEGRADED"
            )

            degraded_samples.append(
                sample_id
            )

        elif (
            dg_ok
            and el_ok
        ):

            overall_change = (
                "BOTH_OK"
            )

            both_ok_samples.append(
                sample_id
            )

        else:

            overall_change = (
                "BOTH_FAILED"
            )

            both_failed_samples.append(
                sample_id
            )

        child_delta = (
            el_child
            - dg_child
        )

        counselor_delta = (
            el_counselor
            - dg_counselor
        )

        detailed_rows.append(
            {
                "sample_id":
                    sample_id,

                "deepgram_status":
                    dg_status,

                "elevenlabs_status":
                    el_status,

                "deepgram_failure_type":
                    failure_type(
                        dg_status
                    ),

                "elevenlabs_failure_type":
                    failure_type(
                        el_status
                    ),

                "overall_change":
                    overall_change,

                "deepgram_child_coverage":
                    round(
                        dg_child,
                        4
                    ),

                "elevenlabs_child_coverage":
                    round(
                        el_child,
                        4
                    ),

                "child_coverage_delta":
                    round(
                        child_delta,
                        4
                    ),

                "deepgram_counselor_coverage":
                    round(
                        dg_counselor,
                        4
                    ),

                "elevenlabs_counselor_coverage":
                    round(
                        el_counselor,
                        4
                    ),

                "counselor_coverage_delta":
                    round(
                        counselor_delta,
                        4
                    ),

                "deepgram_speaker_count":
                    row.get(
                        "deepgram_speaker_count",
                        ""
                    ),

                "elevenlabs_speaker_count":
                    row.get(
                        "elevenlabs_speaker_count",
                        ""
                    ),

                "deepgram_child_speakers":
                    row.get(
                        "deepgram_child_speakers",
                        ""
                    ),

                "elevenlabs_child_speakers":
                    row.get(
                        "elevenlabs_child_speakers",
                        ""
                    ),

                "deepgram_mixed_speakers":
                    row.get(
                        "deepgram_mixed_speakers",
                        ""
                    ),

                "elevenlabs_mixed_speakers":
                    row.get(
                        "elevenlabs_mixed_speakers",
                        ""
                    ),
            }
        )

    # ========================================================
    # CSV 저장
    # ========================================================

    if detailed_rows:

        OUTPUT_CSV.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        with OUTPUT_CSV.open(
            "w",
            encoding="utf-8-sig",
            newline=""
        ) as f:

            writer = csv.DictWriter(
                f,
                fieldnames=
                    detailed_rows[
                        0
                    ].keys()
            )

            writer.writeheader()

            writer.writerows(
                detailed_rows
            )

    # ========================================================
    # 평균 coverage
    # ========================================================

    def average(values):

        if not values:
            return 0.0

        return sum(
            values
        ) / len(
            values
        )

    dg_child_avg = average(
        dg_child_coverages
    )

    el_child_avg = average(
        el_child_coverages
    )

    dg_counselor_avg = average(
        dg_counselor_coverages
    )

    el_counselor_avg = average(
        el_counselor_coverages
    )

    # ========================================================
    # 결과 출력
    # ========================================================

    print()

    print(
        "[1] Strict role-separation 성공률"
    )

    dg_ok_count = dg_status_counts[
        "ROLE_MAPPING_OK"
    ]

    el_ok_count = el_status_counts[
        "ROLE_MAPPING_OK"
    ]

    total = len(
        rows
    )

    print(
        f"Deepgram: "
        f"{dg_ok_count}/{total} "
        f"({dg_ok_count / total * 100:.2f}%)"
    )

    print(
        f"ElevenLabs: "
        f"{el_ok_count}/{total} "
        f"({el_ok_count / total * 100:.2f}%)"
    )

    print()

    print(
        "[2] CHILD coverage 평균"
    )

    print(
        f"Deepgram: "
        f"{dg_child_avg:.4f}"
    )

    print(
        f"ElevenLabs: "
        f"{el_child_avg:.4f}"
    )

    print(
        f"차이: "
        f"{el_child_avg - dg_child_avg:+.4f}"
    )

    print()

    print(
        "[3] COUNSELOR coverage 평균"
    )

    print(
        f"Deepgram: "
        f"{dg_counselor_avg:.4f}"
    )

    print(
        f"ElevenLabs: "
        f"{el_counselor_avg:.4f}"
    )

    print(
        f"차이: "
        f"{el_counselor_avg - dg_counselor_avg:+.4f}"
    )

    print()

    print(
        "[4] ElevenLabs가 복구한 샘플"
    )

    if improved_samples:

        for sample_id in improved_samples:

            row = next(
                r
                for r in detailed_rows
                if r[
                    "sample_id"
                ] == sample_id
            )

            print(
                f"  {sample_id} | "
                f"{row['deepgram_status']} "
                f"→ "
                f"{row['elevenlabs_status']} | "
                f"CHILD "
                f"{row['deepgram_child_coverage']}"
                f" → "
                f"{row['elevenlabs_child_coverage']}"
            )

    else:

        print(
            "  없음"
        )

    print()

    print(
        "[5] ElevenLabs에서 악화된 샘플"
    )

    if degraded_samples:

        for sample_id in degraded_samples:

            print(
                f"  {sample_id}"
            )

    else:

        print(
            "  없음"
        )

    print()

    print(
        "[6] 둘 다 실패한 샘플"
    )

    if both_failed_samples:

        for sample_id in both_failed_samples:

            row = next(
                r
                for r in detailed_rows
                if r[
                    "sample_id"
                ] == sample_id
            )

            print(
                f"  {sample_id} | "
                f"DG="
                f"{row['deepgram_status']} | "
                f"EL="
                f"{row['elevenlabs_status']}"
            )

    else:

        print(
            "  없음"
        )

    print()

    print(
        "[7] 상태 전환"
    )

    for (
        dg_status,
        el_status
    ), count in sorted(
        transitions.items()
    ):

        print(
            f"  {dg_status}"
            f" → "
            f"{el_status}: "
            f"{count}"
        )

    print()

    print(
        "=" * 76
    )

    print(
        "핵심 해석"
    )

    print(
        "=" * 76
    )

    if (
        len(
            improved_samples
        ) > 0
        and len(
            degraded_samples
        ) == 0
    ):

        print(
            "현재 18개 공통 샘플에서는 "
            "ElevenLabs가 Deepgram 실패 케이스를 "
            "복구한 사례가 있었고,"
        )

        print(
            "Deepgram 성공 케이스를 "
            "ElevenLabs가 실패로 바꾼 사례는 "
            "관찰되지 않았습니다."
        )

    print()

    print(
        "단, 18개는 전체 100개 중 일부이므로 "
        "이 결과만으로 최종 STT provider를 "
        "선정하면 안 됩니다."
    )

    print()

    print(
        f"상세 CSV 저장:\n"
        f"{OUTPUT_CSV}"
    )

    print(
        "=" * 76
    )


if __name__ == "__main__":
    main()