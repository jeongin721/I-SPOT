import argparse
import csv
import json
import os
import time
import zipfile
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from deepgram import DeepgramClient


# ============================================================
# 기본 경로
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

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
    / "deepgram"
    / "outputs"
)

ERROR_LOG = (
    PROJECT_ROOT
    / "data_prep"
    / "evaluation"
    / "deepgram"
    / "errors.jsonl"
)

SUMMARY_CSV = (
    PROJECT_ROOT
    / "data_prep"
    / "evaluation"
    / "deepgram"
    / "run_summary.csv"
)

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================
# 환경 변수
# ============================================================

load_dotenv(PROJECT_ROOT / ".env")

DEEPGRAM_API_KEY = (
    os.getenv("DEEPGRAM_API_KEY")
    or os.getenv("I_SPOT_STT_API_KEY")
)

if not DEEPGRAM_API_KEY:
    raise RuntimeError(
        "Deepgram API 키를 찾을 수 없습니다.\n"
        ".env의 DEEPGRAM_API_KEY 또는 I_SPOT_STT_API_KEY를 확인하세요."
    )

# ============================================================
# 유틸
# ============================================================

def object_to_dict(obj):
    """
    Deepgram SDK 객체를 최대한 안전하게 dict로 변환
    """
    if obj is None:
        return None

    if isinstance(obj, dict):
        return obj

    if hasattr(obj, "to_dict"):
        return obj.to_dict()

    if hasattr(obj, "model_dump"):
        return obj.model_dump()

    if hasattr(obj, "dict"):
        return obj.dict()

    if hasattr(obj, "to_json"):
        raw = obj.to_json()

        if isinstance(raw, str):
            return json.loads(raw)

    raise TypeError(
        f"Deepgram 응답 객체를 dict로 변환할 수 없습니다: {type(obj)}"
    )


def load_pilot_rows():
    if not PILOT_CSV.exists():
        raise FileNotFoundError(
            f"pilot_100.csv을 찾을 수 없습니다:\n{PILOT_CSV}"
        )

    with PILOT_CSV.open(
        "r",
        encoding="utf-8-sig",
        newline=""
    ) as f:
        return list(csv.DictReader(f))


def build_zip_member_map(zf):
    """
    sample_id -> ZIP 내부 MP3 경로
    """
    member_map = {}

    for member in zf.namelist():

        if not member.lower().endswith(".mp3"):
            continue

        sample_id = Path(member).stem

        member_map[sample_id] = member

    return member_map


def extract_normalized_result(response_dict):
    """
    나중 평가를 쉽게 하기 위해
    Deepgram 응답에서 필요한 부분만 별도로 정리
    """

    results = response_dict.get("results", {}) or {}

    utterances_raw = results.get("utterances", []) or []

    utterances = []

    for utt in utterances_raw:

        utterances.append(
            {
                "speaker": utt.get("speaker"),
                "start": utt.get("start"),
                "end": utt.get("end"),
                "confidence": utt.get("confidence"),
                "transcript": utt.get("transcript", ""),
            }
        )

    words = []

    channels = results.get("channels", []) or []

    if channels:

        alternatives = channels[0].get("alternatives", []) or []

        if alternatives:

            raw_words = alternatives[0].get("words", []) or []

            for word in raw_words:

                words.append(
                    {
                        "word": word.get("word", ""),
                        "punctuated_word": word.get(
                            "punctuated_word",
                            word.get("word", "")
                        ),
                        "speaker": word.get("speaker"),
                        "start": word.get("start"),
                        "end": word.get("end"),
                        "confidence": word.get("confidence"),
                    }
                )

    speakers = sorted(
        {
            item["speaker"]
            for item in words
            if item["speaker"] is not None
        }
    )

    full_transcript = ""

    if channels:

        alternatives = channels[0].get("alternatives", []) or []

        if alternatives:
            full_transcript = alternatives[0].get(
                "transcript",
                ""
            )

    return {
        "speaker_count": len(speakers),
        "speakers": speakers,
        "utterance_count": len(utterances),
        "word_count": len(words),
        "transcript": full_transcript,
        "utterances": utterances,
        "words": words,
    }


