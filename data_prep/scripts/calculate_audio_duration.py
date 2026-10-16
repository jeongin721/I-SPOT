import csv
import io
import zipfile
from pathlib import Path

try:
    from mutagen.mp3 import MP3
except ImportError:
    print("mutagen 패키지가 설치되어 있지 않습니다.")
    print("아래 명령을 실행하세요:")
    print("pip install mutagen")
    raise


# ============================================================
# 경로
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

TS_ZIP = Path(
    r"C:\Users\USER\Desktop\헬스케어 4조\024.아동·청소년_상담_데이터"
    r"\3.개방데이터\1.데이터\Training\01.원천데이터\TS_in.zip"
)

OUTPUT_DIR = PROJECT_ROOT / "data_prep" / "evaluation" / "ground_truth"
OUTPUT_CSV = OUTPUT_DIR / "audio_duration_2876.csv"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================
# 시간 표시
# ============================================================

def seconds_to_hms(seconds):
    seconds = int(round(seconds))

    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60

    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


# ============================================================
# 메인
# ============================================================

def main():

    if not TS_ZIP.exists():
        raise FileNotFoundError(
            f"TS_in.zip을 찾을 수 없습니다:\n{TS_ZIP}"
        )

    print("=" * 70)
    print("I-SPOT AUDIO DURATION ANALYSIS")
    print("=" * 70)
    print(f"Audio ZIP: {TS_ZIP}")
    print()

    results = []
    failures = []

    total_seconds = 0.0

    with zipfile.ZipFile(TS_ZIP, "r") as zf:

        mp3_files = sorted(
            name
            for name in zf.namelist()
            if name.lower().endswith(".mp3")
        )

        print(f"MP3 파일 수: {len(mp3_files)}")
        print()

        for idx, member in enumerate(mp3_files, start=1):

            sample_id = Path(member).stem

            try:
                audio_bytes = zf.read(member)

                audio = MP3(io.BytesIO(audio_bytes))

                duration_sec = float(audio.info.length)

                total_seconds += duration_sec

                results.append(
                    {
                        "sample_id": sample_id,
                        "duration_seconds": round(duration_sec, 3),
                        "duration_hms": seconds_to_hms(duration_sec),
                    }
                )

            except Exception as e:

                failures.append(
                    {
                        "sample_id": sample_id,
                        "member": member,
                        "error": str(e),
                    }
                )

            if idx % 100 == 0 or idx == len(mp3_files):

                print(
                    f"[{idx}/{len(mp3_files)}] "
                    f"누적 재생시간: {total_seconds / 3600:.2f}시간"
                )

    # ========================================================
    # CSV 저장
    # ========================================================

    with OUTPUT_CSV.open(
        "w",
        encoding="utf-8-sig",
        newline=""
    ) as f:

        writer = csv.DictWriter(
            f,
            fieldnames=[
                "sample_id",
                "duration_seconds",
                "duration_hms",
            ]
        )

        writer.writeheader()
        writer.writerows(results)

    # ========================================================
    # 통계
    # ========================================================

    successful_count = len(results)

    if successful_count > 0:

        durations = [
            row["duration_seconds"]
            for row in results
        ]

        average_seconds = (
            sum(durations) / successful_count
        )

        min_row = min(
            results,
            key=lambda x: x["duration_seconds"]
        )

        max_row = max(
            results,
            key=lambda x: x["duration_seconds"]
        )

    else:
        average_seconds = 0
        min_row = None
        max_row = None

    # ========================================================
    # 결과 출력
    # ========================================================

    print()
    print("=" * 70)
    print("완료")
    print("=" * 70)

    print(f"MP3 성공: {successful_count}")
    print(f"MP3 실패: {len(failures)}")

    print()
    print(f"전체 초: {total_seconds:,.2f}")
    print(f"전체 분: {total_seconds / 60:,.2f}")
    print(f"전체 시간: {total_seconds / 3600:,.2f} 시간")
    print(f"전체 HH:MM:SS: {seconds_to_hms(total_seconds)}")

    print()
    print(
        f"파일당 평균 길이: "
        f"{average_seconds:.2f}초 "
        f"({average_seconds / 60:.2f}분)"
    )

    if min_row:
        print(
            f"가장 짧은 파일: "
            f"{min_row['sample_id']} "
            f"- {min_row['duration_hms']}"
        )

    if max_row:
        print(
            f"가장 긴 파일: "
            f"{max_row['sample_id']} "
            f"- {max_row['duration_hms']}"
        )

    print()
    print(f"CSV 저장:")
    print(OUTPUT_CSV)

    if failures:

        print()
        print("실패 예시:")

        for item in failures[:10]:
            print(item)


if __name__ == "__main__":
    main()