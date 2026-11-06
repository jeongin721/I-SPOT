# ai/modeling/abuse/key_scan_refine.py — '1차 임시 핵심 발화' 줄 고르기(2026-10-30). 모델 없이 고르기 규칙만 본다.

from app.adapters.module_loader import ensure_repo_root_on_path

ensure_repo_root_on_path()

from ai.modeling.abuse import key_scan_refine as kr  # noqa: E402

CHUNK = [
    ("상담사", "요즘 집에서 어때?", {"segment_id": "seg_001"}),
    ("아동", "아빠가 또 화났어요.", {"segment_id": "seg_002"}),
    ("아동", "많이 때렸어요.", {"segment_id": "seg_003"}),
    ("상담사", "그때 기분은 어땠어?", {"segment_id": "seg_004"}),
    ("아동", "네.", {"segment_id": "seg_005"}),
    ("아동", "", {}),  # 번호 없음 → 뺌
]


def _p(**labels):
    return {label: {"detected": detected, "probability": prob} for label, (detected, prob) in labels.items()}


def test_child_lines_are_paired_with_previous_counselor_question():
    assert kr.child_line_inputs(CHUNK) == [
        ("seg_002", "상담사: 요즘 집에서 어때?\n아동: 아빠가 또 화났어요."),
        ("seg_003", "상담사: 요즘 집에서 어때?\n아동: 많이 때렸어요."),
        ("seg_005", "상담사: 그때 기분은 어땠어?\n아동: 네."),
    ]


def test_child_line_without_question_is_sent_alone():
    assert kr.child_line_inputs([("아동", "무서웠어요.", {"segment_id": "s1"})]) == [("s1", "아동: 무서웠어요.")]


def test_only_lines_that_detect_a_label_are_picked():
    picked = kr.pick_segments(
        ["방임"],
        [
            ("seg_002", _p(신체학대=(False, None), 방임=(False, None))),
            ("seg_008", _p(신체학대=(True, None), 방임=(False, None))),
            ("seg_014", _p(신체학대=(False, None), 방임=(True, None))),
        ],
    )

    # 덩어리 판정이 놓친 신체학대도 줄에서 걸리면 살린다(10/30 실제 모델 사례).
    assert picked == {"seg_008": ["신체학대"], "seg_014": ["방임"]}


def test_chunk_label_not_confirmed_by_any_line_marks_all_lines_like_before():
    picked = kr.pick_segments(
        ["정서학대"],
        [("seg_002", _p(정서학대=(False, None))), ("seg_003", _p(정서학대=(False, None)))],
    )

    assert picked == {"seg_002": ["정서학대"], "seg_003": ["정서학대"]}


def test_bad_predictions_are_ignored():
    assert kr.pick_segments([], [("seg_002", "bad"), ("seg_003", {"신체학대": "x"})]) == {}


def test_several_labels_merge_per_segment():
    picked = kr.pick_segments(
        ["신체학대"],
        [("seg_002", _p(신체학대=(True, None), 정서학대=(True, None))), ("seg_003", _p(신체학대=(True, None)))],
    )

    assert picked == {"seg_002": ["신체학대", "정서학대"], "seg_003": ["신체학대"]}
