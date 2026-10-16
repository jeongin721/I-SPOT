import json
from pathlib import Path


# ============================================================
# 경로
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

SAMPLE_ID = "2730"

GT_JSONL = (
    PROJECT_ROOT
    / "data_prep"
    / "evaluation"
    / "ground_truth"
    / "gt_2876.jsonl"
)

DEEPGRAM_JSON = (
    PROJECT_ROOT
    / "data_prep"
    / "evaluation"
    / "deepgram"
    / "outputs"
    / f"{SAMPLE_ID}_deepgram.json"
)

ELEVENLABS_JSON = (
    PROJECT_ROOT
    / "data_prep"
    / "evaluation"
    / "elevenlabs"
    / "outputs"
    / f"{SAMPLE_ID}_elevenlabs.json"
)


# ============================================================
# GT load
# ============================================================

def load_gt_sample():

    with GT_JSONL.open(
        "r",
        encoding="utf-8"
    ) as f:

        for line in f:

            if not line.strip():
                continue

            row = json.loads(
                line
            )

            if str(
                row.get("sample_id")
            ).strip() == SAMPLE_ID:

                return row

    raise RuntimeError(
        f"GT에서 {SAMPLE_ID}를 찾지 못했습니다."
    )


# ============================================================
# Deepgram load
# ============================================================

def load_deepgram():

    with DEEPGRAM_JSON.open(
        "r",
        encoding="utf-8"
    ) as f:

        return json.load(f)


# ============================================================
# ElevenLabs load
# ============================================================

def load_elevenlabs():

    with ELEVENLABS_JSON.open(
        "r",
        encoding="utf-8"
    ) as f:

        return json.load(f)


# ============================================================
# 시간 표시
# ============================================================

def format_time(seconds):

    seconds = float(
        seconds
    )

    minutes = int(
        seconds // 60
    )

    remain = (
        seconds
        - minutes * 60
    )

    return (
        f"{minutes:02d}:"
        f"{remain:06.3f}"
    )


# ============================================================
# GT 출력
# ============================================================

def print_gt(gt):

    print()
    print(
        "=" * 80
    )
    print(
        "[GT Q/A TIMELINE]"
    )
    print(
        "=" * 80
    )

    utterances = gt.get(
        "utterances",
        []
    )

    for utt in utterances:

        role = utt.get(
            "role"
        )

        start = utt.get(
            "start"
        )

        end = utt.get(
            "end"
        )

        text = (
            utt.get("text")
            or ""
        ).strip()

        if (
            role not in (
                "CHILD",
                "COUNSELOR"
            )
            or start is None
            or end is None
        ):
            continue

        print(
            f"{format_time(start)} ~ "
            f"{format_time(end)} | "
            f"{role:10} | "
            f"{text}"
        )


# ============================================================
# Deepgram utterance 출력
# ============================================================

def print_deepgram(data):

    print()
    print(
        "=" * 80
    )
    print(
        "[DEEPGRAM TIMELINE]"
    )
    print(
        "=" * 80
    )

    normalized = data.get(
        "normalized",
        {}
    )

    speaker_count = normalized.get(
        "speaker_count",
        0
    )

    print(
        f"speaker_count = "
        f"{speaker_count}"
    )

    print()

    utterances = normalized.get(
        "utterances",
        []
    )

    if not utterances:

        print(
            "normalized.utterances 없음"
        )

        return

    for utt in utterances:

        speaker = utt.get(
            "speaker"
        )

        start = utt.get(
            "start"
        )

        end = utt.get(
            "end"
        )

        text = (
            utt.get("transcript")
            or utt.get("text")
            or ""
        ).strip()

        if (
            start is None
            or end is None
        ):
            continue

        print(
            f"{format_time(start)} ~ "
            f"{format_time(end)} | "
            f"SPK_{speaker} | "
            f"{text}"
        )


# ============================================================
# ElevenLabs word → 연속 speaker segment 병합
# ============================================================

