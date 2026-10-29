# ai/modeling/abuse/topic_tag_llm.py — 아동 발화 대화 주제 분류(2026-10-29, 주제 비중 · 처음 나온 이야기).
# openai 가 CI 에 없어 LLM 은 가짜 _call_llm_with_retry 로 바꾸고, 입력 글 · 코드 검사만 본다.
import sys
import time
import types
from concurrent.futures import ThreadPoolExecutor

import pytest

from app.adapters.module_loader import ensure_repo_root_on_path

ensure_repo_root_on_path()

from ai.modeling.abuse import topic_tag_llm as tt  # noqa: E402

SEGMENTS = [
    {"segment_id": "seg_001", "speaker": "COUNSELOR", "text": "요즘 어떻게 지냈어?", "start_ms": 0},
    {"segment_id": "seg_002", "speaker": "CHILD", "text": "아빠가 또 화났어요. 많이 때렸어요.", "start_ms": 41000},
    {"segment_id": "seg_003", "speaker": "CHILD", "text": "무서웠어요.", "start_ms": 96000},
    {"segment_id": "seg_004", "speaker": "CHILD", "text": "밥도 안 줄 때가 있어요.", "start_ms": 135000},
    {"segment_id": "seg_005", "speaker": "UNKNOWN", "text": "누구 말인지 모름", "start_ms": 140000},
    {"segment_id": "seg_006", "speaker": "CHILD", "text": "   ", "start_ms": 150000},
]


# ------------------------------------------------------------
# 입력 글
# ------------------------------------------------------------


def test_format_child_lines_keeps_only_child_utterances():
    text = tt.format_child_lines(SEGMENTS)

    assert text.splitlines() == [
        "[seg_002] 아빠가 또 화났어요. 많이 때렸어요.",
        "[seg_003] 무서웠어요.",
        "[seg_004] 밥도 안 줄 때가 있어요.",
    ]


def test_format_child_lines_stops_before_limit(monkeypatch):
    monkeypatch.setattr(tt, "MAX_INPUT_CHARS", 40)

    assert tt.format_child_lines(SEGMENTS).splitlines() == ["[seg_002] 아빠가 또 화났어요. 많이 때렸어요."]


@pytest.mark.parametrize("value", [None, "seg", {"a": 1}, [None, 3]])
def test_format_child_lines_tolerates_bad_input(value):
    assert tt.format_child_lines(value) == ""


# ------------------------------------------------------------
# 코드 검사
# ------------------------------------------------------------


def test_clean_tags_keeps_known_topics_in_topic_order_with_quote():
    tags = tt._clean_tags(
        [
            {"topic": "식사 · 돌봄", "segment_ids": ["seg_004"]},
            {"topic": "신체 체벌 경험", "segment_ids": ["seg_002"]},
            {"topic": "두려움 · 정서", "segment_ids": ["seg_003"]},
        ],
        SEGMENTS,
    )

    assert [tag["topic"] for tag in tags] == ["신체 체벌 경험", "두려움 · 정서", "식사 · 돌봄"]
    assert tags[2] == {
        "topic": "식사 · 돌봄",
        "segment_ids": ["seg_004"],
        "quote": "밥도 안 줄 때가 있어요.",
        "start_ms": 135000,
    }


def test_clean_tags_drops_unknown_topic_names():
    tags = tt._clean_tags(
        [{"topic": "가정 내 체벌", "segment_ids": ["seg_002"]}, {"topic": " 학교생활 ", "segment_ids": ["seg_003"]}],
        SEGMENTS,
    )

    assert [tag["topic"] for tag in tags] == ["학교생활"]


def test_clean_tags_keeps_only_child_segment_ids():
    tags = tt._clean_tags(
        [
            {"topic": "보호자 관계", "segment_ids": ["seg_001", "seg_999", "seg_005", 3, "seg_002"]},
            {"topic": "학교생활", "segment_ids": ["seg_001"]},  # 상담사 발화뿐 → 주제째 빠짐
        ],
        SEGMENTS,
    )

    assert tags == [
        {"topic": "보호자 관계", "segment_ids": ["seg_002"], "quote": "아빠가 또 화났어요. 많이 때렸어요.", "start_ms": 41000}
    ]


