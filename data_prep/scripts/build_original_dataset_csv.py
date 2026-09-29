from pathlib import Path
from zipfile import ZipFile
import csv
import json


# ============================================================
# 경로
# ============================================================

DATA_ROOT = Path(
    r"C:\Users\USER\Desktop\헬스케어 4조"
)

OUTPUT_DIR = Path("data_prep")

OUTPUT_CSV = (
    OUTPUT_DIR
    / "original_dataset_2876.csv"
)


# ============================================================
# 기존 고정 regression 30개
# ============================================================

FIXED_REGRESSION_IDS = {
    "0002", "0004", "0005", "0006", "0018", "3242",
    "3706", "2076", "5036", "1136", "2560", "2677",
    "1786", "1354", "5058", "0216", "0379", "1112",
    "3731", "5113", "3891", "3316", "5069", "3696",
    "3821", "0184", "2637", "2674", "2315", "5194",
}


# ============================================================
# ZIP 검색
# ============================================================

def find_zip(filename):
    matches = list(
        DATA_ROOT.rglob(filename)
    )

    if not matches:
        raise FileNotFoundError(
            f"{filename}을 찾을 수 없습니다.\n"
            f"검색 위치: {DATA_ROOT}"
        )

    if len(matches) > 1:
        print(
            f"⚠️ {filename}이 여러 개 발견되었습니다."
        )

        for path in matches:
            print(f"  - {path}")

        print(
            "첫 번째 파일을 사용합니다."
        )

    return matches[0]


# ============================================================
# timestamp 변환
# ============================================================

def timestamp_to_ms(value):
    """
    예:
    00:02.730
    01:15.080

    -> millisecond
    """

    if value is None:
        return 0

    value = str(value).strip()

    try:
        minute_part, second_part = (
            value.split(":")
        )

        minutes = int(minute_part)
        seconds = float(second_part)

        total_ms = int(
            (
                minutes * 60
                + seconds
            )
            * 1000
        )

        return total_ms

    except Exception:
        return 0


# ============================================================
# JSON 내부 audio 발화 재귀 탐색
# ============================================================

def collect_audio_items(obj, results):
    """
    JSON 전체를 재귀적으로 탐색하면서
    audio 리스트 안의 Q/A 발화를 수집한다.
    """

    if isinstance(obj, dict):

        if (
            "audio" in obj
            and isinstance(
                obj["audio"],
                list,
            )
        ):

            for item in obj["audio"]:

                if not isinstance(
                    item,
                    dict,
                ):
                    continue

                speaker_type = (
                    str(
                        item.get(
                            "type",
                            "",
                        )
                    )
                    .strip()
                    .upper()
                )

                text = str(
                    item.get(
                        "text",
                        "",
                    )
                ).strip()

                if (
                    speaker_type
                    not in {"Q", "A"}
                ):
                    continue

                if not text:
                    continue

                start = item.get(
                    "start",
                    "",
                )

                end = item.get(
                    "end",
                    "",
                )

                results.append(
                    {
                        "type": speaker_type,
                        "text": text,
                        "start": start,
                        "end": end,
                        "start_ms":
                            timestamp_to_ms(
                                start
                            ),
                        "end_ms":
                            timestamp_to_ms(
                                end
                            ),
                    }
                )

        for value in obj.values():
            collect_audio_items(
                value,
                results,
            )

    elif isinstance(obj, list):

        for item in obj:
            collect_audio_items(
                item,
                results,
            )


# ============================================================
# 중복 제거
# ============================================================

def deduplicate_audio_items(items):
    """
    재귀 탐색 과정에서 동일 발화가 중복으로
    잡힐 가능성을 막기 위한 안전장치.
    """

    unique = []
    seen = set()

    for item in items:

        key = (
            item["type"],
            item["text"],
            item["start"],
            item["end"],
        )

        if key in seen:
            continue

        seen.add(key)
        unique.append(item)

    return unique


# ============================================================
# 대화 문자열 생성
# ============================================================

