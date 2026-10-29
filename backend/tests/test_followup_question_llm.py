# '추가 질문' AI 초안 모듈(ai/modeling/abuse/followup_question_llm.py, 2026-10-29 C-1)의 코드 검사를 고정한다.
#
# 아동 면담에서 유도 질문은 가장 큰 위험이라 프롬프트 금지 위에 코드로 한 번 더 거른다(모듈 docstring).
# 걸리면 그 질문만 빠지고 나머지는 남아야 한다. LLM 호출은 가짜 함수로 바꿔 시험한다(CI 에 openai 가 없다).

import sys
import threading
import time
import types
from concurrent.futures import ThreadPoolExecutor

import pytest

from app.adapters.module_loader import ensure_repo_root_on_path

ensure_repo_root_on_path()

from ai.modeling.abuse import followup_question_llm as fq  # noqa: E402

SEGMENTS = [
    {"segment_id": "seg_010", "speaker": "CHILD", "text": "아빠가 술 마시고 오면 때려요."},
    {"segment_id": "seg_012", "speaker": "CHILD", "text": "등이랑 팔이요."},
    {"segment_id": "seg_020", "speaker": "CHILD", "text": "할머니 집에 가고 싶어요."},
]


def _q(text, segment_ids=("seg_012",), reason="통증 이후 치료 여부가 안 나옴"):
    return {"text": text, "segment_ids": list(segment_ids), "reason": reason}


def test_keeps_open_question_grounded_in_child_words():
    cleaned = fq._clean_questions([_q("등이랑 팔이 아팠던 건 지금은 어때?")], SEGMENTS)

    assert cleaned == [
        {
            "text": "등이랑 팔이 아팠던 건 지금은 어때?",
            "kind": "OPEN",
            "segment_ids": ["seg_012"],
            "reason": "통증 이후 치료 여부가 안 나옴",
        }
    ]


@pytest.mark.parametrize(
    "text",
    [
        "등이랑 팔 아팠어?",  # 예/아니오
        "병원에 갔니?",
        "많이 아팠지?",
        "왜 아팠어?",  # '왜' 는 열린 질문 표지로 치지 않는다
        "선생님한테 이야기했어?",  # 이야기를 청하는 꼴이 아니다
    ],
)
def test_drops_closed_questions(text):
    assert fq._clean_questions([_q(text)], SEGMENTS) == []


def test_drops_multiple_questions_in_one():
    assert fq._clean_questions([_q("어디가 아팠어? 누가 봐 줬어?")], SEGMENTS) == []


@pytest.mark.parametrize(
    "text, segment_ids",
    [
        ("아빠가 등을 어떻게 했는지 이야기해 줄래?", ["seg_012"]),  # 근거 발화에 '아빠' 없음
        ("등이랑 팔은 누가 때렸는지 이야기해 줄래?", ["seg_012"]),  # 근거 발화에 '때리' 없음
        ("할머니가 뭐라고 했어?", ["seg_012"]),
        ("형이랑은 어떻게 지내?", ["seg_020"]),
    ],
)
def test_drops_questions_that_introduce_person_or_act(text, segment_ids):
    assert fq._clean_questions([_q(text, segment_ids)], SEGMENTS) == []


def test_keeps_person_and_act_words_the_child_said():
    text = "아빠가 술 마시고 오면 어떻게 되는지 더 이야기해 줄래?"
    cleaned = fq._clean_questions([_q(text, ["seg_010"])], SEGMENTS)

    assert [item["text"] for item in cleaned] == [text]


def test_act_word_in_another_form_counts_as_said():
    # 아이는 "때려요", 질문은 "때린다고" — 같은 행위다(실제 LLM 초안에서 나온 꼴).
    text = "아빠가 술 마시고 오면 때린다고 했는데, 그때 어떻게 됐는지 이야기해 줄래?"
    cleaned = fq._clean_questions([_q(text, ["seg_010", "seg_012"])], SEGMENTS)

    assert [item["text"] for item in cleaned] == [text]


