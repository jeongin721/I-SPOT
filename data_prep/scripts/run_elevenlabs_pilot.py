import csv
import json
import os
import time
import zipfile
from pathlib import Path

from dotenv import load_dotenv
from elevenlabs.client import ElevenLabs


# ============================================================
# 경로
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

ENV_PATH = PROJECT_ROOT / ".env"

TS_ZIP = Path(
    r"C:\Users\USER\Desktop\헬스케어 4조\024.아동·청소년_상담_데이터"
    r"\3.개방데이터\1.데이터\Training\01.원천데이터\TS_in.zip"
)

PILOT_CSV = (
    PROJECT_ROOT
    / "data_prep"
    / "evaluation"
    / "deepgram"
    / "pilot_100.csv"
)

OUTPUT_DIR = (
    PROJECT_ROOT
    / "data_prep"
    / "evaluation"
    / "elevenlabs"
    / "outputs"
)

SUMMARY_CSV = (
    PROJECT_ROOT
    / "data_prep"
    / "evaluation"
    / "elevenlabs"
    / "run_summary.csv"
)

ERROR_JSONL = (
    PROJECT_ROOT
    / "data_prep"
    / "evaluation"
    / "elevenlabs"
    / "errors.jsonl"
)

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True
)


# ============================================================
# 설정
# ============================================================

MODEL_ID = "scribe_v2"

MAX_RETRIES = 3

RETRY_WAIT_SECONDS = 5


# ============================================================
# quota 초과 여부 확인
# ============================================================

def is_quota_exceeded(error):
    """
    ElevenLabs 크레딧이 모두 소진된 경우인지 확인한다.

    quota_exceeded는 잠깐 기다린다고 해결되는 오류가 아니다.
    따라서 일반적인 네트워크 오류처럼 재시도하면 안 된다.
    """

    error_text = str(error).lower()

    quota_keywords = [
        "quota_exceeded",
        "quota exceeded",
        "credits remaining",
        "0 credits remaining",
        "exceeds your quota",
    ]

    return any(
        keyword in error_text
        for keyword in quota_keywords
    )


# ============================================================
# 객체 → dict
# ============================================================

def obj_to_dict(obj):

    if obj is None:
        return None

    if isinstance(
        obj,
        (str, int, float, bool)
    ):
        return obj

    if isinstance(obj, list):

        return [
            obj_to_dict(x)
            for x in obj
        ]

    if isinstance(obj, dict):

        return {
            k: obj_to_dict(v)
            for k, v in obj.items()
        }

    if hasattr(obj, "model_dump"):

        return obj_to_dict(
            obj.model_dump()
        )

    if hasattr(obj, "dict"):

        return obj_to_dict(
            obj.dict()
        )

    if hasattr(obj, "__dict__"):

        return {
            k: obj_to_dict(v)
            for k, v
            in vars(obj).items()
            if not k.startswith("_")
        }

    return str(obj)


# ============================================================
# Pilot CSV
# ============================================================

def load_pilot():

    with PILOT_CSV.open(
        "r",
        encoding="utf-8-sig",
        newline=""
    ) as f:

        return list(
            csv.DictReader(f)
        )


# ============================================================
# MP3 검색
# ============================================================

def build_audio_index(
    zf: zipfile.ZipFile
):

    index = {}

    for name in zf.namelist():

        if not name.lower().endswith(
            ".mp3"
        ):
            continue

        sample_id = Path(name).stem

        index[sample_id] = name

    return index


# ============================================================
# JSON 유효성 검사
# ============================================================

def valid_existing_json(
    path: Path
):

    if not path.exists():
        return False

    try:

        with path.open(
            "r",
            encoding="utf-8"
        ) as f:

            data = json.load(f)

        if not isinstance(
            data,
            dict
        ):
            return False

        if "words" not in data:
            return False

        return True

    except Exception:

        return False


# ============================================================
# speaker 통계
# ============================================================

