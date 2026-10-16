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
            f"{filename}을 찾을 수 없습니다."
        )

    return matches[0]


def main():
    label_zip = find_zip("TL_out.zip")

    print("=" * 70)
    print("I-SPOT ABUSE LABEL DISTRIBUTION")
    print("=" * 70)
    print(f"TL ZIP : {label_zip}")
    print()

    label_counter = Counter()
    crisis_counter = Counter()
    type_counter = Counter()

    missing_label = []
    errors = []

    total = 0

    with ZipFile(label_zip, "r") as zf:

        json_files = [
            item.filename
            for item in zf.infolist()
            if (
                not item.is_dir()
                and item.filename.lower().endswith(".json")
            )
        ]

        for filename in json_files:
            total += 1

            try:
                with zf.open(filename) as fp:
                    data = json.load(fp)

                info = data.get("info", {})

                sample_id = str(
                    info.get("ID", Path(filename).stem)
                )

                abuse_label = info.get("학대의심")
                crisis_level = info.get("위기단계")
                child_type = info.get("유형구분")

                # -----------------------------
                # 학대 라벨
                # -----------------------------
                if abuse_label is None:
                    label_counter["<MISSING>"] += 1
                    missing_label.append(sample_id)

                else:
                    abuse_label = str(abuse_label).strip()

                    if abuse_label == "":
                        label_counter["<EMPTY>"] += 1
                        missing_label.append(sample_id)
                    else:
                        label_counter[abuse_label] += 1

                # -----------------------------
                # 위기단계
                # -----------------------------
                if crisis_level is None:
                    crisis_counter["<MISSING>"] += 1
                else:
                    crisis_counter[
                        str(crisis_level).strip()
                    ] += 1

                # -----------------------------
                # 유형구분
                # -----------------------------
                if child_type is None:
                    type_counter["<MISSING>"] += 1
                else:
                    type_counter[
                        str(child_type).strip()
                    ] += 1

            except Exception as e:
                errors.append(
                    (filename, repr(e))
                )

    # =========================================================
    # 결과 출력
    # =========================================================

    print("=" * 70)
    print("1. 전체 JSON")
    print("=" * 70)

    print(f"전체 JSON 수 : {total:,}")
    print(f"읽기 성공    : {total - len(errors):,}")
    print(f"읽기 실패    : {len(errors):,}")

    print()

    print("=" * 70)
    print("2. 학대의심 라벨 분포")
    print("=" * 70)

    for label, count in label_counter.most_common():

        ratio = (
            count / total * 100
            if total
            else 0
        )

        print(
            f"{label:<25}"
            f"{count:>6,}개"
            f"   ({ratio:6.2f}%)"
        )

    print()

    print("=" * 70)
    print("3. 위기단계 분포")
    print("=" * 70)

    for label, count in crisis_counter.most_common():

        ratio = (
            count / total * 100
            if total
            else 0
        )

        print(
            f"{label:<25}"
            f"{count:>6,}개"
            f"   ({ratio:6.2f}%)"
        )

    print()

    print("=" * 70)
    print("4. 유형구분 분포")
    print("=" * 70)

    for label, count in type_counter.most_common():

        ratio = (
            count / total * 100
            if total
            else 0
        )

        print(
            f"{label:<25}"
            f"{count:>6,}개"
            f"   ({ratio:6.2f}%)"
        )

    print()

    print("=" * 70)
    print("5. 데이터 품질 확인")
    print("=" * 70)

    print(
        f"학대의심 누락/빈값 : "
        f"{len(missing_label):,}"
    )

    print(
        f"JSON 읽기 실패     : "
        f"{len(errors):,}"
    )

    if missing_label:
        print()
        print("학대의심 누락 ID 예시:")
        print(
            ", ".join(
                missing_label[:20]
            )
        )

    if errors:
        print()
        print("JSON 오류 예시:")

        for filename, error in errors[:10]:
            print(
                f"- {filename}: {error}"
            )

    print()
    print("=" * 70)
    print("FINAL SUMMARY")
    print("=" * 70)

    print(f"전체 데이터 : {total:,}")

    known_abuse_labels = [
        "신체학대",
        "정서학대",
        "성학대",
        "방임",
    ]

    for label in known_abuse_labels:
        print(
            f"{label:<10}: "
            f"{label_counter.get(label, 0):>6,}"
        )

    print()
    print("※ 위 4개 이외의 라벨도 원본 그대로 위에 출력됩니다.")
    print("※ 임의로 '해당없음'을 가정하지 않습니다.")

    print()
    print("✅ abuse label distribution complete")


if __name__ == "__main__":
    main()
    