def test_request_to_tell_with_object_particle_is_open():
    text = "등이랑 팔에 있었던 일 뒤에 병원이나 약 같은 도움을 받은 이야기를 해 줄래?"

    assert len(fq._clean_questions([_q(text)], SEGMENTS)) == 1


def test_short_person_word_inside_other_word_is_not_a_person():
    # '형편' 의 '형' 은 사람이 아니다.
    segments = [{"segment_id": "seg_001", "text": "집 형편이 어려워요."}]
    cleaned = fq._clean_questions([_q("집 형편이 어려운 건 어떤 때 느껴?", ["seg_001"])], segments)

    assert len(cleaned) == 1


@pytest.mark.parametrize(
    "item",
    [
        {"text": "지금은 어때?", "segment_ids": []},
        {"text": "지금은 어때?", "segment_ids": ["seg_999"]},
        {"text": "지금은 어때?"},
        {"text": "지금은 어때?", "segment_ids": "seg_012"},
        {"text": "지금은 어때?", "segment_ids": [["seg_012"]]},
        {"text": "", "segment_ids": ["seg_012"]},
        {"text": 3, "segment_ids": ["seg_012"]},
        {"text": "어때?" + "가" * 300, "segment_ids": ["seg_012"]},
        "지금은 어때?",
        None,
    ],
)
def test_drops_malformed_or_ungrounded_items(item):
    assert fq._clean_questions([item], SEGMENTS) == []


def test_non_list_input_is_empty():
    assert fq._clean_questions({"text": "지금은 어때?"}, SEGMENTS) == []
    assert fq._clean_questions(None, SEGMENTS) == []


def test_keeps_valid_ids_dedupes_and_caps_at_five():
    raw = [_q("등이랑 팔이 아팠던 건 지금은 어때?", ["seg_012", "seg_999", "seg_012"])]
    raw += [_q(f"{n}번째로 궁금한 건 어때?") for n in range(1, 8)]
    raw.insert(1, _q("등이랑 팔이 아팠던 건 지금은 어때?"))  # 같은 문장은 한 번만

    cleaned = fq._clean_questions(raw, SEGMENTS)

    assert len(cleaned) == fq.MAX_QUESTIONS
    assert cleaned[0]["segment_ids"] == ["seg_012"]
    assert len({item["text"] for item in cleaned}) == fq.MAX_QUESTIONS


def test_bad_items_do_not_drop_good_ones():
    raw = [_q("병원에 갔니?"), _q("등이랑 팔이 아팠던 건 지금은 어때?"), 7]

    assert [item["text"] for item in fq._clean_questions(raw, SEGMENTS)] == [
        "등이랑 팔이 아팠던 건 지금은 어때?"
    ]


def test_reason_is_optional_and_trimmed():
    cleaned = fq._clean_questions(
        [{"text": "지금은  어때?", "segment_ids": ["seg_012"], "reason": 5}], SEGMENTS
    )

    assert cleaned == [{"text": "지금은 어때?", "kind": "OPEN", "segment_ids": ["seg_012"], "reason": ""}]


@pytest.mark.parametrize(
    "case_context, expected",
    [
        ({"child_age_band": "만 6~9세"}, "만 6~9세"),
        ({"child_age_band": "9살"}, "알 수 없음"),
        ({"child_age_band": ["만 6~9세"]}, "알 수 없음"),
        (None, "알 수 없음"),
    ],
)
def test_child_age_band_uses_allowlist(case_context, expected):
    assert fq.child_age_band(case_context) == expected


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


def _masked(session_content, case_context="- 아동: 만 10~13세"):
    return session_content + fq.SPLIT_MARKER + "없음" + fq.SPLIT_MARKER + case_context