def get_speaker_stats(data):

    words = data.get(
        "words",
        []
    )

    speaker_ids = []

    word_count = 0

    for item in words:

        if not isinstance(
            item,
            dict
        ):
            continue

        # spacing / audio_event 제외
        if item.get("type") != "word":
            continue

        word_count += 1

        speaker_id = item.get(
            "speaker_id"
        )

        if (
            speaker_id is not None
            and speaker_id
            not in speaker_ids
        ):
            speaker_ids.append(
                speaker_id
            )

    return (
        speaker_ids,
        word_count
    )


# ============================================================
# 에러 기록
# ============================================================

def log_error(
    sample_id,
    error
):

    record = {
        "sample_id": sample_id,
        "error": str(error),
    }

    with ERROR_JSONL.open(
        "a",
        encoding="utf-8"
    ) as f:

        f.write(
            json.dumps(
                record,
                ensure_ascii=False
            )
            + "\n"
        )


# ============================================================
# Summary 저장
# ============================================================

def save_summary(rows):

    fields = [
        "sample_id",
        "status",
        "speaker_count",
        "speaker_ids",
        "word_count",
        "audio_duration_secs",
        "language_code",
        "language_probability",
        "elapsed_seconds",
        "error",
    ]

    with SUMMARY_CSV.open(
        "w",
        encoding="utf-8-sig",
        newline=""
    ) as f:

        writer = csv.DictWriter(
            f,
            fieldnames=fields
        )

        writer.writeheader()
        writer.writerows(rows)


# ============================================================
# main
# ============================================================

