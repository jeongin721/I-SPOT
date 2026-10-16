import json
from pathlib import Path
from collections import Counter

DATA_ROOT = Path(
    r"C:\Users\USER\Desktop\최종_프로젝트\최종프로젝트_데이터셋"
)

label_counter = Counter()
json_count = 0

for json_path in DATA_ROOT.rglob("*.json"):
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        label = data.get("info", {}).get("학대의심")

        if label is not None:
            label_counter[str(label).strip()] += 1

        json_count += 1

    except Exception as e:
        print(f"[ERROR] {json_path}: {e}")

print("\n전체 JSON:", json_count)

print("\n===== 학대의심 값 종류 =====")
for label, count in label_counter.most_common():
    print(f"{label!r}: {count}")

print("\n고유 label 개수:", len(label_counter))

missing_count = 0
missing_examples = []

for json_path in DATA_ROOT.rglob("*.json"):
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        if "학대의심" not in data.get("info", {}):
            missing_count += 1

            if len(missing_examples) < 10:
                missing_examples.append(json_path)

    except Exception:
        pass

print("\n학대의심 없는 JSON:", missing_count)

print("\n===== 예시 경로 =====")
for path in missing_examples:
    print(path)