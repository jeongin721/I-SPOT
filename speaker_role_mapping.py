from collections import defaultdict

from evaluate_diarization import (
    load_ground_truth,
)


def overlap_ms(
    start1,
    end1,
    start2,
    end2,
):
    """
    두 시간 구간의 겹치는 길이를 ms 단위로 계산한다.
    """

    return max(
        0,
        min(end1, end2)
        - max(start1, start2),
    )


def map_speakers_to_roles(
    gt_segments,
    stt_segments,
):
    """
    Deepgram SPEAKER_n을
    GT의 Q/A 역할에 매핑한다.

    기준:
        각 speaker가 Q/A GT와
        시간상 얼마나 많이 겹치는지 누적한다.
    """

    scores = defaultdict(
        lambda: {
            "Q": 0,
            "A": 0,
        }
    )

    # --------------------------------------------------------
    # 1. STT speaker별 Q/A overlap 누적
    # --------------------------------------------------------

    for stt in stt_segments:

        speaker = stt.get(
            "speaker"
        )

        if speaker is None:
            continue

        stt_start = stt.get(
            "start_ms"
        )

        stt_end = stt.get(
            "end_ms"
        )

        if (
            stt_start is None
            or stt_end is None
        ):
            continue

        for gt in gt_segments:

            role = gt.get(
                "speaker"
            )

            if role not in {
                "Q",
                "A",
            }:
                continue

            gt_start = gt.get(
                "start_ms"
            )

            gt_end = gt.get(
                "end_ms"
            )

            if (
                gt_start is None
                or gt_end is None
            ):
                continue

            overlap = overlap_ms(
                stt_start,
                stt_end,
                gt_start,
                gt_end,
            )

            if overlap > 0:
                scores[speaker][role] += (
                    overlap
                )

    # --------------------------------------------------------
    # 2. speaker별 role 결정
    # --------------------------------------------------------

    mapping = {}

    for speaker, role_scores in scores.items():

        q_score = role_scores["Q"]
        a_score = role_scores["A"]

        total = (
            q_score + a_score
        )

        if total == 0:

            role = "UNKNOWN"
            confidence = 0.0

        else:

            q_ratio = q_score / total
            a_ratio = a_score / total

            if q_ratio >= a_ratio:
                candidate_role = "Q"
                confidence = q_ratio
            else:
                candidate_role = "A"
                confidence = a_ratio

            # 신뢰도가 낮으면 강제로 Q/A에 배정하지 않음
            if confidence >= 0.80:
                role = candidate_role
            else:
                role = "UNKNOWN"


        mapping[speaker] = {
            "role": role,

            "q_overlap_ms":
                q_score,

            "a_overlap_ms":
                a_score,

            "confidence":
                round(
                    confidence,
                    4,
                ),
        }

    return mapping


if __name__ == "__main__":

    import json
    from pathlib import Path

    gt_path = Path(
        "test_sample/0005.json"
    )

    stt_path = Path(
        "test_sample/0005_stt.json"
    )

    gt_segments = load_ground_truth(
        gt_path
    )

    with open(
        stt_path,
        "r",
        encoding="utf-8",
    ) as f:

        data = json.load(f)

    stt_segments = (
        data
        .get("stt_data", {})
        .get("segments", [])
    )

    print("GT 첫 번째 segment:")
    print(gt_segments[0])

    print()

    print("STT 첫 번째 segment:")
    print(stt_segments[0])

    mapping = map_speakers_to_roles(
        gt_segments,
        stt_segments,
    )

    print()
    print("=" * 60)
    print("Speaker Role Mapping")
    print("=" * 60)

    for speaker, info in mapping.items():

        print()
        print(
            f"[{speaker}]"
        )

        print(
            f"Role            : "
            f"{info['role']}"
        )

        print(
            f"Q overlap       : "
            f"{info['q_overlap_ms']} ms"
        )

        print(
            f"A overlap       : "
            f"{info['a_overlap_ms']} ms"
        )

        print(
            f"Confidence      : "
            f"{info['confidence']:.4f}"
        )

    print()
    print("=" * 60)