from pathlib import Path
import json
import subprocess
import time

from pyannote.audio import Pipeline


# ============================================================
# 설정
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent

FILE_IDS = [
    "1786",
    "5113",
    "2315",
    "5194",
]

MODEL_NAME = "pyannote/speaker-diarization-community-1"

CACHE_DIR = (
    PROJECT_ROOT
    / "results"
    / "pyannote_diarization_cache"
)


# ============================================================
# MP3 -> WAV
# ============================================================

def ensure_wav(file_id: str) -> Path:

    mp3_path = (
        PROJECT_ROOT
        / "test_sample"
        / f"{file_id}.mp3"
    )

    wav_path = (
        PROJECT_ROOT
        / "test_sample"
        / f"{file_id}_pyannote_16k.wav"
    )

    if wav_path.exists():

        print(
            f"    WAV exists: "
            f"{wav_path.name}"
        )

        return wav_path

    if not mp3_path.exists():

        raise FileNotFoundError(
            f"MP3 없음: {mp3_path}"
        )

    print(
        f"    MP3 -> WAV 변환: "
        f"{mp3_path.name}"
    )

    command = [
        "ffmpeg",
        "-y",
        "-i",
        str(mp3_path),
        "-ac",
        "1",
        "-ar",
        "16000",
        "-c:a",
        "pcm_s16le",
        str(wav_path),
    ]

    subprocess.run(
        command,
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    return wav_path


# ============================================================
# pyannote 파일 하나 실행 + 저장
# ============================================================

def diarize_and_cache(
    file_id: str,
    pipeline,
):

    cache_path = (
        CACHE_DIR
        / f"{file_id}.json"
    )

    # 이미 캐시가 있으면 다시 돌리지 않는다.
    if cache_path.exists():

        print(
            f"    [SKIP] cache already exists: "
            f"{cache_path.name}"
        )

        return {
            "file": file_id,
            "status": "CACHED",
            "cache_path": str(cache_path),
        }

    wav_path = ensure_wav(
        file_id
    )

    print(
        "    pyannote diarization 시작..."
    )

    start_time = time.perf_counter()

    output = pipeline(
        str(wav_path),
        num_speakers=2,
    )

    elapsed = (
        time.perf_counter()
        - start_time
    )

    segments = []

    speakers = set()

    for turn, speaker in (
        output.speaker_diarization
    ):

        speaker = str(speaker)

        speakers.add(
            speaker
        )

        segments.append(
            {
                "speaker": speaker,

                "start_sec":
                    float(turn.start),

                "end_sec":
                    float(turn.end),

                "start_ms":
                    float(turn.start) * 1000,

                "end_ms":
                    float(turn.end) * 1000,
            }
        )

    cache_data = {
        "file": file_id,

        "model": MODEL_NAME,

        "num_speakers_requested": 2,

        "speakers": sorted(
            speakers
        ),

        "speaker_count": len(
            speakers
        ),

        "segment_count": len(
            segments
        ),

        "elapsed_seconds": elapsed,

        "audio_file": wav_path.name,

        "segments": segments,
    }

    with open(
        cache_path,
        "w",
        encoding="utf-8",
    ) as f:

        json.dump(
            cache_data,
            f,
            ensure_ascii=False,
            indent=2,
        )

    print(
        f"    완료: "
        f"{len(segments)} segments"
    )

    print(
        f"    speakers: "
        f"{sorted(speakers)}"
    )

    print(
        f"    실행 시간: "
        f"{elapsed / 60:.2f}분"
    )

    print(
        f"    저장: "
        f"{cache_path}"
    )

    return {
        "file": file_id,
        "status": "CREATED",
        "speaker_count":
            len(speakers),
        "segment_count":
            len(segments),
        "elapsed_seconds":
            elapsed,
        "cache_path":
            str(cache_path),
    }


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 100)
    print("CACHE PYANNOTE DIARIZATION - UNRESOLVED 4")
    print("=" * 100)

    CACHE_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    print()
    print(
        f"Cache directory:\n"
        f"{CACHE_DIR}"
    )

    print()
    print("[1] pyannote 모델 로드 중...")

    pipeline = Pipeline.from_pretrained(
        MODEL_NAME
    )

    print("    모델 로드 완료")

    results = []

    total_start = (
        time.perf_counter()
    )

    for index, file_id in enumerate(
        FILE_IDS,
        start=1,
    ):

        print()
        print("=" * 100)

        print(
            f"[{index}/{len(FILE_IDS)}] "
            f"FILE: {file_id}"
        )

        print("=" * 100)

        try:

            result = diarize_and_cache(
                file_id,
                pipeline,
            )

        except Exception as exc:

            print(
                f"    [ERROR] "
                f"{type(exc).__name__}: "
                f"{exc}"
            )

            result = {
                "file": file_id,
                "status": "ERROR",
                "error":
                    f"{type(exc).__name__}: "
                    f"{exc}",
            }

        results.append(
            result
        )

    total_elapsed = (
        time.perf_counter()
        - total_start
    )

    # --------------------------------------------------------
    # 실행 요약도 별도로 저장
    # --------------------------------------------------------

    summary_path = (
        CACHE_DIR
        / "_cache_summary.json"
    )

    summary = {
        "model": MODEL_NAME,
        "files": FILE_IDS,
        "total_elapsed_seconds":
            total_elapsed,
        "results": results,
    }

    with open(
        summary_path,
        "w",
        encoding="utf-8",
    ) as f:

        json.dump(
            summary,
            f,
            ensure_ascii=False,
            indent=2,
        )

    # --------------------------------------------------------
    # 출력
    # --------------------------------------------------------

    print()
    print()
    print("=" * 100)
    print("CACHE SUMMARY")
    print("=" * 100)

    for result in results:

        file_id = result["file"]
        status = result["status"]

        if status == "CREATED":

            print(
                f"{file_id}: "
                f"CREATED | "
                f"speakers="
                f"{result['speaker_count']} | "
                f"segments="
                f"{result['segment_count']} | "
                f"time="
                f"{result['elapsed_seconds'] / 60:.2f} min"
            )

        elif status == "CACHED":

            print(
                f"{file_id}: "
                f"ALREADY CACHED"
            )

        else:

            print(
                f"{file_id}: ERROR"
            )

    print()
    print(
        f"Total time: "
        f"{total_elapsed / 60:.2f} min"
    )

    print(
        f"Summary saved:\n"
        f"{summary_path}"
    )

    print("=" * 100)

    print()
    print(
        "다음 실험부터는 이 JSON 캐시를 읽으면 되므로 "
        "pyannote를 다시 실행할 필요가 없습니다."
    )


if __name__ == "__main__":
    main()