import csv
import json
from pathlib import Path

from abuse_model.infer_abuse import predict_abuse


BASE_DIR = Path(__file__).resolve().parent

SAMPLE_DIR = BASE_DIR / "test_sample"

ROLE_MAPPING_PATH = (
    BASE_DIR / "speaker_role_mapping_results.csv"
)

OUTPUT_CSV = (
    BASE_DIR / "abuse_gt_vs_stt_results.csv"
)

TARGET_IDS = sorted(
    path.stem
    for path in SAMPLE_DIR.glob("*.json")
    if path.stem.isdigit()
)


# ============================================================
# 1. 역할 매핑 CSV 로드
# ============================================================

def load_role_mapping():

    mapping = {}

    with open(
        ROLE_MAPPING_PATH,
        "r",
        encoding="utf-8-sig",
    ) as f:

        reader = csv.DictReader(f)

        for row in reader:

            file_id = row["file"]
            speaker = row["speaker"]
            role = row["role"]

            if file_id not in mapping:
                mapping[file_id] = {}

            mapping[file_id][speaker] = role

    return mapping


# ============================================================
# 2. GT JSON에서 A 발화 추출
# ============================================================

def collect_gt_answer_text(obj):

    texts = []

    if isinstance(obj, dict):

        if (
            obj.get("type") == "A"
            and obj.get("text")
        ):
            texts.append(
                str(obj["text"]).strip()
            )

        for value in obj.values():
            texts.extend(
                collect_gt_answer_text(
                    value
                )
            )

    elif isinstance(obj, list):

        for item in obj:
            texts.extend(
                collect_gt_answer_text(
                    item
                )
            )

    return texts


def load_gt_text(file_id):

    path = (
        SAMPLE_DIR
        / f"{file_id}.json"
    )

    with open(
        path,
        "r",
        encoding="utf-8",
    ) as f:

        data = json.load(f)

    texts = collect_gt_answer_text(
        data
    )

    return " ".join(
        text
        for text in texts
        if text
    )


# ============================================================
# 3. STT JSON에서 A 화자 발화 추출
# ============================================================

def load_stt_text(
    file_id,
    answer_speakers,
):

    path = (
        SAMPLE_DIR
        / f"{file_id}_stt.json"
    )

    with open(
        path,
        "r",
        encoding="utf-8",
    ) as f:

        data = json.load(f)

    stt_data = data.get(
        "stt_data",
        {}
    )

    segments = stt_data.get(
        "segments",
        []
    )

    texts = []

    for segment in segments:

        speaker = segment.get(
            "speaker"
        )

        text = str(
            segment.get(
                "text",
                ""
            )
        ).strip()

        if (
            speaker in answer_speakers
            and text
        ):
            texts.append(text)

    return " ".join(texts)


# ============================================================
# 4. 한 파일 평가
# ============================================================

def evaluate_file(
    file_id,
    role_mapping,
):

    speaker_roles = role_mapping.get(
        file_id,
        {}
    )

    answer_speakers = [
        speaker
        for speaker, role
        in speaker_roles.items()
        if role == "A"
    ]

    if not answer_speakers:

        raise RuntimeError(
            f"{file_id}: A 역할 speaker 없음"
        )

    gt_text = load_gt_text(
        file_id
    )

    stt_text = load_stt_text(
        file_id,
        answer_speakers,
    )

    if not gt_text:
        raise RuntimeError(
            f"{file_id}: GT A-text 없음"
        )

    if not stt_text:
        raise RuntimeError(
            f"{file_id}: STT A-text 없음"
        )

    gt_result = predict_abuse(
        gt_text
    )

    stt_result = predict_abuse(
        stt_text
    )

    label_rows = []

    same_count = 0

    for label in gt_result.keys():

        gt_item = gt_result[
            label
        ]

        stt_item = stt_result[
            label
        ]

        same_detection = (
            gt_item["detected"]
            ==
            stt_item["detected"]
        )

        if same_detection:
            same_count += 1

        label_rows.append(
            {
                "label":
                    label,

                "gt_probability":
                    gt_item[
                        "probability"
                    ],

                "stt_probability":
                    stt_item[
                        "probability"
                    ],

                "diff":
                    (
                        stt_item[
                            "probability"
                        ]
                        -
                        gt_item[
                            "probability"
                        ]
                    ),

                "gt_detected":
                    gt_item[
                        "detected"
                    ],

                "stt_detected":
                    stt_item[
                        "detected"
                    ],

                "same_detection":
                    same_detection,
            }
        )

    return {
        "file":
            file_id,

        "answer_speakers":
            answer_speakers,

        "gt_text_length":
            len(gt_text),

        "stt_text_length":
            len(stt_text),

        "same_count":
            same_count,

        "total_labels":
            len(label_rows),

        "label_rows":
            label_rows,
    }


