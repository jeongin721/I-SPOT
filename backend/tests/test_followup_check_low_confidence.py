# 확인 메모(ai/modeling/abuse/followup_check_llm.py)의 '불확실한 발화' 입력 줄(2026-11-02, STT #133 대비).
#
# #133 머지 뒤 ElevenLabs 구간 신뢰도가 실제 값(0.01~1.0)으로 채워진다. 값은 오인식과의 관계가 검증되지 않은 확률이라
# LLM 입력에는 숫자를 넣지 않고 '음성 인식 불확실' 로만 알린다. 값이 없는 구간(0.0)은 저신뢰로 보지 않는다.

import importlib
import sys
import types

from app.adapters.module_loader import ensure_repo_root_on_path

ensure_repo_root_on_path()


def _module(monkeypatch):
    """확인 메모 모듈은 openai · second_stage_llm 을 바로 import 한다. CI 에 없으니 가짜 모듈로 바꿔 불러온다."""

    monkeypatch.setitem(sys.modules, "openai", types.SimpleNamespace(OpenAI=object))
    monkeypatch.setitem(
        sys.modules, "ai.modeling.abuse.second_stage_llm", types.SimpleNamespace(_call_llm_with_retry=lambda **_: {})
    )
    monkeypatch.delitem(sys.modules, "ai.modeling.abuse.followup_check_llm", raising=False)
    module = importlib.import_module("ai.modeling.abuse.followup_check_llm")
    monkeypatch.delitem(sys.modules, "ai.modeling.abuse.followup_check_llm", raising=False)
    return module


def _seg(seg_id, text, confidence, low, speaker="CHILD"):
    return {"segment_id": seg_id, "start_ms": 135000, "speaker": speaker, "text": text, "confidence": confidence, "is_low_confidence": low}


def test_low_confidence_lines_carry_no_probability(monkeypatch):
    fc = _module(monkeypatch)

    text = fc._format_low_confidence(
        [
            _seg("seg_1", "밥도 안 줄 때가 있어요.", 0.42, True),
            _seg("seg_2", "병원은 안 갔어요", 0.3, True, speaker="UNKNOWN"),
            _seg("seg_3", "할머니 집에 가고 싶어요.", 0.0, False),  # 값 없음 — 넣지 않는다
            _seg("seg_4", "네", 0.2, True),  # 단답 — 넣지 않는다
        ]
    )

    assert text.splitlines() == [
        '- [seg_1] 02:15 "밥도 안 줄 때가 있어요." (음성 인식 불확실)',
        '- [seg_2] 02:15 "병원은 안 갔어요" (음성 인식 불확실 · 화자 불확실)',
    ]
    assert "0.42" not in text and "신뢰도" not in text


def test_prompt_says_uncertain_text_may_be_misheard(monkeypatch):
    fc = _module(monkeypatch)

    assert "음성 인식이 잘못 받아 적은 것일 수" in fc.SYSTEM_PROMPT
    assert "신뢰도가 0.59" not in fc.SYSTEM_PROMPT
