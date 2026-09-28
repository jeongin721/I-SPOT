import json
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from abuse_model.infer_abuse import predict_abuse


TARGET_FILES = [
    "1786",
    "5113",
    "2315",
    "5194",
]

TEST_SAMPLE_DIR = PROJECT_ROOT / "test_sample"


def collect_gt_a_utterances(obj):
    """
    JSON 전체를 재귀 탐색하면서

    audio 리스트 내부의
        type == "A"

    인 항목만 수집한다.

    A = 아동 발화
    Q = 상담자 발화
    """

    results = []

    if isinstance(obj, dict):

        # 현재 dict 안에 audio가 있는지 확인
        audio = obj.get("audio")

        if isinstance(audio, list):

            for item in audio:

                if not isinstance(item, dict):
                    continue

                speaker_type = (
                    item.get("type") or ""
                ).strip()

                text = (
                    item.get("text") or ""
                ).strip()

                if (
                    speaker_type == "A"
                    and text
                ):
                    results.append(
                        {
                            "text": text,
                            "start": item.get("start"),
                            "end": item.get("end"),
                        }
                    )

        # 하위 구조 계속 탐색
        for value in obj.values():

            results.extend(
                collect_gt_a_utterances(value)
            )

    elif isinstance(obj, list):

        for item in obj:

            results.extend(
                collect_gt_a_utterances(item)
            )

    return results


def time_to_ms(time_string):
    """
    '00:03.593'
        ↓
    3593 ms

    시간 형식이 이상하면 정렬을 위해
    아주 큰 값을 반환한다.
    """

    if not time_string:
        return 10**15

    try:

        minute, rest = time_string.split(":")

        second, millisecond = rest.split(".")

        return (
            int(minute) * 60 * 1000
            + int(second) * 1000
            + int(millisecond)
        )

    except Exception:

        return 10**15


def remove_exact_duplicates(
    utterances,
):
    """
    JSON 구조 탐색 과정에서 같은 audio 항목이
    중복 수집되는 상황을 방지한다.

    text만으로 제거하지 않고
    start/end/text 조합으로 제거한다.
    """

    seen = set()
    results = []

    for item in utterances:

        key = (
            item.get("start"),
            item.get("end"),
            item.get("text"),
        )

        if key in seen:
            continue

        seen.add(key)
        results.append(item)

    return results


def print_prediction(
    prediction,
):

    for label, info in prediction.items():

        if isinstance(info, dict):

            probability = info.get(
                "probability"
            )

            threshold = info.get(
                "threshold"
            )

            detected = info.get(
                "detected"
            )

            print(
                f"{label:8} | "
                f"prob={probability} | "
                f"threshold={threshold} | "
                f"detected={detected}"
            )

        else:

            print(
                f"{label:8} | {info}"
            )


def analyze_file(
    file_id,
):

    print()
    print("=" * 100)
    print(f"FILE: {file_id}")
    print("=" * 100)

    json_path = (
        TEST_SAMPLE_DIR
        / f"{file_id}.json"
    )

    if not json_path.exists():

        print(
            f"[ERROR] JSON 없음: "
            f"{json_path}"
        )

        return

    with open(
        json_path,
        "r",
        encoding="utf-8",
    ) as f:

        data = json.load(f)

    utterances = (
        collect_gt_a_utterances(data)
    )

    utterances = (
        remove_exact_duplicates(
            utterances
        )
    )

    # 실제 상담 시간 순으로 정렬
    utterances.sort(
        key=lambda x: time_to_ms(
            x.get("start")
        )
    )

    gt_a_text = " ".join(
        item["text"]
        for item in utterances
    ).strip()

    print(
        f"GT A 발화 수       : "
        f"{len(utterances)}"
    )

    print(
        f"GT A-text 글자 수  : "
        f"{len(gt_a_text)}"
    )

    if not gt_a_text:

        print(
            "[ERROR] GT A-text 없음"
        )

        return

    print()
    print(
        "GT A-text preview:"
    )
    print("-" * 100)

    print(
        gt_a_text[:500]
    )

    print()
    print(
        "GT A-text RoBERTa prediction:"
    )
    print("-" * 100)

    prediction = predict_abuse(
        gt_a_text
    )

    print_prediction(
        prediction
    )


def main():

    print("=" * 100)
    print(
        "GT CHILD(A) TEXT → "
        "RoBERTa TEST"
    )
    print("=" * 100)

    for file_id in TARGET_FILES:

        try:

            analyze_file(
                file_id
            )

        except Exception as e:

            print()
            print(
                f"[ERROR] "
                f"{file_id}: {e}"
            )


if __name__ == "__main__":
    main()