def main():

    load_dotenv(
        ENV_PATH
    )

    api_key = os.getenv(
        "ELEVENLABS_API_KEY"
    )

    if not api_key:

        raise RuntimeError(
            "ELEVENLABS_API_KEY가 "
            ".env에 없습니다."
        )

    client = ElevenLabs(
        api_key=api_key
    )

    pilot_rows = load_pilot()

    print("=" * 72)
    print(
        "I-SPOT ElevenLabs "
        "Scribe v2 Pilot 100"
    )
    print("=" * 72)

    print(
        f"대상 샘플: "
        f"{len(pilot_rows)}"
    )

    print(
        f"모델: {MODEL_ID}"
    )

    print(
        "diarization: ON"
    )

    print(
        "num_speakers: 지정하지 않음"
    )

    print()

    summary_rows = []

    success_count = 0
    skip_count = 0
    fail_count = 0

    # quota가 떨어졌는지 기록
    quota_exhausted = False

    with zipfile.ZipFile(
        TS_ZIP,
        "r"
    ) as zf:

        audio_index = (
            build_audio_index(zf)
        )

        for idx, row in enumerate(
            pilot_rows,
            start=1
        ):

            sample_id = str(
                row["sample_id"]
            ).strip()

            output_path = (
                OUTPUT_DIR
                / f"{sample_id}_elevenlabs.json"
            )

            # ------------------------------------------------
            # 이미 정상 결과가 있으면 SKIP
            # ------------------------------------------------

            if valid_existing_json(
                output_path
            ):

                with output_path.open(
                    "r",
                    encoding="utf-8"
                ) as f:

                    existing = json.load(f)

                speaker_ids, word_count = (
                    get_speaker_stats(
                        existing
                    )
                )

                summary_rows.append(
                    {
                        "sample_id":
                            sample_id,

                        "status":
                            "SKIPPED_EXISTING",

                        "speaker_count":
                            len(
                                speaker_ids
                            ),

                        "speaker_ids":
                            ",".join(
                                speaker_ids
                            ),

                        "word_count":
                            word_count,

                        "audio_duration_secs":
                            existing.get(
                                "audio_duration_secs",
                                ""
                            ),

                        "language_code":
                            existing.get(
                                "language_code",
                                ""
                            ),

                        "language_probability":
                            existing.get(
                                "language_probability",
                                ""
                            ),

                        "elapsed_seconds":
                            "",

                        "error":
                            "",
                    }
                )

                skip_count += 1

                print(
                    f"[{idx:03d}/"
                    f"{len(pilot_rows)}] "
                    f"{sample_id} "
                    f"SKIP "
                    f"(speakers="
                    f"{len(speaker_ids)})"
                )

                continue

            # ------------------------------------------------
            # MP3 확인
            # ------------------------------------------------

            mp3_name = audio_index.get(
                sample_id
            )

            if mp3_name is None:

                error_message = (
                    "MP3_NOT_FOUND"
                )

                print(
                    f"[{idx:03d}/"
                    f"{len(pilot_rows)}] "
                    f"{sample_id} "
                    f"FAIL - "
                    f"{error_message}"
                )

                log_error(
                    sample_id,
                    error_message
                )

                summary_rows.append(
                    {
                        "sample_id":
                            sample_id,

                        "status":
                            "FAILED",

                        "speaker_count":
                            "",

                        "speaker_ids":
                            "",

                        "word_count":
                            "",

                        "audio_duration_secs":
                            "",

                        "language_code":
                            "",

                        "language_probability":
                            "",

                        "elapsed_seconds":
                            "",

                        "error":
                            error_message,
                    }
                )

                fail_count += 1

                save_summary(
                    summary_rows
                )

                continue

            audio_bytes = zf.read(
                mp3_name
            )

            # ------------------------------------------------
            # API 호출
            # ------------------------------------------------

            final_error = None

            for attempt in range(
                1,
                MAX_RETRIES + 1
            ):

                try:

                    print(
                        f"[{idx:03d}/"
                        f"{len(pilot_rows)}] "
                        f"{sample_id} "
                        f"호출 중 "
                        f"(시도 "
                        f"{attempt}/"
                        f"{MAX_RETRIES})..."
                    )

                    started = (
                        time.perf_counter()
                    )

                    response = (
                        client
                        .speech_to_text
                        .convert(
                            file=audio_bytes,
                            model_id=MODEL_ID,
                            language_code="kor",
                            diarize=True,
                            tag_audio_events=False,
                        )
                    )

                    elapsed = (
                        time.perf_counter()
                        - started
                    )

                    data = obj_to_dict(
                        response
                    )

                    # ----------------------------------------
                    # JSON 저장
                    # ----------------------------------------

                    with output_path.open(
                        "w",
                        encoding="utf-8"
                    ) as f:

                        json.dump(
                            data,
                            f,
                            ensure_ascii=False,
                            indent=2,
                            default=str
                        )

                    # 저장된 JSON 재검증
                    if not valid_existing_json(
                        output_path
                    ):

                        raise RuntimeError(
                            "저장된 JSON "
                            "유효성 검사 실패"
                        )

                    (
                        speaker_ids,
                        word_count
                    ) = get_speaker_stats(
                        data
                    )

                    summary_rows.append(
                        {
                            "sample_id":
                                sample_id,

                            "status":
                                "SUCCESS",

                            "speaker_count":
                                len(
                                    speaker_ids
                                ),

                            "speaker_ids":
                                ",".join(
                                    speaker_ids
                                ),

                            "word_count":
                                word_count,

                            "audio_duration_secs":
                                data.get(
                                    "audio_duration_secs",
                                    ""
                                ),

                            "language_code":
                                data.get(
                                    "language_code",
                                    ""
                                ),

                            "language_probability":
                                data.get(
                                    "language_probability",
                                    ""
                                ),

                            "elapsed_seconds":
                                round(
                                    elapsed,
                                    2
                                ),

                            "error":
                                "",
                        }
                    )

                    success_count += 1

                    print(
                        f"    SUCCESS | "
                        f"speakers="
                        f"{len(speaker_ids)} | "
                        f"words="
                        f"{word_count} | "
                        f"{elapsed:.1f}s"
                    )

                    final_error = None
                    break

                except Exception as e:

                    final_error = e

                    print(
                        f"    ERROR: "
                        f"{e}"
                    )

                    # ========================================
                    # 핵심 수정
                    # quota 소진은 재시도하지 않고
                    # 전체 pilot 실행을 즉시 중단
                    # ========================================

                    if is_quota_exceeded(e):

                        quota_exhausted = True

                        print()
                        print(
                            "    [QUOTA EXHAUSTED]"
                        )

                        print(
                            "    ElevenLabs 크레딧이 "
                            "부족합니다."
                        )

                        print(
                            "    같은 요청을 재시도하지 않고 "
                            "전체 실행을 안전하게 중단합니다."
                        )

                        break

                    # quota 문제가 아닌 경우에만 재시도
                    if (
                        attempt
                        < MAX_RETRIES
                    ):

                        print(
                            f"    "
                            f"{RETRY_WAIT_SECONDS}초 후 "
                            f"재시도..."
                        )

                        time.sleep(
                            RETRY_WAIT_SECONDS
                        )

            # ------------------------------------------------
            # 최종 실패 기록
            # ------------------------------------------------

            if final_error is not None:

                fail_count += 1

                log_error(
                    sample_id,
                    final_error
                )

                summary_rows.append(
                    {
                        "sample_id":
                            sample_id,

                        "status":
                            (
                                "QUOTA_EXHAUSTED"
                                if quota_exhausted
                                else "FAILED"
                            ),

                        "speaker_count":
                            "",

                        "speaker_ids":
                            "",

                        "word_count":
                            "",

                        "audio_duration_secs":
                            "",

                        "language_code":
                            "",

                        "language_probability":
                            "",

                        "elapsed_seconds":
                            "",

                        "error":
                            str(
                                final_error
                            ),
                    }
                )

            # 매 샘플마다 summary 갱신
            # 중간 종료돼도 기록이 남는다.
            save_summary(
                summary_rows
            )

            # quota가 소진됐으면
            # 다음 sample로 넘어가지 않고 종료
            if quota_exhausted:

                break

    # ========================================================
    # 최종 결과
    # ========================================================

    save_summary(
        summary_rows
    )

    print()
    print("=" * 72)

    if quota_exhausted:

        print(
            "ElevenLabs Pilot 안전 중단 "
            "(크레딧 부족)"
        )

    else:

        print(
            "ElevenLabs Pilot 실행 완료"
        )

    print("=" * 72)

    print(
        f"전체 대상: "
        f"{len(pilot_rows)}"
    )

    print(
        f"이번 실행 신규 성공: "
        f"{success_count}"
    )

    print(
        f"기존 결과 SKIP: "
        f"{skip_count}"
    )

    print(
        f"이번 실행 실패: "
        f"{fail_count}"
    )

    current_valid_count = sum(
        1
        for row in pilot_rows
        if valid_existing_json(
            OUTPUT_DIR
            / (
                f"{str(row['sample_id']).strip()}"
                "_elevenlabs.json"
            )
        )
    )

    print(
        f"현재 누적 정상 결과: "
        f"{current_valid_count}/"
        f"{len(pilot_rows)}"
    )

    print(
        f"남은 미처리: "
        f"{len(pilot_rows) - current_valid_count}"
    )

    print()

    print(
        f"결과 폴더: "
        f"{OUTPUT_DIR}"
    )

    print(
        f"요약 CSV: "
        f"{SUMMARY_CSV}"
    )

    if fail_count > 0:

        print(
            f"에러 로그: "
            f"{ERROR_JSONL}"
        )

    if quota_exhausted:

        print()
        print(
            "크레딧을 추가한 뒤 "
            "같은 명령을 다시 실행하면 됩니다."
        )

        print(
            "이미 성공한 JSON은 자동으로 SKIP됩니다."
        )


if __name__ == "__main__":
    main()