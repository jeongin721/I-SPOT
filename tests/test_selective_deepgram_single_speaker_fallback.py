"""Offline tests for the opt-in selective Deepgram fallback prototype."""

from __future__ import annotations

from copy import deepcopy

import stt.ispot_stt as ispot_stt
from stt.ispot_stt import (
    AudioProviderError,
    BaseSTTProvider,
    ProviderFailureFallbackSTTProvider,
    SelectiveSingleSpeakerFallbackSTTProvider,
    Transcriber,
)


class StaticProvider(BaseSTTProvider):
    def __init__(self, result=None, error=None):
        super().__init__()
        self.result, self.error, self.calls = result, error, 0

    def transcribe(self, audio_path):
        self.calls += 1
        if self.error:
            raise self.error
        return deepcopy(self.result)


def elevenlabs_result(raw_speakers=1):
    segments = [
        {
            "segment_id": "el_1",
            "speaker": "UNKNOWN",
            "start_ms": 0,
            "end_ms": 500,
            "text": "primary text",
            "confidence": 0.0,
        }
    ]
    return {
        "schema_version": "1.0",
        "segments": segments,
        "_ispot_metadata": {
            "primary_provider": "elevenlabs",
            "primary_raw_speaker_count": raw_speakers,
            "valid_normalized_words": True,
        },
    }


def deepgram_result(*, speaker_count=2, ambiguous=False):
    if speaker_count == 1:
        segments = [
            {"segment_id": "dg_1", "speaker": "SPEAKER_0", "start_ms": 0, "end_ms": 400, "text": "question?", "confidence": 0.9},
            {"segment_id": "dg_2", "speaker": "SPEAKER_0", "start_ms": 500, "end_ms": 900, "text": "answer", "confidence": 0.9},
        ]
    else:
        second_text = "also question?" if ambiguous else "answer"
        segments = [
            {"segment_id": "dg_1", "speaker": "SPEAKER_0", "start_ms": 0, "end_ms": 400, "text": "question?", "confidence": 0.9},
            {"segment_id": "dg_2", "speaker": "SPEAKER_0", "start_ms": 500, "end_ms": 900, "text": "question?", "confidence": 0.9},
            {"segment_id": "dg_3", "speaker": "SPEAKER_1", "start_ms": 1000, "end_ms": 1300, "text": second_text, "confidence": 0.9},
            {"segment_id": "dg_4", "speaker": "SPEAKER_1", "start_ms": 1400, "end_ms": 1700, "text": second_text, "confidence": 0.9},
        ]
    return {"schema_version": "1.0", "segments": segments}


def prototype(primary, secondary, *, enabled=True):
    return SelectiveSingleSpeakerFallbackSTTProvider(primary, secondary, enabled=enabled)


def test_flag_off_single_elevenlabs_keeps_unknown_and_never_calls_deepgram():
    primary, secondary = StaticProvider(elevenlabs_result()), StaticProvider(deepgram_result())
    result = prototype(primary, secondary, enabled=False).transcribe("unused.wav")
    assert primary.calls == 1 and secondary.calls == 0
    assert result["segments"][0]["speaker"] == "UNKNOWN"


def test_enabled_two_speaker_elevenlabs_never_calls_deepgram():
    primary, secondary = StaticProvider(elevenlabs_result(raw_speakers=2)), StaticProvider(deepgram_result())
    result = prototype(primary, secondary).transcribe("unused.wav")
    assert primary.calls == 1 and secondary.calls == 0
    assert result["_ispot_metadata"]["primary_raw_speaker_count"] == 2


def test_enabled_single_calls_deepgram_once_and_uses_only_resolved_runtime_roles():
    primary, secondary = StaticProvider(elevenlabs_result()), StaticProvider(deepgram_result())
    result = prototype(primary, secondary).transcribe("unused.wav")
    assert primary.calls == 1 and secondary.calls == 1
    assert result["_ispot_metadata"]["fallback_used"] is True
    assert result["_ispot_metadata"]["secondary_role_resolved"] is True
    assert {segment["speaker"] for segment in result["segments"]} == {"COUNSELOR", "CHILD"}
    assert {segment["provider_speaker_id"] for segment in result["segments"]} == {"SPEAKER_0", "SPEAKER_1"}