def build_elevenlabs_segments(data):

    words = []

    for word in data.get(
        "words",
        []
    ):

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

        text = (
            word.get("text")
            or ""
        ).strip()

        if (
            speaker is None
            or start is None
            or end is None
            or not text
        ):
            continue

        words.append(
            {
                "speaker":
                    str(speaker),

                "start":
                    float(start),

                "end":
                    float(end),

                "text":
                    text,
            }
        )

    if not words:
        return []

    segments = []

    current = {
        "speaker":
            words[0]["speaker"],

        "start":
            words[0]["start"],

        "end":
            words[0]["end"],

        "texts":
            [words[0]["text"]],
    }

    for word in words[1:]:

        same_speaker = (
            word["speaker"]
            == current["speaker"]
        )

        gap = (
            word["start"]
            - current["end"]
        )

        # 같은 speaker이고
        # 단어 간 간격이 2초 이하이면
        # 같은 발화 segment로 합침
        if (
            same_speaker
            and gap <= 2.0
        ):

            current[
                "end"
            ] = word[
                "end"
            ]

            current[
                "texts"
            ].append(
                word[
                    "text"
                ]
            )

        else:

            segments.append(
                current
            )

            current = {
                "speaker":
                    word["speaker"],

                "start":
                    word["start"],

                "end":
                    word["end"],

                "texts":
                    [word["text"]],
            }

    segments.append(
        current
    )

    return segments


# ============================================================
# ElevenLabs 출력
# ============================================================

def print_elevenlabs(data):

    print()
    print(
        "=" * 80
    )
    print(
        "[ELEVENLABS TIMELINE]"
    )
    print(
        "=" * 80
    )

    segments = (
        build_elevenlabs_segments(
            data
        )
    )

    speaker_ids = sorted(
        {
            segment["speaker"]
            for segment
            in segments
        }
    )

    print(
        f"speaker_count = "
        f"{len(speaker_ids)}"
    )

    print(
        f"speakers = "
        f"{speaker_ids}"
    )

    print()

    for segment in segments:

        text = " ".join(
            segment[
                "texts"
            ]
        )

        print(
            f"{format_time(segment['start'])} ~ "
            f"{format_time(segment['end'])} | "
            f"{segment['speaker']} | "
            f"{text}"
        )


# ============================================================
# speaker word count
# ============================================================

def print_word_counts(
    deepgram,
    elevenlabs
):

    print()
    print(
        "=" * 80
    )
    print(
        "[SPEAKER WORD COUNT]"
    )
    print(
        "=" * 80
    )

    dg_counts = {}

    normalized = deepgram.get(
        "normalized",
        {}
    )

    for word in normalized.get(
        "words",
        []
    ):

        speaker = word.get(
            "speaker"
        )

        if speaker is None:
            continue

        speaker = str(
            speaker
        )

        dg_counts[
            speaker
        ] = (
            dg_counts.get(
                speaker,
                0
            )
            + 1
        )

    print(
        "Deepgram:"
    )

    for speaker, count in sorted(
        dg_counts.items()
    ):

        print(
            f"  speaker {speaker}: "
            f"{count} words"
        )

    el_counts = {}

    for word in elevenlabs.get(
        "words",
        []
    ):

        if word.get(
            "type"
        ) != "word":
            continue

        speaker = word.get(
            "speaker_id"
        )

        if speaker is None:
            continue

        speaker = str(
            speaker
        )

        el_counts[
            speaker
        ] = (
            el_counts.get(
                speaker,
                0
            )
            + 1
        )

    print()

    print(
        "ElevenLabs:"
    )

    for speaker, count in sorted(
        el_counts.items()
    ):

        print(
            f"  {speaker}: "
            f"{count} words"
        )


# ============================================================
# main
# ============================================================

def main():

    print(
        "=" * 80
    )

    print(
        f"I-SPOT {SAMPLE_ID} "
        "Diarization Timeline Inspection"
    )

    print(
        "=" * 80
    )

    gt = load_gt_sample()

    deepgram = load_deepgram()

    elevenlabs = load_elevenlabs()

    print_gt(
        gt
    )

    print_deepgram(
        deepgram
    )

    print_elevenlabs(
        elevenlabs
    )

    print_word_counts(
        deepgram,
        elevenlabs
    )

    print()
    print(
        "=" * 80
    )

    print(
        "확인 포인트"
    )

    print(
        "=" * 80
    )

    print(
        "1. GT에서는 COUNSELOR와 CHILD가 "
        "실제로 번갈아 나타나는지"
    )

    print(
        "2. Deepgram이 그 구간들을 "
        "하나의 speaker로 합쳤는지"
    )

    print(
        "3. ElevenLabs도 동일하게 "
        "하나의 speaker로 합쳤는지"
    )

    print(
        "4. STT 문장 자체는 정상인데 "
        "speaker label만 실패한 것인지"
    )


if __name__ == "__main__":
    main()