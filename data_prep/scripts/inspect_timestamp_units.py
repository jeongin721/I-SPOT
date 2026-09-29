import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]

GT_JSONL = (
    PROJECT_ROOT
    / "data_prep"
    / "evaluation"
    / "ground_truth"
    / "gt_2876.jsonl"
)

DG_FILE = (
    PROJECT_ROOT
    / "data_prep"
    / "evaluation"
    / "deepgram"
    / "outputs"
    / "2915_deepgram.json"
)

SAMPLE_ID = "2915"


def main():

    # ========================================================
    # GT 2915 찾기
    # ========================================================

    gt = None

    with GT_JSONL.open(
        "r",
        encoding="utf-8"
    ) as f:

        for line in f:

            row = json.loads(line)

            if str(row["sample_id"]) == SAMPLE_ID:
                gt = row
                break

    if gt is None:
        raise RuntimeError(
            f"GT에서 {SAMPLE_ID}를 찾지 못했습니다."
        )

    # ========================================================
    # Deepgram
    # ========================================================

    with DG_FILE.open(
        "r",
        encoding="utf-8"
    ) as f:

        dg = json.load(f)

    gt_utts = gt["utterances"]

    dg_utts = (
        dg
        .get("normalized", {})
        .get("utterances", [])
    )

    dg_words = (
        dg
        .get("normalized", {})
        .get("words", [])
    )

    # ========================================================
    # 출력
    # ========================================================

    print("=" * 70)
    print("TIMESTAMP UNIT CHECK")
    print("=" * 70)

    print()
    print("[GT 앞 5개]")

    for utt in gt_utts[:5]:

        print(
            f"{utt['role']:10} | "
            f"start={utt['start']} | "
            f"end={utt['end']} | "
            f"text={utt['text'][:40]}"
        )

    print()
    print("[Deepgram utterance 앞 5개]")

    for utt in dg_utts[:5]:

        print(
            f"speaker={utt['speaker']} | "
            f"start={utt['start']} | "
            f"end={utt['end']} | "
            f"text={utt['transcript'][:40]}"
        )

    print()
    print("[Deepgram word 앞 5개]")

    for word in dg_words[:5]:

        print(
            f"speaker={word['speaker']} | "
            f"start={word['start']} | "
            f"end={word['end']} | "
            f"word={word['word']}"
        )

    # ========================================================
    # 전체 범위
    # ========================================================

    gt_starts = [
        float(x["start"])
        for x in gt_utts
        if x["start"] is not None
    ]

    gt_ends = [
        float(x["end"])
        for x in gt_utts
        if x["end"] is not None
    ]

    dg_starts = [
        float(x["start"])
        for x in dg_words
        if x["start"] is not None
    ]

    dg_ends = [
        float(x["end"])
        for x in dg_words
        if x["end"] is not None
    ]

    print()
    print("[전체 시간 범위]")

    print(
        f"GT       : "
        f"{min(gt_starts)} ~ {max(gt_ends)}"
    )

    print(
        f"Deepgram : "
        f"{min(dg_starts)} ~ {max(dg_ends)}"
    )

    print()
    print("[비율 확인]")

    gt_max = max(gt_ends)
    dg_max = max(dg_ends)

    if dg_max > 0:

        print(
            f"GT max / DG max = "
            f"{gt_max / dg_max:.4f}"
        )


if __name__ == "__main__":
    main()