def build_text_fields(audio_items):

    audio_items = sorted(
        audio_items,
        key=lambda x: (
            x["start_ms"],
            x["end_ms"],
        ),
    )

    child_texts = []
    counselor_texts = []
    dialogue_lines = []

    child_count = 0
    counselor_count = 0

    for item in audio_items:

        if item["type"] == "A":

            child_count += 1

            child_texts.append(
                item["text"]
            )

            dialogue_lines.append(
                f"CHILD: {item['text']}"
            )

        elif item["type"] == "Q":

            counselor_count += 1

            counselor_texts.append(
                item["text"]
            )

            dialogue_lines.append(
                f"COUNSELOR: {item['text']}"
            )

    child_text = " ".join(
        child_texts
    )

    counselor_text = " ".join(
        counselor_texts
    )

    dialogue = "\n".join(
        dialogue_lines
    )

    return {
        "child_text": child_text,
        "counselor_text":
            counselor_text,
        "dialogue": dialogue,
        "child_utterance_count":
            child_count,
        "counselor_utterance_count":
            counselor_count,
        "total_utterance_count":
            len(audio_items),
    }


# ============================================================
# 라벨 binary 변환
# ============================================================

def build_label_flags(label):

    return {
        "physical":
            1
            if label == "신체학대"
            else 0,

        "emotional":
            1
            if label == "정서학대"
            else 0,

        "sexual":
            1
            if label == "성학대"
            else 0,

        "neglect":
            1
            if label == "방임"
            else 0,
    }


# ============================================================
# JSON 하나 처리
# ============================================================

def process_json(
    filename,
    data,
):

    info = data.get(
        "info",
        {},
    )

    sample_id = str(
        info.get(
            "ID",
            Path(filename).stem,
        )
    ).strip()

    abuse_label = str(
        info.get(
            "학대의심",
            "",
        )
    ).strip()

    audio_items = []

    collect_audio_items(
        data.get("list", []),
        audio_items,
    )

    audio_items = (
        deduplicate_audio_items(
            audio_items
        )
    )

    text_fields = (
        build_text_fields(
            audio_items
        )
    )

    label_flags = (
        build_label_flags(
            abuse_label
        )
    )

    fixed_regression = (
        1
        if sample_id
        in FIXED_REGRESSION_IDS
        else 0
    )

    return {
        "sample_id":
            sample_id,

        "source":
            "AIHUB_REAL",

        "abuse_label":
            abuse_label,

        "physical":
            label_flags[
                "physical"
            ],

        "emotional":
            label_flags[
                "emotional"
            ],

        "sexual":
            label_flags[
                "sexual"
            ],

        "neglect":
            label_flags[
                "neglect"
            ],

        "gender":
            str(
                info.get(
                    "성별",
                    "",
                )
            ).strip(),

        "age":
            str(
                info.get(
                    "나이",
                    "",
                )
            ).strip(),

        "grade":
            str(
                info.get(
                    "학년",
                    "",
                )
            ).strip(),

        "child_type":
            str(
                info.get(
                    "유형구분",
                    "",
                )
            ).strip(),

        "family_environment":
            str(
                info.get(
                    "가정환경",
                    "",
                )
            ).strip(),

        "interaction":
            str(
                info.get(
                    "상호작용 특성(종합)",
                    "",
                )
            ).strip(),

        "tension_level":
            str(
                info.get(
                    "긴장 수준(종합)",
                    "",
                )
            ).strip(),

        "behavior":
            str(
                info.get(
                    "행동 특성(종합)",
                    "",
                )
            ).strip(),

        "crisis_level":
            str(
                info.get(
                    "위기단계",
                    "",
                )
            ).strip(),

        "total_score":
            info.get(
                "합계점수",
                "",
            ),

        "behavior_score":
            info.get(
                "행동특성 점수",
                "",
            ),

        "clinical_opinion":
            str(
                info.get(
                    "임상가 종합소견",
                    "",
                )
            ).strip(),

        "child_utterance_count":
            text_fields[
                "child_utterance_count"
            ],

        "counselor_utterance_count":
            text_fields[
                "counselor_utterance_count"
            ],

        "total_utterance_count":
            text_fields[
                "total_utterance_count"
            ],

        "child_text":
            text_fields[
                "child_text"
            ],

        "counselor_text":
            text_fields[
                "counselor_text"
            ],

        "dialogue":
            text_fields[
                "dialogue"
            ],

        "fixed_regression_30":
            fixed_regression,
    }


