from pathlib import Path
from zipfile import ZipFile
import json
import pprint


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


def show_structure(value, depth=0, max_depth=4):
    indent = "  " * depth

    if depth > max_depth:
        print(f"{indent}...")
        return

    if isinstance(value, dict):
        print(f"{indent}dict ({len(value)} keys)")

        for key, child in value.items():
            print(
                f"{indent}├─ {key!r} "
                f"[{type(child).__name__}]"
            )

            show_structure(
                child,
                depth + 1,
                max_depth,
            )

    elif isinstance(value, list):
        print(
            f"{indent}list "
            f"(length={len(value)})"
        )

        # 리스트 전체를 출력하지 않고
        # 첫 번째 항목만 구조 확인
        if value:
            print(f"{indent}└─ [0]")
            show_structure(
                value[0],
                depth + 1,
                max_depth,
            )

    else:
        preview = repr(value)

        if len(preview) > 150:
            preview = preview[:150] + "..."

        print(
            f"{indent}= {preview}"
        )


def main():
    label_zip = find_zip("TL_out.zip")

    print("=" * 70)
    print("I-SPOT LABEL STRUCTURE INSPECTION")
    print("=" * 70)

    print(f"\nZIP : {label_zip}")

    with ZipFile(label_zip, "r") as zf:

        json_files = [
            item.filename
            for item in zf.infolist()
            if (
                not item.is_dir()
                and item.filename.lower().endswith(".json")
            )
        ]

        if not json_files:
            raise RuntimeError(
                "JSON 파일이 없습니다."
            )

        # 첫 번째 JSON
        sample_name = json_files[0]

        with zf.open(sample_name) as fp:
            data = json.load(fp)

    print()
    print("=" * 70)
    print("SAMPLE FILE")
    print("=" * 70)

    print(sample_name)

    print()
    print("=" * 70)
    print("JSON STRUCTURE")
    print("=" * 70)

    show_structure(data)

    print()
    print("=" * 70)
    print("INFO CONTENT")
    print("=" * 70)

    if isinstance(data, dict):
        pprint.pprint(
            data.get("info"),
            width=120,
            sort_dicts=False,
        )

    print()
    print("=" * 70)
    print("FIRST LIST ITEM")
    print("=" * 70)

    if (
        isinstance(data, dict)
        and isinstance(data.get("list"), list)
        and data["list"]
    ):
        pprint.pprint(
            data["list"][0],
            width=120,
            sort_dicts=False,
        )

    print()
    print("✅ label structure inspection complete")


if __name__ == "__main__":
    main()