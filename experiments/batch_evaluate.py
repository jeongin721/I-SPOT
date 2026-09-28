import csv
import json
from pathlib import Path

from dotenv import load_dotenv

from stt.ispot_stt import DeepgramSTTProvider
from stt.ispot_postprocess import STTPostProcessor

from evaluate_diarization import (
    load_ground_truth,
    find_best_stt_for_gt,
    detect_many_gt_to_one_stt,
    calculate_cer,
)


# ============================================================
# 1. 기본 설정
# ============================================================

TEST_DIR = Path("test_sample")
RESULT_CSV = Path("evaluation_results.csv")

SUPPORTED_AUDIO = {
    ".mp3",
    ".wav",
    ".m4a",
    ".flac",
    ".ogg",
    ".aac",
}


# ============================================================
# 2. Deepgram STT 실행
# ============================================================

def run_stt(audio_path: Path):
    """
    실제 I-SPOT API와 동일한 흐름으로 실행한다.

    오디오
      ↓
    DeepgramSTTProvider
      ↓
    STTPostProcessor
      ↓
    최종 STT 결과
    """

    provider = DeepgramSTTProvider()

    raw_result = provider.transcribe(
        str(audio_path)
    )

    post_processor = STTPostProcessor(
        low_confidence_threshold=0.70
    )

    final_result = post_processor.process(
        raw_result
    )

    return final_result


# ============================================================
# 3. STT 결과 JSON 저장
# ============================================================

def save_stt_result(
    audio_path: Path,
    stt_result: dict,
):
    """
    예:
        0002.mp3
        → 0002_stt.json
    """

    output_path = (
        audio_path.parent
        / f"{audio_path.stem}_stt.json"
    )

    response_body = {
        "status": "success",
        "file_name": audio_path.name,
        "stt_data": stt_result,
    }

    with open(
        output_path,
        "w",
        encoding="utf-8",
    ) as f:

        json.dump(
            response_body,
            f,
            ensure_ascii=False,
            indent=2,
        )

    return output_path


# ============================================================
# 4. 파일 하나 평가
# ============================================================

def detect_gt_coverage_issue(
    gt_segments,
    stt_segments,
    max_gap_ms=10000,
    min_run_ms=20000,
    min_chars=80,
    min_segments=3,
):
    """
    GT와 전혀 겹치지 않는 STT segment가
    연속적으로 많이 존재하는지 검사한다.

    이런 경우:
        MP3에는 실제 음성이 존재하지만
        GT JSON에는 해당 발화가 빠져 있을 가능성이 있다.
    """

    uncovered = []

    # --------------------------------------------------------
    # GT와 하나도 겹치지 않는 STT 찾기
    # --------------------------------------------------------

    for stt in stt_segments:

        has_overlap = False

        for gt in gt_segments:

            overlap = max(
                0,
                min(
                    stt["end_ms"],
                    gt["end_ms"],
                )
                - max(
                    stt["start_ms"],
                    gt["start_ms"],
                ),
            )

            if overlap > 0:
                has_overlap = True
                break

        if not has_overlap and stt.get("text", "").strip():
            uncovered.append(stt)

    # 아무 문제도 없는 경우
    if not uncovered:

        return {
            "data_quality": "OK",
            "uncovered_segments": 0,
            "longest_uncovered_ms": 0,
            "longest_uncovered_chars": 0,
        }

    # --------------------------------------------------------
    # 연속된 uncovered STT를 하나의 run으로 묶기
    # --------------------------------------------------------

    runs = []

    current_run = [
        uncovered[0]
    ]

    for stt in uncovered[1:]:

        previous = current_run[-1]

        gap = (
            stt["start_ms"]
            - previous["end_ms"]
        )

        if gap <= max_gap_ms:

            current_run.append(
                stt
            )

        else:

            runs.append(
                current_run
            )

            current_run = [
                stt
            ]

    runs.append(
        current_run
    )

    # --------------------------------------------------------
    # 가장 큰 uncovered 구간 계산
    # --------------------------------------------------------

    run_infos = []

    for run in runs:

        start_ms = run[0][
            "start_ms"
        ]

        end_ms = run[-1][
            "end_ms"
        ]

        duration_ms = (
            end_ms - start_ms
        )

        text = " ".join(
            seg.get("text", "")
            for seg in run
        )

        char_count = len(
            "".join(
                text.split()
            )
        )

        run_infos.append(
            {
                "segment_count": len(run),
                "duration_ms": duration_ms,
                "char_count": char_count,
                "start_ms": start_ms,
                "end_ms": end_ms,
            }
        )

    longest = max(
        run_infos,
        key=lambda x: (
            x["duration_ms"],
            x["char_count"],
        ),
    )

    # --------------------------------------------------------
    # GT 불완전 의심 판정
    # --------------------------------------------------------

    is_incomplete = (
        longest["segment_count"]
        >= min_segments

        and longest["duration_ms"]
        >= min_run_ms

        and longest["char_count"]
        >= min_chars
    )

    return {
        "data_quality":
            "GT_INCOMPLETE"
            if is_incomplete
            else "OK",

        "uncovered_segments":
            len(uncovered),

        "longest_uncovered_ms":
            longest["duration_ms"],

        "longest_uncovered_chars":
            longest["char_count"],
    }


