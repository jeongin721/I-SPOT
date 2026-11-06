# ai/modeling/abuse/key_scan_refine.py — '1차 임시 핵심 발화' 줄 고르기(2026-10-30 · 정밀도 개선 2026-11-06). 모델 없이 고르기 규칙만 본다.
#
# 11/06: 덩어리에서 걸린 유형이 어느 줄에서도 안 걸리면 덩어리 아동 발화 전체에 붙이던 되돌림을 '확률 가장 높은 줄 하나'(top1,
# 기본) · '안 붙임'(none) · '전체'(all) 로 바꾸고, 줄 임계값(KEY_SCAN_LINE_THRESHOLD) · 줄 판정 상한 계획(걸린 덩어리부터)을 더했다.

from app.adapters.module_loader import ensure_repo_root_on_path

ensure_repo_root_on_path()

import pytest  # noqa: E402

from ai.modeling.abuse import key_scan_refine as kr  # noqa: E402

CHUNK = [
    ("상담사", "요즘 집에서 어때?", {"segment_id": "seg_001"}),
    ("아동", "아빠가 또 화났어요.", {"segment_id": "seg_002"}),
    ("아동", "많이 때렸어요.", {"segment_id": "seg_003"}),
    ("상담사", "그때 기분은 어땠어?", {"segment_id": "seg_004"}),
    ("아동", "네.", {"segment_id": "seg_005"}),
    ("아동", "", {}),  # 번호 없음 → 뺌
]

THRESHOLD = 0.5  # 모델 checkpoint 의 유형별 임계값을 흉내 낸다.

TOP1 = kr.ScanConfig()
NONE = kr.ScanConfig(chunk_fallback="none")
ALL = kr.ScanConfig(chunk_fallback="all")


def _p(**labels):
    """유형별 확률 → 판정 dict. 값이 (확률, 사유) 튜플이면 부정 응답 필터가 내린 유형(detected False · filtered_reason)."""

    prediction = {}
    for label, value in labels.items():
        filtered = None
        if isinstance(value, tuple):
            value, filtered = value
        info = {"probability": value, "detected": value >= THRESHOLD, "threshold": THRESHOLD}
        if filtered:
            info["detected"] = False
            info["filtered_reason"] = filtered
        prediction[label] = info
    return prediction


# ---------------------------------------------------------------------------
# 줄 입력
# ---------------------------------------------------------------------------


def test_child_lines_are_paired_with_previous_counselor_question():
    assert kr.child_line_inputs(CHUNK) == [
        ("seg_002", "상담사: 요즘 집에서 어때?\n아동: 아빠가 또 화났어요."),
        ("seg_003", "상담사: 요즘 집에서 어때?\n아동: 많이 때렸어요."),
        ("seg_005", "상담사: 그때 기분은 어땠어?\n아동: 네."),
    ]


def test_child_line_without_question_is_sent_alone():
    assert kr.child_line_inputs([("아동", "무서웠어요.", {"segment_id": "s1"})]) == [("s1", "아동: 무서웠어요.")]


# ---------------------------------------------------------------------------
# 줄 고르기
# ---------------------------------------------------------------------------


def test_only_lines_over_the_threshold_are_picked_whatever_the_chunk_said():
    picked = kr.pick_segments(
        _p(방임=0.8),
        [
            ("seg_002", _p(신체학대=0.1, 방임=0.2)),
            ("seg_008", _p(신체학대=0.9, 방임=0.1)),
            ("seg_014", _p(신체학대=0.1, 방임=0.7)),
        ],
        TOP1,
    )

    # 덩어리 판정이 놓친 신체학대도 줄에서 걸리면 살린다(10/30 실제 모델 사례). 방임은 넘은 줄(seg_014)에만.
    assert picked == {"seg_008": ["신체학대"], "seg_014": ["방임"]}


def test_chunk_label_no_line_confirms_goes_to_the_most_likely_line_only():
    lines = [("seg_002", _p(정서학대=0.3)), ("seg_003", _p(정서학대=0.45)), ("seg_005", _p(정서학대=0.05))]

    # 11/06 전에는 세 줄 모두에 붙었다 — "네" 같은 줄에도 조문이 붙던 원인.
    assert kr.pick_segments(_p(정서학대=0.9), lines, TOP1) == {"seg_003": ["정서학대"]}
    assert kr.pick_segments(_p(정서학대=0.9), lines) == {"seg_003": ["정서학대"]}  # 환경 변수 없으면 기본 top1


