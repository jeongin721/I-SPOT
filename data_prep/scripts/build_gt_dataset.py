import csv
import json
import zipfile
from pathlib import Path

# ============================================================
# 경로 설정
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

TL_ZIP = Path(
    r"C:\Users\USER\Desktop\헬스케어 4조\024.아동·청소년_상담_데이터"
    r"\3.개방데이터\1.데이터\Training\02.라벨링데이터\TL_out.zip"
)

OUTPUT_DIR = PROJECT_ROOT / "data_prep" / "evaluation" / "ground_truth"
OUTPUT_CSV = OUTPUT_DIR / "gt_2876.csv"
OUTPUT_JSONL = OUTPUT_DIR / "gt_2876.jsonl"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================
# 유틸 함수
# ============================================================

def safe_text(value):
    if value is None:
        return ""
    return str(value).strip()

def parse_timestamp(value):
    """
    GT timestamp 예:
    00:05.242  -> 5.242초
    01:23.456  -> 83.456초

    혹시 숫자형 데이터가 들어오면 그대로 초로 처리한다.
    """
    if value is None:
        return None

    if isinstance(value, (int, float)):
        return float(value)

    value = str(value).strip()

    if not value:
        return None

    try:
        parts = value.split(":")

        if len(parts) == 2:
            minutes = float(parts[0])
            seconds = float(parts[1])

            return minutes * 60 + seconds

        elif len(parts) == 3:
            hours = float(parts[0])
            minutes = float(parts[1])
            seconds = float(parts[2])

            return (
                hours * 3600
                + minutes * 60
                + seconds
            )

        return float(value)

    except (TypeError, ValueError):
        return None


def find_audio_items(obj):
    """
    JSON 내부를 재귀적으로 탐색해서
    audio 정보가 들어 있는 모든 dict를 찾는다.

    기대 구조 예:
    {
        "type": "Q",
        "text": "...",
        "wave": "all.wav",
        "start": 12.3,
        "end": 15.1
    }
    """
    found = []

    if isinstance(obj, dict):
        keys = set(obj.keys())

        # 실제 발화 항목으로 판단
        if "type" in keys and "text" in keys and "start" in keys and "end" in keys:
            found.append(obj)

        for value in obj.values():
            found.extend(find_audio_items(value))

    elif isinstance(obj, list):
        for item in obj:
            found.extend(find_audio_items(item))

    return found


def parse_label_json(data, sample_id):
    info = data.get("info", {})

    audio_items = find_audio_items(data.get("list", data))

    utterances = []
    child_texts = []
    counselor_texts = []

    q_count = 0
    a_count = 0

    for item in audio_items:
        speaker_type = safe_text(item.get("type")).upper()
        text = safe_text(item.get("text"))

        start = parse_timestamp(item.get("start"))
        end = parse_timestamp(item.get("end"))

        # Q = 상담사, A = 아동
        if speaker_type == "Q":
            role = "COUNSELOR"
            q_count += 1

            if text:
                counselor_texts.append(text)

        elif speaker_type == "A":
            role = "CHILD"
            a_count += 1

            if text:
                child_texts.append(text)

        else:
            role = "UNKNOWN"

        utterances.append(
            {
                "type": speaker_type,
                "role": role,
                "text": text,
                "start": start,
                "end": end,
            }
        )

    # 시간 순서 정렬
    utterances.sort(
        key=lambda x: (
            x["start"] is None,
            x["start"] if x["start"] is not None else 999999999
        )
    )

    child_text = " ".join(child_texts).strip()
    counselor_text = " ".join(counselor_texts).strip()

    all_text = " ".join(
        u["text"]
        for u in utterances
        if u["text"]
    ).strip()

    return {
        "sample_id": sample_id,

        # 기본 정보
        "gender": safe_text(info.get("성별")),
        "age": safe_text(info.get("나이")),
        "grade": safe_text(info.get("학년")),
        "subject_type": safe_text(info.get("유형구분")),

        # 상담/행동 정보
        "tension_level": safe_text(info.get("긴장 수준(종합)")),
        "behavior_characteristic": safe_text(info.get("행동 특성(종합)")),
        "interaction_characteristic": safe_text(info.get("상호작용 특성(종합)")),

        # 위험/학대 정보
        "risk_stage": safe_text(info.get("위기단계")),
        "abuse_label": safe_text(info.get("학대의심")),

        # 발화 통계
        "utterance_count": len(utterances),
        "counselor_utterance_count": q_count,
        "child_utterance_count": a_count,

        # GT 텍스트
        "child_text": child_text,
        "counselor_text": counselor_text,
        "all_text": all_text,

        # 상세 발화
        "utterances": utterances,
    }


