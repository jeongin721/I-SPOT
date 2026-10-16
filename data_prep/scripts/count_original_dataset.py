from pathlib import Path
from zipfile import ZipFile
from collections import Counter
import json

DATA_ROOT = Path(
    r"C:\Users\USER\Desktop\헬스케어 4조"
)


def find_zip(filename):
    matches = list(DATA_ROOT.rglob(filename))

    if not matches:
        raise FileNotFoundError(
            f"{filename}을 찾을 수 없습니다.\n"
            f"검색 위치: {DATA_ROOT}"
        )

    if len(matches) > 1:
        print(f"⚠️ {filename}이 여러 개 발견되었습니다.")
        for path in matches:
            print(f"  - {path}")

        print("첫 번째 파일을 사용합니다.")

    return matches[0]


TS_ZIP = find_zip("TS_in.zip")
TL_ZIP = find_zip("TL_out.zip")


AUDIO_EXTENSIONS = {
    ".wav",
    ".mp3",
    ".m4a",
    ".flac",
    ".ogg",
}


def stem_from_zip_name(name):
    return Path(name).stem


def print_counter(title, counter):
    print()
    print("=" * 70)
    print(title)
    print("=" * 70)

    if not counter:
        print("(없음)")
        return

    for key, value in counter.most_common():
        print(f"{str(key):30s} : {value}")


def inspect_source_zip():
    print()
    print("=" * 70)
    print("1. 원천데이터 TS_in.zip 검사")
    print("=" * 70)

    with ZipFile(TS_ZIP, "r") as zf:
        names = [
            x.filename
            for x in zf.infolist()
            if not x.is_dir()
        ]

    extension_counter = Counter(
        Path(name).suffix.lower()
        for name in names
    )

    audio_files = [
        name
        for name in names
        if Path(name).suffix.lower() in AUDIO_EXTENSIONS
    ]

    audio_ids = {
        stem_from_zip_name(name)
        for name in audio_files
    }

    print(f"ZIP 내부 전체 파일 수 : {len(names):,}")
    print(f"음성 파일 수          : {len(audio_files):,}")
    print(f"고유 음성 ID 수       : {len(audio_ids):,}")

    print_counter(
        "TS_in.zip 확장자별 파일 수",
        extension_counter,
    )

    return audio_files, audio_ids


def inspect_label_zip():
    print()
    print("=" * 70)
    print("2. 라벨링데이터 TL_out.zip 검사")
    print("=" * 70)

    with ZipFile(TL_ZIP, "r") as zf:

        json_files = [
            x.filename
            for x in zf.infolist()
            if (
                not x.is_dir()
                and Path(x.filename).suffix.lower() == ".json"
            )
        ]

        label_ids = {
            stem_from_zip_name(name)
            for name in json_files
        }

        print(f"JSON 파일 수     : {len(json_files):,}")
        print(f"고유 JSON ID 수  : {len(label_ids):,}")

        # JSON 구조를 파악하기 위한 최상위 key 조사
        top_key_counter = Counter()

        read_success = 0
        read_failure = 0

        for name in json_files:

            try:
                with zf.open(name) as fp:
                    data = json.load(fp)

                read_success += 1

                if isinstance(data, dict):
                    for key in data.keys():
                        top_key_counter[key] += 1

            except Exception:
                read_failure += 1

    print(f"JSON 읽기 성공   : {read_success:,}")
    print(f"JSON 읽기 실패   : {read_failure:,}")

    print_counter(
        "JSON 최상위 Key 출현 횟수",
        top_key_counter,
    )

    return json_files, label_ids


def compare_ids(audio_ids, label_ids):

    matched = audio_ids & label_ids
    audio_only = audio_ids - label_ids
    label_only = label_ids - audio_ids

    print()
    print("=" * 70)
    print("3. 음성 ↔ 라벨 매칭")
    print("=" * 70)

    print(f"매칭된 ID           : {len(matched):,}")
    print(f"음성만 존재         : {len(audio_only):,}")
    print(f"라벨만 존재         : {len(label_only):,}")

    if audio_only:
        print()
        print("[음성만 존재하는 ID 예시]")
        for sample_id in sorted(audio_only)[:10]:
            print(" ", sample_id)

    if label_only:
        print()
        print("[라벨만 존재하는 ID 예시]")
        for sample_id in sorted(label_only)[:10]:
            print(" ", sample_id)


def main():

    print("=" * 70)
    print("I-SPOT ORIGINAL DATASET INVENTORY")
    print("=" * 70)

    print()
    print(f"TS : {TS_ZIP}")
    print(f"TL : {TL_ZIP}")

    if not TS_ZIP.exists():
        raise FileNotFoundError(
            f"TS_in.zip을 찾을 수 없습니다:\n{TS_ZIP}"
        )

    if not TL_ZIP.exists():
        raise FileNotFoundError(
            f"TL_out.zip을 찾을 수 없습니다:\n{TL_ZIP}"
        )

    audio_files, audio_ids = inspect_source_zip()

    json_files, label_ids = inspect_label_zip()

    compare_ids(
        audio_ids,
        label_ids,
    )

    print()
    print("=" * 70)
    print("FINAL SUMMARY")
    print("=" * 70)

    print(f"전체 음성 파일 : {len(audio_files):,}")
    print(f"전체 JSON      : {len(json_files):,}")
    print(f"매칭 ID        : {len(audio_ids & label_ids):,}")

    print()
    print("✅ dataset inventory complete")


if __name__ == "__main__":
    main()