# ai/modeling/abuse/key_scan_llm.py — STT 검수 1차 임시 핵심 발화를 LLM 으로 확인(2026-11-20, 팀장 결정).
# 가리기 · OpenAI 는 가짜를 넣는다(표준 라이브러리만으로 시험).
from typing import Any, Dict, List

from app.adapters.module_loader import ensure_repo_root_on_path

ensure_repo_root_on_path()

from ai.modeling.abuse import key_scan_llm  # noqa: E402
from ai.modeling.abuse.key_scan_llm import (  # noqa: E402
    LlmVerifyConfig,
    build_excerpt,
    llm_verify_config,
    parse_response,
    similar_name_variants,
    verify_picks,
)


def _seg(number: int, speaker: str, text: str) -> Dict[str, Any]:
    return {"segment_id": f"seg_{number:03d}", "speaker": speaker, "text": text}


# 11/20 시험 녹음과 같은 모양: 교통사고(오탐)와 실제 신체학대 진술이 떨어져 있다.
SEGMENTS = [
    _seg(1, "COUNSELOR", "최근에 다친 적이 있었어? 얼마나 다쳤어?"),
    _seg(2, "CHILD", "오토바이에 치여서 다쳤어요. 병원 갔는데 다행히 뼈는 안 부러졌어요."),
    _seg(3, "COUNSELOR", "친구는 뭘 할 때가 즐거워?"),
    _seg(4, "CHILD", "동물들 보면 귀여워서 힐링돼요."),
    _seg(5, "COUNSELOR", "누가 김수하를 때린 적 있어?"),
    _seg(6, "CHILD", "아빠가    때렸어요."),
    _seg(7, "COUNSELOR", "그랬구나."),
    _seg(8, "CHILD", "학교 갔어요."),
    _seg(9, "COUNSELOR", "또 다른 건?"),
    _seg(10, "CHILD", "없어요."),
]

TARGETS = {"seg_002": ["신체학대"], "seg_006": ["신체학대", "정서학대"]}


def test_excerpt_keeps_only_picked_lines_and_their_neighbours():
    """원문 전체가 아니라 고른 줄 ± 앞뒤 줄만, 떨어진 덩어리 사이는 '…', 고른 줄에 ▶ (팀장 결정 11/20)."""

    text, line_map, target_lines = build_excerpt(SEGMENTS, TARGETS, context_lines=1)

    assert text.splitlines() == [
        "[1] 상담사: 최근에 다친 적이 있었어? 얼마나 다쳤어?",
        "▶ [2] 아동: 오토바이에 치여서 다쳤어요. 병원 갔는데 다행히 뼈는 안 부러졌어요.",
        "[3] 상담사: 친구는 뭘 할 때가 즐거워?",
        "…",
        "[4] 상담사: 누가 김수하를 때린 적 있어?",
        "▶ [5] 아동: 아빠가 때렸어요.",
        "[6] 상담사: 그랬구나.",
    ]
    assert line_map == {1: "seg_001", 2: "seg_002", 3: "seg_003", 4: "seg_005", 5: "seg_006", 6: "seg_007"}
    assert target_lines == {2: ["신체학대"], 5: ["신체학대", "정서학대"]}
    assert "학교 갔어요" not in text and "없어요" not in text


def test_excerpt_with_zero_context_and_unknown_targets():
    text, _, target_lines = build_excerpt(SEGMENTS, {"seg_006": ["신체학대"], "seg_999": ["방임"]}, context_lines=0)

    assert text == "▶ [1] 아동: 아빠가 때렸어요."
    assert target_lines == {1: ["신체학대"]}


def test_similar_name_variants_catches_one_letter_stt_misspellings():
    """등록 이름 '김수아' 가 STT 에서 '김수하' 로 적혀도 가린다. 성이 다르거나 두 글자 이상 다르면 아니다. 두 글자 이름은 보지 않는다."""

    text = "김수하가 왔고 박수아도 왔고 김하늘 김수아 수하"

    assert similar_name_variants(text, ["김수아", "수아"]) == ["김수하"]
    assert similar_name_variants(text, []) == []
    assert similar_name_variants(text, None) == []


def test_parse_keeps_only_marked_lines_and_candidate_types():
    line_map = {1: "seg_001", 2: "seg_002", 5: "seg_006"}
    target_lines = {2: ["신체학대"], 5: ["신체학대", "정서학대"]}

    parsed = parse_response(
        {
            "items": [
                {"line": 2, "types": [], "reason": "교통사고로 다침"},
                {"line": "5", "types": ["신체학대", "방임", "신체학대"], "reason": "  아빠가   때렸다고 말함 "},
                {"line": 1, "types": ["신체학대"], "reason": "▶ 줄이 아님"},
                {"line": True, "types": ["신체학대"]},
                "bad",
            ]
        },
        line_map,
        target_lines,
    )

    assert parsed == {"seg_002": [], "seg_006": [{"type": "신체학대", "reason": "아빠가 때렸다고 말함"}]}


