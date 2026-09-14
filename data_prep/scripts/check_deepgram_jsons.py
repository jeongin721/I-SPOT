import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

OUTPUT_DIR = (
    PROJECT_ROOT
    / "data_prep"
    / "evaluation"
    / "deepgram"
    / "outputs"
)

def main():
    files = sorted(OUTPUT_DIR.glob("*_deepgram.json"))

    ok = 0
    broken = []

    for path in files:
        try:
            with path.open("r", encoding="utf-8") as f:
                json.load(f)

            ok += 1

        except Exception as e:
            broken.append((path, str(e)))

    print("=" * 70)
    print("DEEPGRAM JSON CHECK")
    print("=" * 70)

    print(f"전체 JSON: {len(files)}")
    print(f"정상: {ok}")
    print(f"깨진 파일: {len(broken)}")

    if broken:
        print()
        print("[깨진 파일]")
        for path, error in broken:
            print(f"{path.name}")
            print(f"  {error}")

if __name__ == "__main__":
    main()