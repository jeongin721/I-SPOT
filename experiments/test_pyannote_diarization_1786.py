from pathlib import Path
import subprocess

from pyannote.audio import Pipeline


PROJECT_ROOT = Path(__file__).resolve().parent.parent

AUDIO_PATH = (
    PROJECT_ROOT
    / "test_sample"
    / "1786.mp3"
)

WAV_PATH = (
    PROJECT_ROOT
    / "test_sample"
    / "1786_pyannote_16k.wav"
)

MODEL_NAME = "pyannote/speaker-diarization-community-1"


def format_time(seconds: float) -> str:
    minutes = int(seconds // 60)
    remaining = seconds % 60

    return f"{minutes:02d}:{remaining:06.3f}"


def convert_mp3_to_wav():
    """
    MP3를 pyannote 분석용
    16kHz / mono / PCM WAV로 변환한다.

    원본 MP3는 수정하지 않는다.
    """

    print()
    print("[1] MP3 -> WAV 변환")

    command = [
        "ffmpeg",
        "-y",
        "-i",
        str(AUDIO_PATH),
        "-ac",
        "1",
        "-ar",
        "16000",
        "-c:a",
        "pcm_s16le",
        str(WAV_PATH),
    ]

    subprocess.run(
        command,
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    print(f"    생성 완료: {WAV_PATH.name}")


def main():

    print("=" * 100)
    print("PYANNOTE DIARIZATION TEST - 1786")
    print("=" * 100)

    if not AUDIO_PATH.exists():
        raise FileNotFoundError(
            f"음성 파일을 찾을 수 없습니다: {AUDIO_PATH}"
        )

    print()
    print(f"Original audio: {AUDIO_PATH.name}")
    print(f"Model: {MODEL_NAME}")

    # --------------------------------------------------
    # 1. MP3 -> WAV
    # --------------------------------------------------

    convert_mp3_to_wav()

    # --------------------------------------------------
    # 2. pyannote 모델 로드
    # --------------------------------------------------

    print()
    print("[2] pyannote 모델 불러오는 중...")

    pipeline = Pipeline.from_pretrained(
        MODEL_NAME
    )

    print("    모델 로드 완료")

    # --------------------------------------------------
    # 3. 화자 분리
    # --------------------------------------------------

    print()
    print("[3] 1786 WAV 화자 분리 시작...")
    print("    상담자 + 아동 = 화자 수 2명으로 지정")

    output = pipeline(
        str(WAV_PATH),
        num_speakers=2,
    )

    print()
    print("[4] 화자 분리 완료")

    # Community-1 / pyannote.audio 4.x
    diarization = output.speaker_diarization

    speakers = set()
    segments = []

    for turn, speaker in diarization:

        speaker = str(speaker)

        speakers.add(speaker)

        segments.append(
            {
                "start": float(turn.start),
                "end": float(turn.end),
                "speaker": speaker,
            }
        )

    # --------------------------------------------------
    # 4. 결과 출력
    # --------------------------------------------------

    print()
    print("=" * 100)
    print("RESULT")
    print("=" * 100)

    print(f"Detected speakers: {sorted(speakers)}")
    print(f"Speaker count: {len(speakers)}")
    print(f"Diarization segments: {len(segments)}")

    print()
    print("-" * 100)
    print("START        END          SPEAKER")
    print("-" * 100)

    for item in segments:

        print(
            f"{format_time(item['start']):<12} "
            f"{format_time(item['end']):<12} "
            f"{item['speaker']}"
        )

    print()
    print("=" * 100)

    if len(speakers) == 2:

        print(
            "[SUCCESS] "
            "pyannote가 2개 화자 트랙으로 분리했습니다."
        )

    else:

        print(
            "[CHECK] "
            f"화자 수가 {len(speakers)}명으로 나왔습니다."
        )

    print("=" * 100)


if __name__ == "__main__":
    main()