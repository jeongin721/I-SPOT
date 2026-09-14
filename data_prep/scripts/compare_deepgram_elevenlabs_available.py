import csv
import json
from collections import defaultdict
from pathlib import Path


# ============================================================
# 경로
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

GT_JSONL = (
    PROJECT_ROOT
    / "data_prep"
    / "evaluation"
    / "ground_truth"
    / "gt_2876.jsonl"
)

DEEPGRAM_DIR = (
    PROJECT_ROOT
    / "data_prep"
    / "evaluation"
    / "deepgram"
    / "outputs"
)

ELEVENLABS_DIR = (
    PROJECT_ROOT
    / "data_prep"
    / "evaluation"
    / "elevenlabs"
    / "outputs"
)

OUTPUT_CSV = (
    PROJECT_ROOT
    / "data_prep"
    / "evaluation"
    / "elevenlabs"
    / "comparison_available.csv"
)


# ============================================================
# 기존 Deepgram evaluator와 완전히 동일한 기준
# ============================================================

PURITY_THRESHOLD = 0.80
ROLE_COVERAGE_THRESHOLD = 0.80


# ============================================================
# interval overlap
# ============================================================

def overlap_duration(
    a_start,
    a_end,
    b_start,
    b_end
):

    start = max(
        a_start,
        b_start
    )

    end = min(
        a_end,
        b_end
    )

    return max(
        0.0,
        end - start
    )


# ============================================================
# GT load
# ============================================================

def load_gt():

    result = {}

    with GT_JSONL.open(
        "r",
        encoding="utf-8"
    ) as f:

        for line in f:

            line = line.strip()

            if not line:
                continue

            row = json.loads(
                line
            )

            sample_id = str(
                row["sample_id"]
            ).strip()

            result[
                sample_id
            ] = row

    return result


# ============================================================
# GT utterances
# ============================================================

def get_gt_utterances(
    gt
):

    result = []

    for utt in gt.get(
        "utterances",
        []
    ):

        role = utt.get(
            "role"
        )

        if role not in (
            "CHILD",
            "COUNSELOR"
        ):
            continue

        start = utt.get(
            "start"
        )

        end = utt.get(
            "end"
        )

        if (
            start is None
            or end is None
        ):
            continue

        result.append(
            {
                "role":
                    role,

                "start":
                    float(
                        start
                    ),

                "end":
                    float(
                        end
                    ),
            }
        )

    return result


# ============================================================
# Deepgram adapter
#
# 중요:
# 기존 evaluator와 동일하게
# dg["normalized"]["words"] 사용
# ============================================================

def load_deepgram_words(
    path
):

    with path.open(
        "r",
        encoding="utf-8"
    ) as f:

        dg = json.load(
            f
        )

    normalized = dg.get(
        "normalized",
        {}
    )

    raw_words = normalized.get(
        "words",
        []
    )

    words = []

    for word in raw_words:

        speaker = word.get(
            "speaker"
        )

        start = word.get(
            "start"
        )

        end = word.get(
            "end"
        )

        if (
            speaker is None
            or start is None
            or end is None
        ):
            continue

        words.append(
            {
                "speaker":
                    str(
                        speaker
                    ),

                "start":
                    float(
                        start
                    ),

                "end":
                    float(
                        end
                    ),
            }
        )

    speaker_count = normalized.get(
        "speaker_count",
        0
    )

    return (
        words,
        int(
            speaker_count
        )
    )


# ============================================================
# ElevenLabs adapter
#
# spacing / audio_event 제외
# speaker_id → 공통 speaker 필드로 변환
# ============================================================

def load_elevenlabs_words(
    path
):

    with path.open(
        "r",
        encoding="utf-8"
    ) as f:

        data = json.load(
            f
        )

    words = []

    speaker_ids = set()

    for word in data.get(
        "words",
        []
    ):

        # 실제 단어만 사용
        if word.get(
            "type"
        ) != "word":
            continue

        speaker = word.get(
            "speaker_id"
        )

        start = word.get(
            "start"
        )

        end = word.get(
            "end"
        )

        if (
            speaker is None
            or start is None
            or end is None
        ):
            continue

        speaker = str(
            speaker
        )

        speaker_ids.add(
            speaker
        )

        words.append(
            {
                "speaker":
                    speaker,

                "start":
                    float(
                        start
                    ),

                "end":
                    float(
                        end
                    ),
            }
        )

    return (
        words,
        len(
            speaker_ids
        )
    )


