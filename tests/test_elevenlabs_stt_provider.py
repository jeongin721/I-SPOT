"""Offline regression tests for the ElevenLabs Scribe v2 production adapter."""

import math
from pathlib import Path
import sys

import pytest

import stt.ispot_stt as ispot_stt
from stt.ispot_stt import (
    AudioProviderError,
    BaseSTTProvider,
    ElevenLabsScribeV2Provider,
    ProviderFailureFallbackSTTProvider,
    Transcriber,
)


WORDS = [
    {"type": "word", "text": "무슨", "start": 0.0, "end": 0.2, "speaker_id": "speaker_7"},
    {"type": "word", "text": "일이", "start": 0.2, "end": 0.4, "speaker_id": "speaker_7"},
    {"type": "word", "text": "있었나요?", "start": 0.4, "end": 0.8, "speaker_id": "speaker_7"},
    {"type": "spacing", "text": " ", "start": 0.8, "end": 0.8, "speaker_id": "speaker_7"},
    {"type": "word", "text": "몰라요.", "start": 1.234, "end": 1.7, "speaker_id": "speaker_2"},
]


def test_elevenlabs_words_become_contract_segments_without_positional_roles():
    segments = ElevenLabsScribeV2Provider._coerce_to_contract({"words": WORDS})

    assert len(segments) == 2
    assert segments[0]["provider_speaker_id"] == "speaker_7"
    assert segments[1]["provider_speaker_id"] == "speaker_2"
    assert segments[0]["speaker"] == "COUNSELOR"  # question content, not ID position
    assert segments[1]["speaker"] == "CHILD"
    assert segments[1]["start_ms"] == 1234
    assert segments[1]["end_ms"] == 1700
    assert segments[0]["text"] == "무슨 일이 있었나요?"
    assert segments[0]["confidence"] == 0.0
    assert segments[0]["is_low_confidence"] is False
    assert len(segments[0]["words"]) == 3  # type != word excluded


def test_single_speaker_is_unknown_not_a_fallback_condition():
    segments = ElevenLabsScribeV2Provider._coerce_to_contract(
        {"words": [
            {"type": "word", "text": "안녕하세요.", "start": 0, "end": 0.5, "speaker_id": "speaker_0"},
        ]}
    )
    assert segments[0]["provider_speaker_id"] == "speaker_0"
    assert segments[0]["speaker"] == "UNKNOWN"


class _StaticProvider(BaseSTTProvider):
    def __init__(self, result=None, error=None):
        super().__init__()
        self.result = result
        self.error = error
        self.calls = 0

    def transcribe(self, audio_path):
        self.calls += 1
        if self.error:
            raise self.error
        return self.result


def test_normal_elevenlabs_result_does_not_call_deepgram_fallback():
    primary = _StaticProvider(result={"schema_version": "1.0", "segments": []})
    fallback = _StaticProvider(result={"schema_version": "1.0", "segments": []})

    result = ProviderFailureFallbackSTTProvider(primary, fallback).transcribe("unused.wav")

    assert result["segments"] == []
    assert primary.calls == 1
    assert fallback.calls == 0


class _FailingSpeechToText:
    def convert(self, **kwargs):
        raise RuntimeError("network unavailable")


class _FailingElevenLabsClient:
    speech_to_text = _FailingSpeechToText()


def test_elevenlabs_api_error_uses_deepgram_fallback(tmp_path):
    audio = tmp_path / "sample.wav"
    audio.write_bytes(b"audio")
    primary = ElevenLabsScribeV2Provider(client=_FailingElevenLabsClient())
    fallback = _StaticProvider(result={"schema_version": "1.0", "segments": []})

    result = ProviderFailureFallbackSTTProvider(primary, fallback).transcribe(str(audio))

    assert result["provider_fallback_used"] is True
    assert fallback.calls == 1


def test_elevenlabs_uses_evaluated_scribe_settings(tmp_path):
    class SpeechToText:
        def __init__(self):
            self.kwargs = None

        def convert(self, **kwargs):
            self.kwargs = kwargs
            return {"words": WORDS}

    class Client:
        def __init__(self):
            self.speech_to_text = SpeechToText()

    audio = tmp_path / "sample.wav"
    audio.write_bytes(b"audio")
    client = Client()

    ElevenLabsScribeV2Provider(client=client).transcribe(str(audio))

    assert client.speech_to_text.kwargs["model_id"] == "scribe_v2"
    assert client.speech_to_text.kwargs["language_code"] == "kor"
    assert client.speech_to_text.kwargs["diarize"] is True
    assert client.speech_to_text.kwargs["tag_audio_events"] is False


def test_transcriber_registry_accepts_elevenlabs(monkeypatch):
    class DummyEleven(BaseSTTProvider):
        def transcribe(self, audio_path):
            return {"schema_version": "1.0", "segments": []}

    class DummyDeepgram(BaseSTTProvider):
        def transcribe(self, audio_path):
            return {"schema_version": "1.0", "segments": []}

    monkeypatch.setattr(ispot_stt, "ElevenLabsScribeV2Provider", DummyEleven)
    monkeypatch.setattr(ispot_stt, "DeepgramSTTProvider", DummyDeepgram)
    monkeypatch.setenv("I_SPOT_STT_FALLBACK_PROVIDER", "deepgram")

    transcriber = Transcriber(provider="elevenlabs")

    assert isinstance(transcriber._provider, ProviderFailureFallbackSTTProvider)


