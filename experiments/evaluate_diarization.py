import json
from pathlib import Path


GT_JSON_PATH = Path("test_sample/0006.json")
STT_JSON_PATH = Path("test_sample/0006_stt.json")


def time_to_ms(time_str: str) -> int:
    """
    예:
    00:01.970 -> 1970 ms
    01:02.300 -> 62300 ms
    """

    parts = time_str.split(":")

    # MM:SS.mmm 형식
    if len(parts) == 2:
        minutes = int(parts[0])
        seconds, milliseconds = parts[1].split(".")

        return (
            minutes * 60 * 1000
            + int(seconds) * 1000
            + int(milliseconds)
        )

    # HH:MM:SS.mmm 형식이 혹시 있을 경우
    if len(parts) == 3:
        hours = int(parts[0])
        minutes = int(parts[1])
        seconds, milliseconds = parts[2].split(".")

        return (
            hours * 60 * 60 * 1000
            + minutes * 60 * 1000
            + int(seconds) * 1000
            + int(milliseconds)
        )

    raise ValueError(
        f"알 수 없는 시간 형식: {time_str}"
    )


def collect_audio_items(obj):
    """
    JSON 전체를 재귀적으로 탐색해서
    'audio' 배열 안의 Q/A 발화를 모두 수집한다.
    """

    collected = []

    if isinstance(obj, dict):

        for key, value in obj.items():

            if key == "audio" and isinstance(value, list):

                for item in value:

                    if not isinstance(item, dict):
                        continue

                    if (
                        "text" in item
                        and "start" in item
                        and "end" in item
                    ):
                        collected.append(item)

            else:
                collected.extend(
                    collect_audio_items(value)
                )

    elif isinstance(obj, list):

        for item in obj:
            collected.extend(
                collect_audio_items(item)
            )

    return collected


def load_ground_truth(path: Path):

    with open(
        path,
        "r",
        encoding="utf-8",
    ) as f:
        data = json.load(f)

    audio_items = collect_audio_items(data)

    result = []

    for idx, item in enumerate(
        audio_items,
        start=1,
    ):

        result.append(
            {
                "gt_id": idx,
                "speaker": item.get(
                    "type",
                    "UNKNOWN",
                ),
                "start_ms": time_to_ms(
                    item["start"]
                ),
                "end_ms": time_to_ms(
                    item["end"]
                ),
                "text": item.get(
                    "text",
                    "",
                ).strip(),
            }
        )

    # 시간 순서로 정렬
    result.sort(
        key=lambda x: (
            x["start_ms"],
            x["end_ms"],
        )
    )

    # 정렬 후 ID 다시 부여
    for idx, item in enumerate(
        result,
        start=1,
    ):
        item["gt_id"] = idx

    return result


def load_stt(path: Path):

    with open(
        path,
        "r",
        encoding="utf-8",
    ) as f:
        data = json.load(f)

    # Swagger 전체 Response Body인 경우
    if "stt_data" in data:
        return data["stt_data"].get(
            "segments",
            [],
        )

    # stt_data 내부만 저장한 경우
    return data.get(
        "segments",
        [],
    )


def overlap_ms(
    a_start,
    a_end,
    b_start,
    b_end,
):

    start = max(
        a_start,
        b_start,
    )

    end = min(
        a_end,
        b_end,
    )

    return max(
        0,
        end - start,
    )


def find_best_stt_for_gt(
    gt,
    stt_segments,
):

    best = None
    best_overlap = 0

    for stt in stt_segments:

        overlap = overlap_ms(
            gt["start_ms"],
            gt["end_ms"],
            stt["start_ms"],
            stt["end_ms"],
        )

        if overlap > best_overlap:
            best_overlap = overlap
            best = stt

    return best, best_overlap


