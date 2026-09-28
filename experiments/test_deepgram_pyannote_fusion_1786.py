from pathlib import Path
import json
import re

from pyannote.audio import Pipeline


# ============================================================
# 프로젝트 import
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent

import sys

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from abuse_model.infer_abuse import predict_abuse


# ============================================================
# 경로
# ============================================================

FILE_ID = "1786"

WAV_PATH = (
    PROJECT_ROOT
    / "test_sample"
    / f"{FILE_ID}_pyannote_16k.wav"
)

STT_PATH = (
    PROJECT_ROOT
    / "test_sample"
    / f"{FILE_ID}_stt.json"
)

MODEL_NAME = "pyannote/speaker-diarization-community-1"


# ============================================================
# 질문 판별
# ============================================================

QUESTION_ENDINGS = (
    "나요",
    "가요",
    "까요",
    "인가요",
    "있나요",
    "없나요",
    "했나요",
    "하나요",
    "해요",
    "예요",
    "이에요",
    "니",
    "나요",
)


def is_question(text: str) -> bool:
    """
    기존 runtime mapper와 비슷한 목적의 간단한 질문 판별.
    pyannote speaker의 역할을 GT 없이 추론하기 위해 사용한다.
    """

    text = text.strip()

    if not text:
        return False

    if text.endswith("?"):
        return True

    clean = re.sub(
        r"[.!~\s]+$",
        "",
        text,
    )

    return clean.endswith(QUESTION_ENDINGS)


# ============================================================
# Deepgram word 추출
# ============================================================

def collect_words(obj):
    """
    저장된 STT JSON 전체를 재귀 탐색해서
    word/start_ms/end_ms를 가진 Deepgram word를 찾는다.
    """

    found = []

    def walk(value):

        if isinstance(value, dict):

            word = value.get("word")

            start_ms = value.get("start_ms")
            end_ms = value.get("end_ms")

            if (
                isinstance(word, str)
                and start_ms is not None
                and end_ms is not None
            ):

                try:

                    found.append(
                        {
                            "word": word.strip(),
                            "start_ms": float(start_ms),
                            "end_ms": float(end_ms),
                        }
                    )

                except (TypeError, ValueError):
                    pass

            for child in value.values():
                walk(child)

        elif isinstance(value, list):

            for child in value:
                walk(child)

    walk(obj)

    # --------------------------------------------------------
    # 중복 제거
    # --------------------------------------------------------

    unique = {}

    for item in found:

        if not item["word"]:
            continue

        key = (
            item["word"],
            item["start_ms"],
            item["end_ms"],
        )

        unique[key] = item

    words = list(unique.values())

    words.sort(
        key=lambda x: (
            x["start_ms"],
            x["end_ms"],
        )
    )

    return words


# ============================================================
# 시간 overlap
# ============================================================

def overlap_ms(
    start1,
    end1,
    start2,
    end2,
):
    return max(
        0.0,
        min(end1, end2)
        - max(start1, start2),
    )


# ============================================================
# pyannote 화자 → Deepgram word 배정
# ============================================================

def assign_word_to_speaker(
    word,
    diarization_segments,
):
    """
    Deepgram 단어의 시간과 가장 많이 겹치는
    pyannote speaker를 선택한다.

    overlap이 전혀 없으면 단어 중앙점과
    가장 가까운 pyannote 구간을 사용한다.
    """

    word_start = word["start_ms"]
    word_end = word["end_ms"]

    best_speaker = None
    best_overlap = 0.0

    for segment in diarization_segments:

        overlap = overlap_ms(
            word_start,
            word_end,
            segment["start_ms"],
            segment["end_ms"],
        )

        if overlap > best_overlap:

            best_overlap = overlap
            best_speaker = segment["speaker"]

    if best_speaker is not None:
        return best_speaker

    # --------------------------------------------------------
    # overlap이 없는 경우
    # --------------------------------------------------------

    midpoint = (
        word_start
        + word_end
    ) / 2

    best_distance = None

    for segment in diarization_segments:

        if midpoint < segment["start_ms"]:

            distance = (
                segment["start_ms"]
                - midpoint
            )

        elif midpoint > segment["end_ms"]:

            distance = (
                midpoint
                - segment["end_ms"]
            )

        else:

            distance = 0.0

        if (
            best_distance is None
            or distance < best_distance
        ):

            best_distance = distance
            best_speaker = segment["speaker"]

    return best_speaker


