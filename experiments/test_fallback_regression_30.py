import csv
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TEST_SAMPLE_DIR = PROJECT_ROOT / "test_sample"
RESULTS_DIR = PROJECT_ROOT / "results"

sys.path.insert(0, str(PROJECT_ROOT))

from abuse_model.infer_abuse import predict_abuse
from child_analysis_text import ChildAnalysisTextBuilder


LABELS = [
    "신체학대",
    "정서학대",
    "성학대",
    "방임",
]


def load_gt_prediction_reference():
    """
    기존 GT A-text 기반 분류 결과를 불러온다.

    results/abuse_gt_vs_stt_results.csv 에서
    GT text의 label별 판정값을 정답 기준으로 사용한다.
    """

    csv_path = (
        RESULTS_DIR
        / "abuse_gt_vs_stt_results.csv"
    )

    reference = {}

    with open(
        csv_path,
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as f:

        reader = csv.DictReader(f)

        for row in reader:

            file_id = str(
                row.get("file", "")
            ).strip()

            label = str(
                row.get("label", "")
            ).strip()

            if not file_id or label not in LABELS:
                continue

            gt_detected_raw = str(
                row.get("gt_detected", "")
            ).strip().lower()

            gt_detected = (
                gt_detected_raw
                in {
                    "true",
                    "1",
                    "yes",
                }
            )

            reference[
                (file_id, label)
            ] = gt_detected

    return reference


def load_stt_data(file_id: str):
    """
    최신 selective fallback 결과가 있으면 그것을 우선 사용하고,
    없으면 기존 저장 STT JSON을 사용한다.
    """

    latest_path = (
        TEST_SAMPLE_DIR
        / f"{file_id}_stt_latest.json"
    )

    normal_path = (
        TEST_SAMPLE_DIR
        / f"{file_id}_stt.json"
    )

    if latest_path.exists():
        target_path = latest_path
        source_type = "latest"

    elif normal_path.exists():
        target_path = normal_path
        source_type = "existing"

    else:
        return None, None

    with open(
        target_path,
        "r",
        encoding="utf-8",
    ) as f:
        data = json.load(f)

    return (
        data.get("stt_data", {}),
        source_type,
    )


def main():

    reference = load_gt_prediction_reference()

    builder = ChildAnalysisTextBuilder()

    file_ids = sorted(
        {
            file_id
            for file_id, _ in reference.keys()
        }
    )

    total_files = 0
    analyzable_files = 0
    unresolved_files = []

    total_labels = 0
    matched_labels = 0
    mismatched_labels = 0

    all_match_files = 0
    mismatch_cases = []

    print()
    print("=" * 110)
    print("30-Sample Fallback Regression Test")
    print("=" * 110)

    for file_id in file_ids:

        stt_data, source_type = (
            load_stt_data(file_id)
        )

        if stt_data is None:
            print()
            print(
                f"[{file_id}] STT 파일 없음"
            )
            continue

        total_files += 1

        build_result = builder.build(
            stt_data
        )

        status = build_result.get(
            "status"
        )

        child_speaker = build_result.get(
            "child_speaker"
        )

        child_text = (
            build_result.get(
                "child_analysis_text",
                "",
            )
            or ""
        ).strip()

        print()
        print(
            f"[{file_id}] "
            f"source={source_type} "
            f"| status={status} "
            f"| child={child_speaker}"
        )

        if (
            status != "OK"
            or not child_text
        ):

            unresolved_files.append(
                {
                    "file_id": file_id,
                    "status": status,
                    "child_speaker": child_speaker,
                }
            )

            print(
                "  → 분석용 아동 텍스트 생성 실패"
            )
            continue

        analyzable_files += 1

        abuse_result = predict_abuse(
            child_text
        )

        file_all_match = True

        for label in LABELS:

            expected = reference.get(
                (file_id, label)
            )

            if expected is None:
                continue

            info = abuse_result.get(
                label,
                {},
            )

            predicted = bool(
                info.get(
                    "detected",
                    False,
                )
            )

            probability = info.get(
                "probability"
            )

            total_labels += 1

            same = (
                predicted == expected
            )

            if same:
                matched_labels += 1
                result_text = "OK"

            else:
                mismatched_labels += 1
                file_all_match = False
                result_text = "MISMATCH"

                mismatch_cases.append(
                    {
                        "file_id":
                            file_id,

                        "label":
                            label,

                        "expected":
                            expected,

                        "predicted":
                            predicted,

                        "probability":
                            probability,

                        "source":
                            source_type,

                        "child_speaker":
                            child_speaker,
                    }
                )

            print(
                f"  {label:<6} "
                f"GT={str(expected):<5} "
                f"Runtime={str(predicted):<5} "
                f"| prob={probability} "
                f"| {result_text}"
            )

        if file_all_match:
            all_match_files += 1

    print()
    print("=" * 110)
    print("FINAL RESULT")
    print("=" * 110)

    print(
        f"전체 파일                  : "
        f"{total_files}"
    )

    print(
        f"child_analysis_text 생성   : "
        f"{analyzable_files}"
    )

    print(
        f"분석 불가 파일             : "
        f"{len(unresolved_files)}"
    )

    print(
        f"평가 label 수              : "
        f"{total_labels}"
    )

    print(
        f"일치 label                 : "
        f"{matched_labels}"
    )

    print(
        f"불일치 label               : "
        f"{mismatched_labels}"
    )

    if total_labels > 0:

        agreement = (
            matched_labels
            / total_labels
            * 100
        )

        print(
            f"label-level agreement      : "
            f"{agreement:.2f}%"
        )

    if analyzable_files > 0:

        file_agreement = (
            all_match_files
            / analyzable_files
            * 100
        )

        print(
            f"4-label 전체 일치 파일      : "
            f"{all_match_files}"
            f"/{analyzable_files} "
            f"({file_agreement:.2f}%)"
        )

    print()
    print("=" * 110)
    print("MISMATCH CASES")
    print("=" * 110)

    if not mismatch_cases:
        print("없음")
    else:
        for case in mismatch_cases:
            print(case)

    print()
    print("=" * 110)
    print("UNRESOLVED FILES")
    print("=" * 110)

    if not unresolved_files:
        print("없음")
    else:
        for case in unresolved_files:
            print(case)

    print()
    print("=" * 110)
    print("1354 CHECK")
    print("=" * 110)

    has_1354_reference = any(
        file_id == "1354"
        for file_id in file_ids
    )

    if not has_1354_reference:
        print(
            "1354 기준 데이터가 없어 "
            "검증할 수 없습니다."
        )
    else:
        mismatch_1354 = [
            case
            for case in mismatch_cases
            if case["file_id"] == "1354"
        ]

        unresolved_1354 = [
            case
            for case in unresolved_files
            if case["file_id"] == "1354"
        ]

        if unresolved_1354:
            print(
                "1354는 child_analysis_text 생성에 실패"
            )

        elif mismatch_1354:
            print(
                "1354 mismatch 발견:"
            )

            for case in mismatch_1354:
                print(case)

        else:
            print(
                "1354는 GT 4-label 판정과 모두 일치"
            )

if __name__ == "__main__":
    main()