import json
import random
import zipfile
from collections import Counter
from pathlib import Path


# ============================================================
# 1. 설정
# ============================================================

BASE_DIR = Path(__file__).resolve().parent
TEST_SAMPLE_DIR = BASE_DIR / "test_sample"

# 네 AI-Hub 데이터 경로
AUDIO_ZIP = Path(
    r"C:\Users\USER\Desktop\헬스케어 4조"
    r"\024.아동·청소년_상담_데이터"
    r"\3.개방데이터\1.데이터\Training"
    r"\01.원천데이터\TS_in.zip"
)

LABEL_ZIP = Path(
    r"C:\Users\USER\Desktop\헬스케어 4조"
    r"\024.아동·청소년_상담_데이터"
    r"\3.개방데이터\1.데이터\Training"
    r"\02.라벨링데이터\TL_out.zip"
)

TARGET_TOTAL = 30
SEED = 69

random.seed(SEED)


# ============================================================
# 2. 학대유형 정규화
# ============================================================

LABEL_GROUPS = [
    "신체학대",
    "정서학대",
    "성학대",
    "방임",
    "해당없음",
]


def normalize_label(value):

    value = str(value).strip()

    if value in {
        "",
        "해당없음",
        "해당 없음",
        "(해당 없음)",
        "없음",
    }:
        return "해당없음"

    for label in [
        "신체학대",
        "정서학대",
        "성학대",
        "방임",
    ]:
        if label in value:
            return label

    return "기타"


# ============================================================
# 3. ZIP 내부 파일 ID 맵 생성
# ============================================================

def build_zip_map(zip_file, suffix):

    result = {}

    for name in zip_file.namelist():

        if not name.lower().endswith(suffix):
            continue

        stem = Path(name).stem

        # 0002 같은 숫자 ID만 사용
        if stem.isdigit():
            result[stem] = name

    return result


# ============================================================
# 4. ZIP 안의 JSON 읽기
# ============================================================

def read_json_from_zip(
    zip_file,
    internal_name,
):

    raw = zip_file.read(
        internal_name
    )

    text = raw.decode(
        "utf-8-sig"
    )

    return json.loads(text)


# ============================================================
# 5. 기존 test_sample ID 확인
# ============================================================

def get_existing_ids():

    ids = set()

    for json_path in TEST_SAMPLE_DIR.glob(
        "*.json"
    ):

        # *_stt.json은 제외
        if json_path.stem.endswith(
            "_stt"
        ):
            continue

        if json_path.stem.isdigit():
            ids.add(
                json_path.stem
            )

    return ids


# ============================================================
# 6. 기존 샘플 라벨 확인
# ============================================================

def get_existing_label_counts(
    existing_ids,
):

    counts = Counter()

    for file_id in existing_ids:

        json_path = (
            TEST_SAMPLE_DIR
            / f"{file_id}.json"
        )

        try:

            with open(
                json_path,
                "r",
                encoding="utf-8",
            ) as f:

                data = json.load(f)

            label = normalize_label(
                data
                .get("info", {})
                .get(
                    "학대의심",
                    ""
                )
            )

            counts[label] += 1

        except Exception as e:

            print(
                f"[경고] {file_id} "
                f"기존 JSON 확인 실패: {e}"
            )

    return counts


# ============================================================
# 7. 균형 샘플 선택
# ============================================================

def choose_samples(
    candidates_by_label,
    existing_counts,
    needed_count,
):

    selected = []

    # 총 30개라면 5개 그룹 × 약 6개씩을 목표
    target_per_group = (
        TARGET_TOTAL
        // len(LABEL_GROUPS)
    )

    print()
    print(
        f"그룹별 기본 목표 : "
        f"{target_per_group}개"
    )

    # ----------------------------------------
    # 1차: 부족한 그룹부터 채움
    # ----------------------------------------

    for label in LABEL_GROUPS:

        current = existing_counts.get(
            label,
            0,
        )

        need = max(
            0,
            target_per_group - current,
        )

        pool = candidates_by_label.get(
            label,
            []
        )

        random.shuffle(pool)

        take = min(
            need,
            len(pool),
            needed_count - len(selected),
        )

        selected.extend(
            pool[:take]
        )

        # 이미 선택된 후보 제거
        candidates_by_label[label] = (
            pool[take:]
        )

        if len(selected) >= needed_count:
            return selected

    # ----------------------------------------
    # 2차: 그래도 부족하면 남은 모든 후보에서 채움
    # ----------------------------------------

    remaining = []

    for label, pool in candidates_by_label.items():

        remaining.extend(
            pool
        )

    random.shuffle(
        remaining
    )

    remaining_need = (
        needed_count
        - len(selected)
    )

    selected.extend(
        remaining[
            :remaining_need
        ]
    )

    return selected


# ============================================================
# 8. Main
# ============================================================