def test_clean_tags_merges_repeated_topic_in_utterance_order():
    tags = tt._clean_tags(
        [
            {"topic": "두려움 · 정서", "segment_ids": ["seg_004"]},
            {"topic": "두려움 · 정서", "segment_ids": ["seg_003", "seg_004"]},
        ],
        SEGMENTS,
    )

    assert tags[0]["segment_ids"] == ["seg_003", "seg_004"]
    assert tags[0]["quote"] == "무서웠어요."


def test_clean_tags_shortens_long_quote_and_ignores_bad_start():
    segments = [{"segment_id": "s1", "speaker": "CHILD", "text": "가" * 100, "start_ms": True}]

    tag = tt._clean_tags([{"topic": "놀이 · 일상", "segment_ids": ["s1"]}], segments)[0]

    assert tag["quote"] == "가" * tt.QUOTE_CHARS + "…"
    assert tag["start_ms"] is None


@pytest.mark.parametrize("raw", [None, "tags", [None, "x", {"topic": 3}, {"topic": "학교생활", "segment_ids": "seg_002"}]])
def test_clean_tags_tolerates_malformed_items(raw):
    assert tt._clean_tags(raw, SEGMENTS) == []


# ------------------------------------------------------------
# LLM 호출 — 가짜 _call_llm_with_retry
# ------------------------------------------------------------


@pytest.fixture
def fake_llm(monkeypatch):
    calls = []
    response = {"value": {}}

    def fake_call(**kwargs):
        calls.append(kwargs)
        if isinstance(response["value"], Exception):
            raise response["value"]
        return response["value"]

    module = types.ModuleType("ai.modeling.abuse.second_stage_llm")
    module._call_llm_with_retry = fake_call
    monkeypatch.setitem(sys.modules, "ai.modeling.abuse.second_stage_llm", module)

    return calls, response


def test_generate_sends_masked_lines_and_topic_list(fake_llm):
    calls, response = fake_llm
    response["value"] = {"tags": [{"topic": "식사 · 돌봄", "segment_ids": ["seg_004"]}]}

    tags = tt.generate_topic_tags_from_masked_text(
        client=None, model="m", masked_child_lines="[seg_004] [이름1] 밥도 안 줘요", segments=SEGMENTS
    )

    assert [tag["topic"] for tag in tags] == ["식사 · 돌봄"]
    prompt = calls[0]["system_prompt"]
    assert "[seg_004] [이름1] 밥도 안 줘요" in prompt
    assert all(f"- {topic}" in prompt for topic in tt.TOPICS)
    # 원본 발화(마스킹 전)는 보내지 않는다.
    assert "[seg_004] 밥도 안 줄 때가 있어요" not in prompt


def test_generate_skips_llm_without_child_lines(fake_llm):
    calls, _ = fake_llm

    assert tt.generate_topic_tags_from_masked_text(None, "m", "  ", SEGMENTS) == []
    assert calls == []


@pytest.mark.parametrize("value", [RuntimeError("boom"), None, "text", {"tags": "x"}, {}])
def test_generate_returns_none_on_failure(fake_llm, value):
    _, response = fake_llm
    response["value"] = value

    assert tt.generate_topic_tags_from_masked_text(None, "m", "[seg_002] 글", SEGMENTS) is None


def test_generate_returns_none_when_llm_module_import_fails(monkeypatch):
    monkeypatch.setitem(sys.modules, "ai.modeling.abuse.second_stage_llm", None)

    assert tt.generate_topic_tags_from_masked_text(None, "m", "[seg_002] 글", SEGMENTS) is None


def test_generate_returns_empty_list_when_nothing_matches(fake_llm):
    _, response = fake_llm
    response["value"] = {"tags": []}

    assert tt.generate_topic_tags_from_masked_text(None, "m", "[seg_002] 글", SEGMENTS) == []


# ------------------------------------------------------------
# 마감 기다리기
# ------------------------------------------------------------


def test_wait_returns_result_in_time():
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(lambda: [{"topic": "학교생활"}])
        assert tt.wait_for_topic_tags(future, time.monotonic() + 10) == [{"topic": "학교생활"}]


def test_wait_gives_none_after_deadline():
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(time.sleep, 0.5)
        assert tt.wait_for_topic_tags(future, time.monotonic() + 0.1) is None


def test_wait_gives_none_on_error_or_non_list():
    with ThreadPoolExecutor(max_workers=1) as pool:
        assert tt.wait_for_topic_tags(pool.submit(lambda: 1 / 0), None) is None
        assert tt.wait_for_topic_tags(pool.submit(lambda: None), None) is None
