import csv
import json
import sys
from pathlib import Path


# ---------------------------------------------------------
# 프로젝트 경로
# ---------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TEST_SAMPLE_DIR = PROJECT_ROOT / "test_sample"
RESULTS_DIR = PROJECT_ROOT / "results"

sys.path.insert(0, str(PROJECT_ROOT))

from speaker_role_runtime import RuntimeSpeakerRoleMapper


# ---------------------------------------------------------
# GT 기반 speaker-role 정답표 불러오기
# ---------------------------------------------------------

def load_gt_mapping():

    csv_path = (
        RESULTS_DIR
        / "speaker_role_mapping_results.csv"
    )

    mapping = {}

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

            speaker = str(
                row.get("speaker", "")
            ).strip()

            role = str(
                row.get("role", "")
            ).strip()

            if (
                not file_id
                or not speaker
                or role not in {"Q", "A"}
            ):
                continue

            # 평가용 GT:
            # Q = 상담자
            # A = 아동
            expected_role = (
                "COUNSELOR"
                if role == "Q"
                else "CHILD"
            )

            mapping[
                (file_id, speaker)
            ] = expected_role

    return mapping


# ---------------------------------------------------------
# 실행
# ---------------------------------------------------------

def main():

    gt_mapping = load_gt_mapping()

    mapper = RuntimeSpeakerRoleMapper()

    total = 0
    correct = 0
    wrong = 0
    unknown = 0

    wrong_cases = []
    unknown_cases = []

    stt_files = sorted(
        TEST_SAMPLE_DIR.glob("*_stt.json")
    )

    print()
    print("=" * 100)
    print("Runtime Speaker Role Mapper Evaluation")
    print("=" * 100)

    for stt_path in stt_files:

        file_id = (
            stt_path.stem
            .replace("_stt", "")
        )

        with open(
            stt_path,
            "r",
            encoding="utf-8",
        ) as f:
            data = json.load(f)

        segments = (
            data
            .get("stt_data", {})
            .get("segments", [])
        )

        runtime_mapping = (
            mapper.map_roles(segments)
        )

        print()
        print(f"[{file_id}]")

        for speaker, prediction in runtime_mapping.items():

            expected = gt_mapping.get(
                (file_id, speaker)
            )

            # GT가 UNKNOWN이었던 speaker는
            # 정확도 계산에서 제외
            if expected is None:
                print(
                    f"  {speaker:<10} "
                    f"GT=UNKNOWN "
                    f"→ Runtime={prediction['role']}"
                )
                continue

            predicted = prediction["role"]

            total += 1

            if predicted == "UNKNOWN":
                unknown += 1

                unknown_cases.append(
                    {
                        "file_id": file_id,
                        "speaker": speaker,
                        "expected": expected,
                        "question_ratio":
                            prediction[
                                "question_ratio"
                            ],
                        "confidence":
                            prediction[
                                "confidence"
                            ],
                    }
                )

                result_text = "UNKNOWN"

            elif predicted == expected:
                correct += 1
                result_text = "OK"

            else:
                wrong += 1

                wrong_cases.append(
                    {
                        "file_id": file_id,
                        "speaker": speaker,
                        "expected": expected,
                        "predicted": predicted,
                        "question_ratio":
                            prediction[
                                "question_ratio"
                            ],
                        "confidence":
                            prediction[
                                "confidence"
                            ],
                    }
                )

                result_text = "WRONG"

            print(
                f"  {speaker:<10} "
                f"GT={expected:<10} "
                f"→ Runtime={predicted:<10} "
                f"| question="
                f"{prediction['question_ratio']:.3f} "
                f"| confidence="
                f"{prediction['confidence']:.3f} "
                f"| {result_text}"
            )

    # -----------------------------------------------------
    # 최종 결과
    # -----------------------------------------------------

    print()
    print("=" * 100)
    print("FINAL RESULT")
    print("=" * 100)

    print(f"평가 대상 speaker : {total}")
    print(f"정답              : {correct}")
    print(f"오답              : {wrong}")
    print(f"UNKNOWN           : {unknown}")

    if total > 0:

        accuracy_all = (
            correct / total * 100
        )

        decided = (
            correct + wrong
        )

        if decided > 0:
            accuracy_decided = (
                correct / decided * 100
            )
        else:
            accuracy_decided = 0.0

        print(
            f"전체 기준 정확도    : "
            f"{accuracy_all:.2f}%"
        )

        print(
            f"판정된 것만 정확도  : "
            f"{accuracy_decided:.2f}%"
        )

    # -----------------------------------------------------
    # 오답 상세
    # -----------------------------------------------------

    print()
    print("=" * 100)
    print("WRONG CASES")
    print("=" * 100)

    if not wrong_cases:
        print("없음")
    else:
        for case in wrong_cases:
            print(case)

    # -----------------------------------------------------
    # UNKNOWN 상세
    # -----------------------------------------------------

    print()
    print("=" * 100)
    print("UNKNOWN CASES")
    print("=" * 100)

    if not unknown_cases:
        print("없음")
    else:
        for case in unknown_cases:
            print(case)


if __name__ == "__main__":
    main()