def detect_many_gt_to_one_stt(
    gt_segments,
    stt_segments,
):
    """
    서로 다른 GT 발화 여러 개가
    하나의 STT segment에 매칭되는 경우 탐지.

    예:
    GT Q: 최근에 다친 적이 있었니?
    GT A: 다친 적은 없어요.

    둘 다 seg_009로 매칭되는 경우.
    """

    mapping = {}

    for gt in gt_segments:

        best, overlap = (
            find_best_stt_for_gt(
                gt,
                stt_segments,
            )
        )

        if best is None:
            continue

        if overlap <= 0:
            continue

        seg_id = best.get(
            "segment_id",
            "UNKNOWN",
        )

        mapping.setdefault(
            seg_id,
            [],
        ).append(gt)

    problems = []

    for seg_id, gts in mapping.items():

        if len(gts) < 2:
            continue

        speakers = {
            gt["speaker"]
            for gt in gts
        }

        # 서로 다른 GT 화자가 한 STT segment에 들어간 경우
        if len(speakers) >= 2:

            problems.append(
                {
                    "segment_id": seg_id,
                    "gt_segments": gts,
                }
            )

    return problems


def collect_overlapping_stt_text(gt, stt_segments):
    """
    하나의 GT 발화 시간 구간과 겹치는
    모든 STT segment의 텍스트를 시간순으로 모은다.
    """

    overlapping = []

    for stt in stt_segments:
        overlap = overlap_ms(
            gt["start_ms"],
            gt["end_ms"],
            stt["start_ms"],
            stt["end_ms"],
        )

        if overlap > 0:
            overlapping.append(stt)

    overlapping.sort(
        key=lambda x: (
            x["start_ms"],
            x["end_ms"],
        )
    )

    combined_text = " ".join(
        seg.get("text", "").strip()
        for seg in overlapping
        if seg.get("text")
    )

    return combined_text, overlapping


def analyze_top_cer_errors(
    gt_segments,
    stt_segments,
    top_n=10,
):
    """
    GT 발화별로 겹치는 STT 텍스트를 모은 뒤
    구간 CER이 높은 순서로 출력한다.
    """

    results = []

    for gt in gt_segments:

        stt_text, matched_segments = (
            collect_overlapping_stt_text(
                gt,
                stt_segments,
            )
        )

        if not stt_text:
            results.append(
                {
                    "gt": gt,
                    "stt_text": "",
                    "matched_segments": [],
                    "cer": 1.0,
                    "distance": len(
                        normalize_for_cer(
                            gt["text"],
                            remove_spaces=True,
                        )
                    ),
                }
            )

            continue

        cer, distance, gt_len = calculate_cer(
            gt["text"],
            stt_text,
            remove_spaces=True,
        )

        results.append(
            {
                "gt": gt,
                "stt_text": stt_text,
                "matched_segments": matched_segments,
                "cer": cer,
                "distance": distance,
                "gt_len": gt_len,
            }
        )

    results.sort(
        key=lambda x: x["cer"],
        reverse=True,
    )

    print()
    print("=" * 90)
    print(
        f"GT 발화별 CER 오류 TOP {top_n}"
    )
    print("=" * 90)

    for rank, item in enumerate(
        results[:top_n],
        start=1,
    ):

        gt = item["gt"]

        print()
        print(
            f"[TOP {rank}] "
            f"GT {gt['gt_id']:03d} "
            f"{gt['speaker']}"
        )

        print(
            f"시간: "
            f"{gt['start_ms']} ~ "
            f"{gt['end_ms']}"
        )

        print(
            f"GT : "
            f"{gt['text']}"
        )

        print(
            f"STT: "
            f"{item['stt_text']}"
        )

        print(
            f"구간 CER(공백 제거): "
            f"{item['cer'] * 100:.2f}%"
        )

        if item["matched_segments"]:

            ids = [
                seg.get(
                    "segment_id",
                    "UNKNOWN",
                )
                for seg
                in item["matched_segments"]
            ]

            print(
                "겹친 STT segment: "
                + ", ".join(ids)
            )

        else:

            print(
                "겹친 STT segment: 없음"
            )