# ============================================================
# MAIN
# ============================================================

def main():

    label_zip = find_zip(
        "TL_out.zip"
    )

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    print("=" * 70)
    print(
        "I-SPOT ORIGINAL DATASET BUILDER"
    )
    print("=" * 70)

    print()
    print(
        f"TL ZIP : {label_zip}"
    )

    rows = []

    errors = []

    with ZipFile(
        label_zip,
        "r",
    ) as zf:

        json_files = sorted(
            [
                item.filename
                for item
                in zf.infolist()
                if (
                    not item.is_dir()
                    and item.filename
                    .lower()
                    .endswith(".json")
                )
            ]
        )

        total = len(
            json_files
        )

        for index, filename in enumerate(
            json_files,
            start=1,
        ):

            try:

                with zf.open(
                    filename
                ) as fp:

                    data = json.load(
                        fp
                    )

                row = process_json(
                    filename,
                    data,
                )

                rows.append(
                    row
                )

            except Exception as e:

                errors.append(
                    (
                        filename,
                        repr(e),
                    )
                )

            if (
                index % 250 == 0
                or index == total
            ):

                print(
                    f"processed : "
                    f"{index:,}"
                    f"/{total:,}"
                )

    # ========================================================
    # CSV 저장
    # ========================================================

    fieldnames = [
        "sample_id",
        "source",
        "abuse_label",

        "physical",
        "emotional",
        "sexual",
        "neglect",

        "gender",
        "age",
        "grade",
        "child_type",
        "family_environment",

        "interaction",
        "tension_level",
        "behavior",

        "crisis_level",
        "total_score",
        "behavior_score",

        "clinical_opinion",

        "child_utterance_count",
        "counselor_utterance_count",
        "total_utterance_count",

        "child_text",
        "counselor_text",
        "dialogue",

        "fixed_regression_30",
    ]

    with OUTPUT_CSV.open(
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as f:

        writer = csv.DictWriter(
            f,
            fieldnames=fieldnames,
        )

        writer.writeheader()

        writer.writerows(
            rows
        )

    # ========================================================
    # 검증
    # ========================================================

    label_counts = {}

    empty_child = 0

    regression_count = 0

    for row in rows:

        label = row[
            "abuse_label"
        ]

        label_counts[label] = (
            label_counts.get(
                label,
                0,
            )
            + 1
        )

        if not row[
            "child_text"
        ].strip():

            empty_child += 1

        if row[
            "fixed_regression_30"
        ] == 1:

            regression_count += 1

    print()
    print("=" * 70)
    print("FINAL RESULT")
    print("=" * 70)

    print(
        f"JSON total          : "
        f"{len(rows) + len(errors):,}"
    )

    print(
        f"success             : "
        f"{len(rows):,}"
    )

    print(
        f"errors              : "
        f"{len(errors):,}"
    )

    print(
        f"empty child_text    : "
        f"{empty_child:,}"
    )

    print(
        f"fixed regression 30 : "
        f"{regression_count:,}"
    )

    print()

    print(
        "[ABUSE LABEL COUNTS]"
    )

    for label, count in sorted(
        label_counts.items(),
        key=lambda x: (
            -x[1],
            x[0],
        ),
    ):

        print(
            f"{label:<15}"
            f": {count:>6,}"
        )

    print()

    print(
        f"output : {OUTPUT_CSV}"
    )

    if errors:

        print()
        print(
            "[ERROR EXAMPLES]"
        )

        for filename, error in (
            errors[:10]
        ):

            print(
                f"- {filename}: "
                f"{error}"
            )

    print()
    print(
        "✅ original dataset build complete"
    )


if __name__ == "__main__":
    main()