# ============================================================
# 메인 처리
# ============================================================

def main():
    if not TL_ZIP.exists():
        raise FileNotFoundError(f"TL_out.zip을 찾을 수 없습니다:\n{TL_ZIP}")

    rows = []
    json_failures = []
    empty_child_text = []

    print("=" * 70)
    print("I-SPOT GT DATASET BUILD")
    print("=" * 70)
    print(f"Label ZIP : {TL_ZIP}")
    print(f"Output CSV: {OUTPUT_CSV}")
    print(f"Output JSONL: {OUTPUT_JSONL}")
    print()

    with zipfile.ZipFile(TL_ZIP, "r") as zf:
        json_files = [
            name
            for name in zf.namelist()
            if name.lower().endswith(".json")
        ]

        print(f"JSON 파일 수: {len(json_files)}")
        print()

        for idx, member in enumerate(sorted(json_files), start=1):

            sample_id = Path(member).stem

            try:
                with zf.open(member) as f:
                    raw = f.read().decode("utf-8-sig")
                    data = json.loads(raw)

                parsed = parse_label_json(data, sample_id)
                rows.append(parsed)

                if not parsed["child_text"]:
                    empty_child_text.append(sample_id)

            except Exception as e:
                json_failures.append(
                    {
                        "sample_id": sample_id,
                        "member": member,
                        "error": str(e),
                    }
                )

            if idx % 100 == 0 or idx == len(json_files):
                print(f"[{idx}/{len(json_files)}] 처리 완료")

    # ========================================================
    # JSONL 저장
    # ========================================================

    with OUTPUT_JSONL.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(
                json.dumps(
                    row,
                    ensure_ascii=False
                )
                + "\n"
            )

    # ========================================================
    # CSV 저장
    # ========================================================

    csv_fields = [
        "sample_id",
        "gender",
        "age",
        "grade",
        "subject_type",
        "tension_level",
        "behavior_characteristic",
        "interaction_characteristic",
        "risk_stage",
        "abuse_label",
        "utterance_count",
        "counselor_utterance_count",
        "child_utterance_count",
        "child_text",
        "counselor_text",
        "all_text",
    ]

    with OUTPUT_CSV.open(
        "w",
        encoding="utf-8-sig",
        newline=""
    ) as f:

        writer = csv.DictWriter(
            f,
            fieldnames=csv_fields
        )

        writer.writeheader()

        for row in rows:
            writer.writerow(
                {
                    field: row[field]
                    for field in csv_fields
                }
            )

    # ========================================================
    # 요약 출력
    # ========================================================

    print()
    print("=" * 70)
    print("완료")
    print("=" * 70)

    print(f"성공: {len(rows)}")
    print(f"JSON 실패: {len(json_failures)}")
    print(f"child_text 비어 있음: {len(empty_child_text)}")

    total_q = sum(
        row["counselor_utterance_count"]
        for row in rows
    )

    total_a = sum(
        row["child_utterance_count"]
        for row in rows
    )

    print(f"상담사(Q) 총 발화 수: {total_q}")
    print(f"아동(A) 총 발화 수: {total_a}")

    print()
    print("생성 파일:")
    print(OUTPUT_CSV)
    print(OUTPUT_JSONL)

    if json_failures:
        print()
        print("JSON 실패 예시:")
        for item in json_failures[:5]:
            print(item)

    if empty_child_text:
        print()
        print("child_text 비어 있는 ID 예시:")
        print(empty_child_text[:20])


if __name__ == "__main__":
    main()