# ============================================================
# 기존 strict evaluator 핵심 로직
#
# evaluate_deepgram_role_mapping.py와 동일한 방식
# ============================================================

def evaluate(
    words,
    speaker_count,
    gt_utts
):

    speaker_stats = defaultdict(
        lambda: {
            "CHILD": 0.0,
            "COUNSELOR": 0.0,
            "word_count": 0,
        }
    )

    # --------------------------------------------------------
    # speaker별 GT role overlap 계산
    # --------------------------------------------------------

    for word in words:

        speaker = word.get(
            "speaker"
        )

        start = word.get(
            "start"
        )

        end = word.get(
            "end"
        )

        if (
            speaker is None
            or start is None
            or end is None
        ):
            continue

        speaker = str(
            speaker
        )

        start = float(
            start
        )

        end = float(
            end
        )

        speaker_stats[
            speaker
        ]["word_count"] += 1

        for gt_utt in gt_utts:

            overlap = overlap_duration(
                start,
                end,
                gt_utt[
                    "start"
                ],
                gt_utt[
                    "end"
                ],
            )

            if overlap <= 0:
                continue

            speaker_stats[
                speaker
            ][
                gt_utt["role"]
            ] += overlap

    # --------------------------------------------------------
    # 기존 evaluator와 동일:
    #
    # GT 전체 발화 길이가 아니라
    # 모든 STT word의 GT role overlap 총량
    # --------------------------------------------------------

    total_child_overlap = sum(
        stat["CHILD"]
        for stat
        in speaker_stats.values()
    )

    total_counselor_overlap = sum(
        stat["COUNSELOR"]
        for stat
        in speaker_stats.values()
    )

    # --------------------------------------------------------
    # speaker role 분류
    # --------------------------------------------------------

    speaker_mapping = []

    child_speakers = []
    counselor_speakers = []
    mixed_speakers = []

    for speaker in sorted(
        speaker_stats.keys()
    ):

        stat = speaker_stats[
            speaker
        ]

        child_sec = stat[
            "CHILD"
        ]

        counselor_sec = stat[
            "COUNSELOR"
        ]

        total = (
            child_sec
            + counselor_sec
        )

        if total <= 0:

            role = "UNKNOWN"
            purity = 0.0

        else:

            dominant = max(
                child_sec,
                counselor_sec
            )

            purity = (
                dominant
                / total
            )

            if (
                purity
                < PURITY_THRESHOLD
            ):

                role = "MIXED"

            elif (
                child_sec
                > counselor_sec
            ):

                role = "CHILD"

            else:

                role = "COUNSELOR"

        if role == "CHILD":

            child_speakers.append(
                speaker
            )

        elif role == "COUNSELOR":

            counselor_speakers.append(
                speaker
            )

        elif role == "MIXED":

            mixed_speakers.append(
                speaker
            )

        speaker_mapping.append(
            {
                "speaker":
                    speaker,

                "role":
                    role,

                "child_sec":
                    round(
                        child_sec,
                        4
                    ),

                "counselor_sec":
                    round(
                        counselor_sec,
                        4
                    ),

                "purity":
                    round(
                        purity,
                        4
                    ),

                "word_count":
                    stat[
                        "word_count"
                    ],
            }
        )

    # --------------------------------------------------------
    # 기존 evaluator와 동일한 role coverage
    # --------------------------------------------------------

    assigned_child_overlap = sum(
        speaker_stats[
            speaker
        ]["CHILD"]
        for speaker
        in child_speakers
    )

    assigned_counselor_overlap = sum(
        speaker_stats[
            speaker
        ]["COUNSELOR"]
        for speaker
        in counselor_speakers
    )

    if total_child_overlap > 0:

        child_coverage = (
            assigned_child_overlap
            / total_child_overlap
        )

    else:

        child_coverage = 0.0

    if total_counselor_overlap > 0:

        counselor_coverage = (
            assigned_counselor_overlap
            / total_counselor_overlap
        )

    else:

        counselor_coverage = 0.0

    # --------------------------------------------------------
    # 기존 evaluator와 동일한 status 판정 순서
    # --------------------------------------------------------

    child_ok = (
        len(
            child_speakers
        ) > 0
        and
        child_coverage
        >= ROLE_COVERAGE_THRESHOLD
    )

    counselor_ok = (
        len(
            counselor_speakers
        ) > 0
        and
        counselor_coverage
        >= ROLE_COVERAGE_THRESHOLD
    )

    if (
        child_ok
        and counselor_ok
    ):

        mapping_status = (
            "ROLE_MAPPING_OK"
        )

    elif speaker_count == 1:

        mapping_status = (
            "SINGLE_SPEAKER_COLLAPSE"
        )

    elif mixed_speakers:

        mapping_status = (
            "MIXED_SPEAKER_COLLAPSE"
        )

    elif (
        not child_speakers
        or not counselor_speakers
    ):

        mapping_status = (
            "ROLE_MISSING"
        )

    else:

        mapping_status = (
            "AMBIGUOUS"
        )

    return {
        "speaker_count":
            speaker_count,

        "mapping_status":
            mapping_status,

        "child_speaker_ids":
            ",".join(
                child_speakers
            ),

        "counselor_speaker_ids":
            ",".join(
                counselor_speakers
            ),

        "mixed_speaker_ids":
            ",".join(
                mixed_speakers
            ),

        "child_coverage":
            round(
                child_coverage,
                4
            ),

        "counselor_coverage":
            round(
                counselor_coverage,
                4
            ),

        "speaker_mapping_json":
            json.dumps(
                speaker_mapping,
                ensure_ascii=False
            ),
    }