def write_error(sample_id, error):
    record = {
        "sample_id": sample_id,
        "error": str(error),
        "time": datetime.now().isoformat(
            timespec="seconds"
        ),
    }

    with ERROR_LOG.open(
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


def write_summary(rows):
    fields = [
        "sample_id",
        "status",
        "speaker_count",
        "utterance_count",
        "word_count",
        "duration_seconds",
        "abuse_label",
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
# Deepgram 호출
# ============================================================

def transcribe(client, audio_bytes):
    """
    현재 I-SPOT에서 사용 중인 Deepgram 설정과 동일하게 유지
    """

    response = client.listen.v1.media.transcribe_file(
        request=audio_bytes,
        model="nova-2",
        language="ko",
        diarize_model="latest",
        punctuate=True,
        utterances=True,
    )

    return response


# ============================================================
# 메인
# ============================================================

def main():

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--limit",
        type=int,
        default=1,
        help="이번 실행에서 새로 처리할 최대 파일 수",
    )

    parser.add_argument(
        "--retry",
        type=int,
        default=3,
        help="API 오류 발생 시 최대 재시도 횟수",
    )

    args = parser.parse_args()

    if not TS_ZIP.exists():
        raise FileNotFoundError(
            f"TS_in.zip을 찾을 수 없습니다:\n{TS_ZIP}"
        )

    pilot_rows = load_pilot_rows()

    client = DeepgramClient(
        api_key=DEEPGRAM_API_KEY
    )

    summary_rows = []

    new_processed = 0
    success_count = 0
    skip_count = 0
    failure_count = 0

    print("=" * 70)
    print("I-SPOT DEEPGRAM PILOT")
    print("=" * 70)
    print(f"Pilot 대상: {len(pilot_rows)}개")
    print(f"이번 실행 최대 신규 처리: {args.limit}개")
    print(f"Output: {OUTPUT_DIR}")
    print()

    with zipfile.ZipFile(TS_ZIP, "r") as zf:

        member_map = build_zip_member_map(zf)

        for idx, row in enumerate(
            pilot_rows,
            start=1
        ):

            sample_id = row["sample_id"].strip()

            output_path = (
                OUTPUT_DIR
                / f"{sample_id}_deepgram.json"
            )

            # --------------------------------------------
            # 이미 처리된 파일은 건너뛰기
            # --------------------------------------------

            if output_path.exists():

                skip_count += 1

                try:
                    with output_path.open(
                        "r",
                        encoding="utf-8"
                    ) as f:
                        existing = json.load(f)

                    normalized = existing.get(
                        "normalized",
                        {}
                    )

                    summary_rows.append(
                        {
                            "sample_id": sample_id,
                            "status": "SKIPPED_EXISTING",
                            "speaker_count": normalized.get(
                                "speaker_count",
                                ""
                            ),
                            "utterance_count": normalized.get(
                                "utterance_count",
                                ""
                            ),
                            "word_count": normalized.get(
                                "word_count",
                                ""
                            ),
                            "duration_seconds": row.get(
                                "duration_seconds",
                                ""
                            ),
                            "abuse_label": row.get(
                                "abuse_label",
                                ""
                            ),
                            "error": "",
                        }
                    )

                except Exception:
                    pass

                continue

            # 이번 실행 limit 도달
            if new_processed >= args.limit:
                continue

            new_processed += 1

            print(
                f"[{idx}/{len(pilot_rows)}] "
                f"{sample_id} 처리 시작"
            )

            if sample_id not in member_map:

                error = (
                    f"ZIP에서 MP3를 찾을 수 없음: "
                    f"{sample_id}"
                )

                print(f"  ERROR: {error}")

                failure_count += 1

                write_error(
                    sample_id,
                    error
                )

                summary_rows.append(
                    {
                        "sample_id": sample_id,
                        "status": "FAILED",
                        "speaker_count": "",
                        "utterance_count": "",
                        "word_count": "",
                        "duration_seconds": row.get(
                            "duration_seconds",
                            ""
                        ),
                        "abuse_label": row.get(
                            "abuse_label",
                            ""
                        ),
                        "error": error,
                    }
                )

                continue

            member = member_map[sample_id]

            audio_bytes = zf.read(member)

            last_error = None
            response = None

            # --------------------------------------------
            # 재시도
            # --------------------------------------------

            for attempt in range(
                1,
                args.retry + 1
            ):

                try:

                    response = transcribe(
                        client,
                        audio_bytes
                    )

                    last_error = None
                    break

                except Exception as e:

                    last_error = e

                    print(
                        f"  API 오류 "
                        f"{attempt}/{args.retry}: "
                        f"{e}"
                    )

                    if attempt < args.retry:
                        time.sleep(
                            min(
                                2 ** attempt,
                                10
                            )
                        )

            # --------------------------------------------
            # 실패
            # --------------------------------------------

            if response is None:

                failure_count += 1

                write_error(
                    sample_id,
                    last_error
                )

                summary_rows.append(
                    {
                        "sample_id": sample_id,
                        "status": "FAILED",
                        "speaker_count": "",
                        "utterance_count": "",
                        "word_count": "",
                        "duration_seconds": row.get(
                            "duration_seconds",
                            ""
                        ),
                        "abuse_label": row.get(
                            "abuse_label",
                            ""
                        ),
                        "error": str(last_error),
                    }
                )

                continue

            # --------------------------------------------
            # 응답 변환
            # --------------------------------------------

            try:

                response_dict = object_to_dict(
                    response
                )

                normalized = extract_normalized_result(
                    response_dict
                )

                save_data = {
                    "sample_id": sample_id,
                    "abuse_label": row.get(
                        "abuse_label",
                        ""
                    ),
                    "risk_stage": row.get(
                        "risk_stage",
                        ""
                    ),
                    "duration_seconds": row.get(
                        "duration_seconds",
                        ""
                    ),
                    "deepgram_config": {
                        "model": "nova-2",
                        "language": "ko",
                        "diarize_model": "latest",
                        "punctuate": True,
                        "utterances": True,
                    },
                    "normalized": normalized,
                    "raw_response": response_dict,
                }

                with output_path.open(
                    "w",
                    encoding="utf-8"
                ) as f:

                    json.dump(
                        save_data,
                        f,
                        ensure_ascii=False,
                        indent=2,
                        default=str
                    )

                success_count += 1

                print(
                    f"  성공 | "
                    f"speakers="
                    f"{normalized['speaker_count']} | "
                    f"utterances="
                    f"{normalized['utterance_count']} | "
                    f"words="
                    f"{normalized['word_count']}"
                )

                summary_rows.append(
                    {
                        "sample_id": sample_id,
                        "status": "SUCCESS",
                        "speaker_count": normalized[
                            "speaker_count"
                        ],
                        "utterance_count": normalized[
                            "utterance_count"
                        ],
                        "word_count": normalized[
                            "word_count"
                        ],
                        "duration_seconds": row.get(
                            "duration_seconds",
                            ""
                        ),
                        "abuse_label": row.get(
                            "abuse_label",
                            ""
                        ),
                        "error": "",
                    }
                )

            except Exception as e:

                failure_count += 1

                print(
                    f"  응답 저장 오류: {e}"
                )

                write_error(
                    sample_id,
                    e
                )

                summary_rows.append(
                    {
                        "sample_id": sample_id,
                        "status": "FAILED_SAVE",
                        "speaker_count": "",
                        "utterance_count": "",
                        "word_count": "",
                        "duration_seconds": row.get(
                            "duration_seconds",
                            ""
                        ),
                        "abuse_label": row.get(
                            "abuse_label",
                            ""
                        ),
                        "error": str(e),
                    }
                )

    write_summary(summary_rows)

    print()
    print("=" * 70)
    print("이번 실행 완료")
    print("=" * 70)

    print(f"신규 성공: {success_count}")
    print(f"기존 파일 건너뜀: {skip_count}")
    print(f"실패: {failure_count}")

    print()
    print(f"결과 폴더:")
    print(OUTPUT_DIR)

    print()
    print(f"요약 CSV:")
    print(SUMMARY_CSV)


if __name__ == "__main__":
    main()