def evaluate_one_file(
    audio_path: Path,
    gt_path: Path,
):

    print()
    print("=" * 80)
    print(f"평가 시작: {audio_path.name}")
    print("=" * 80)

    # --------------------------------------------------------
    # 4-1. Deepgram STT 실행
    # --------------------------------------------------------

    print("1. Deepgram STT 실행 중...")

    stt_result = run_stt(
        audio_path
    )

    stt_segments = stt_result.get(
        "segments",
        [],
    )

    print(
        f"   STT 완료: "
        f"{len(stt_segments)}개 segment"
    )

    # --------------------------------------------------------
    # 4-2. STT 결과 JSON 저장
    # --------------------------------------------------------

    stt_json_path = save_stt_result(
        audio_path,
        stt_result,
    )

    print(
        f"2. STT 결과 저장 완료: "
        f"{stt_json_path.name}"
    )

    # --------------------------------------------------------
    # 4-3. GT 불러오기
    # --------------------------------------------------------

    gt_segments = load_ground_truth(
        gt_path
    )

    coverage_result = detect_gt_coverage_issue(
    gt_segments,
    stt_segments,
    )

    print(
        f"3. GT 불러오기 완료: "
        f"{len(gt_segments)}개 발화"
    )

    # --------------------------------------------------------
    # 4-4. Diarization 진단
    # --------------------------------------------------------

    no_match = 0
    suspicious = 0

    for gt in gt_segments:

        best, overlap = find_best_stt_for_gt(
            gt,
            stt_segments,
        )

        # 겹치는 STT segment가 없는 경우
        if best is None or overlap <= 0:
            no_match += 1
            continue

        gt_duration = max(
            1,
            gt["end_ms"] - gt["start_ms"],
        )

        overlap_ratio = (
            overlap / gt_duration
        )

        stt_duration = (
            best["end_ms"]
            - best["start_ms"]
        )

        reasons = []

        # GT와 STT가 절반도 겹치지 않음
        if overlap_ratio < 0.5:
            reasons.append(
                "시간 겹침 낮음"
            )

        # STT segment가 GT보다 지나치게 긴 경우
        if (
            stt_duration
            > gt_duration * 1.8
        ):
            reasons.append(
                "STT segment가 GT보다 지나치게 김"
            )

        # 데이터셋이 Q/A 2화자 구조인데
        # 세 번째 speaker cluster가 나온 경우
        if (
            best.get("speaker")
            == "SPEAKER_2"
        ):
            reasons.append(
                "SPEAKER_2"
            )

        if reasons:
            suspicious += 1

    # --------------------------------------------------------
    # 4-5. SPEAKER_2 segment 개수
    # --------------------------------------------------------

    speaker2_count = sum(
        1
        for seg in stt_segments
        if seg.get("speaker")
        == "SPEAKER_2"
    )

    # --------------------------------------------------------
    # 4-6. Q/A 병합 의심 segment
    # --------------------------------------------------------

    merge_problems = detect_many_gt_to_one_stt(
        gt_segments,
        stt_segments,
    )

    merge_count = len(
        merge_problems
    )

    # --------------------------------------------------------
    # 4-7. 전체 텍스트 만들기
    # --------------------------------------------------------

    gt_text = " ".join(
        item["text"]
        for item in gt_segments
        if item.get("text")
    )

    stt_text = " ".join(
        seg["text"]
        for seg in stt_segments
        if seg.get("text")
    )

    # --------------------------------------------------------
    # 4-8. CER - 공백 포함
    # --------------------------------------------------------

    cer_space, dist_space, gt_len_space = (
        calculate_cer(
            gt_text,
            stt_text,
            remove_spaces=False,
        )
    )

    # --------------------------------------------------------
    # 4-9. CER - 공백 제거
    # --------------------------------------------------------

    cer_no_space, dist_no_space, gt_len_no_space = (
        calculate_cer(
            gt_text,
            stt_text,
            remove_spaces=True,
        )
    )

    # --------------------------------------------------------
    # 4-10. 결과 정리
    # --------------------------------------------------------

    result = {
        "file": audio_path.stem,

        "gt_count": len(
            gt_segments
        ),

        "stt_count": len(
            stt_segments
        ),

        "no_match": no_match,

        "suspicious_gt": suspicious,

        "speaker2_count": speaker2_count,

        "qa_merge_count": merge_count,

        "gt_chars_space": gt_len_space,

        "edit_errors_space": dist_space,

        "cer_space": round(
            cer_space * 100,
            2,
        ),

        "gt_chars_no_space": gt_len_no_space,

        "edit_errors_no_space": dist_no_space,

        "cer_no_space": round(
            cer_no_space * 100,
            2,
        ),

        "data_quality":
            coverage_result["data_quality"],

        "uncovered_segments":
            coverage_result["uncovered_segments"],

        "longest_uncovered_ms":
            coverage_result["longest_uncovered_ms"],

        "longest_uncovered_chars":
            coverage_result["longest_uncovered_chars"],
    }

    # --------------------------------------------------------
    # 4-11. 파일별 결과 출력
    # --------------------------------------------------------

    print()
    print("-" * 80)

    print(
        f"파일              : "
        f"{result['file']}"
    )

    print(
        f"GT 발화 수         : "
        f"{result['gt_count']}"
    )

    print(
        f"STT segment 수    : "
        f"{result['stt_count']}"
    )

    print(
        f"매칭 실패          : "
        f"{result['no_match']}"
    )

    print(
        f"의심 GT 발화       : "
        f"{result['suspicious_gt']}"
    )

    print(
        f"SPEAKER_2 segment : "
        f"{result['speaker2_count']}"
    )

    print(
        f"Q/A 병합 의심      : "
        f"{result['qa_merge_count']}"
    )

    print(
        f"CER - 공백 포함    : "
        f"{result['cer_space']}%"
    )

    print(
        f"CER - 공백 제거    : "
        f"{result['cer_no_space']}%"
    )

    print(
        f"데이터 품질         : "
        f"{result['data_quality']}"
    )

    print(
        f"GT 미겹침 STT      : "
        f"{result['uncovered_segments']}개"
    )

    print(
        f"최장 미겹침 구간    : "
        f"{result['longest_uncovered_ms'] / 1000:.1f}초"
    )

    print("-" * 80)

    return result