def test_top1_needs_the_minimum_probability():
    lines = [("seg_002", _p(정서학대=0.05)), ("seg_003", _p(정서학대=0.1))]

    assert kr.pick_segments(_p(정서학대=0.9), lines, TOP1) == {}
    assert kr.pick_segments(_p(정서학대=0.9), lines, kr.ScanConfig(fallback_min_probability=0.1)) == {"seg_003": ["정서학대"]}


def test_fallback_none_drops_and_all_marks_every_line_like_before():
    lines = [("seg_002", _p(정서학대=0.3)), ("seg_003", _p(정서학대=0.45))]

    assert kr.pick_segments(_p(정서학대=0.9), lines, NONE) == {}
    assert kr.pick_segments(_p(정서학대=0.9), lines, ALL) == {"seg_002": ["정서학대"], "seg_003": ["정서학대"]}


def test_line_threshold_overrides_the_checkpoint_threshold():
    strict = kr.ScanConfig(line_threshold=0.8)
    lines = [("seg_002", _p(신체학대=0.7)), ("seg_003", _p(신체학대=0.85))]

    assert kr.pick_segments(_p(), lines, TOP1) == {"seg_002": ["신체학대"], "seg_003": ["신체학대"]}
    assert kr.pick_segments(_p(), lines, strict) == {"seg_003": ["신체학대"]}

    # 되돌림(top1)은 줄 임계값이 아니라 최소 확률만 본다 — 덩어리가 걸렸으면 가장 높은 줄 하나는 남긴다.
    assert kr.pick_segments(_p(신체학대=0.9), [("seg_002", _p(신체학대=0.7))], strict) == {"seg_002": ["신체학대"]}


def test_label_the_denial_filter_turned_off_is_never_picked():
    lines = [("seg_002", _p(성학대=(0.9, "아동이 관련 발화를 명확히 부정함"))), ("seg_003", _p(성학대=0.3))]

    # 확률이 높아도 안 붙고, 되돌림(top1)의 후보도 아니다 → 다음 줄.
    assert kr.pick_segments(_p(성학대=0.9), lines, TOP1) == {"seg_003": ["성학대"]}
    assert kr.pick_segments(_p(성학대=0.9), lines, kr.ScanConfig(line_threshold=0.8)) == {"seg_003": ["성학대"]}


def test_bad_predictions_are_ignored():
    assert kr.pick_segments([], [("seg_002", "bad"), ("seg_003", {"신체학대": "x"})], TOP1) == {}
    assert kr.pick_segments("bad", [("seg_002", _p(신체학대=0.9))], TOP1) == {"seg_002": ["신체학대"]}


def test_predictions_without_probabilities_fall_back_to_detected():
    # 예전 모양(확률 없음)이면 detected 를 그대로 믿고, 되돌림은 고를 확률이 없어 top1 이면 아무 줄도 안 고른다.
    lines = [("seg_002", {"신체학대": {"detected": True}}), ("seg_003", {"신체학대": {"detected": False}, "방임": {"detected": False}})]

    assert kr.pick_segments(["방임"], lines, TOP1) == {"seg_002": ["신체학대"]}
    assert kr.pick_segments(["방임"], lines, ALL) == {"seg_002": ["신체학대", "방임"], "seg_003": ["방임"]}


def test_several_labels_merge_per_segment():
    picked = kr.pick_segments(
        _p(신체학대=0.9),
        [("seg_002", _p(신체학대=0.9, 정서학대=0.8)), ("seg_003", _p(신체학대=0.6))],
        TOP1,
    )

    assert picked == {"seg_002": ["신체학대", "정서학대"], "seg_003": ["신체학대"]}


# ---------------------------------------------------------------------------
# 줄 판정 상한 계획 · 예전 방식 · 합치기
# ---------------------------------------------------------------------------

