from pathlib import Path
import json

from pyannote.audio import Pipeline


# ============================================================
# 경로 설정
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent

AUDIO_PATH = (
    PROJECT_ROOT
    / "test_sample"
    / "1786_pyannote_16k.wav"
)

GT_PATH = (
    PROJECT_ROOT
    / "test_sample"
    / "1786.json"
)

MODEL_NAME = "pyannote/speaker-diarization-community-1"


# ============================================================
# 시간 변환
# ============================================================

def time_to_seconds(time_string: str) -> float:
    """
    GT의 시간 문자열을 초(float)로 변환한다.

    예:
        00:03.593 -> 3.593
        01:12.500 -> 72.500
    """

    minutes, seconds = time_string.split(":")

    return (
        int(minutes) * 60
        + float(seconds)
    )


# ============================================================
# GT Q/A 구간 추출
# ============================================================

def extract_gt_segments(data):
    """
    AI-Hub GT JSON 내부의 모든 audio 항목을 찾아
    Q/A 구간을 추출한다.

    Q = 상담자
    A = 아동
    """

    segments = []

    def walk(obj):

        if isinstance(obj, dict):

            audio = obj.get("audio")

            if isinstance(audio, list):

                for item in audio:

                    if not isinstance(item, dict):
                        continue

                    role = item.get("type")

                    if role not in {"Q", "A"}:
                        continue

                    start = item.get("start")
                    end = item.get("end")
                    text = item.get("text", "")

                    if not start or not end:
                        continue

                    segments.append(
                        {
                            "role": role,
                            "start": time_to_seconds(start),
                            "end": time_to_seconds(end),
                            "text": text,
                        }
                    )

            for value in obj.values():
                walk(value)

        elif isinstance(obj, list):

            for item in obj:
                walk(item)

    walk(data)

    # 혹시 같은 audio 구조를 여러 번 순회하면서
    # 중복이 생기는 경우를 막는다.
    unique = {}

    for segment in segments:

        key = (
            segment["role"],
            segment["start"],
            segment["end"],
            segment["text"],
        )

        unique[key] = segment

    segments = list(unique.values())

    segments.sort(
        key=lambda x: (
            x["start"],
            x["end"],
        )
    )

    return segments


# ============================================================
# 시간 겹침 계산
# ============================================================

