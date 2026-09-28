import json
import time
from pathlib import Path

from dotenv import load_dotenv

from stt.ispot_stt import DeepgramSTTProvider
from stt.ispot_postprocess import STTPostProcessor


# ============================================================
# 1. 설정
# ============================================================

BASE_DIR = Path(__file__).resolve().parent
SAMPLE_DIR = BASE_DIR / "test_sample"

load_dotenv()

provider = DeepgramSTTProvider()
postprocessor = STTPostProcessor()


# ============================================================
# 2. STT 결과 저장
# ============================================================

def save_stt_result(
    mp3_path: Path,
    processed_result: dict,
):

    output_path = (
        SAMPLE_DIR
        / f"{mp3_path.stem}_stt.json"
    )

    result = {
        "status": "success",
        "file_name": mp3_path.name,
        "stt_data": processed_result,
    }

    with open(
        output_path,
        "w",
        encoding="utf-8",
    ) as f:

        json.dump(
            result,
            f,
            ensure_ascii=False,
            indent=2,
        )

    return output_path


# ============================================================
# 3. 실패 로그 저장
# ============================================================

def save_error_log(errors):

    error_path = (
        SAMPLE_DIR
        / "batch_stt_errors.json"
    )

    with open(
        error_path,
        "w",
        encoding="utf-8",
    ) as f:

        json.dump(
            errors,
            f,
            ensure_ascii=False,
            indent=2,
        )

    return error_path


# ============================================================
# 4. Main
# ============================================================

def main():

    print()
    print("=" * 75)
    print("I-SPOT 30 Sample STT Batch")
    print("=" * 75)

    mp3_files = sorted(
        SAMPLE_DIR.glob("*.mp3")
    )

    # child_audio 폴더 안 파일은 glob("*.mp3")에 안 잡히므로 안전
    total_mp3 = len(mp3_files)

    print(
        f"전체 MP3 수 : {total_mp3}"
    )

    if total_mp3 == 0:

        print(
            "처리할 MP3가 없습니다."
        )
        return

    skip_count = 0
    success_count = 0
    fail_count = 0

    errors = []

    start_time = time.time()

    for index, mp3_path in enumerate(
        mp3_files,
        start=1,
    ):

        stt_output_path = (
            SAMPLE_DIR
            / f"{mp3_path.stem}_stt.json"
        )

        print()
        print(
            f"[{index:02d}/{total_mp3:02d}] "
            f"{mp3_path.name}"
        )

        # ----------------------------------------
        # 기존 결과가 있으면 API 재호출 안 함
        # ----------------------------------------

        if stt_output_path.exists():

            print(
                f"SKIP → "
                f"{stt_output_path.name} 이미 존재"
            )

            skip_count += 1
            continue

        try:

            file_start = time.time()

            print(
                "Deepgram STT 요청 중..."
            )

            raw_result = provider.transcribe(
                str(mp3_path)
            )

            processed_result = (
                postprocessor.process(
                    raw_result
                )
            )

            output_path = save_stt_result(
                mp3_path,
                processed_result,
            )

            elapsed = (
                time.time()
                - file_start
            )

            segment_count = len(
                processed_result.get(
                    "segments",
                    [],
                )
            )

            print(
                f"SUCCESS"
            )

            print(
                f"Segments : "
                f"{segment_count}"
            )

            print(
                f"Time     : "
                f"{elapsed:.2f} sec"
            )

            print(
                f"Saved    : "
                f"{output_path.name}"
            )

            success_count += 1

        except Exception as e:

            fail_count += 1

            error_info = {
                "file": mp3_path.name,
                "error_type": type(e).__name__,
                "error": str(e),
            }

            errors.append(
                error_info
            )

            print(
                f"FAILED"
            )

            print(
                f"{type(e).__name__}: "
                f"{e}"
            )

            # 한 파일 실패해도 다음 파일 계속 진행
            continue


    # ========================================================
    # 5. Summary
    # ========================================================

    total_elapsed = (
        time.time()
        - start_time
    )

    print()
    print("=" * 75)
    print("STT Batch 완료")
    print("=" * 75)

    print(
        f"전체 MP3      : "
        f"{total_mp3}"
    )

    print(
        f"기존 결과 SKIP: "
        f"{skip_count}"
    )

    print(
        f"신규 성공      : "
        f"{success_count}"
    )

    print(
        f"실패           : "
        f"{fail_count}"
    )

    print(
        f"총 소요시간    : "
        f"{total_elapsed / 60:.2f} min"
    )

    if errors:

        error_path = save_error_log(
            errors
        )

        print()
        print(
            f"오류 로그 저장 → "
            f"{error_path}"
        )

    print()
    print(
        f"STT JSON 위치 → "
        f"{SAMPLE_DIR}"
    )

    print("=" * 75)


if __name__ == "__main__":
    main()