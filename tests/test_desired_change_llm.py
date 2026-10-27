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
