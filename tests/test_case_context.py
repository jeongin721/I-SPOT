# 분석 입력 case_context(사례 정보) → 프롬프트 글(ai/modeling/abuse/case_context.py)을 고정한다.
# 알려진 키만 읽고(이름 · 생년월일 · 메모 등은 버림), 모양이 틀리면 조용히 버리고, 없으면 "없음".

from ai.modeling.abuse.case_context import EMPTY, format_case_context, normalize_case_context

FULL = {
    "child_age_band": "만 10~13세",
    "child_gender": "F",
    "guardian_type": "FATHER",
    "intake_child_traits": ["불안", "불안", "낮은자존감"],
    "intake_family_situations": ["알콜남용"],
    "previous_session": {
        "session_label": "1회차",
        "consulted_on": "2026-10-20",
        "assessment": {"strengths_resources": "조모에게 연락하는 방법을 앎", "safety_risks": "", "unknown": "버림"},
    },
    "child_name": "김하늘",
    "notes": "메모",
}


def test_format_case_context_uses_known_keys_only():
    text = format_case_context(FULL)

    assert "만 10~13세 · 여" in text
    assert "보호자 유형: 부" in text
    assert "초기면접 아동 특성: 불안, 낮은자존감" in text
    assert "초기면접 가정상황: 알콜남용" in text
    assert "지난 회차 확정 요약(1회차 · 2026-10-20)" in text
    assert "강점과 자원: 조모에게 연락하는 방법을 앎" in text
    assert "김하늘" not in text and "메모" not in text and "버림" not in text
    assert "위험요인" not in text  # 빈 칸은 쓰지 않는다


def test_empty_or_malformed_case_context_is_none():
    assert format_case_context(None) == EMPTY
    assert format_case_context("문자열") == EMPTY
    assert format_case_context({"child_gender": "X", "intake_child_traits": "불안"}) == EMPTY
    assert normalize_case_context({"previous_session": {"assessment": ["목록"]}}) is None