import difflib


def analyze_text_diff(gt_segments, stt_segments, top_n=10):
    """
    GT 전체 텍스트와 STT 전체 텍스트를 직접 비교해서
    실제 문자 차이가 큰 구간을 출력한다.

    시간(timestamp)은 사용하지 않는다.
    """

    # 1. 전체 텍스트 생성
    gt_text = " ".join(
        seg.get("text", "").strip()
        for seg in gt_segments
        if seg.get("text")
    )

    stt_text = " ".join(
        seg.get("text", "").strip()
        for seg in stt_segments
        if seg.get("text")
    )

    # 띄어쓰기 차이는 이번 분석에서 제외
    gt_normalized = "".join(gt_text.split())
    stt_normalized = "".join(stt_text.split())

    # 2. 전체 문자열 정렬
    matcher = difflib.SequenceMatcher(
        None,
        gt_normalized,
        stt_normalized,
        autojunk=False,
    )

    errors = []

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():

        # equal은 GT/STT가 같은 부분
        if tag == "equal":
            continue

        gt_part = gt_normalized[i1:i2]
        stt_part = stt_normalized[j1:j2]

        # 차이 크기
        error_size = max(
            len(gt_part),
            len(stt_part),
        )

        errors.append(
            {
                "tag": tag,
                "gt": gt_part,
                "stt": stt_part,
                "error_size": error_size,
                "gt_start": i1,
                "gt_end": i2,
                "stt_start": j1,
                "stt_end": j2,
            }
        )

    # 큰 차이부터 정렬
    errors.sort(
        key=lambda x: x["error_size"],
        reverse=True,
    )

    print()
    print("=" * 90)
    print(f"전체 텍스트 실제 차이 TOP {top_n}")
    print("=" * 90)

    for rank, error in enumerate(
        errors[:top_n],
        start=1,
    ):

        tag = error["tag"]

        if tag == "replace":
            error_type = "치환"

        elif tag == "delete":
            error_type = "GT 내용 누락"

        elif tag == "insert":
            error_type = "STT 내용 추가"

        else:
            error_type = tag

        # 오류 주변 문맥도 같이 출력
        context_size = 30

        gt_context_start = max(
            0,
            error["gt_start"] - context_size,
        )

        gt_context_end = min(
            len(gt_normalized),
            error["gt_end"] + context_size,
        )

        stt_context_start = max(
            0,
            error["stt_start"] - context_size,
        )

        stt_context_end = min(
            len(stt_normalized),
            error["stt_end"] + context_size,
        )

        gt_context = gt_normalized[
            gt_context_start:gt_context_end
        ]

        stt_context = stt_normalized[
            stt_context_start:stt_context_end
        ]

        print()
        print("-" * 90)

        print(
            f"[TOP {rank}] "
            f"{error_type}"
        )

        print(
            f"차이 크기: "
            f"{error['error_size']}자"
        )

        print()

        print(
            f"GT 차이 : "
            f"{error['gt'] if error['gt'] else '(없음)'}"
        )

        print(
            f"STT 차이: "
            f"{error['stt'] if error['stt'] else '(없음)'}"
        )

        print()

        print("[주변 문맥]")

        print(
            f"GT : ...{gt_context}..."
        )

        print(
            f"STT: ...{stt_context}..."
        )

    print()
    print("=" * 90)