def test_generate_sends_only_session_content_and_age_band(fake_llm):
    calls, response = fake_llm
    response["value"] = {"questions": [_q("등이랑 팔이 아팠던 건 지금은 어때?"), _q("병원에 갔니?")]}

    result = fq.generate_followup_questions_from_masked_text(
        client=None,
        model="m",
        masked_combined_text=_masked("- [seg_012] (아동 진술) 등과 팔이 아프다고 했다", "- 초기면접 가정상황: 알콜남용"),
        segments=SEGMENTS,
        age_band="만 10~13세",
    )

    assert [item["text"] for item in result] == ["등이랑 팔이 아팠던 건 지금은 어때?"]
    prompt = calls[0]["system_prompt"]
    assert "등과 팔이 아프다고 했다" in prompt
    assert "만 10~13세" in prompt
    # 초기면접 · 지난 회차 요약은 질문 재료로 보내지 않는다.
    assert "알콜남용" not in prompt


def test_generate_skips_llm_without_session_content(fake_llm):
    calls, _ = fake_llm

    assert fq.generate_followup_questions_from_masked_text(None, "m", _masked("없음"), SEGMENTS) == []
    assert calls == []


@pytest.mark.parametrize("value", [RuntimeError("boom"), ["not", "dict"], {"questions": "x"}])
def test_generate_returns_empty_on_failure(fake_llm, value):
    _, response = fake_llm
    response["value"] = value

    assert fq.generate_followup_questions_from_masked_text(None, "m", _masked("- [seg_012] 등"), SEGMENTS) == []


def test_unknown_age_band_is_not_sent(fake_llm):
    calls, response = fake_llm
    response["value"] = {"questions": []}

    fq.generate_followup_questions_from_masked_text(
        None, "m", _masked("- [seg_012] 등"), SEGMENTS, age_band="2015-03-01"
    )

    assert "2015-03-01" not in calls[0]["system_prompt"]


def test_generate_returns_empty_when_llm_module_import_fails(monkeypatch):
    # import 도 try 안이다 — 불러오기가 실패해도 분석 thread 에 예외가 올라가지 않는다(민규 #118).
    monkeypatch.setitem(sys.modules, "ai.modeling.abuse.second_stage_llm", None)

    assert fq.generate_followup_questions_from_masked_text(None, "m", _masked("- [seg_012] 등"), SEGMENTS) == []


# ------------------------------------------------------------
# 확인 메모와 동시 호출 — 마감 전까지만 기다림
# ------------------------------------------------------------


def test_wait_for_questions_gives_up_at_deadline():
    # 질문 LLM 이 늦어도 마감까지만 기다리고 [] — 선택 필드 때문에 분석 전체가 AI_TIMEOUT 이 되지 않게(민규 #118).
    release = threading.Event()
    executor = ThreadPoolExecutor(max_workers=1)

    try:
        future = executor.submit(lambda: release.wait(5) and [_q("지금은 어때?")])
        deadline = time.monotonic() + fq.DEADLINE_MARGIN_SECONDS + 0.2
        started = time.monotonic()

        assert fq.wait_for_questions(future, deadline) == []
        assert time.monotonic() - started < 1.0
    finally:
        release.set()
        executor.shutdown(wait=True)


def test_wait_for_questions_returns_result_in_time():
    executor = ThreadPoolExecutor(max_workers=1)

    try:
        future = executor.submit(lambda: [{"text": "지금은 어때?"}])

        assert fq.wait_for_questions(future, time.monotonic() + 10) == [{"text": "지금은 어때?"}]
        assert fq.wait_for_questions(future, None) == [{"text": "지금은 어때?"}]
    finally:
        executor.shutdown(wait=True)


@pytest.mark.parametrize("outcome", [RuntimeError("boom"), {"not": "list"}])
def test_wait_for_questions_returns_empty_on_error_or_bad_value(outcome):
    def work():
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    executor = ThreadPoolExecutor(max_workers=1)

    try:
        assert fq.wait_for_questions(executor.submit(work), None) == []
    finally:
        executor.shutdown(wait=True)


def test_wait_for_questions_past_deadline_does_not_block():
    release = threading.Event()
    executor = ThreadPoolExecutor(max_workers=1)

    try:
        future = executor.submit(release.wait, 5)
        started = time.monotonic()

        assert fq.wait_for_questions(future, time.monotonic() - 1) == []
        assert time.monotonic() - started < 0.5
    finally:
        release.set()
        executor.shutdown(wait=True)