def overlap_seconds(
    start1,
    end1,
    start2,
    end2,
):
    """
    두 시간 구간이 겹치는 시간을 초 단위로 반환한다.
    """

    start = max(start1, start2)
    end = min(end1, end2)

    return max(
        0.0,
        end - start,
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 100)
    print("PYANNOTE vs GT Q/A EVALUATION - 1786")
    print("=" * 100)

    # --------------------------------------------------------
    # 파일 확인
    # --------------------------------------------------------

    if not AUDIO_PATH.exists():

        raise FileNotFoundError(
            f"WAV 파일을 찾을 수 없습니다:\n"
            f"{AUDIO_PATH}"
        )

    if not GT_PATH.exists():

        raise FileNotFoundError(
            f"GT JSON을 찾을 수 없습니다:\n"
            f"{GT_PATH}"
        )

    # --------------------------------------------------------
    # GT 읽기
    # --------------------------------------------------------

    print()
    print("[1] GT JSON 읽는 중...")

    with open(
        GT_PATH,
        "r",
        encoding="utf-8",
    ) as f:

        gt_data = json.load(f)

    gt_segments = extract_gt_segments(
        gt_data
    )

    q_segments = [
        x
        for x in gt_segments
        if x["role"] == "Q"
    ]

    a_segments = [
        x
        for x in gt_segments
        if x["role"] == "A"
    ]

    print(
        f"    Q(상담자) GT 구간: "
        f"{len(q_segments)}개"
    )

    print(
        f"    A(아동) GT 구간: "
        f"{len(a_segments)}개"
    )

    # --------------------------------------------------------
    # pyannote
    # --------------------------------------------------------

    print()
    print("[2] pyannote 모델 불러오는 중...")

    pipeline = Pipeline.from_pretrained(
        MODEL_NAME
    )

    print("    모델 로드 완료")

    print()
    print("[3] 화자 분리 실행 중...")
    print("    화자 수 = 2명으로 지정")

    output = pipeline(
        str(AUDIO_PATH),
        num_speakers=2,
    )

    diarization = output.speaker_diarization

    pyannote_segments = []

    for turn, speaker in diarization:

        pyannote_segments.append(
            {
                "speaker": str(speaker),
                "start": float(turn.start),
                "end": float(turn.end),
            }
        )

    speakers = sorted(
        set(
            x["speaker"]
            for x in pyannote_segments
        )
    )

    print(
        f"    pyannote 화자: "
        f"{speakers}"
    )

    print(
        f"    pyannote 구간 수: "
        f"{len(pyannote_segments)}"
    )

    # --------------------------------------------------------
    # Speaker ↔ GT overlap 계산
    # --------------------------------------------------------

    print()
    print("[4] GT Q/A와 시간 겹침 계산 중...")

    results = {}

    for speaker in speakers:

        speaker_segments = [
            x
            for x in pyannote_segments
            if x["speaker"] == speaker
        ]

        q_overlap = 0.0
        a_overlap = 0.0

        speaker_total = sum(
            x["end"] - x["start"]
            for x in speaker_segments
        )

        for pred in speaker_segments:

            for gt in q_segments:

                q_overlap += overlap_seconds(
                    pred["start"],
                    pred["end"],
                    gt["start"],
                    gt["end"],
                )

            for gt in a_segments:

                a_overlap += overlap_seconds(
                    pred["start"],
                    pred["end"],
                    gt["start"],
                    gt["end"],
                )

        qa_overlap = (
            q_overlap
            + a_overlap
        )

        if qa_overlap > 0:

            q_ratio = (
                q_overlap
                / qa_overlap
            )

            a_ratio = (
                a_overlap
                / qa_overlap
            )

        else:

            q_ratio = 0.0
            a_ratio = 0.0

        if q_overlap > a_overlap:

            mapped_role = "COUNSELOR"

        elif a_overlap > q_overlap:

            mapped_role = "CHILD"

        else:

            mapped_role = "UNKNOWN"

        results[speaker] = {
            "speaker_total": speaker_total,
            "q_overlap": q_overlap,
            "a_overlap": a_overlap,
            "q_ratio": q_ratio,
            "a_ratio": a_ratio,
            "mapped_role": mapped_role,
        }

    # --------------------------------------------------------
    # 결과 출력
    # --------------------------------------------------------

    print()
    print("=" * 100)
    print("RESULT")
    print("=" * 100)

    for speaker in speakers:

        result = results[speaker]

        print()
        print(f"[{speaker}]")

        print(
            f"  전체 발화 시간: "
            f"{result['speaker_total']:.2f} sec"
        )

        print(
            f"  Q(상담자) overlap: "
            f"{result['q_overlap']:.2f} sec"
        )

        print(
            f"  A(아동) overlap: "
            f"{result['a_overlap']:.2f} sec"
        )

        print()

        print(
            f"  Q 비율: "
            f"{result['q_ratio'] * 100:.2f}%"
        )

        print(
            f"  A 비율: "
            f"{result['a_ratio'] * 100:.2f}%"
        )

        print()

        print(
            f"  => GT 기준 역할: "
            f"{result['mapped_role']}"
        )

    # --------------------------------------------------------
    # 두 화자가 서로 다른 역할로 잘 나뉘었는지 확인
    # --------------------------------------------------------

    mapped_roles = [
        result["mapped_role"]
        for result in results.values()
    ]

    print()
    print("=" * 100)

    if (
        "COUNSELOR" in mapped_roles
        and
        "CHILD" in mapped_roles
    ):

        print(
            "[SUCCESS] "
            "pyannote의 두 화자가 GT 기준 "
            "상담자/아동으로 서로 다르게 매핑되었습니다."
        )

    else:

        print(
            "[CHECK] "
            "pyannote 화자와 GT 역할 매핑을 "
            "추가 확인해야 합니다."
        )

    print("=" * 100)

    # --------------------------------------------------------
    # 처음 20개 GT 구간도 같이 확인
    # --------------------------------------------------------

    print()
    print("=" * 100)
    print("GT SAMPLE - FIRST 20")
    print("=" * 100)

    for item in gt_segments[:20]:

        role_name = (
            "COUNSELOR"
            if item["role"] == "Q"
            else "CHILD"
        )

        print(
            f"{item['start']:8.3f} ~ "
            f"{item['end']:8.3f} | "
            f"{role_name:<10} | "
            f"{item['text']}"
        )


if __name__ == "__main__":
    main()