def analyze_stt_segments_against_gt(
    gt_segments,
    stt_segments,
    top_n=10,
):
    """
    실제 STT segment 각각을 기준으로
    시간상 겹치는 GT 발화들과 비교한다.

    목적:
    - 실제 0006_stt.json에 존재하는 segment만 검사
    - STT가 GT에 없는 내용을 말했는지 확인
    - segment 병합/분할 문제와 실제 전사 오류를 구분
    """

    results = []

    for stt in stt_segments:

        overlapping_gt = []

        # --------------------------------------------
        # 이 STT segment와 겹치는 GT 전부 찾기
        # --------------------------------------------
        for gt in gt_segments:

            overlap = overlap_ms(
                stt["start_ms"],
                stt["end_ms"],
                gt["start_ms"],
                gt["end_ms"],
            )

            if overlap > 0:
                overlapping_gt.append(gt)

        # 시간순 정렬
        overlapping_gt.sort(
            key=lambda x: (
                x["start_ms"],
                x["end_ms"],
            )
        )

        # --------------------------------------------
        # 겹치는 GT 텍스트 합치기
        # --------------------------------------------
        gt_text = " ".join(
            gt.get("text", "").strip()
            for gt in overlapping_gt
            if gt.get("text")
        )

        stt_text = stt.get(
            "text",
            "",
        ).strip()

        # --------------------------------------------
        # 겹치는 GT 자체가 없는 경우
        # --------------------------------------------
        if not gt_text:

            results.append(
                {
                    "segment_id": stt.get(
                        "segment_id",
                        "UNKNOWN",
                    ),
                    "speaker": stt.get(
                        "speaker",
                        "UNKNOWN",
                    ),
                    "start_ms": stt["start_ms"],
                    "end_ms": stt["end_ms"],
                    "stt_text": stt_text,
                    "gt_text": "",
                    "gt_items": [],
                    "cer": 1.0,
                    "similarity": 0.0,
                    "reason": "겹치는 GT 없음",
                }
            )

            continue

        # --------------------------------------------
        # CER 계산
        # --------------------------------------------
        cer, _, _ = calculate_cer(
            gt_text,
            stt_text,
            remove_spaces=True,
        )

        # CER는 100%를 넘을 수도 있으므로
        # 보기 쉬운 유사도는 별도로 계산
        gt_norm = normalize_for_cer(
            gt_text,
            remove_spaces=True,
        )

        stt_norm = normalize_for_cer(
            stt_text,
            remove_spaces=True,
        )

        import difflib

        similarity = difflib.SequenceMatcher(
            None,
            gt_norm,
            stt_norm,
            autojunk=False,
        ).ratio()

        results.append(
            {
                "segment_id": stt.get(
                    "segment_id",
                    "UNKNOWN",
                ),
                "speaker": stt.get(
                    "speaker",
                    "UNKNOWN",
                ),
                "start_ms": stt["start_ms"],
                "end_ms": stt["end_ms"],
                "stt_text": stt_text,
                "gt_text": gt_text,
                "gt_items": overlapping_gt,
                "cer": cer,
                "similarity": similarity,
                "reason": "",
            }
        )

    # --------------------------------------------
    # 유사도가 낮은 실제 STT segment부터 정렬
    # --------------------------------------------

    results.sort(
        key=lambda x: (
            x["similarity"],
            -len(x["stt_text"]),
        )
    )

    print()
    print("=" * 90)
    print(
        f"실제 STT segment 기준 오류 후보 TOP {top_n}"
    )
    print("=" * 90)

    for rank, item in enumerate(
        results[:top_n],
        start=1,
    ):

        print()
        print("-" * 90)

        print(
            f"[TOP {rank}] "
            f"{item['segment_id']} "
            f"| {item['speaker']}"
        )

        print(
            f"시간: "
            f"{item['start_ms']} ~ "
            f"{item['end_ms']}"
        )

        print(
            f"유사도: "
            f"{item['similarity'] * 100:.2f}%"
        )

        print(
            f"구간 CER: "
            f"{item['cer'] * 100:.2f}%"
        )

        if item["reason"]:

            print(
                f"판정: "
                f"{item['reason']}"
            )

        print()

        print(
            f"STT 원문: "
            f"{item['stt_text']}"
        )

        print(
            f"GT 비교 : "
            f"{item['gt_text'] if item['gt_text'] else '(없음)'}"
        )

        # 어떤 GT 발화와 겹쳤는지도 표시
        if item["gt_items"]:

            print()
            print("겹친 GT:")

            for gt in item["gt_items"]:

                print(
                    f"  "
                    f"{gt.get('speaker', '?')} "
                    f"| "
                    f"{gt['start_ms']} ~ "
                    f"{gt['end_ms']} "
                    f"| "
                    f"{gt.get('text', '')}"
                )

    print()
    print("=" * 90)


