import csv
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

ROLE_CSV = (
    PROJECT_ROOT
    / "data_prep"
    / "evaluation"
    / "deepgram"
    / "gt_role_mapping_100.csv"
)

CER_CSV = (
    PROJECT_ROOT
    / "data_prep"
    / "evaluation"
    / "deepgram"
    / "child_text_cer_100.csv"
)

DG_DIR = (
    PROJECT_ROOT
    / "data_prep"
    / "evaluation"
    / "deepgram"
    / "outputs"
)

SAMPLE_IDS = ["3140", "1726"]


def load_gt():
    result = {}

    with GT_JSONL.open("r", encoding="utf-8") as f:
        for line in f:
            row = json.loads(line)

            sample_id = str(
                row["sample_id"]
            ).strip()

            if sample_id in SAMPLE_IDS:
                result[sample_id] = row

    return result


def load_csv_map(path):
    with path.open(
        "r",
        encoding="utf-8-sig",
        newline=""
    ) as f:

        return {
            row["sample_id"].strip(): row
            for row in csv.DictReader(f)
        }


def main():

    gt_map = load_gt()
    role_map = load_csv_map(ROLE_CSV)
    cer_map = load_csv_map(CER_CSV)

    for sample_id in SAMPLE_IDS:

        print()
        print("=" * 90)
        print(f"SAMPLE {sample_id}")
        print("=" * 90)

        gt = gt_map[sample_id]
        role = role_map[sample_id]
        cer = cer_map[sample_id]

        dg_path = (
            DG_DIR
            / f"{sample_id}_deepgram.json"
        )

        with dg_path.open(
            "r",
            encoding="utf-8"
        ) as f:
            dg = json.load(f)

        normalized = dg["normalized"]

        print()
        print("[기본 결과]")

        print(
            f"Deepgram speaker 수: "
            f"{normalized['speaker_count']}"
        )

        print(
            f"mapping_status: "
            f"{role['mapping_status']}"
        )

        print(
            f"CHILD speaker: "
            f"{role['child_speaker_ids']}"
        )

        print(
            f"COUNSELOR speaker: "
            f"{role['counselor_speaker_ids']}"
        )

        print(
            f"CER(공백 제거): "
            f"{float(cer['cer_without_spaces']) * 100:.2f}%"
        )

        print()
        print("[speaker mapping 상세]")

        details = json.loads(
            role["speaker_mapping_json"]
        )

        for item in details:

            print(
                f"speaker={item['speaker']} | "
                f"role={item['role']} | "
                f"CHILD overlap={item['child_sec']:.2f}s | "
                f"COUNSELOR overlap={item['counselor_sec']:.2f}s | "
                f"purity={item['purity']:.4f} | "
                f"words={item['word_count']}"
            )

        print()
        print("[GT CHILD TEXT 앞 500자]")
        print(
            gt["child_text"][:500]
        )

        print()
        print("[DEEPGRAM CHILD TEXT 앞 500자]")
        print(
            cer["deepgram_child_text"][:500]
        )

        print()
        print("[GT 발화 앞 20개]")

        for utt in gt["utterances"][:20]:

            print(
                f"{utt['role']:10} | "
                f"{utt['start']:8.3f} ~ "
                f"{utt['end']:8.3f} | "
                f"{utt['text']}"
            )

        print()
        print("[Deepgram utterance 앞 20개]")

        for utt in normalized["utterances"][:20]:

            print(
                f"SPK{utt['speaker']} | "
                f"{utt['start']:8.3f} ~ "
                f"{utt['end']:8.3f} | "
                f"{utt['transcript']}"
            )


if __name__ == "__main__":
    main()