CHUNKS = [
    [("상담사", "q", {"segment_id": "a1"}), ("아동", "x", {"segment_id": "a2"}), ("아동", "x", {"segment_id": "a3"})],
    [("아동", "x", {"segment_id": "b1"}), ("아동", "x", {"segment_id": "b2"}), ("아동", "x", {"segment_id": "b3"})],
    [("상담사", "q", {"segment_id": "c1"}), ("아동", "x", {"segment_id": "c2"}), ("아동", "x", {"segment_id": "c3"})],
    [("상담사", "q", {"segment_id": "d1"})],  # 아동 줄 없음
]
PREDICTIONS = [_p(신체학대=0.9), _p(신체학대=0.1), _p(방임=0.7), _p(정서학대=0.9)]


def test_detected_chunks_are_scored_first_and_chunks_are_all_or_nothing():
    inputs, skipped = kr.plan_line_scoring(CHUNKS, PREDICTIONS, 4)

    assert list(inputs) == [0, 2]
    assert [segment_id for segment_id, _ in inputs[0]] == ["a2", "a3"]
    assert [segment_id for segment_id, _ in inputs[2]] == ["c2", "c3"]
    assert skipped == [1]  # 안 걸린 덩어리는 뒤로 밀려 상한에 못 들었다. 아동 줄 없는 덩어리(3)는 어느 쪽도 아니다.


def test_budget_large_enough_scores_everything_and_zero_scores_nothing():
    inputs, skipped = kr.plan_line_scoring(CHUNKS, PREDICTIONS, 100)
    assert list(inputs) == [0, 1, 2] and skipped == []

    inputs, skipped = kr.plan_line_scoring(CHUNKS, PREDICTIONS, 0)
    assert inputs == {} and skipped == [0, 1, 2]


def test_chunk_wide_pick_marks_child_lines_only():
    assert kr.chunk_wide_pick(CHUNKS[0], ["신체학대", "방임"]) == {"a2": ["신체학대", "방임"], "a3": ["신체학대", "방임"]}
    assert kr.chunk_wide_pick(CHUNKS[0], []) == {}


def test_merge_picks_keeps_order_without_duplicates():
    target = {"s1": ["신체학대"]}
    kr.merge_picks(target, {"s1": ["신체학대", "방임"], "s2": ["정서학대"]})
    assert target == {"s1": ["신체학대", "방임"], "s2": ["정서학대"]}


def test_detected_labels_reads_dicts_and_lists():
    assert kr.detected_labels(_p(신체학대=0.9, 방임=0.1)) == ["신체학대"]
    assert kr.detected_labels(["방임", 3]) == ["방임"]
    assert kr.detected_labels(None) == []


# ---------------------------------------------------------------------------
# 설정
# ---------------------------------------------------------------------------


def test_scan_config_defaults_when_environment_is_empty():
    config = kr.scan_config({})

    assert config == kr.ScanConfig(line_threshold=None, chunk_fallback="top1", fallback_min_probability=0.2, max_line_predictions=400)


def test_scan_config_reads_environment():
    config = kr.scan_config(
        {
            "KEY_SCAN_LINE_THRESHOLD": "0.75",
            "KEY_SCAN_CHUNK_FALLBACK": "None",
            "KEY_SCAN_FALLBACK_MIN_PROBABILITY": "0.3",
            "KEY_SCAN_MAX_LINE_PREDICTIONS": "120",
        }
    )

    assert config == kr.ScanConfig(line_threshold=0.75, chunk_fallback="none", fallback_min_probability=0.3, max_line_predictions=120)


def test_scan_config_falls_back_to_defaults_on_bad_values_instead_of_failing_the_scan():
    config = kr.scan_config(
        {
            "KEY_SCAN_LINE_THRESHOLD": "high",
            "KEY_SCAN_CHUNK_FALLBACK": "maybe",
            "KEY_SCAN_FALLBACK_MIN_PROBABILITY": "1.5",
            "KEY_SCAN_MAX_LINE_PREDICTIONS": " ",
        }
    )

    assert config == kr.ScanConfig()


def test_scan_config_rejects_unknown_fallback_when_built_directly():
    with pytest.raises(ValueError):
        kr.ScanConfig(chunk_fallback="maybe")
