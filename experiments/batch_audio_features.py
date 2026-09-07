import csv
import json
from pathlib import Path

from ispot_audio_features import extract_audio_features


# ============================================================
# 1. 기본 설정
# ============================================================

TEST_DIR = Path("test_sample")

OUTPUT_JSON = Path(
    "audio_features_results.json"
)

OUTPUT_CSV = Path(
    "audio_features_results.csv"
)

SUPPORTED_AUDIO = {
    ".mp3",
    ".wav",
    ".m4a",
    ".flac",
    ".ogg",
    ".aac",
}


# ============================================================
# 2. STT JSON 로드
# ============================================================

def load_stt_segments(
    stt_json_path: Path,
):
    """
    기존 Deepgram STT 결과 JSON에서
    segments를 불러온다.
    """

    with open(
        stt_json_path,
        "r",
        encoding="utf-8",
    ) as f:
        data = json.load(f)

    stt_segments = (
        data
        .get("stt_data", {})
        .get("segments", [])
    )

    return stt_segments


# ============================================================
# 3. 파일 하나의 Audio Feature 추출
# ============================================================

def process_one_file(
    audio_path: Path,
    stt_json_path: Path,
):
    """
    MP3 + STT JSON을 이용하여
    화자별 Audio Feature를 추출한다.
    """

    print()
    print("=" * 80)
    print(
        f"Audio Feature 추출 시작: "
        f"{audio_path.name}"
    )
    print("=" * 80)

    stt_segments = load_stt_segments(
        stt_json_path
    )

    print(
        f"STT segment 수: "
        f"{len(stt_segments)}"
    )

    features = extract_audio_features(
        audio_path,
        stt_segments,
    )

    print(
        f"화자 수: "
        f"{len(features)}"
    )

    print(
        "Audio Feature 추출 완료"
    )

    return features


# ============================================================
# 4. CSV용 Row 생성
# ============================================================

def make_csv_rows(
    file_id,
    features,
):
    """
    화자별 Feature Vector를
    CSV 한 행씩 변환한다.

    예:
        0002 / SPEAKER_0
        0002 / SPEAKER_1
    """

    rows = []

    for speaker, feature_dict in features.items():

        row = {
            "file": file_id,
            "speaker": speaker,
        }

        row.update(
            feature_dict
        )

        rows.append(
            row
        )

    return rows


# ============================================================
# 5. JSON 저장
# ============================================================

def save_json(results):

    with open(
        OUTPUT_JSON,
        "w",
        encoding="utf-8",
    ) as f:

        json.dump(
            results,
            f,
            ensure_ascii=False,
            indent=2,
        )


# ============================================================
# 6. CSV 저장
# ============================================================

def save_csv(rows):

    if not rows:
        return

    fieldnames = list(
        rows[0].keys()
    )

    with open(
        OUTPUT_CSV,
        "w",
        newline="",
        encoding="utf-8-sig",
    ) as f:

        writer = csv.DictWriter(
            f,
            fieldnames=fieldnames,
        )

        writer.writeheader()

        writer.writerows(
            rows
        )


# ============================================================
# 7. 전체 Batch 실행
# ============================================================

def main():

    if not TEST_DIR.exists():

        print(
            "❌ test_sample 폴더를 "
            "찾을 수 없습니다."
        )

        return

    # --------------------------------------------------------
    # 오디오 파일 찾기
    # --------------------------------------------------------

    audio_files = sorted(
        path
        for path in TEST_DIR.iterdir()
        if (
            path.is_file()
            and path.suffix.lower()
            in SUPPORTED_AUDIO
        )
    )

    if not audio_files:

        print(
            "❌ test_sample 폴더에 "
            "오디오 파일이 없습니다."
        )

        return

    print()
    print("=" * 80)
    print(
        "I-SPOT Audio Feature Batch"
    )
    print("=" * 80)

    print(
        f"대상 오디오 수: "
        f"{len(audio_files)}"
    )

    results = {}
    csv_rows = []

    # --------------------------------------------------------
    # 파일별 반복
    # --------------------------------------------------------

    for index, audio_path in enumerate(
        audio_files,
        start=1,
    ):

        file_id = audio_path.stem

        stt_json_path = (
            audio_path.parent
            / f"{file_id}_stt.json"
        )

        print()
        print(
            f"[{index}/{len(audio_files)}] "
            f"{audio_path.name}"
        )

        # STT JSON이 없는 경우
        if not stt_json_path.exists():

            print(
                f"⚠ STT JSON 없음 → "
                f"{stt_json_path.name}"
            )

            print(
                "이 파일은 건너뜁니다."
            )

            continue

        try:

            features = process_one_file(
                audio_path,
                stt_json_path,
            )

            results[file_id] = (
                features
            )

            rows = make_csv_rows(
                file_id,
                features,
            )

            csv_rows.extend(
                rows
            )

        except Exception as e:

            print()
            print(
                f"❌ {audio_path.name} "
                f"처리 실패"
            )

            print(
                f"오류: {e}"
            )

            continue

    # --------------------------------------------------------
    # 결과가 없는 경우
    # --------------------------------------------------------

    if not results:

        print()
        print(
            "❌ 추출된 Audio Feature가 "
            "없습니다."
        )

        return

    # --------------------------------------------------------
    # 저장
    # --------------------------------------------------------

    save_json(
        results
    )

    save_csv(
        csv_rows
    )

    # --------------------------------------------------------
    # 최종 출력
    # --------------------------------------------------------

    print()
    print("=" * 80)
    print(
        "Audio Feature Batch 완료"
    )
    print("=" * 80)

    print(
        f"처리 성공 파일 수: "
        f"{len(results)}"
    )

    print(
        f"화자 Row 수     : "
        f"{len(csv_rows)}"
    )

    print()

    print(
        f"JSON 저장 → "
        f"{OUTPUT_JSON}"
    )

    print(
        f"CSV 저장  → "
        f"{OUTPUT_CSV}"
    )

    print("=" * 80)


# ============================================================
# 8. 프로그램 시작
# ============================================================

if __name__ == "__main__":
    main()