# ============================================================
# 단어 → 발화 묶기
# ============================================================

def build_utterances(
    assigned_words,
    max_gap_ms=1200,
):
    """
    같은 speaker의 연속 단어를 하나의 발화로 묶는다.

    1.2초 이상 침묵이 있으면 같은 화자라도
    새 발화로 나눈다.
    """

    utterances = []

    current = None

    for word in assigned_words:

        speaker = word["speaker"]

        if speaker is None:
            continue

        if current is None:

            current = {
                "speaker": speaker,
                "start_ms": word["start_ms"],
                "end_ms": word["end_ms"],
                "words": [word["word"]],
            }

            continue

        gap = (
            word["start_ms"]
            - current["end_ms"]
        )

        same_speaker = (
            speaker
            == current["speaker"]
        )

        if (
            same_speaker
            and gap <= max_gap_ms
        ):

            current["words"].append(
                word["word"]
            )

            current["end_ms"] = (
                word["end_ms"]
            )

        else:

            current["text"] = " ".join(
                current["words"]
            ).strip()

            utterances.append(
                current
            )

            current = {
                "speaker": speaker,
                "start_ms": word["start_ms"],
                "end_ms": word["end_ms"],
                "words": [word["word"]],
            }

    if current is not None:

        current["text"] = " ".join(
            current["words"]
        ).strip()

        utterances.append(
            current
        )

    return utterances


# ============================================================
# GT 없이 역할 추론
# ============================================================

