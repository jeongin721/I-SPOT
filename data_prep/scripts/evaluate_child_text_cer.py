import csv
import json
import re
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

DG_DIR = (
    PROJECT_ROOT
    / "data_prep"
    / "evaluation"
    / "deepgram"
    / "outputs"
)

OUTPUT_CSV = (
    PROJECT_ROOT
    / "data_prep"
    / "evaluation"
    / "deepgram"
    / "child_text_cer_100.csv"
)


# ============================================================
# CER
# ============================================================

def levenshtein(a, b):
    """
    문자 단위 Levenshtein distance
    """
    if len(a) < len(b):
        a, b = b, a

    previous = list(range(len(b) + 1))

    for i, ca in enumerate(a, start=1):

        current = [i]

        for j, cb in enumerate(b, start=1):

            insert_cost = current[j - 1] + 1
            delete_cost = previous[j] + 1
            replace_cost = previous[j - 1] + (ca != cb)

            current.append(
                min(
                    insert_cost,
                    delete_cost,
                    replace_cost
                )
            )

        previous = current

    return previous[-1]


def cer(reference, hypothesis):

    if not reference:
        return None

    distance = levenshtein(
        reference,
        hypothesis
    )

    return distance / len(reference)


# ============================================================
# 정규화
# ============================================================

def normalize_with_spaces(text):

    text = text or ""

    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text.strip()


def normalize_without_spaces(text):

    text = normalize_with_spaces(text)

    return re.sub(
        r"\s+",
        "",
        text
    )


# ============================================================
# GT 로드
# ============================================================

def load_gt():

    gt_map = {}

    with GT_JSONL.open(
        "r",
        encoding="utf-8"
    ) as f:

        for line in f:

            line = line.strip()

            if not line:
                continue

            row = json.loads(line)

            gt_map[
                str(row["sample_id"]).strip()
            ] = row

    return gt_map


# ============================================================
# 메인
# ============================================================