def test_secondary_single_or_ambiguous_result_remains_safe_unknown():
    for secondary_result in (deepgram_result(speaker_count=1), deepgram_result(ambiguous=True)):
        primary, secondary = StaticProvider(elevenlabs_result()), StaticProvider(secondary_result)
        result = prototype(primary, secondary).transcribe("unused.wav")
        assert secondary.calls == 1
        assert result["_ispot_metadata"]["fallback_used"] is False
        assert result["_ispot_metadata"]["secondary_role_resolved"] is False
        assert {segment["speaker"] for segment in result["segments"]} == {"UNKNOWN"}


def test_secondary_exception_and_malformed_result_do_not_crash_or_create_child():
    for secondary in (StaticProvider(error=AudioProviderError("network")), StaticProvider({"segments": "invalid"})):
        result = prototype(StaticProvider(elevenlabs_result()), secondary).transcribe("unused.wav")
        assert result["_ispot_metadata"]["fallback_used"] is False
        assert {segment["speaker"] for segment in result["segments"]} == {"UNKNOWN"}


def test_missing_primary_valid_word_metadata_does_not_trigger_selective_path():
    primary_result = elevenlabs_result()
    primary_result["_ispot_metadata"]["valid_normalized_words"] = False
    primary, secondary = StaticProvider(primary_result), StaticProvider(deepgram_result())
    prototype(primary, secondary).transcribe("unused.wav")
    assert secondary.calls == 0


def test_provider_failure_fallback_does_not_trigger_a_second_deepgram_call():
    fallback = StaticProvider(deepgram_result())
    provider_failure_path = ProviderFailureFallbackSTTProvider(
        StaticProvider(error=AudioProviderError("elevenlabs network")), fallback,
    )
    selective_secondary = StaticProvider(deepgram_result())
    result = prototype(provider_failure_path, selective_secondary).transcribe("unused.wav")
    assert fallback.calls == 1
    assert selective_secondary.calls == 0
    assert result["provider_fallback_used"] is True


def test_feature_off_factory_preserves_existing_provider_failure_wrapper(monkeypatch):
    class DummyEleven(BaseSTTProvider):
        def transcribe(self, audio_path):
            return elevenlabs_result()

    class DummyDeepgram(BaseSTTProvider):
        def transcribe(self, audio_path):
            return deepgram_result()

    monkeypatch.setattr(ispot_stt, "ElevenLabsScribeV2Provider", DummyEleven)
    monkeypatch.setattr(ispot_stt, "DeepgramSTTProvider", DummyDeepgram)
    monkeypatch.setenv("I_SPOT_STT_FALLBACK_PROVIDER", "deepgram")
    monkeypatch.setenv("I_SPOT_SINGLE_SPEAKER_FALLBACK", "off")
    assert isinstance(Transcriber(provider="elevenlabs")._provider, ProviderFailureFallbackSTTProvider)


def test_transcriber_strips_internal_provenance_before_shared_contract(monkeypatch, tmp_path):
    class DummyEleven(BaseSTTProvider):
        def __init__(self, *args, **kwargs):
            super().__init__()

        def transcribe(self, audio_path):
            return elevenlabs_result()

    class DummyDeepgram(BaseSTTProvider):
        def __init__(self, *args, **kwargs):
            super().__init__()

        def transcribe(self, audio_path):
            return deepgram_result()

    monkeypatch.setattr(ispot_stt, "ElevenLabsScribeV2Provider", DummyEleven)
    monkeypatch.setattr(ispot_stt, "DeepgramSTTProvider", DummyDeepgram)
    monkeypatch.setenv("I_SPOT_STT_FALLBACK_PROVIDER", "deepgram")
    monkeypatch.setenv("I_SPOT_SINGLE_SPEAKER_FALLBACK", "on")
    audio = tmp_path / "audio.wav"
    audio.write_bytes(b"audio")
    result = Transcriber(provider="elevenlabs").transcribe(audio)
    assert "_ispot_metadata" not in result
    assert {segment["speaker"] for segment in result["segments"]} == {"COUNSELOR", "CHILD"}