# ============================================================
# 5. CSV 저장
# ============================================================

def save_csv(results):

    fieldnames = [
        "file",
        "gt_count",
        "stt_count",
        "no_match",
        "suspicious_gt",
        "speaker2_count",
        "qa_merge_count",
        "gt_chars_space",
        "edit_errors_space",
        "cer_space",
        "gt_chars_no_space",
        "edit_errors_no_space",
        "cer_no_space",
        "data_quality",
        "uncovered_segments",
        "longest_uncovered_ms",
        "longest_uncovered_chars",
    ]

    with open(
        RESULT_CSV,
        "w",
        newline="",
        encoding="utf-8-sig",
    ) as f:

        writer = csv.DictWriter(
            f,
            fieldnames=fieldnames,
        )

        writer.writeheader()

        writer.writerows(
            results
        )


# ============================================================
# 6. 전체 배치 평가
# ============================================================

def main():

    # .env의 DEEPGRAM_API_KEY 등을 불러온다.
    load_dotenv()

    # --------------------------------------------------------
    # test_sample 안의 오디오 파일 찾기
    # --------------------------------------------------------

    if not TEST_DIR.exists():

        print(
            "❌ test_sample 폴더를 찾을 수 없습니다."
        )

        return

    audio_files = sorted(
        path
        for path in TEST_DIR.iterdir()
        if (
            path.is_file()
            and path.suffix.lower()
            in SUPPORTED_AUDIO
        )
    )

    if not audio_files:

        print(
            "❌ test_sample 폴더에 "
            "오디오 파일이 없습니다."
        )

        return

    print()
    print("=" * 80)
    print("I-SPOT Deepgram 배치 평가")
    print("=" * 80)

    print(
        f"평가 대상 오디오: "
        f"{len(audio_files)}개"
    )

    print()

    results = []

    # --------------------------------------------------------
    # 파일별 반복 평가
    # --------------------------------------------------------

    for index, audio_path in enumerate(
        audio_files,
        start=1,
    ):

        gt_path = (
            audio_path.parent
            / f"{audio_path.stem}.json"
        )

        print()
        print(
            f"[{index}/{len(audio_files)}] "
            f"{audio_path.name}"
        )

        # 대응하는 GT JSON이 없는 경우
        if not gt_path.exists():

            print(
                f"⚠ GT JSON 없음 → "
                f"{gt_path.name}"
            )

            print(
                "이 파일은 평가에서 건너뜁니다."
            )

            continue

        try:

            result = evaluate_one_file(
                audio_path,
                gt_path,
            )

            results.append(
                result
            )

        except Exception as e:

            print()
            print(
                f"❌ {audio_path.name} "
                f"평가 실패"
            )

            print(
                f"오류: {e}"
            )

            # 한 파일에서 오류가 나더라도
            # 나머지 파일은 계속 평가한다.
            continue

    # --------------------------------------------------------
    # 평가 성공 파일이 하나도 없는 경우
    # --------------------------------------------------------

    if not results:

        print()
        print(
            "❌ 평가에 성공한 파일이 없습니다."
        )

        return

    # --------------------------------------------------------
    # CSV 저장
    # --------------------------------------------------------

    save_csv(
        results
    )

    # --------------------------------------------------------
    # 전체 평균 및 합계
    # --------------------------------------------------------

    avg_cer_space = (
        sum(
            row["cer_space"]
            for row in results
        )
        / len(results)
    )

    avg_cer_no_space = (
        sum(
            row["cer_no_space"]
            for row in results
        )
        / len(results)
    )


    # --------------------------------------------------------
    # GT 데이터 품질이 정상인 파일만 따로 평균 계산
    # --------------------------------------------------------

    valid_results = [
        row
        for row in results
        if row["data_quality"] == "OK"
    ]

    if valid_results:

        valid_avg_cer_no_space = (
            sum(
                row["cer_no_space"]
                for row in valid_results
            )
            / len(valid_results)
        )

    else:

        valid_avg_cer_no_space = None


    # --------------------------------------------------------
    # 기존 전체 합계 계산
    # --------------------------------------------------------

    total_gt = sum(
        row["gt_count"]
        for row in results
    )

    total_stt = sum(
        row["stt_count"]
        for row in results
    )

    total_no_match = sum(
        row["no_match"]
        for row in results
    )

    total_suspicious = sum(
        row["suspicious_gt"]
        for row in results
    )

    total_merge = sum(
        row["qa_merge_count"]
        for row in results
    )

    total_speaker2 = sum(
        row["speaker2_count"]
        for row in results
    )

    # --------------------------------------------------------
    # 전체 결과 출력
    # --------------------------------------------------------

    print()
    print("=" * 80)
    print("전체 평가 완료")
    print("=" * 80)

    print(
        f"평가 성공 파일 수       : "
        f"{len(results)}"
    )

    print(
        f"전체 GT 발화 수         : "
        f"{total_gt}"
    )

    print(
        f"전체 STT segment 수    : "
        f"{total_stt}"
    )

    print(
        f"전체 매칭 실패          : "
        f"{total_no_match}"
    )

    print(
        f"전체 의심 GT 발화       : "
        f"{total_suspicious}"
    )

    print(
        f"전체 SPEAKER_2 segment : "
        f"{total_speaker2}"
    )

    print(
        f"전체 Q/A 병합 의심      : "
        f"{total_merge}"
    )

    print()

    print(
        f"평균 CER - 공백 포함    : "
        f"{avg_cer_space:.2f}%"
    )

    print(
        f"평균 CER - 공백 제거    : "
        f"{avg_cer_no_space:.2f}%"
    )

    if valid_avg_cer_no_space is not None:

        print(
            f"GT 품질 OK 평균 CER     : "
            f"{valid_avg_cer_no_space:.2f}%"
        )

    print()

    print(
        f"CSV 저장 완료 → "
        f"{RESULT_CSV}"
    )

    print("=" * 80)


# ============================================================
# 7. 프로그램 시작
# ============================================================

if __name__ == "__main__":
    main()