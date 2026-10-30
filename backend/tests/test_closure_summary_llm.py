# ai/modeling/abuse/closure_summary_llm.py — 종결 검토 요약(2026-10-30). 입력 글 · 코드 검사 · LLM 없는 묶기만 본다.

import pytest

from app.adapters.module_loader import ensure_repo_root_on_path

ensure_repo_root_on_path()

from ai.modeling.abuse import closure_summary_llm as cs  # noqa: E402

SESSIONS = [
    {"number": 1, "date": "2026-04-10", "assessment": {"safety_risks": "보호자 고성 · 위협", "strengths_resources": ""}, "signals": ["정서"]},
    {"number": 3, "date": "", "assessment": {"safety_changes": "새 학대 진술 없음", "desired_changes": "학교 적응"}, "signals": []},
]


def test_case_input_lists_fields_and_signals():
    text = cs.format_case_input(SESSIONS)

    assert "## 1회차 (2026-04-10)" in text and "- 위험요인: 보호자 고성 · 위협" in text and "- AI 관련 신호: 정서" in text
    assert "## 3회차\n" in text and "- AI 관련 신호: 없음" in text
    assert "강점과 자원" not in text  # 빈 칸은 넣지 않는다


def test_case_input_drops_oldest_sessions_over_limit(monkeypatch):
    monkeypatch.setattr(cs, "MAX_INPUT_CHARS", 60)

    text = cs.format_case_input(SESSIONS)

    assert "## 1회차" not in text and "## 3회차" in text


def test_clean_output_keeps_known_groups_and_real_sessions():
    cleaned = cs.clean_output(
        {
            "groups": [
                {"title": "학대 관련 진술", "items": [{"text": " 3회차 이후 새 진술 없음 ", "sessions": [3, 9, True, "1"]}]},
                {"title": "모르는 묶음", "items": [{"text": "x", "sessions": [1]}]},
                {"title": "안전 자원 · 강점", "items": [{"text": "근거 없음", "sessions": [7]}, {"text": "", "sessions": [1]}]},
            ],
            "report": {
                "initial_situation": {"text": "처음엔 위축", "sessions": [1]},
                "closing_situation": {"text": "근거 없는 종결", "sessions": []},
            },
        },
        [1, 3],
    )

    assert cleaned["groups"][0] == {"title": "학대 관련 진술", "items": [{"text": "3회차 이후 새 진술 없음", "sessions": [3]}]}
    assert [group["title"] for group in cleaned["groups"]] == list(cs.GROUP_TITLES)
    assert cleaned["groups"][3]["items"] == []
    assert cleaned["report"] == {"initial_situation": {"text": "처음엔 위축", "sessions": [1]}, "closing_situation": None}


def test_clean_output_limits_items_and_length():
    items = [{"text": f"문장 {n}", "sessions": [1]} for n in range(5)] + [{"text": "가" * 201, "sessions": [1]}]

    cleaned = cs.clean_output({"groups": [{"title": "아동 정서 · 행동", "items": items}]}, [1])

    assert [item["text"] for item in cleaned["groups"][1]["items"]] == ["문장 0", "문장 1", "문장 2"]


@pytest.mark.parametrize("raw", [None, "text", {}, {"groups": [{"title": "학대 관련 진술", "items": [{"text": "x", "sessions": [99]}]}]}])
def test_clean_output_without_any_sentence_raises(raw):
    with pytest.raises(cs.ClosureSummaryOutputError):
        cs.clean_output(raw, [1, 3])


def test_rule_based_summary_groups_approved_fields():
    summary = cs.rule_based_summary(SESSIONS)

    assert [group["title"] for group in summary["groups"]] == ["위험요인", "강점과 자원", "조사 후 변화", "원하는 변화"]
    assert summary["groups"][0]["items"] == [{"text": "보호자 고성 · 위협", "sessions": [1]}]
    assert summary["groups"][1]["items"] == []
    assert summary["report"] == {
        "initial_situation": {"text": "보호자 고성 · 위협", "sessions": [1]},
        "closing_situation": {"text": "새 학대 진술 없음", "sessions": [3]},
    }