def main():

    gt_map = load_gt()

    with ROLE_CSV.open(
        "r",
        encoding="utf-8-sig",
        newline=""
    ) as f:

        role_rows = list(
            csv.DictReader(f)
        )

    results = []

    for role_row in role_rows:

        sample_id = (
            role_row["sample_id"].strip()
        )

        mapping_status = (
            role_row["mapping_status"].strip()
        )

        # --------------------------------------------
        # CHILD speaker IDs
        # --------------------------------------------

        raw_child_ids = (
            role_row["child_speaker_ids"]
            .strip()
        )

        child_speaker_ids = set()

        if raw_child_ids:

            for value in raw_child_ids.split(","):

                value = value.strip()

                if value:
                    child_speaker_ids.add(
                        int(value)
                    )

        # --------------------------------------------
        # GT
        # --------------------------------------------

        gt = gt_map.get(sample_id)

        if gt is None:
            continue

        gt_child_text = (
            gt.get("child_text", "")
        )

        # --------------------------------------------
        # Deepgram
        # --------------------------------------------

        dg_path = (
            DG_DIR
            / f"{sample_id}_deepgram.json"
        )

        if not dg_path.exists():
            continue

        with dg_path.open(
            "r",
            encoding="utf-8"
        ) as f:

            dg = json.load(f)

        words = (
            dg
            .get("normalized", {})
            .get("words", [])
        )

        # --------------------------------------------
        # GT가 CHILD라고 매핑한 speaker들의 word만 선택
        # --------------------------------------------

        selected_words = []

        for word in words:

            speaker = word.get("speaker")

            if speaker not in child_speaker_ids:
                continue

            start = word.get("start")

            text = (
                word.get("punctuated_word")
                or word.get("word")
                or ""
            )

            selected_words.append(
                {
                    "start": (
                        float(start)
                        if start is not None
                        else 999999999
                    ),
                    "text": text,
                }
            )

        selected_words.sort(
            key=lambda x: x["start"]
        )

        dg_child_text = " ".join(
            item["text"]
            for item in selected_words
            if item["text"]
        )

        # --------------------------------------------
        # CER 계산
        # --------------------------------------------

        ref_space = normalize_with_spaces(
            gt_child_text
        )

        hyp_space = normalize_with_spaces(
            dg_child_text
        )

        ref_nospace = normalize_without_spaces(
            gt_child_text
        )

        hyp_nospace = normalize_without_spaces(
            dg_child_text
        )

        cer_space = cer(
            ref_space,
            hyp_space
        )

        cer_nospace = cer(
            ref_nospace,
            hyp_nospace
        )

        results.append(
            {
                "sample_id": sample_id,

                "mapping_status":
                    mapping_status,

                "child_speaker_ids":
                    raw_child_ids,

                "gt_child_chars":
                    len(ref_space),

                "dg_child_chars":
                    len(hyp_space),

                "cer_with_spaces":
                    (
                        round(cer_space, 6)
                        if cer_space is not None
                        else ""
                    ),

                "cer_without_spaces":
                    (
                        round(cer_nospace, 6)
                        if cer_nospace is not None
                        else ""
                    ),

                "gt_child_text":
                    gt_child_text,

                "deepgram_child_text":
                    dg_child_text,
            }
        )

    # ========================================================
    # CSV 저장
    # ========================================================

    fields = [
        "sample_id",
        "mapping_status",
        "child_speaker_ids",
        "gt_child_chars",
        "dg_child_chars",
        "cer_with_spaces",
        "cer_without_spaces",
        "gt_child_text",
        "deepgram_child_text",
    ]

    with OUTPUT_CSV.open(
        "w",
        encoding="utf-8-sig",
        newline=""
    ) as f:

        writer = csv.DictWriter(
            f,
            fieldnames=fields
        )

        writer.writeheader()
        writer.writerows(results)

    # ========================================================
    # 통계
    # ========================================================

    def valid_values(rows, field):

        values = []

        for row in rows:

            value = row[field]

            if value == "":
                continue

            values.append(
                float(value)
            )

        return values

    all_cer = valid_values(
        results,
        "cer_without_spaces"
    )

    ok_rows = [
        row
        for row in results
        if row["mapping_status"]
        == "ROLE_MAPPING_OK"
    ]

    ok_cer = valid_values(
        ok_rows,
        "cer_without_spaces"
    )

    missing_rows = [
        row
        for row in results
        if row["mapping_status"]
        == "ROLE_MISSING"
    ]

    ambiguous_rows = [
        row
        for row in results
        if row["mapping_status"]
        == "AMBIGUOUS"
    ]

    print("=" * 70)
    print("I-SPOT GT-ASSISTED CHILD TEXT CER")
    print("=" * 70)

    print(
        f"평가 샘플: "
        f"{len(results)}"
    )

    print()

    print(
        f"ROLE_MAPPING_OK: "
        f"{len(ok_rows)}"
    )

    print(
        f"ROLE_MISSING: "
        f"{len(missing_rows)}"
    )

    print(
        f"AMBIGUOUS: "
        f"{len(ambiguous_rows)}"
    )

    print()

    if all_cer:

        print(
            "전체 평균 CER "
            "(공백 제거): "
            f"{sum(all_cer) / len(all_cer) * 100:.2f}%"
        )

    if ok_cer:

        print(
            "ROLE_MAPPING_OK 평균 CER "
            "(공백 제거): "
            f"{sum(ok_cer) / len(ok_cer) * 100:.2f}%"
        )

    # --------------------------------------------------------
    # CER 좋은/나쁜 샘플
    # --------------------------------------------------------

    ranked = [
        row
        for row in results
        if row["cer_without_spaces"] != ""
    ]

    ranked.sort(
        key=lambda x: float(
            x["cer_without_spaces"]
        ),
        reverse=True
    )

    print()
    print("[CER 높은 샘플 TOP 10]")

    for row in ranked[:10]:

        print(
            f"  {row['sample_id']} | "
            f"{row['mapping_status']} | "
            f"CER="
            f"{float(row['cer_without_spaces']) * 100:.2f}% | "
            f"child_speakers="
            f"{row['child_speaker_ids']}"
        )

    print()

    print("저장 완료:")
    print(OUTPUT_CSV)


if __name__ == "__main__":
    main()