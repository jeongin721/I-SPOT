"""Offline regression for the production STT-to-CHILD handoff boundary.

Only the provider boundary is fake.  ``Transcriber``, runtime role mapping,
and ``ChildAnalysisTextBuilder`` are the production implementations.
"""

from __future__ import annotations

from copy import deepcopy
import wave

import pytest

from child_analysis_text import ChildAnalysisTextBuilder
from stt.ispot_stt import BaseSTTProvider, Transcriber, single_speaker_fallback_enabled


class StaticProvider(BaseSTTProvider):
    """In-memory provider boundary; it has no SDK, network, or API key use."""

    def __init__(self, result):
        super().__init__()
        self.result = result
        self.calls = 0

    def transcribe(self, _audio_path):
        self.calls += 1
        return deepcopy(self.result)


def _segment(segment_id, speaker, start_ms, text):
    return {
        "segment_id": segment_id,
        "speaker": speaker,
        "start_ms": start_ms,
        "end_ms": start_ms + 500,
        "text": text,
        "confidence": 0.0,
    }


def _provider_result(segments):
    return {"schema_version": "1.0", "segments": segments}


@pytest.fixture
def run_pipeline(tmp_path, monkeypatch):
    audio_path = tmp_path / "synthetic.wav"
    with wave.open(str(audio_path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(8000)
        wav.writeframes(b"\0\0" * 80)

    def run(provider_result):
        provider = StaticProvider(provider_result)
        monkeypatch.setattr(Transcriber, "_build_provider", lambda _self: provider)
        stt_result = Transcriber(provider="mock").transcribe(audio_path)
        child_result = ChildAnalysisTextBuilder().build(stt_result)
        return provider, stt_result, child_result

    return run


def test_two_speaker_pipeline_hands_off_confirmed_child_only(run_pipeline):
    provider, stt_result, child = run_pipeline(
        _provider_result(
            [
                _segment("q1", "SPEAKER_0", 0, "What happened today?"),
                _segment("a1", "SPEAKER_1", 1000, "CHILD_ONLY"),
                _segment("q2", "SPEAKER_0", 2000, "Who was there?"),
                _segment("a2", "SPEAKER_1", 3000, "CHILD_ONLY_SECOND"),
            ]
        )
    )

    assert provider.calls == 1
    assert stt_result["schema_version"] == "1.0"
    assert child["status"] == "OK"
    assert isinstance(child["child_analysis_text"], str)
    assert child["child_analysis_text"] == "CHILD_ONLY CHILD_ONLY_SECOND"
    assert "What happened today?" not in child["child_analysis_text"]
    assert "Who was there?" not in child["child_analysis_text"]


def test_multiple_child_utterances_are_time_ordered_when_provider_order_is_not(run_pipeline):
    _, _, child = run_pipeline(
        _provider_result(
            [
                _segment("a2", "SPEAKER_1", 3000, "CHILD_SECOND"),
                _segment("q1", "SPEAKER_0", 0, "Question one?"),
                _segment("q2", "SPEAKER_0", 2000, "Question two?"),
                _segment("a1", "SPEAKER_1", 1000, "CHILD_FIRST"),
            ]
        )
    )

    assert child["status"] == "OK"
    assert child["child_analysis_text"] == "CHILD_FIRST CHILD_SECOND"


def test_extra_canonical_speaker_text_never_enters_child_handoff(run_pipeline):
    _, _, child = run_pipeline(
        _provider_result(
            [
                _segment("q1", "SPEAKER_0", 0, "Question one?"),
                _segment("a1", "SPEAKER_1", 1000, "CHILD_ONLY"),
                _segment("q2", "SPEAKER_0", 2000, "Question two?"),
                _segment("a2", "SPEAKER_1", 3000, "CHILD_ONLY_SECOND"),
                _segment("x1", "SPEAKER_2", 4000, "EXTRA_SPEAKER_TEXT"),
            ]
        )
    )

    assert child["status"] == "OK"
    assert "EXTRA_SPEAKER_TEXT" not in child["child_analysis_text"]


def test_ambiguous_roles_abstain_without_normal_child_text(run_pipeline):
    _, _, child = run_pipeline(
        _provider_result(
            [
                _segment("a1", "SPEAKER_0", 0, "Question from first?"),
                _segment("b1", "SPEAKER_1", 1000, "Question from second?"),
            ]
        )
    )

    assert child["status"] == "UNRESOLVED_CHILD_SPEAKER"
    assert child["child_analysis_text"] == ""
    assert child["child_speaker"] is None


def test_single_speaker_abstains_with_selective_fallback_off(run_pipeline, monkeypatch):
    monkeypatch.setenv("I_SPOT_SINGLE_SPEAKER_FALLBACK", "off")
    provider, _, child = run_pipeline(
        _provider_result(
            [
                _segment("s1", "SPEAKER_0", 0, "Question?"),
                _segment("s2", "SPEAKER_0", 1000, "Answer"),
            ]
        )
    )

    assert single_speaker_fallback_enabled() is False
    assert provider.calls == 1
    assert child["status"] == "UNRESOLVED_CHILD_SPEAKER"
    assert child["child_analysis_text"] == ""


@pytest.mark.parametrize("child_text", ["", "  \t\n "])
def test_empty_child_content_never_becomes_normal_handoff(run_pipeline, child_text):
    _, _, child = run_pipeline(
        _provider_result(
            [
                _segment("q1", "SPEAKER_0", 0, "Question one?"),
                _segment("a1", "SPEAKER_1", 1000, child_text),
                _segment("q2", "SPEAKER_0", 2000, "Question two?"),
            ]
        )
    )

    assert child["status"] == "UNRESOLVED_CHILD_SPEAKER"
    assert child["child_analysis_text"] == ""
    assert isinstance(child["child_analysis_text"], str)