def test_invalid_elevenlabs_payload_is_provider_error():
    with pytest.raises(ValueError, match="top-level words"):
        ElevenLabsScribeV2Provider._coerce_to_contract({"text": "missing words"})


def test_existing_backend_contract_accepts_the_provider_payload_without_changes():
    backend_dir = Path(__file__).resolve().parents[1] / "backend"
    sys.path.insert(0, str(backend_dir))
    try:
        from app.schemas.contracts import STTResult
    finally:
        sys.path.remove(str(backend_dir))

    payload = {
        "schema_version": "1.0",
        "segments": ElevenLabsScribeV2Provider._coerce_to_contract({"words": WORDS}),
    }
    result = STTResult.model_validate(payload)

    assert result.schema_version == "1.0"
    assert [segment.speaker.value for segment in result.segments] == ["COUNSELOR", "CHILD"]


# ---------------------------------------------------------------------------
# 단어 · 구간 confidence (exp(logprob)). 가짜 토큰만 쓴다.
# ---------------------------------------------------------------------------
def _word(text, start, logprob=None, speaker="spk_a", kind="word"):
    item = {"type": kind, "text": text, "start": start, "end": start + 0.1, "speaker_id": speaker}
    if logprob is not None:
        item["logprob"] = logprob
    return item


def _one_segment(words):
    segments = ElevenLabsScribeV2Provider._coerce_to_contract({"words": words})
    assert len(segments) == 1
    return segments[0]


def test_segment_confidence_is_min_of_word_exp_logprob():  # (가)
    segment = _one_segment([_word("tok_a", 0.0, -0.1), _word("tok_b", 0.1, -0.5), _word("tok_c", 0.2, -0.2)])

    assert [w["confidence"] for w in segment["words"]] == pytest.approx(
        [math.exp(-0.1), math.exp(-0.5), math.exp(-0.2)]
    )
    assert segment["confidence"] == pytest.approx(math.exp(-0.5))
    assert segment["is_low_confidence"] is True  # exp(-0.5) = 0.607 < 0.7


def test_word_confidence_floor_is_0_01_and_cap_is_1():  # (나)
    segment = _one_segment([_word("tok_a", 0.0, -20.0), _word("tok_b", 0.1, 0.5)])

    assert segment["words"][0]["confidence"] == 0.01
    assert segment["words"][1]["confidence"] == 1.0
    assert segment["confidence"] == 0.01
    assert segment["is_low_confidence"] is True


@pytest.mark.parametrize("missing", [None, "abc", float("nan"), float("inf"), float("-inf"), True])
def test_words_without_usable_logprob_are_left_out(missing):  # (다)
    words = [_word("tok_a", 0.0, -0.05), _word("tok_b", 0.1), _word("tok_c", 0.2, -0.1)]
    if missing is not None:
        words[1]["logprob"] = missing
    segment = _one_segment(words)

    assert segment["words"][1]["confidence"] == 0.0
    assert segment["confidence"] == pytest.approx(math.exp(-0.1))
    assert segment["is_low_confidence"] is False


def test_no_usable_logprob_keeps_0_0_and_not_low():  # (라)
    segment = _one_segment([_word("tok_a", 0.0), _word("tok_b", 0.1, float("nan"))])

    assert segment["confidence"] == 0.0
    assert segment["is_low_confidence"] is False
    assert [w["confidence"] for w in segment["words"]] == [0.0, 0.0]


def test_low_confidence_boundary_is_strict_0_7():  # (마)
    assert ispot_stt.LOW_CONFIDENCE_THRESHOLD == 0.7
    at = _one_segment([_word("tok_a", 0.0, math.log(0.7))])
    below = _one_segment([_word("tok_a", 0.0, math.log(0.69))])

    assert at["confidence"] == 0.7
    assert at["is_low_confidence"] is False
    assert below["confidence"] == pytest.approx(0.69)
    assert below["is_low_confidence"] is True


def test_spacing_items_are_ignored_for_confidence():  # (바)
    segment = _one_segment([
        _word("tok_a", 0.0, -0.1),
        _word(" ", 0.1, -30.0, kind="spacing"),
        _word("tok_b", 0.2, -0.2),
    ])

    assert len(segment["words"]) == 2
    assert segment["confidence"] == pytest.approx(math.exp(-0.2))


def test_return_structure_is_unchanged():  # (사)
    for words in (WORDS, [_word("tok_a", 0.0, -0.3), _word("tok_b", 0.1)]):
        for segment in ElevenLabsScribeV2Provider._coerce_to_contract({"words": words}):
            assert set(segment) == {
                "segment_id", "speaker", "provider_speaker_id", "start_ms", "end_ms",
                "text", "confidence", "is_low_confidence", "words",
            }
            assert isinstance(segment["confidence"], float)
            assert isinstance(segment["is_low_confidence"], bool)
            assert isinstance(segment["start_ms"], int) and isinstance(segment["end_ms"], int)
            for word in segment["words"]:
                assert set(word) == {"word", "speaker", "start_ms", "end_ms", "confidence"}
                assert isinstance(word["confidence"], float)
