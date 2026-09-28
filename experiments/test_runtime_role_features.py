import csv
import json
import sys
from collections import defaultdict
from pathlib import Path


# ---------------------------------------------------------
# 프로젝트 경로 설정
# ---------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TEST_SAMPLE_DIR = PROJECT_ROOT / "test_sample"
RESULTS_DIR = PROJECT_ROOT / "results"

sys.path.insert(0, str(PROJECT_ROOT))


# ---------------------------------------------------------
# 질문형 문장 판별
# ---------------------------------------------------------

def is_question(text: str) -> bool:
    text = (text or "").strip()

    if not text:
        return False

    question_patterns = (
        "?",
        "까",
        "니",
        "어?",
        "야?",
        "있어?",
        "했어?",
        "했니?",
        "인가?",
    )

    return any(
        text.endswith(pattern)
        for pattern in question_patterns
    )


# ---------------------------------------------------------
# 기존 GT 기반 speaker-role mapping 결과 불러오기
# ---------------------------------------------------------

def load_gt_role_mapping():
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

            mapping[
                (file_id, speaker)
            ] = role

    return mapping


# ---------------------------------------------------------
# speaker별 runtime 특징 추출
# ---------------------------------------------------------

def extract_features(segments):

    speaker_data = defaultdict(
        lambda: {
            "utterance_count": 0,
            "question_count": 0,
            "total_chars": 0,
            "short_answer_count": 0,
        }
    )

    for segment in segments:

        speaker = segment.get("speaker")
        text = (
            segment.get("text") or ""
        ).strip()

        if (
            not speaker
            or speaker == "UNKNOWN"
            or not text
        ):
            continue

        data = speaker_data[speaker]

        data["utterance_count"] += 1
        data["total_chars"] += len(text)

        if is_question(text):
            data["question_count"] += 1

        # 우선 단순한 탐색용 기준
        if len(text) <= 10:
            data["short_answer_count"] += 1

    features = {}

    for speaker, data in speaker_data.items():

        count = data["utterance_count"]

        if count == 0:
            continue

        features[speaker] = {
            "utterance_count":
                count,

            "question_count":
                data["question_count"],

            "question_ratio":
                data["question_count"]
                / count,

            "avg_chars":
                data["total_chars"]
                / count,

            "short_answer_ratio":
                data["short_answer_count"]
                / count,
        }

    return features


# ---------------------------------------------------------
# 실행
# ---------------------------------------------------------

def main():

    gt_mapping = load_gt_role_mapping()

    rows = []

    stt_files = sorted(
        TEST_SAMPLE_DIR.glob("*_stt.json")
    )

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
            stt_json = json.load(f)

        segments = (
            stt_json
            .get("stt_data", {})
            .get("segments", [])
        )

        features = extract_features(
            segments
        )

        for speaker, feature in features.items():

            gt_role = gt_mapping.get(
                (file_id, speaker),
                "UNKNOWN",
            )

            rows.append(
                {
                    "file_id":
                        file_id,

                    "speaker":
                        speaker,

                    "gt_role":
                        gt_role,

                    **feature,
                }
            )

    # -----------------------------------------------------
    # 화면 출력
    # -----------------------------------------------------

    print()
    print("=" * 90)
    print("Runtime Speaker Role Feature Analysis")
    print("=" * 90)

    for row in rows:

        print(
            f"{row['file_id']:>4} | "
            f"{row['speaker']:<10} | "
            f"GT={row['gt_role']:<7} | "
            f"utter={row['utterance_count']:>3} | "
            f"question={row['question_ratio']:.3f} | "
            f"avg_chars={row['avg_chars']:.1f} | "
            f"short={row['short_answer_ratio']:.3f}"
        )

    # -----------------------------------------------------
    # Q / A 평균 비교
    # -----------------------------------------------------

    print()
    print("=" * 90)
    print("GT Role Average")
    print("=" * 90)

    for role in ("Q", "A"):

        role_rows = [
            row
            for row in rows
            if row["gt_role"] == role
        ]

        if not role_rows:
            print(
                f"{role}: usable rows 없음"
            )
            continue

        avg_question = sum(
            row["question_ratio"]
            for row in role_rows
        ) / len(role_rows)

        avg_chars = sum(
            row["avg_chars"]
            for row in role_rows
        ) / len(role_rows)

        avg_short = sum(
            row["short_answer_ratio"]
            for row in role_rows
        ) / len(role_rows)

        print(
            f"{role} | "
            f"speakers={len(role_rows)} | "
            f"question_ratio={avg_question:.3f} | "
            f"avg_chars={avg_chars:.1f} | "
            f"short_answer_ratio={avg_short:.3f}"
        )


if __name__ == "__main__":
    main()