# ============================================================
# 5. 출력
# ============================================================

def print_file_result(
    result,
):

    print()
    print("=" * 80)
    print(
        f"[{result['file']}]"
    )
    print("=" * 80)

    print(
        f"A Speaker       : "
        f"{result['answer_speakers']}"
    )

    print(
        f"GT Text Length  : "
        f"{result['gt_text_length']}"
    )

    print(
        f"STT Text Length : "
        f"{result['stt_text_length']}"
    )

    print()

    for row in result[
        "label_rows"
    ]:

        mark = (
            "O"
            if row[
                "same_detection"
            ]
            else "X"
        )

        print(
            f"{row['label']:<6} "
            f"GT={row['gt_probability'] * 100:>6.2f}% "
            f"STT={row['stt_probability'] * 100:>6.2f}% "
            f"Diff={row['diff'] * 100:+6.2f}%p "
            f"GT판정={row['gt_detected']} "
            f"STT판정={row['stt_detected']} "
            f"| 동일={mark}"
        )

    print()

    print(
        f"판정 일치      : "
        f"{result['same_count']}"
        f"/{result['total_labels']}"
    )


# ============================================================
# 6. CSV 저장
# ============================================================

def save_csv(
    results,
):

    rows = []

    for result in results:

        for label_row in result[
            "label_rows"
        ]:

            rows.append(
                {
                    "file":
                        result[
                            "file"
                        ],

                    "label":
                        label_row[
                            "label"
                        ],

                    "gt_probability":
                        round(
                            label_row[
                                "gt_probability"
                            ],
                            6,
                        ),

                    "stt_probability":
                        round(
                            label_row[
                                "stt_probability"
                            ],
                            6,
                        ),

                    "difference":
                        round(
                            label_row[
                                "diff"
                            ],
                            6,
                        ),

                    "gt_detected":
                        label_row[
                            "gt_detected"
                        ],

                    "stt_detected":
                        label_row[
                            "stt_detected"
                        ],

                    "same_detection":
                        label_row[
                            "same_detection"
                        ],
                }
            )

    with open(
        OUTPUT_CSV,
        "w",
        newline="",
        encoding="utf-8-sig",
    ) as f:

        writer = csv.DictWriter(
            f,
            fieldnames=list(
                rows[0].keys()
            ),
        )

        writer.writeheader()

        writer.writerows(
            rows
        )


# ============================================================
# 7. 전체 Summary
# ============================================================

def print_summary(
    results,
):

    print()
    print("=" * 80)
    print(
        "GT A-text vs STT A-text 전체 비교"
    )
    print("=" * 80)

    total_labels = 0
    same_labels = 0

    perfect_files = 0

    for result in results:

        total_labels += (
            result[
                "total_labels"
            ]
        )

        same_labels += (
            result[
                "same_count"
            ]
        )

        if (
            result[
                "same_count"
            ]
            ==
            result[
                "total_labels"
            ]
        ):
            perfect_files += 1

        print(
            f"{result['file']} "
            f"→ "
            f"{result['same_count']}"
            f"/{result['total_labels']} "
            f"라벨 판정 일치"
        )

    print()
    print(
        f"전체 라벨 수      : "
        f"{total_labels}"
    )

    print(
        f"판정 일치 라벨 수 : "
        f"{same_labels}"
    )

    agreement = (
        same_labels
        / total_labels
        if total_labels > 0
        else 0.0
    )

    print(
        f"판정 일치율       : "
        f"{agreement * 100:.2f}%"
    )

    print(
        f"4/4 완전일치 파일 : "
        f"{perfect_files}"
        f"/{len(results)}"
    )

    print()
    print(
        f"CSV 저장 → "
        f"{OUTPUT_CSV}"
    )

    print("=" * 80)


# ============================================================
# 8. Main
# ============================================================

def main():

    role_mapping = (
        load_role_mapping()
    )

    results = []

    for file_id in TARGET_IDS:

        try:

            result = evaluate_file(
                file_id,
                role_mapping,
            )

            print_file_result(
                result
            )

            results.append(
                result
            )

        except Exception as e:

            print()
            print(
                f"[{file_id}] "
                f"평가 실패: {e}"
            )

    if not results:

        print(
            "평가 가능한 파일이 없습니다."
        )
        return

    save_csv(
        results
    )

    print_summary(
        results
    )


if __name__ == "__main__":
    main()