def main():

    print()
    print("=" * 75)
    print("I-SPOT Test Sample 확대")
    print("=" * 75)

    TEST_SAMPLE_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    # ----------------------------------------
    # 경로 확인
    # ----------------------------------------

    if not AUDIO_ZIP.exists():

        raise FileNotFoundError(
            f"TS_in.zip을 찾을 수 없습니다:\n"
            f"{AUDIO_ZIP}"
        )

    if not LABEL_ZIP.exists():

        raise FileNotFoundError(
            f"TL_out.zip을 찾을 수 없습니다:\n"
            f"{LABEL_ZIP}"
        )

    existing_ids = (
        get_existing_ids()
    )

    print(
        f"현재 기존 샘플 수 : "
        f"{len(existing_ids)}"
    )

    print(
        f"기존 ID           : "
        f"{sorted(existing_ids)}"
    )

    if len(existing_ids) >= TARGET_TOTAL:

        print()
        print(
            f"이미 {TARGET_TOTAL}개 이상 "
            f"존재합니다."
        )
        return

    needed_count = (
        TARGET_TOTAL
        - len(existing_ids)
    )

    print(
        f"추가 필요 샘플 수 : "
        f"{needed_count}"
    )

    existing_counts = (
        get_existing_label_counts(
            existing_ids
        )
    )

    print()
    print(
        "현재 학대유형 분포:"
    )

    for label in LABEL_GROUPS:

        print(
            f"  {label:<6}: "
            f"{existing_counts.get(label, 0)}"
        )

    # ----------------------------------------
    # ZIP 열기
    # ----------------------------------------

    with zipfile.ZipFile(
        AUDIO_ZIP,
        "r",
    ) as audio_zip, zipfile.ZipFile(
        LABEL_ZIP,
        "r",
    ) as label_zip:

        audio_map = build_zip_map(
            audio_zip,
            ".mp3",
        )

        label_map = build_zip_map(
            label_zip,
            ".json",
        )

        common_ids = (
            set(audio_map.keys())
            &
            set(label_map.keys())
        )

        print()
        print(
            f"MP3 ID 수         : "
            f"{len(audio_map)}"
        )

        print(
            f"JSON ID 수        : "
            f"{len(label_map)}"
        )

        print(
            f"공통 ID 수        : "
            f"{len(common_ids)}"
        )

        # 기존 샘플 제외
        candidate_ids = sorted(
            common_ids
            - existing_ids
        )

        # ----------------------------------------
        # 후보를 라벨별로 분류
        # ----------------------------------------

        candidates_by_label = {
            label: []
            for label in LABEL_GROUPS
        }

        candidates_by_label[
            "기타"
        ] = []

        for file_id in candidate_ids:

            try:

                data = read_json_from_zip(
                    label_zip,
                    label_map[file_id],
                )

                label = normalize_label(
                    data
                    .get("info", {})
                    .get(
                        "학대의심",
                        ""
                    )
                )

                candidates_by_label[
                    label
                ].append(
                    file_id
                )

            except Exception as e:

                print(
                    f"[경고] "
                    f"{file_id}.json "
                    f"읽기 실패: {e}"
                )

        print()
        print(
            "추출 가능 후보 분포:"
        )

        for label in LABEL_GROUPS:

            print(
                f"  {label:<6}: "
                f"{len(candidates_by_label[label])}"
            )

        # ----------------------------------------
        # 샘플 선택
        # ----------------------------------------

        selected_ids = choose_samples(
            candidates_by_label,
            existing_counts,
            needed_count,
        )

        print()
        print("=" * 75)
        print(
            f"추가 선택 ID "
            f"({len(selected_ids)}개)"
        )
        print("=" * 75)

        print(
            selected_ids
        )

        # ----------------------------------------
        # 실제 추출
        # ----------------------------------------

        for index, file_id in enumerate(
            selected_ids,
            start=1,
        ):

            mp3_out = (
                TEST_SAMPLE_DIR
                / f"{file_id}.mp3"
            )

            json_out = (
                TEST_SAMPLE_DIR
                / f"{file_id}.json"
            )

            print(
                f"[{index:02d}/"
                f"{len(selected_ids):02d}] "
                f"{file_id}"
            )

            # MP3
            with audio_zip.open(
                audio_map[file_id]
            ) as src:

                with open(
                    mp3_out,
                    "wb",
                ) as dst:

                    dst.write(
                        src.read()
                    )

            # JSON
            with label_zip.open(
                label_map[file_id]
            ) as src:

                with open(
                    json_out,
                    "wb",
                ) as dst:

                    dst.write(
                        src.read()
                    )

    # ----------------------------------------
    # 최종 확인
    # ----------------------------------------

    final_ids = (
        get_existing_ids()
    )

    final_counts = (
        get_existing_label_counts(
            final_ids
        )
    )

    print()
    print("=" * 75)
    print("샘플 확대 완료")
    print("=" * 75)

    print(
        f"최종 샘플 수 : "
        f"{len(final_ids)}"
    )

    print()
    print(
        "최종 학대유형 분포:"
    )

    for label in LABEL_GROUPS:

        print(
            f"  {label:<6}: "
            f"{final_counts.get(label, 0)}"
        )

    print()
    print(
        f"저장 위치 → "
        f"{TEST_SAMPLE_DIR}"
    )

    print("=" * 75)


if __name__ == "__main__":
    main()