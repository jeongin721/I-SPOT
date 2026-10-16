import csv
import json
from collections import Counter
from pathlib import Path


# ============================================================
# 경로
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

PILOT_CSV = (
    PROJECT_ROOT
    / "data_prep"
    / "evaluation"
    / "deepgram"
    / "pilot_100.csv"
)

OUTPUT_DIR = (
    PROJECT_ROOT
    / "data_prep"
    / "evaluation"
    / "deepgram"
    / "outputs"
)

RESULT_CSV = (
    PROJECT_ROOT
    / "data_prep"
    / "evaluation"
    / "deepgram"
    / "speaker_analysis_100.csv"
)


# ============================================================
# 메인
# ============================================================

def main():

    # --------------------------------------------------------
    # Pilot 정보
    # --------------------------------------------------------

    with PILOT_CSV.open(
        "r",
        encoding="utf-8-sig",
        newline=""
    ) as f:

        pilot_rows = list(csv.DictReader(f))

    pilot_map = {
        row["sample_id"].strip(): row
        for row in pilot_rows
    }

    # --------------------------------------------------------
    # Deepgram 결과 읽기
    # --------------------------------------------------------

    results = []

    missing = []

    for sample_id, pilot in pilot_map.items():

        json_path = (
            OUTPUT_DIR
            / f"{sample_id}_deepgram.json"
        )

        if not json_path.exists():

            missing.append(sample_id)
            continue

        with json_path.open(
            "r",
            encoding="utf-8"
        ) as f:

            data = json.load(f)

        normalized = data.get(
            "normalized",
            {}
        )

        speaker_count = normalized.get(
            "speaker_count",
            0
        )

        speakers = normalized.get(
            "speakers",
            []
        )

        utterances = normalized.get(
            "utterances",
            []
        )

        words = normalized.get(
            "words",
            []
        )

        # ----------------------------------------------------
        # speaker별 utterance 수
        # ----------------------------------------------------

        utterance_counter = Counter(
            u.get("speaker")
            for u in utterances
            if u.get("speaker") is not None
        )

        # ----------------------------------------------------
        # speaker별 word 수
        # ----------------------------------------------------

        word_counter = Counter(
            w.get("speaker")
            for w in words
            if w.get("speaker") is not None
        )

        speaker0_utterances = utterance_counter.get(
            0,
            0
        )

        speaker1_utterances = utterance_counter.get(
            1,
            0
        )

        speaker0_words = word_counter.get(
            0,
            0
        )

        speaker1_words = word_counter.get(
            1,
            0
        )

        # ----------------------------------------------------
        # 상태 분류
        # ----------------------------------------------------

        if speaker_count == 1:

            diarization_status = "SINGLE_SPEAKER_COLLAPSE"

        elif speaker_count == 2:

            diarization_status = "TWO_SPEAKERS"

        elif speaker_count > 2:

            diarization_status = "MORE_THAN_TWO"

        else:

            diarization_status = "NO_SPEAKER"

        results.append(
            {
                "sample_id": sample_id,

                "abuse_label": pilot.get(
                    "abuse_label",
                    ""
                ),

                "risk_stage": pilot.get(
                    "risk_stage",
                    ""
                ),

                "age": pilot.get(
                    "age",
                    ""
                ),

                "gender": pilot.get(
                    "gender",
                    ""
                ),

                "tension_level": pilot.get(
                    "tension_level",
                    ""
                ),

                "duration_seconds": pilot.get(
                    "duration_seconds",
                    ""
                ),

                "speaker_count": speaker_count,

                "speakers": ",".join(
                    str(x)
                    for x in speakers
                ),

                "utterance_count": len(
                    utterances
                ),

                "word_count": len(
                    words
                ),

                "speaker0_utterances":
                    speaker0_utterances,

                "speaker1_utterances":
                    speaker1_utterances,

                "speaker0_words":
                    speaker0_words,

                "speaker1_words":
                    speaker1_words,

                "diarization_status":
                    diarization_status,
            }
        )

    # --------------------------------------------------------
    # CSV 저장
    # --------------------------------------------------------

    fields = [
        "sample_id",
        "abuse_label",
        "risk_stage",
        "age",
        "gender",
        "tension_level",
        "duration_seconds",
        "speaker_count",
        "speakers",
        "utterance_count",
        "word_count",
        "speaker0_utterances",
        "speaker1_utterances",
        "speaker0_words",
        "speaker1_words",
        "diarization_status",
    ]

    with RESULT_CSV.open(
        "w",
        encoding="utf-8-sig",
        newline=""
    ) as f:

        writer = csv.DictWriter(
            f,
            fieldnames=fields
        )

        writer.writeheader()
        writer.writerows(results)

    # --------------------------------------------------------
    # 통계
    # --------------------------------------------------------

    status_counter = Counter(
        row["diarization_status"]
        for row in results
    )

    speaker_counter = Counter(
        row["speaker_count"]
        for row in results
    )

    print("=" * 70)
    print("I-SPOT DEEPGRAM SPEAKER ANALYSIS")
    print("=" * 70)

    print(f"Pilot 대상: {len(pilot_rows)}")
    print(f"분석 성공: {len(results)}")
    print(f"결과 파일 없음: {len(missing)}")

    print()
    print("[speaker_count 분포]")

    for count in sorted(speaker_counter):

        print(
            f"{count}명: "
            f"{speaker_counter[count]}개"
        )

    print()
    print("[화자분리 상태]")

    for status, count in status_counter.items():

        rate = (
            count
            / len(results)
            * 100
        )

        print(
            f"{status}: "
            f"{count}개 "
            f"({rate:.2f}%)"
        )

    # --------------------------------------------------------
    # 문제 샘플
    # --------------------------------------------------------

    problematic = [
        row
        for row in results
        if row["diarization_status"]
        != "TWO_SPEAKERS"
    ]

    print()
    print(
        f"2명으로 분리되지 않은 샘플: "
        f"{len(problematic)}개"
    )

    for row in problematic:

        print(
            f"  {row['sample_id']} | "
            f"{row['abuse_label']} | "
            f"speaker_count="
            f"{row['speaker_count']} | "
            f"utterances="
            f"{row['utterance_count']}"
        )

    if missing:

        print()
        print("[결과 파일 없는 ID]")

        for sample_id in missing:
            print(f"  {sample_id}")

    print()
    print("저장 완료:")
    print(RESULT_CSV)


if __name__ == "__main__":
    main()