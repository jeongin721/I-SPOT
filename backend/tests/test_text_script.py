# LLM 결과에 다른 나라 문자가 섞이면 버린다(ai/modeling/abuse/text_script.py, 2026-10-30).
#
# 데모 확인 메모에 "재발 방지 ব্যবস্থা의 진행 여부"(벵골어 '조치')가 나왔다. 확인 메모 · 추가 질문 초안 · 종결 요약에서
# 그런 문장만 빠지고 나머지는 남아야 한다.

import importlib
import sys
import types

import pytest

from app.adapters.module_loader import ensure_repo_root_on_path

ensure_repo_root_on_path()

from ai.modeling.abuse import closure_summary_llm as cs  # noqa: E402
from ai.modeling.abuse import followup_question_llm as fq  # noqa: E402
from ai.modeling.abuse.text_script import has_foreign_script  # noqa: E402

DEMO_TEXT = "성적·신체적 가해 이후 보호조치와 재발 방지 ব্যবস্থা의 진행 여부 확인 필요."


@pytest.mark.parametrize(
    "text",
    [DEMO_TEXT, "аня 진술 확인", "아버지 नमस्ते 확인", "보호자 ありがとう", "قال 아동"],
)
def test_foreign_letters_are_flagged(text):
    assert has_foreign_script(text)


@pytest.mark.parametrize(
    "text",
    ["어깨 통증 이후 치료 여부 확인 필요.", "seg_012 · 07:27 ADHD 약 복용", "兒童 보호(한자)", "ＡＢＣ 전각", "😀 ①②", ""],
)
def test_korean_latin_han_and_symbols_pass(text):
    assert not has_foreign_script(text)


def test_followup_check_points_drop_foreign_script_item(monkeypatch):
    """확인 메모 모듈은 openai · second_stage_llm 을 바로 import 한다. CI 에 없으니 가짜 모듈로 바꿔 불러온다."""

    monkeypatch.setitem(sys.modules, "openai", types.SimpleNamespace(OpenAI=object))
    monkeypatch.setitem(
        sys.modules,
        "ai.modeling.abuse.second_stage_llm",
        types.SimpleNamespace(_call_llm_with_retry=lambda **_: {}),
    )
    monkeypatch.delitem(sys.modules, "ai.modeling.abuse.followup_check_llm", raising=False)
    fc = importlib.import_module("ai.modeling.abuse.followup_check_llm")

    cleaned = fc._clean_points(
        [{"text": DEMO_TEXT, "segment_ids": ["seg_001"]}, {"text": "치료 여부 확인 필요.", "segment_ids": ["seg_001"]}],
        {"seg_001"},
    )

    assert [point["text"] for point in cleaned] == ["치료 여부 확인 필요."]
    monkeypatch.delitem(sys.modules, "ai.modeling.abuse.followup_check_llm", raising=False)


def test_followup_question_drops_foreign_script_question():
    segments = [{"segment_id": "seg_012", "speaker": "CHILD", "text": "등이랑 팔이요."}]
    raw = [
        {"text": "등이 아팠던 건 지금은 ব্যবস্থা 어때?", "segment_ids": ["seg_012"], "reason": "치료 여부"},
        {"text": "등이랑 팔이 아팠던 건 지금은 어때?", "segment_ids": ["seg_012"], "reason": "치료 여부"},
    ]

    assert [q["text"] for q in fq._clean_questions(raw, segments)] == ["등이랑 팔이 아팠던 건 지금은 어때?"]


def test_closure_summary_drops_foreign_script_sentence():
    raw = {
        "groups": [
            {
                "title": "학대 관련 진술",
                "items": [{"text": DEMO_TEXT, "sessions": [1]}, {"text": "새 학대 진술 없음", "sessions": [1]}],
            }
        ],
        "report": {"initial_situation": {"text": "재발 방지 ব্যবস্থা", "sessions": [1]}},
    }

    cleaned = cs.clean_output(raw, [1])

    assert cleaned["groups"][0]["items"] == [{"text": "새 학대 진술 없음", "sessions": [1]}]
    assert cleaned["report"]["initial_situation"] is None