def infer_roles(
    utterances,
    speakers,
):
    """
    질문 비율이 높은 화자를 COUNSELOR,
    낮은 화자를 CHILD로 추론한다.

    이번 실험에서는 GT Q/A 정보를 절대 사용하지 않는다.
    """

    stats = {}

    for speaker in speakers:

        speaker_utterances = [
            x
            for x in utterances
            if x["speaker"] == speaker
            and x["text"]
        ]

        question_count = sum(
            1
            for x in speaker_utterances
            if is_question(x["text"])
        )

        total = len(
            speaker_utterances
        )

        question_ratio = (
            question_count / total
            if total
            else 0.0
        )

        stats[speaker] = {
            "utterance_count": total,
            "question_count": question_count,
            "question_ratio": question_ratio,
        }

    if len(speakers) != 2:

        return {}, stats

    ordered = sorted(
        speakers,
        key=lambda speaker:
        stats[speaker]["question_ratio"],
        reverse=True,
    )

    counselor = ordered[0]
    child = ordered[1]

    roles = {
        counselor: "COUNSELOR",
        child: "CHILD",
    }

    return roles, stats


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 100)
    print("DEEPGRAM + PYANNOTE FUSION TEST - 1786")
    print("=" * 100)

    if not WAV_PATH.exists():

        raise FileNotFoundError(
            f"WAV 파일 없음:\n{WAV_PATH}"
        )

    if not STT_PATH.exists():

        raise FileNotFoundError(
            f"STT JSON 없음:\n{STT_PATH}"
        )

    # --------------------------------------------------------
    # 1. 저장된 Deepgram STT
    # --------------------------------------------------------

    print()
    print("[1] Deepgram STT JSON 읽는 중...")

    with open(
        STT_PATH,
        "r",
        encoding="utf-8",
    ) as f:

        stt_data = json.load(f)

    words = collect_words(
        stt_data
    )

    print(
        f"    Deepgram words: "
        f"{len(words)}"
    )

    if not words:

        raise RuntimeError(
            "Deepgram word timestamp를 찾지 못했습니다."
        )

    # --------------------------------------------------------
    # 2. pyannote
    # --------------------------------------------------------

    print()
    print("[2] pyannote 모델 로드 중...")

    pipeline = Pipeline.from_pretrained(
        MODEL_NAME
    )

    print("    모델 로드 완료")

    print()
    print("[3] pyannote 화자 분리 실행 중...")

    output = pipeline(
        str(WAV_PATH),
        num_speakers=2,
    )

    diarization = (
        output.speaker_diarization
    )

    diarization_segments = []

    for turn, speaker in diarization:

        diarization_segments.append(
            {
                "speaker": str(speaker),

                "start_ms":
                    float(turn.start)
                    * 1000,

                "end_ms":
                    float(turn.end)
                    * 1000,
            }
        )

    speakers = sorted(
        set(
            x["speaker"]
            for x in diarization_segments
        )
    )

    print(
        f"    pyannote speakers: "
        f"{speakers}"
    )

    # --------------------------------------------------------
    # 3. Deepgram word ↔ pyannote 결합
    # --------------------------------------------------------

    print()
    print(
        "[4] Deepgram words에 "
        "pyannote speaker 배정 중..."
    )

    assigned_words = []

    for word in words:

        speaker = assign_word_to_speaker(
            word,
            diarization_segments,
        )

        assigned_words.append(
            {
                **word,
                "speaker": speaker,
            }
        )

    assigned_count = sum(
        1
        for x in assigned_words
        if x["speaker"] is not None
    )

    print(
        f"    speaker 배정: "
        f"{assigned_count}/{len(words)} words"
    )

    # --------------------------------------------------------
    # 4. 발화 생성
    # --------------------------------------------------------

    utterances = build_utterances(
        assigned_words
    )

    print(
        f"    fusion utterances: "
        f"{len(utterances)}"
    )

    # --------------------------------------------------------
    # 5. 역할 추론
    # --------------------------------------------------------

    print()
    print("[5] GT 없이 역할 추론...")

    roles, stats = infer_roles(
        utterances,
        speakers,
    )

    print()

    for speaker in speakers:

        stat = stats[speaker]

        print(
            f"    {speaker}: "
            f"utterances="
            f"{stat['utterance_count']}, "
            f"questions="
            f"{stat['question_count']}, "
            f"question_ratio="
            f"{stat['question_ratio']:.3f}"
        )

    print()

    for speaker, role in roles.items():

        print(
            f"    {speaker} "
            f"=> {role}"
        )

    child_speakers = [
        speaker
        for speaker, role
        in roles.items()
        if role == "CHILD"
    ]

    if len(child_speakers) != 1:

        raise RuntimeError(
            "CHILD speaker를 하나로 "
            "결정하지 못했습니다."
        )

    child_speaker = (
        child_speakers[0]
    )

    # --------------------------------------------------------
    # 6. CHILD text
    # --------------------------------------------------------

    child_utterances = [
        x
        for x in utterances
        if x["speaker"]
        == child_speaker
    ]

    child_text = " ".join(
        x["text"]
        for x in child_utterances
        if x["text"]
    ).strip()

    print()
    print("=" * 100)
    print("CHILD TEXT")
    print("=" * 100)

    print(
        f"Child speaker: "
        f"{child_speaker}"
    )

    print(
        f"Child utterances: "
        f"{len(child_utterances)}"
    )

    print(
        f"Child text length: "
        f"{len(child_text)} chars"
    )

    print()
    print(child_text)

    # --------------------------------------------------------
    # 7. RoBERTa
    # --------------------------------------------------------

    print()
    print("=" * 100)
    print("ROBERTA RESULT")
    print("=" * 100)

    if not child_text:

        raise RuntimeError(
            "CHILD text가 비어 있습니다."
        )

    prediction = predict_abuse(
        child_text
    )

    print(
        json.dumps(
            prediction,
            ensure_ascii=False,
            indent=2,
        )
    )

    # --------------------------------------------------------
    # 8. 이번 실험의 기준값 표시
    # --------------------------------------------------------

    print()
    print("=" * 100)
    print("REFERENCE - GT A-TEXT RESULT")
    print("=" * 100)

    print(
        "1786 GT A-text 기준:\n"
        "  신체학대: False  (~0.62%)\n"
        "  정서학대: True   (~99.50%)\n"
        "  성학대:   False  (~0.27%)\n"
        "  방임:     False  (~0.31%)"
    )

    print()
    print(
        "특히 확인할 것:"
    )

    print(
        "  1. 정서학대가 True인지"
    )

    print(
        "  2. 방임이 False로 유지되는지"
    )

    print()
    print(
        "이전 regex 단일화자 복구에서는 "
        "방임이 약 97.11% True로 오탐되었습니다."
    )

    print("=" * 100)


if __name__ == "__main__":
    main()