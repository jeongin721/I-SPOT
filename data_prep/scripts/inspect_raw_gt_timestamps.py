import json
import zipfile
from pathlib import Path


# ============================================================
# 원본 라벨 ZIP
# ============================================================

TL_ZIP = Path(
    r"C:\Users\USER\Desktop\헬스케어 4조\024.아동·청소년_상담_데이터"
    r"\3.개방데이터\1.데이터\Training\02.라벨링데이터\TL_out.zip"
)

SAMPLE_ID = "2915"


# ============================================================
# Q/A 관련 dict 찾기
# ============================================================

def find_qa_dicts(obj, path="root", results=None):

    if results is None:
        results = []

    if isinstance(obj, dict):

        type_value = obj.get("type")

        if type_value in ("Q", "A"):

            results.append(
                {
                    "path": path,
                    "dict": obj,
                }
            )

        for key, value in obj.items():

            find_qa_dicts(
                value,
                f"{path}.{key}",
                results
            )

    elif isinstance(obj, list):

        for index, item in enumerate(obj):

            find_qa_dicts(
                item,
                f"{path}[{index}]",
                results
            )

    return results


# ============================================================
# 메인
# ============================================================

def main():

    if not TL_ZIP.exists():

        raise FileNotFoundError(
            f"TL_out.zip을 찾을 수 없습니다:\n{TL_ZIP}"
        )

    with zipfile.ZipFile(
        TL_ZIP,
        "r"
    ) as zf:

        candidates = [
            name
            for name in zf.namelist()
            if Path(name).stem == SAMPLE_ID
            and name.lower().endswith(".json")
        ]

        if not candidates:

            raise RuntimeError(
                f"{SAMPLE_ID}.json을 찾지 못했습니다."
            )

        member = candidates[0]

        print("=" * 80)
        print("RAW GT TIMESTAMP INSPECTION")
        print("=" * 80)

        print(f"ZIP member: {member}")
        print()

        with zf.open(member) as f:

            raw = f.read().decode(
                "utf-8-sig"
            )

            data = json.loads(raw)

    qa_items = find_qa_dicts(data)

    print(
        f"Q/A dict 발견 개수: "
        f"{len(qa_items)}"
    )

    print()

    # 앞 10개만 출력
    for index, item in enumerate(
        qa_items[:10],
        start=1
    ):

        obj = item["dict"]

        print("-" * 80)
        print(f"[{index}] PATH")
        print(item["path"])

        print()
        print("[전체 dict]")
        print(
            json.dumps(
                obj,
                ensure_ascii=False,
                indent=2
            )
        )

        print()
        print("[핵심 필드]")

        for key in [
            "type",
            "text",
            "wave",
            "start",
            "end",
            "audio",
        ]:

            value = obj.get(
                key,
                "<KEY 없음>"
            )

            print(
                f"{key}: "
                f"{repr(value)} "
                f"(type={type(value).__name__})"
            )

        print()


if __name__ == "__main__":
    main()