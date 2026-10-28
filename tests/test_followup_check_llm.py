# 다음 상담에서 확인할 것(ai/modeling/abuse/followup_check_llm.py)의
# segment_id 검증 로직을 테스트한다.
#
# 2026-10-26 민규(Backend) 리뷰(PR #82)에서 지적된 지점: 이 카드의 각
# 항목이 어느 발화에서 나온 건지 화면에서 보여주려면(증거 위치 표시)
# segment_ids가 있어야 하는데, 지금까지는 contract_adapter.py가 무조건
# 빈 배열을 채워 넣고 있었다. protective_factor_llm.py의 _clean_points와
# 같은 패턴(LLM이 주장한 segment_id를 실제 segment 목록과 대조해 검증,
# 근거 없는 항목은 제외)을 그대로 가져왔다 — 이 테스트가 그 검증 로직을
# 고정한다.

from ai.modeling.abuse.followup_check_llm import _clean_points


def test_clean_points_keeps_items_with_valid_segment_ids():
    valid_segment_ids = {"seg_001", "seg_002"}
    raw_points = [
        {"text": "등 통증 이후 치료 여부 확인 필요", "segment_ids": ["seg_001"]},
    ]

    cleaned = _clean_points(raw_points, valid_segment_ids)

    assert cleaned == [
        {"text": "등 통증 이후 치료 여부 확인 필요", "segment_ids": ["seg_001"]}
    ]


def test_clean_points_drops_items_without_valid_segment_id():
    # LLM이 존재하지 않는 segment_id를 지어내 인용했거나, segment_ids를
    # 아예 안 준 경우 — "증거 위치 표시"를 보장할 수 없으니 엄격하게
    # 제외한다(protective_factor_llm._clean_points와 같은 정책).
    valid_segment_ids = {"seg_001"}
    raw_points = [
        {"text": "지어낸 근거", "segment_ids": ["seg_999"]},
        {"text": "근거 없음", "segment_ids": []},
        {"text": "segment_ids 필드 자체가 없음"},
    ]

    cleaned = _clean_points(raw_points, valid_segment_ids)

    assert cleaned == []


def test_clean_points_filters_invalid_ids_but_keeps_valid_ones_in_same_item():
    valid_segment_ids = {"seg_001", "seg_002"}
    raw_points = [
        {
            "text": "여러 줄에 걸친 근거",
            "segment_ids": ["seg_001", "seg_999", "seg_002"],
        },
    ]

    cleaned = _clean_points(raw_points, valid_segment_ids)

    assert cleaned == [
        {
            "text": "여러 줄에 걸친 근거",
            "segment_ids": ["seg_001", "seg_002"],
        }
    ]


def test_clean_points_handles_malformed_input():
    valid_segment_ids = {"seg_001"}

    assert _clean_points(None, valid_segment_ids) == []
    assert _clean_points("문자열", valid_segment_ids) == []
    assert _clean_points([{"segment_ids": ["seg_001"]}], valid_segment_ids) == []
    assert _clean_points([{"text": "   ", "segment_ids": ["seg_001"]}], valid_segment_ids) == []


def test_clean_points_drops_item_with_non_list_segment_ids_but_keeps_others():
    # 2026-10-27 민규 교차검증: segment_ids가 5나 true처럼 list가 아니면
    # `for sid in (... or [])`에서 TypeError가 나서 회차 분석 전체가
    # AI_FAILED로 끝났다. 그 항목만 버리고 나머지는 그대로 통과해야 한다.
    # {"seg_001": true} 같은 dict도 돌면 키만 나와서 list처럼 통과해
    # 버리면 안 된다.
    valid_segment_ids = {"seg_001", "seg_002"}
    raw_points = [
        {"text": "정상 항목", "segment_ids": ["seg_001"]},
        {"text": "숫자형 segment_ids", "segment_ids": 5},
        {"text": "불리언 segment_ids", "segment_ids": True},
        {"text": "dict형 segment_ids", "segment_ids": {"seg_002": True}},
    ]

    cleaned = _clean_points(raw_points, valid_segment_ids)

    assert cleaned == [{"text": "정상 항목", "segment_ids": ["seg_001"]}]