# ============================================================
# summary
# ============================================================

def print_summary(
    name,
    results
):

    status_counts = defaultdict(
        int
    )

    for row in results:

        status_counts[
            row[
                "mapping_status"
            ]
        ] += 1

    total = len(
        results
    )

    print()
    print(
        f"[{name}]"
    )

    print(
        f"평가 샘플: "
        f"{total}"
    )

    status_order = [
        "ROLE_MAPPING_OK",
        "SINGLE_SPEAKER_COLLAPSE",
        "MIXED_SPEAKER_COLLAPSE",
        "ROLE_MISSING",
        "AMBIGUOUS",
    ]

    for status in status_order:

        count = status_counts[
            status
        ]

        percentage = (
            count / total * 100
            if total
            else 0.0
        )

        print(
            f"  {status}: "
            f"{count} "
            f"({percentage:.2f}%)"
        )

    ok = status_counts[
        "ROLE_MAPPING_OK"
    ]

    if total:

        print(
            "  strict role-separation "
            f"success: "
            f"{ok}/{total} "
            f"({ok / total * 100:.2f}%)"
        )


# ============================================================
# main
# ============================================================

def main():

    gt_map = load_gt()

    elevenlabs_files = sorted(
        ELEVENLABS_DIR.glob(
            "*_elevenlabs.json"
        )
    )

    available = []

    for el_path in elevenlabs_files:

        sample_id = (
            el_path.name
            .replace(
                "_elevenlabs.json",
                ""
            )
        )

        dg_path = (
            DEEPGRAM_DIR
            / f"{sample_id}_deepgram.json"
        )

        if (
            sample_id in gt_map
            and dg_path.exists()
        ):

            available.append(
                {
                    "sample_id":
                        sample_id,

                    "deepgram_path":
                        dg_path,

                    "elevenlabs_path":
                        el_path,
                }
            )

    print(
        "=" * 72
    )

    print(
        "Deepgram vs ElevenLabs "
        "동일 Strict Evaluator 비교"
    )

    print(
        "=" * 72
    )

    print(
        f"ElevenLabs 정상 JSON: "
        f"{len(elevenlabs_files)}"
    )

    print(
        f"양쪽 비교 가능: "
        f"{len(available)}"
    )

    deepgram_results = []
    elevenlabs_results = []

    comparison_rows = []

    for item in available:

        sample_id = item[
            "sample_id"
        ]

        gt = gt_map[
            sample_id
        ]

        gt_utts = (
            get_gt_utterances(
                gt
            )
        )

        # ----------------------------------------------------
        # Deepgram
        # ----------------------------------------------------

        (
            dg_words,
            dg_speaker_count
        ) = load_deepgram_words(
            item[
                "deepgram_path"
            ]
        )

        dg_result = evaluate(
            dg_words,
            dg_speaker_count,
            gt_utts
        )

        # ----------------------------------------------------
        # ElevenLabs
        # ----------------------------------------------------

        (
            el_words,
            el_speaker_count
        ) = load_elevenlabs_words(
            item[
                "elevenlabs_path"
            ]
        )

        el_result = evaluate(
            el_words,
            el_speaker_count,
            gt_utts
        )

        deepgram_results.append(
            dg_result
        )

        elevenlabs_results.append(
            el_result
        )

        dg_ok = (
            dg_result[
                "mapping_status"
            ]
            == "ROLE_MAPPING_OK"
        )

        el_ok = (
            el_result[
                "mapping_status"
            ]
            == "ROLE_MAPPING_OK"
        )

        if (
            not dg_ok
            and el_ok
        ):

            comparison = (
                "ELEVENLABS_IMPROVED"
            )

        elif (
            dg_ok
            and not el_ok
        ):

            comparison = (
                "DEEPGRAM_BETTER"
            )

        elif (
            dg_ok
            and el_ok
        ):

            comparison = (
                "BOTH_OK"
            )

        else:

            comparison = (
                "BOTH_FAILED"
            )

        comparison_rows.append(
            {
                "sample_id":
                    sample_id,

                "deepgram_status":
                    dg_result[
                        "mapping_status"
                    ],

                "elevenlabs_status":
                    el_result[
                        "mapping_status"
                    ],

                "comparison":
                    comparison,

                "deepgram_speaker_count":
                    dg_result[
                        "speaker_count"
                    ],

                "elevenlabs_speaker_count":
                    el_result[
                        "speaker_count"
                    ],

                "deepgram_child_coverage":
                    dg_result[
                        "child_coverage"
                    ],

                "elevenlabs_child_coverage":
                    el_result[
                        "child_coverage"
                    ],

                "deepgram_counselor_coverage":
                    dg_result[
                        "counselor_coverage"
                    ],

                "elevenlabs_counselor_coverage":
                    el_result[
                        "counselor_coverage"
                    ],

                "deepgram_child_speakers":
                    dg_result[
                        "child_speaker_ids"
                    ],

                "elevenlabs_child_speakers":
                    el_result[
                        "child_speaker_ids"
                    ],

                "deepgram_mixed_speakers":
                    dg_result[
                        "mixed_speaker_ids"
                    ],

                "elevenlabs_mixed_speakers":
                    el_result[
                        "mixed_speaker_ids"
                    ],
            }
        )

    # ========================================================
    # CSV 저장
    # ========================================================

    if comparison_rows:

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
                    comparison_rows[
                        0
                    ].keys()
            )

            writer.writeheader()

            writer.writerows(
                comparison_rows
            )

    # ========================================================
    # 요약
    # ========================================================

    print_summary(
        "Deepgram",
        deepgram_results
    )

    print_summary(
        "ElevenLabs",
        elevenlabs_results
    )

    # ========================================================
    # 직접 비교
    # ========================================================

    counts = defaultdict(
        int
    )

    for row in comparison_rows:

        counts[
            row[
                "comparison"
            ]
        ] += 1

    print()
    print(
        "[직접 비교]"
    )

    print(
        "ElevenLabs만 성공: "
        f"{counts['ELEVENLABS_IMPROVED']}"
    )

    print(
        "Deepgram만 성공: "
        f"{counts['DEEPGRAM_BETTER']}"
    )

    print(
        "둘 다 성공: "
        f"{counts['BOTH_OK']}"
    )

    print(
        "둘 다 실패: "
        f"{counts['BOTH_FAILED']}"
    )

    # ========================================================
    # 샘플별 비교
    # ========================================================

    print()
    print(
        "[샘플별 비교]"
    )

    for row in comparison_rows:

        marker = ""

        if (
            row[
                "comparison"
            ]
            == "ELEVENLABS_IMPROVED"
        ):

            marker = (
                " <-- ElevenLabs 개선"
            )

        elif (
            row[
                "comparison"
            ]
            == "DEEPGRAM_BETTER"
        ):

            marker = (
                " <-- Deepgram 우세"
            )

        print(
            f"{row['sample_id']} | "
            f"DG="
            f"{row['deepgram_status']} | "
            f"EL="
            f"{row['elevenlabs_status']} | "
            f"DG child="
            f"{row['deepgram_child_coverage']} | "
            f"EL child="
            f"{row['elevenlabs_child_coverage']}"
            f"{marker}"
        )

    print()
    print(
        "=" * 72
    )

    print(
        f"결과 저장: "
        f"{OUTPUT_CSV}"
    )

    print(
        f"purity >= "
        f"{PURITY_THRESHOLD:.0%}"
    )

    print(
        f"role coverage >= "
        f"{ROLE_COVERAGE_THRESHOLD:.0%}"
    )

    print()

    print(
        "※ 기존 Deepgram strict evaluator와 "
        "동일한 coverage 정의를 사용합니다."
    )

    print(
        "=" * 72
    )


if __name__ == "__main__":
    main()