def main():

    gt_segments = load_ground_truth(
        GT_JSON_PATH
    )

    stt_segments = load_stt(
        STT_JSON_PATH
    )

    print("=" * 90)
    print(
        "I-SPOT STT / 화자분리 비교"
    )
    print("=" * 90)

    print()

    print(
        f"GT 발화 수       : "
        f"{len(gt_segments)}"
    )

    print(
        f"STT segment 수  : "
        f"{len(stt_segments)}"
    )

    speaker2_count = sum(
        1
        for seg in stt_segments
        if seg.get("speaker")
        == "SPEAKER_2"
    )

    print(
        f"SPEAKER_2 segment 수 : "
        f"{speaker2_count}"
    )

    print()
    print("=" * 90)
    print(
        "GT 발화별 가장 많이 겹치는 STT segment"
    )
    print("=" * 90)

    no_match = 0
    suspicious = 0

    for gt in gt_segments:

        best, overlap = (
            find_best_stt_for_gt(
                gt,
                stt_segments,
            )
        )

        print()

        print(
            f"[GT {gt['gt_id']:03d}] "
            f"{gt['speaker']} | "
            f"{gt['start_ms']} ~ "
            f"{gt['end_ms']}"
        )

        print(
            f"GT : {gt['text']}"
        )

        if best is None:

            print(
                "STT: 매칭 없음"
            )

            no_match += 1
            continue

        gt_duration = max(
            1,
            gt["end_ms"]
            - gt["start_ms"],
        )

        overlap_ratio = (
            overlap
            / gt_duration
        )

        print(
            f"STT: "
            f"{best.get('segment_id')} | "
            f"{best.get('speaker')} | "
            f"{best.get('start_ms')} ~ "
            f"{best.get('end_ms')}"
        )

        print(
            f"    "
            f"{best.get('text')}"
        )

        print(
            f"시간 겹침률: "
            f"{overlap_ratio * 100:.1f}%"
        )

        reasons = []

        if overlap_ratio < 0.5:
            reasons.append(
                "시간 겹침 낮음"
            )

        stt_duration = (
            best["end_ms"]
            - best["start_ms"]
        )

        if (
            stt_duration
            > gt_duration * 1.8
        ):
            reasons.append(
                "STT segment가 GT보다 지나치게 김"
            )

        if (
            best.get("speaker")
            == "SPEAKER_2"
        ):
            reasons.append(
                "SPEAKER_2 발생"
            )

        if reasons:

            suspicious += 1

            print(
                "⚠ 의심:",
                ", ".join(reasons),
            )

    # ========================================================
    # 서로 다른 Q/A가 하나의 STT segment로 합쳐진 경우
    # ========================================================

    merge_problems = (
        detect_many_gt_to_one_stt(
            gt_segments,
            stt_segments,
        )
    )

    print()
    print("=" * 90)
    print(
        "서로 다른 GT 화자가 하나의 STT segment에 합쳐진 경우"
    )
    print("=" * 90)

    if not merge_problems:

        print(
            "발견되지 않음"
        )

    else:

        for problem in merge_problems:

            print()

            print(
                f"⚠ {problem['segment_id']}"
            )

            for gt in problem[
                "gt_segments"
            ]:

                print(
                    f"   "
                    f"{gt['speaker']} | "
                    f"{gt['start_ms']} ~ "
                    f"{gt['end_ms']} | "
                    f"{gt['text']}"
                )

    print()
    print("=" * 90)
    print("요약")
    print("=" * 90)

    print(
        f"GT 발화 수             : "
        f"{len(gt_segments)}"
    )

    print(
        f"STT segment 수        : "
        f"{len(stt_segments)}"
    )

    print(
        f"매칭 실패              : "
        f"{no_match}"
    )

    print(
        f"의심 GT 발화           : "
        f"{suspicious}"
    )

    print(
        f"SPEAKER_2 segment     : "
        f"{speaker2_count}"
    )

    print(
        f"Q/A 병합 의심 segment : "
        f"{len(merge_problems)}"
    )
    evaluate_cer(gt_segments, stt_segments)
    analyze_top_cer_errors(gt_segments, stt_segments, top_n=10)
    analyze_text_diff(gt_segments, stt_segments, top_n=10)
    analyze_stt_segments_against_gt(gt_segments, stt_segments, top_n=10,)


