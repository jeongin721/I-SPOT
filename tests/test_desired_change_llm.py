# 상담 요약 '앞으로 원하는 변화 · 원하는 서비스/지원' 칸
# (ai/modeling/abuse/desired_change_llm.py)의 근거 검증과 한 칸으로 잇기를 고정한다.

from ai.modeling.abuse.desired_change_llm import EMPTY_TEXT, _clean_points, join_points


def test_clean_points_keeps_only_valid_segment_ids():
    cleaned = _clean_points(
        [
            {"text": "할머니 집에 가고 싶다고 말함.", "segment_ids": ["seg_015", "seg_999"]},
            {"text": "지어낸 근거", "segment_ids": ["seg_999"]},
            {"text": "근거 없음", "segment_ids": []},
            "문자열 항목",
        ],
        {"seg_015"},
    )

    assert cleaned == [{"text": "할머니 집에 가고 싶다고 말함.", "segment_ids": ["seg_015"]}]


def test_clean_points_drops_item_with_non_list_segment_ids_but_keeps_others():
    # 2026-10-27 민규 교차검증: segment_ids 가 목록이 아니면 TypeError 로 회차 분석 전체가 실패했다
    # (followup_check_llm 915b4e6 과 같은 버그). 그 항목만 버리고 나머지는 남아야 한다.
    # dict 는 돌면 키만 나와 목록처럼 통과하면 안 되고, true 는 int 의 하위형이라 번호로 쓰면 안 된다.
    cleaned = _clean_points(
        [
            {"text": "정상 항목", "segment_ids": ["seg_001"]},
            {"text": "숫자형", "segment_ids": 5},
            {"text": "불리언", "segment_ids": True},
            {"text": "dict형", "segment_ids": {"seg_002": True}},
            {"text": "목록 안 불리언", "segment_ids": [True, "seg_002"]},
        ],
        {"seg_001", "seg_002", "True"},
    )

    assert cleaned == [
        {"text": "정상 항목", "segment_ids": ["seg_001"]},
        {"text": "목록 안 불리언", "segment_ids": ["seg_002"]},
    ]


def test_join_points_merges_text_and_unique_ids_in_order():
    joined = join_points(
        [
            {"text": "할머니 집에 가고 싶다고 말함.", "segment_ids": ["seg_015"]},
            {"text": "팔 통증 의료 확인 필요.", "segment_ids": ["seg_004", "seg_015"]},
        ]
    )

    assert joined == {
        "text": "할머니 집에 가고 싶다고 말함. 팔 통증 의료 확인 필요.",
        "segment_ids": ["seg_015", "seg_004"],
    }


def test_join_points_without_items_is_empty_text():
    assert join_points([]) == {"text": EMPTY_TEXT, "segment_ids": []}