def test_clean_points_deduplicates_nothing_but_preserves_order():
    # 항목 자체의 중복 제거는 하지 않는다(LLM 출력 그대로 몇 개 왔는지
    # 보존) — law_qa_llm/legal_manual_qa_llm의 인용 중복 제거와는 다른
    # 성격의 필드라서 의도적으로 안 건드린다.
    valid_segment_ids = {"seg_001"}
    raw_points = [
        {"text": "첫 번째", "segment_ids": ["seg_001"]},
        {"text": "두 번째", "segment_ids": ["seg_001"]},
    ]

    cleaned = _clean_points(raw_points, valid_segment_ids)

    assert [item["text"] for item in cleaned] == ["첫 번째", "두 번째"]


# 2026-10-28: 사례 정보(case_context)를 세 번째 칸으로 넣는다.

from ai.modeling.abuse import followup_check_llm as followup_module
from ai.modeling.abuse.followup_check_llm import SPLIT_MARKER, format_inputs_for_masking


def test_case_context_goes_into_third_part_and_prompt(monkeypatch):
    segments = [{"segment_id": "seg_001", "speaker": "CHILD", "text": "아빠가 술 마시고 와서 때려요.", "start_ms": 0}]
    points = [{"text": "아빠가 술 마시고 와서 때린다고 말함.", "segment_ids": ["seg_001"]}]
    combined = format_inputs_for_masking(
        segments, points, [], case_context={"intake_family_situations": ["알콜남용"]}
    )

    parts = combined.split(SPLIT_MARKER)
    assert len(parts) == 3
    assert "초기면접 가정상황: 알콜남용" in parts[2]

    seen = {}

    def fake_llm(**kwargs):
        seen["prompt"] = kwargs["system_prompt"]
        return {"check_points": [{"text": "보호자 음주 빈도 확인 필요", "segment_ids": ["seg_001"]}]}

    monkeypatch.setattr(followup_module, "_call_llm_with_retry", fake_llm)

    result = followup_module.generate_followup_check_points_from_masked_text(
        client=None, model="test", masked_combined_text=combined, segments=segments
    )

    assert "초기면접 가정상황: 알콜남용" in seen["prompt"]
    assert result == [{"text": "보호자 음주 빈도 확인 필요", "segment_ids": ["seg_001"]}]


def test_old_two_part_text_still_works(monkeypatch):
    segments = [{"segment_id": "seg_001", "speaker": "CHILD", "text": "무서웠어요.", "start_ms": 0}]
    old = "- [seg_001] (아동 진술) 무서웠다고 말함." + SPLIT_MARKER + "없음"
    seen = {}

    def fake_llm(**kwargs):
        seen["prompt"] = kwargs["system_prompt"]
        return {"check_points": []}

    monkeypatch.setattr(followup_module, "_call_llm_with_retry", fake_llm)
    followup_module.generate_followup_check_points_from_masked_text(
        client=None, model="test", masked_combined_text=old, segments=segments
    )

    assert '사례 정보(초기면접 · 지난 회차 확정 요약), 없으면 "없음"]\n없음' in seen["prompt"]


# 2026-10-28 민규 리뷰(#100 §7 답 3): 근거가 지난 회차 확정 요약뿐인 메모는 previous_session_label 로 남긴다.

def test_previous_session_only_point_kept_with_label_from_case_context():
    raw = [
        {"text": "안전 계획 유지 여부 확인 필요", "segment_ids": [], "from_previous_session": True},
        {"text": "근거 없는 메모", "segment_ids": []},
        {"text": "지어낸 회차를 붙인 메모", "segment_ids": [], "from_previous_session": True, "previous_session_label": "99회차"},
    ]

    cleaned = _clean_points(raw, {"seg_001"}, previous_session_label="7회차")

    assert cleaned == [
        {"text": "안전 계획 유지 여부 확인 필요", "segment_ids": [], "previous_session_label": "7회차"},
        {"text": "지어낸 회차를 붙인 메모", "segment_ids": [], "previous_session_label": "7회차"},
    ]


def test_previous_session_only_point_dropped_without_previous_session():
    raw = [{"text": "안전 계획 유지 여부 확인 필요", "segment_ids": [], "from_previous_session": True}]

    assert _clean_points(raw, {"seg_001"}) == []