def levenshtein_distance(a: str, b: str) -> int:
    """
    문자열 a -> b로 바꾸기 위한 최소 편집 횟수
    삽입 / 삭제 / 치환
    """
    prev = list(range(len(b) + 1))

    for i, ca in enumerate(a, start=1):
        curr = [i]

        for j, cb in enumerate(b, start=1):
            insert_cost = curr[j - 1] + 1
            delete_cost = prev[j] + 1
            replace_cost = prev[j - 1] + (0 if ca == cb else 1)

            curr.append(
                min(
                    insert_cost,
                    delete_cost,
                    replace_cost,
                )
            )

        prev = curr

    return prev[-1]


def normalize_for_cer(text: str, remove_spaces: bool = False) -> str:
    """
    CER 계산용 간단한 정규화
    """
    text = text.strip()

    if remove_spaces:
        text = "".join(text.split())
    else:
        # 여러 개의 공백을 하나로 통일
        text = " ".join(text.split())

    return text


def calculate_cer(gt_text: str, stt_text: str, remove_spaces: bool = False):
    gt = normalize_for_cer(gt_text, remove_spaces=remove_spaces)
    stt = normalize_for_cer(stt_text, remove_spaces=remove_spaces)

    if len(gt) == 0:
        return 0.0, 0, 0

    distance = levenshtein_distance(gt, stt)
    cer = distance / len(gt)

    return cer, distance, len(gt)


def evaluate_cer(gt_items, stt_segments):
    """
    전체 상담 음성 기준 CER 계산
    """

    gt_text = " ".join(
        item["text"]
        for item in gt_items
        if item.get("text")
    )

    stt_text = " ".join(
        seg["text"]
        for seg in stt_segments
        if seg.get("text")
    )

    cer_with_spaces, dist1, gt_len1 = calculate_cer(
        gt_text,
        stt_text,
        remove_spaces=False
    )

    cer_without_spaces, dist2, gt_len2 = calculate_cer(
        gt_text,
        stt_text,
        remove_spaces=True
    )

    print()
    print("=" * 80)
    print("STT 텍스트 정확도 평가")
    print("=" * 80)

    print(f"GT 문자 수 - 공백 포함   : {gt_len1}")
    print(f"편집 오류 수 - 공백 포함 : {dist1}")
    print(f"CER - 공백 포함          : {cer_with_spaces * 100:.2f}%")

    print()

    print(f"GT 문자 수 - 공백 제거   : {gt_len2}")
    print(f"편집 오류 수 - 공백 제거 : {dist2}")
    print(f"CER - 공백 제거          : {cer_without_spaces * 100:.2f}%")

    print()
    print(f"문자 정확도 - 공백 포함   : {(1 - cer_with_spaces) * 100:.2f}%")
    print(f"문자 정확도 - 공백 제거   : {(1 - cer_without_spaces) * 100:.2f}%")


if __name__ == "__main__":
    main()
    

