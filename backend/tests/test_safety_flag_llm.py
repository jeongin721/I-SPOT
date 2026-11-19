# ai/modeling/abuse/safety_flag_llm.py — 안전 플래그 · 재학대 요인 후보(2026-11-05, 팀 확인 기준안 S1~S10 · R1~R10).
# LLM 은 가짜 _call_llm 로 바꾸고, 코드 검사 · 실패 처리만 본다. 계약 변환 · 분석 흐름은 test_ai_known_identifiers.py.
import pytest

from app.adapters.module_loader import ensure_repo_root_on_path

ensure_repo_root_on_path()

from ai.modeling.abuse import safety_flag_llm as sf  # noqa: E402

SEGMENTS = [{"segment_id": "seg_001"}, {"segment_id": "seg_002"}, {"segment_id": "seg_003"}]
TEXT = "[seg_001] CHILD: 말하면 더 혼난대요.\n[seg_002] CHILD: 아빠가 술 마시면 때려요.\n[seg_003] CHILD: 집에 가기 싫어요."


def _fake_llm(monkeypatch, reply):
    calls = []

    def call(**kwargs):
        calls.append(kwargs)
        if isinstance(reply, Exception):
            raise reply
        return reply

    monkeypatch.setattr(sf, "_call_llm", call)
    return calls


def _run():
    return sf.generate_safety_flags(client=object(), model="fake", masked_transcript_text=TEXT, segments=SEGMENTS)


def test_keeps_only_known_codes_with_real_segments(monkeypatch):
    _fake_llm(
        monkeypatch,
        {
            "safety_flags": [
                {"code": "S2", "text": "말하면 더 혼난다고 함", "certainty": "CLEAR", "segment_ids": ["seg_001"]},
                {"code": "S7", "text": "집에 가기 싫다고 함", "certainty": "모름", "segment_ids": ["seg_003", "seg_999"]},
                {"code": "S11", "text": "없는 코드", "certainty": "CLEAR", "segment_ids": ["seg_001"]},
                {"code": "S1", "text": "근거 없는 플래그", "certainty": "CLEAR", "segment_ids": ["seg_999"]},
                {"code": "S4", "text": "  ", "segment_ids": ["seg_001"]},
                "bad",
            ],
            "reabuse_factors": [
                {"code": "R2", "text": "술 마시면 때린다고 함", "segment_ids": ["seg_002"]},
                # R1(중복학대)은 화면이 유형 수로 센다 — 모듈은 받지 않는다.
                {"code": "R1", "text": "중복", "segment_ids": ["seg_002"]},
                {"code": "R5", "text": "근거 없음", "segment_ids": []},
            ],
        },
    )

    result = _run()

    assert result == {
        "safety_flags": [
            {"code": "S2", "text": "말하면 더 혼난다고 함", "certainty": "CLEAR", "segment_ids": ["seg_001"]},
            # 모르는 certainty 는 확인 필요로, 원문에 없는 번호는 뺀다.
            {"code": "S7", "text": "집에 가기 싫다고 함", "certainty": "CHECK", "segment_ids": ["seg_003"]},
        ],
        "reabuse_factors": [{"code": "R2", "text": "술 마시면 때린다고 함", "segment_ids": ["seg_002"]}],
    }


def test_same_code_twice_is_merged(monkeypatch):
    _fake_llm(
        monkeypatch,
        {
            "safety_flags": [
                {"code": "S2", "text": "첫 문장", "certainty": "CHECK", "segment_ids": ["seg_001"]},
                {"code": "S2", "text": "둘째 문장", "certainty": "CLEAR", "segment_ids": ["seg_002", "seg_001"]},
            ],
            "reabuse_factors": [],
        },
    )

    assert _run()["safety_flags"] == [
        {"code": "S2", "text": "첫 문장", "certainty": "CLEAR", "segment_ids": ["seg_001", "seg_002"]}
    ]


@pytest.mark.parametrize("reply", [RuntimeError("LLM down"), "not a dict", None])
def test_failure_returns_none(monkeypatch, reply):
    _fake_llm(monkeypatch, reply)

    assert _run() is None


def test_empty_transcript_finds_nothing_without_calling(monkeypatch):
    calls = _fake_llm(monkeypatch, {})

    result = sf.generate_safety_flags(client=object(), model="fake", masked_transcript_text="  ", segments=SEGMENTS)

    assert result == {"safety_flags": [], "reabuse_factors": []}
    assert calls == []


def test_prompt_carries_every_code_and_the_transcript(monkeypatch):
    calls = _fake_llm(monkeypatch, {"safety_flags": [], "reabuse_factors": []})

    _run()

    [call] = calls
    for code in list(sf.SAFETY_FLAG_DEFINITIONS) + list(sf.REABUSE_FACTOR_DEFINITIONS):
        assert f"- {code}:" in call["system_prompt"]
    assert "R1:" not in call["system_prompt"]
    assert TEXT in call["user_prompt"]
