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
