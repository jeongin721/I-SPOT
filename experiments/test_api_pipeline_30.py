import csv
import json
import time
from pathlib import Path

import requests


# ---------------------------------------------------------
# 설정
# ---------------------------------------------------------

API_URL = "http://127.0.0.1:8000/api/v1/analyze"

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SAMPLE_DIR = PROJECT_ROOT / "test_sample"
RESULT_DIR = PROJECT_ROOT / "results"

RESULT_DIR.mkdir(exist_ok=True)

CSV_PATH = RESULT_DIR / "api_pipeline_30_results.csv"
JSON_PATH = RESULT_DIR / "api_pipeline_30_results.json"


# 기존에 선정한 30개 평가 샘플
FILE_IDS = [
    "0002", "0004", "0005", "0006", "0018",
    "3242", "3706", "2076", "5036", "1136",
    "2560", "2677", "1786", "1354", "5058",
    "0216", "0379", "1112", "3731", "5113",
    "3891", "3316", "5069", "3696", "3821",
    "0184", "2637", "2674", "2315", "5194",
]


def main():

    all_results = []

    print("=" * 70)
    print("I-SPOT 최종 API 파이프라인 30개 통합 테스트")
    print("=" * 70)

    for index, file_id in enumerate(FILE_IDS, start=1):

        audio_path = SAMPLE_DIR / f"{file_id}.mp3"

        print()
        print(
            f"[{index:02d}/{len(FILE_IDS)}] "
            f"{file_id}.mp3 분석 시작"
        )

        if not audio_path.exists():
            print("❌ MP3 파일 없음")

            result_row = {
                "file": file_id,
                "api_success": False,
                "http_status": None,
                "child_status": "FILE_NOT_FOUND",
                "child_speaker": None,
                "fallback_used": False,
                "fallback_count": 0,
                "physical_detected": None,
                "emotional_detected": None,
                "sexual_detected": None,
                "neglect_detected": None,
                "error": "MP3 file not found",
            }

            all_results.append(result_row)
            save_results(all_results)

            continue

        try:

            start_time = time.time()

            with open(audio_path, "rb") as audio_file:

                response = requests.post(
                    API_URL,
                    files={
                        "file": (
                            audio_path.name,
                            audio_file,
                            "audio/mpeg",
                        )
                    },
                    timeout=1800,
                )

            elapsed = time.time() - start_time

            print(
                f"HTTP {response.status_code} "
                f"| {elapsed:.1f}초"
            )

            if response.status_code != 200:

                print("❌ API 요청 실패")

                result_row = {
                    "file": file_id,
                    "api_success": False,
                    "http_status": response.status_code,
                    "child_status": None,
                    "child_speaker": None,
                    "fallback_used": False,
                    "fallback_count": 0,
                    "physical_detected": None,
                    "emotional_detected": None,
                    "sexual_detected": None,
                    "neglect_detected": None,
                    "error": response.text[:500],
                }

                all_results.append(result_row)
                save_results(all_results)

                continue

            data = response.json()

            stt_data = data.get("stt_data", {}) or {}

            fallback_evidence = (
                stt_data.get(
                    "fallback_evidence",
                    [],
                )
                or []
            )

            prediction = (
                data.get(
                    "abuse_prediction",
                    {}
                )
                or {}
            )

            result_row = {
                "file": file_id,

                "api_success": True,

                "http_status":
                    response.status_code,

                "elapsed_sec":
                    round(elapsed, 2),

                "child_status":
                    data.get(
                        "child_analysis_status"
                    ),

                "child_speaker":
                    data.get(
                        "child_speaker"
                    ),

                "fallback_used":
                    bool(
                        stt_data.get(
                            "fallback_used",
                            False,
                        )
                    ),

                "fallback_count":
                    len(fallback_evidence),

                "physical_detected":
                    get_detected(
                        prediction,
                        "신체학대",
                    ),

                "emotional_detected":
                    get_detected(
                        prediction,
                        "정서학대",
                    ),

                "sexual_detected":
                    get_detected(
                        prediction,
                        "성학대",
                    ),

                "neglect_detected":
                    get_detected(
                        prediction,
                        "방임",
                    ),

                "error": "",
            }

            all_results.append(result_row)

            print(
                "아동 화자:",
                result_row["child_speaker"],
            )

            print(
                "분석 상태:",
                result_row["child_status"],
            )

            print(
                "Fallback:",
                result_row["fallback_used"],
                f"({result_row['fallback_count']}개)",
            )

            print(
                "학대 판정:",
                {
                    "신체": result_row[
                        "physical_detected"
                    ],
                    "정서": result_row[
                        "emotional_detected"
                    ],
                    "성": result_row[
                        "sexual_detected"
                    ],
                    "방임": result_row[
                        "neglect_detected"
                    ],
                },
            )

            # 한 파일이 끝날 때마다 저장
            save_results(all_results)

        except Exception as e:

            print(
                f"❌ 오류 발생: {e}"
            )

            result_row = {
                "file": file_id,
                "api_success": False,
                "http_status": None,
                "child_status": None,
                "child_speaker": None,
                "fallback_used": False,
                "fallback_count": 0,
                "physical_detected": None,
                "emotional_detected": None,
                "sexual_detected": None,
                "neglect_detected": None,
                "error": str(e),
            }

            all_results.append(result_row)

            save_results(all_results)

    print_summary(all_results)


def get_detected(prediction, label):

    label_result = (
        prediction.get(label, {})
        or {}
    )

    return label_result.get(
        "detected"
    )


def save_results(results):

    # JSON 저장
    with open(
        JSON_PATH,
        "w",
        encoding="utf-8",
    ) as f:

        json.dump(
            results,
            f,
            ensure_ascii=False,
            indent=2,
        )

    # CSV 저장
    if not results:
        return

    fieldnames = [
        "file",
        "api_success",
        "http_status",
        "elapsed_sec",
        "child_status",
        "child_speaker",
        "fallback_used",
        "fallback_count",
        "physical_detected",
        "emotional_detected",
        "sexual_detected",
        "neglect_detected",
        "error",
    ]

    with open(
        CSV_PATH,
        "w",
        newline="",
        encoding="utf-8-sig",
    ) as f:

        writer = csv.DictWriter(
            f,
            fieldnames=fieldnames,
            extrasaction="ignore",
        )

        writer.writeheader()
        writer.writerows(results)


def print_summary(results):

    total = len(results)

    success = sum(
        1
        for row in results
        if row.get("api_success")
    )

    unresolved = sum(
        1
        for row in results
        if row.get("child_status") != "OK"
    )

    fallback_files = sum(
        1
        for row in results
        if row.get("fallback_used")
    )

    print()
    print("=" * 70)
    print("FINAL RESULT")
    print("=" * 70)

    print(f"전체 파일       : {total}")
    print(f"API 성공        : {success}/{total}")
    print(
        f"아동 화자 미확정 : {unresolved}"
    )
    print(
        f"Fallback 발생   : {fallback_files}개 파일"
    )

    print()
    print(
        f"CSV  : {CSV_PATH}"
    )
    print(
        f"JSON : {JSON_PATH}"
    )


if __name__ == "__main__":
    main()