def test_parse_rejects_wrong_shapes():
    assert parse_response("not json", {1: "a"}, {1: ["방임"]}) is None
    assert parse_response({"result": []}, {1: "a"}, {1: ["방임"]}) is None
    assert parse_response('{"items": []}', {1: "a"}, {1: ["방임"]}) == {"a": []}


def test_config_reads_environment_and_falls_back_on_bad_values():
    assert llm_verify_config({}) == LlmVerifyConfig(True, 30.0, 2)
    assert llm_verify_config({"KEY_SCAN_LLM_VERIFY": "off"}).enabled is False
    config = llm_verify_config({"KEY_SCAN_LLM_TIMEOUT_SECONDS": "abc", "KEY_SCAN_LLM_CONTEXT_LINES": "9"})
    assert (config.timeout_seconds, config.context_lines) == (30.0, 2)
    assert llm_verify_config({"KEY_SCAN_LLM_TIMEOUT_SECONDS": "8", "KEY_SCAN_LLM_CONTEXT_LINES": "1"}) == LlmVerifyConfig(True, 8.0, 1)


class _Recorder:
    def __init__(self, response: Any = None, error: Exception | None = None):
        self.response = response
        self.error = error
        self.masked: List[Any] = []
        self.calls: List[Dict[str, Any]] = []

    def mask(self, text: str, names: Any):
        self.masked.append((text, names))
        return text.replace("김수하", "[이름1]"), {"[이름1]": "김수하"}

    def call(self, **kwargs: Any):
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return self.response


def _restore(value: Any, entity_map: Dict[str, str]) -> Any:
    for token, original in entity_map.items():
        value = value.replace(token, original)
    return value


def _verify(recorder: _Recorder, names=None, config=None):
    return verify_picks(
        SEGMENTS,
        TARGETS,
        names,
        config=config or LlmVerifyConfig(True, 5.0, 1),
        client=object(),
        model="test-model",
        mask=recorder.mask,
        restore=_restore,
        call=recorder.call,
    )


def test_verify_masks_before_sending_and_keeps_only_confirmed_types():
    """보내는 글은 가린 뒤의 일부 줄뿐이고, 등록 이름과 한 글자 다른 표기도 가릴 이름에 더한다. 이유는 원래 이름으로 되돌린다."""

    recorder = _Recorder(
        {
            "items": [
                {"line": 2, "types": [], "reason": "교통사고"},
                {"line": 5, "types": ["신체학대"], "reason": "[이름1]을 아빠가 때렸다고 말함"},
            ]
        }
    )

    result = _verify(recorder, names=["김수아"])

    assert result == {"seg_002": [], "seg_006": [{"type": "신체학대", "reason": "김수하을 아빠가 때렸다고 말함"}]}

    sent_text, names = recorder.masked[0]
    assert names == ["김수아", "김수하"]
    assert "학교 갔어요" not in sent_text
    prompt = recorder.calls[0]["user_prompt"]
    assert "김수하" not in prompt and "[이름1]" in prompt
    assert "▶ [2] 후보: 신체학대" in prompt and "▶ [5] 후보: 신체학대, 정서학대" in prompt
    assert recorder.calls[0]["model"] == "test-model"
    assert recorder.calls[0]["deadline"] is not None


def test_verify_returns_none_so_the_caller_falls_back():
    """꺼짐 · 고른 줄 없음 · 가리기 차단 · LLM 오류 · 모양 오류 → None(호출부가 로컬 임베딩 매칭으로 돌아감). 예외는 올리지 않는다."""

    assert _verify(_Recorder({"items": []}), config=LlmVerifyConfig(False, 5.0, 1)) is None
    assert verify_picks(SEGMENTS, {}, config=LlmVerifyConfig(True, 5.0, 1)) is None
    assert _verify(_Recorder(error=TimeoutError("late"))) is None
    assert _verify(_Recorder({"wrong": 1})) is None

    class Blocked(Exception):
        pass

    def blocked(text, names):
        raise Blocked("name left")

    assert (
        verify_picks(SEGMENTS, TARGETS, config=LlmVerifyConfig(True, 5.0, 1), client=object(), mask=blocked, call=lambda **_: {})
        is None
    )


def test_verify_without_api_key_falls_back(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    def no_client():
        raise RuntimeError("OPENAI_API_KEY 없음")

    monkeypatch.setattr(key_scan_llm, "_default_client", no_client)

    assert verify_picks(SEGMENTS, TARGETS, config=LlmVerifyConfig(True, 5.0, 1), mask=lambda t, n: (t, {})) is None
