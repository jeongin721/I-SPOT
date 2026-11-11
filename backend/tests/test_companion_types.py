# ai/modeling/abuse/companion_types.py — 1차가 신체학대를 잡으면 정서학대도 2차에 묻기(2026-11-11, 김수아 5회차).
from app.adapters.module_loader import ensure_repo_root_on_path

ensure_repo_root_on_path()

from ai.modeling.abuse.companion_types import CONFIRMED_BY, confirm_companions, second_stage_types  # noqa: E402

ORDER = ["신체학대", "정서학대", "성학대", "방임"]


def _result(label, segment_ids):
    evidence = {"evidence": "컵을 던졌어요", "timestamps": {"segment_ids": segment_ids} if segment_ids else None}
    return {"major_type": label, "subtypes": [{"type": "x", "evidences": [evidence]}]}


def test_physical_adds_emotional_in_label_order():
    assert second_stage_types(["신체학대"], ORDER) == ["신체학대", "정서학대"]
    assert second_stage_types(["방임", "신체학대"], ORDER) == ["신체학대", "정서학대", "방임"]
    assert second_stage_types(["정서학대"], ORDER) == ["정서학대"]
    assert second_stage_types([], ORDER) == []


def test_added_type_counts_only_with_linked_evidence():
    """더해 물은 정서학대는 근거가 줄에 이어질 때만 올리고, 아니면 그 결과를 버린다. 1차 탐지 유형은 그대로 둔다."""

    linked = {"results": [_result("신체학대", []), _result("정서학대", ["seg_004"])]}  # 김수아 5회차 모양
    result, confirmed = confirm_companions(linked, ["신체학대"], ["신체학대", "정서학대"])
    assert confirmed == ["정서학대"]
    assert [r["major_type"] for r in result["results"]] == ["신체학대", "정서학대"]

    unlinked = {"results": [_result("신체학대", ["seg_004"]), _result("정서학대", [])]}
    result, confirmed = confirm_companions(unlinked, ["신체학대"], ["신체학대", "정서학대"])
    assert confirmed == []
    assert [r["major_type"] for r in result["results"]] == ["신체학대"]


def test_nothing_added_leaves_result_alone():
    original = {"results": [_result("정서학대", [])], "note": "그대로"}
    assert confirm_companions(original, ["정서학대"], ["정서학대"]) == (original, [])
    assert CONFIRMED_BY


def test_added_type_is_dropped_when_physical_evidence_was_found():
    """신체학대 근거를 2차가 이미 찾았으면 더해 물은 정서학대는 근거가 있어도 올리지 않는다(11/11 실측: 360회차 중 5회차 추가 · 정답 1)."""

    both = {"results": [_result("신체학대", ["seg_002"]), _result("정서학대", ["seg_004"])]}
    result, confirmed = confirm_companions(both, ["신체학대"], ["신체학대", "정서학대"])

    assert confirmed == []
    assert [r["major_type"] for r in result["results"]] == ["신체학대"]

