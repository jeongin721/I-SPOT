from pathlib import Path
import json


PROJECT_ROOT = Path(__file__).resolve().parent.parent

RESULT_PATH = (
    PROJECT_ROOT
    / "results"
    / "pyannote_fusion_unresolved4.json"
)


LABELS = [
    "신체학대",
    "정서학대",
    "성학대",
    "방임",
]


def bool_mark(value):
    return "T" if value else "F"


def main():

    print("=" * 100)
    print("ANALYZE PYANNOTE FUSION - UNRESOLVED 4")
    print("=" * 100)

    if not RESULT_PATH.exists():

        raise FileNotFoundError(
            f"결과 파일을 찾을 수 없습니다:\n"
            f"{RESULT_PATH}"
        )

    with open(
        RESULT_PATH,
        "r",
        encoding="utf-8",
    ) as f:

        results = json.load(f)

    print()
    print(f"Loaded: {RESULT_PATH}")
    print()

    for result in results:

        file_id = result["file"]

        print()
        print("=" * 100)
        print(f"FILE: {file_id}")
        print("=" * 100)

        if "error" in result:

            print(
                f"[ERROR] {result['error']}"
            )

            continue

        # ----------------------------------------------------
        # 1. 역할 추론 정보
        # ----------------------------------------------------

        print()
        print("[ROLE MAPPING]")

        roles = result["roles"]
        role_stats = result["role_stats"]

        for speaker, stat in role_stats.items():

            mapped_role = roles.get(
                speaker,
                "UNKNOWN",
            )

            print(
                f"  {speaker}"
                f" -> {mapped_role}"
            )

            print(
                f"      utterances     : "
                f"{stat['utterance_count']}"
            )

            print(
                f"      questions      : "
                f"{stat['question_count']}"
            )

            print(
                f"      question_ratio : "
                f"{stat['question_ratio']:.3f}"
            )

        ratios = sorted(
            [
                stat["question_ratio"]
                for stat in role_stats.values()
            ],
            reverse=True,
        )

        if len(ratios) >= 2:

            ratio_gap = (
                ratios[0]
                - ratios[1]
            )

        else:

            ratio_gap = 0.0

        print()
        print(
            f"  question_ratio gap: "
            f"{ratio_gap:.3f}"
        )

        print(
            f"  selected CHILD    : "
            f"{result['child_speaker']}"
        )

        print(
            f"  selected COUNSELOR: "
            f"{result['counselor_speaker']}"
        )

        # ----------------------------------------------------
        # 2. CHILD text 크기
        # ----------------------------------------------------

        print()
        print("[CHILD TEXT]")

        print(
            f"  child utterances : "
            f"{result['child_utterance_count']}"
        )

        print(
            f"  child text length: "
            f"{result['child_text_length']} chars"
        )

        # ----------------------------------------------------
        # 3. RoBERTa
        # ----------------------------------------------------

        print()
        print("[ROBERTA]")

        prediction = result["prediction"]
        expected = result["expected"]

        mismatch_labels = []

        for label in LABELS:

            info = prediction[label]

            pred = info["detected"]
            gt = expected[label]

            same = (
                pred == gt
            )

            mark = (
                "OK"
                if same
                else "MISMATCH"
            )

            if not same:
                mismatch_labels.append(
                    label
                )

            print(
                f"  {label:<6} "
                f"prob={info['percentage']:>6.2f}% "
                f"threshold={info['threshold'] * 100:>5.1f}% "
                f"pred={bool_mark(pred)} "
                f"GT={bool_mark(gt)} "
                f"[{mark}]"
            )

        # ----------------------------------------------------
        # 4. 간단 진단
        # ----------------------------------------------------

        print()
        print("[QUICK CHECK]")

        if ratio_gap < 0.20:

            print(
                "  ! 두 화자의 질문 비율 차이가 작습니다."
            )

            print(
                "    역할 추론(COUNSELOR/CHILD)이 "
                "불안정할 가능성이 있습니다."
            )

        else:

            print(
                "  + 질문 비율 차이는 0.20 이상입니다."
            )

        if mismatch_labels:

            print(
                "  ! GT와 다른 label:"
            )

            for label in mismatch_labels:

                print(
                    f"      - {label}"
                )

        else:

            print(
                "  + 4개 label 모두 GT와 일치"
            )

    # --------------------------------------------------------
    # 전체 요약
    # --------------------------------------------------------

    print()
    print()
    print("=" * 100)
    print("COMPACT SUMMARY")
    print("=" * 100)

    for result in results:

        if "error" in result:

            print(
                f"{result['file']}: ERROR"
            )

            continue

        role_stats = result["role_stats"]

        ratios = sorted(
            [
                x["question_ratio"]
                for x in role_stats.values()
            ],
            reverse=True,
        )

        gap = (
            ratios[0] - ratios[1]
            if len(ratios) >= 2
            else 0.0
        )

        pred_values = []

        gt_values = []

        for label in LABELS:

            pred_values.append(
                bool_mark(
                    result["prediction"][label][
                        "detected"
                    ]
                )
            )

            gt_values.append(
                bool_mark(
                    result["expected"][label]
                )
            )

        print(
            f"{result['file']}: "
            f"q-gap={gap:.3f} | "
            f"CHILD={result['child_speaker']} | "
            f"text={result['child_text_length']} chars | "
            f"GT={' '.join(gt_values)} | "
            f"Fusion={' '.join(pred_values)} | "
            f"{result['match_count']}/4"
        )

    print("=" * 100)


if __name__ == "__main__":
    main()