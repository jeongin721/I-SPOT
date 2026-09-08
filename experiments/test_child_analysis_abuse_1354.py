import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from child_analysis_text import ChildAnalysisTextBuilder
from abuse_model.infer_abuse import predict_abuse


def main():

    stt_path = (
        PROJECT_ROOT
        / "test_sample"
        / "1354_stt_latest.json"
    )

    with open(
        stt_path,
        "r",
        encoding="utf-8",
    ) as f:
        data = json.load(f)

    stt_data = data.get(
        "stt_data",
        {},
    )

    # -----------------------------------------------------
    # 1. 아동 분석용 텍스트 생성
    # -----------------------------------------------------

    builder = ChildAnalysisTextBuilder()

    build_result = builder.build(
        stt_data
    )

    status = build_result.get(
        "status"
    )

    child_speaker = build_result.get(
        "child_speaker"
    )

    child_analysis_text = (
        build_result.get(
            "child_analysis_text",
            "",
        )
        or ""
    ).strip()

    print()
    print("=" * 90)
    print("1354 Child Analysis → Abuse Classification")
    print("=" * 90)

    print(
        "status:",
        status,
    )

    print(
        "child_speaker:",
        child_speaker,
    )

    print()

    # -----------------------------------------------------
    # 2. 텍스트 확인
    # -----------------------------------------------------

    print("=" * 90)
    print("child_analysis_text")
    print("=" * 90)

    print(
        child_analysis_text
    )

    if not child_analysis_text:
        print()
        print(
            "child_analysis_text가 비어 있어서 "
            "학대 분류를 실행하지 않습니다."
        )
        return

    # -----------------------------------------------------
    # 3. KLUE-RoBERTa 학대 유형 예측
    # -----------------------------------------------------

    print()
    print("=" * 90)
    print("KLUE-RoBERTa 결과")
    print("=" * 90)

    abuse_result = predict_abuse(
        child_analysis_text
    )

    for label, info in abuse_result.items():

        print()
        print(
            f"[{label}]"
        )

        print(
            "probability:",
            info.get("probability")
        )

        print(
            "percentage:",
            info.get("percentage")
        )

        print(
            "threshold:",
            info.get("threshold")
        )

        print(
            "detected:",
            info.get("detected")
        )


if __name__ == "__main__":
    main()