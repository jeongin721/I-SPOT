"""STT 실패를 숨기지 않는지 확인하는 오프라인 시험.

공급자는 모두 가짜이고 네트워크를 쓰지 않는다. 문장은 가짜 토큰(tok_*, spk_*)만 쓴다.
- 공급자가 모두 실패하면 가짜 구간 대신 AudioProviderError 가 올라간다.
- 정상 응답에 발화가 없으면 segments 가 빈 목록이다.
- ElevenLabs → Deepgram 대체 때 경고 로그 한 줄만 남기고, 예외 메시지 본문은 로그 · 예외 문구에 넣지 않는다.
"""

import inspect
import logging
import socket
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

import stt.ispot_stt as ispot_stt
from stt.ispot_stt import (
    AudioProviderError,
    BaseSTTProvider,
    DeepgramSTTProvider,
    ElevenLabsScribeV2Provider,
    ProviderFailureFallbackSTTProvider,
    Transcriber,
)

PLACEHOLDER_TEXT = "JSON Contract 형식은 유지합니다"
# 실제 SDK 오류 문구에 섞일 수 있는 것(키 · URL · 응답 본문)을 흉내 낸 가짜 문자열.
SECRET = "tok_secret_body https://api.example.invalid/v1?key=tok_key_123"
LOGGER_NAME = "stt.ispot_stt"

WORDS = [
    {"type": "word", "text": "tok_a", "start": 0.0, "end": 0.2, "speaker_id": "spk_1", "logprob": -0.1},
    {"type": "word", "text": "tok_b", "start": 0.3, "end": 0.5, "speaker_id": "spk_2", "logprob": -0.1},
]


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    """이 파일의 시험은 네트워크를 쓰지 않는다. 연결을 시도하면 바로 실패시킨다."""

    def refuse(*args, **kwargs):
        raise AssertionError("network access is not allowed in this test")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)


def _result(text="tok_ok"):
    return {
        "schema_version": "1.0",
        "segments": [
            {"segment_id": "seg_001", "speaker": "UNKNOWN", "start_ms": 0, "end_ms": 500,
             "text": text, "confidence": 0.9},
        ],
    }


def _secret_error():
    try:
        raise RuntimeError(SECRET)
    except RuntimeError as cause:
        try:
            raise AudioProviderError(f"provider failed: {SECRET}") from cause
        except AudioProviderError as error:
            return error


class _Provider(BaseSTTProvider):
    def __init__(self, name, result=None, error=None):
        super().__init__()
        self.name = name
        self.result = result
        self.error = error
        self.calls = 0

    def transcribe(self, audio_path):
        self.calls += 1
        if self.error is not None:
            raise self.error
        return self.result


def _audio(tmp_path):
    path = tmp_path / "audio.wav"
    path.write_bytes(b"tok_audio")
    return path


def _transcriber_with(monkeypatch, primary, fallback=None, fallback_name="deepgram"):
    """Transcriber(provider="elevenlabs") 가 실제로 만드는 감싸기 구조에 가짜 공급자를 끼운다."""

    monkeypatch.setattr(ispot_stt, "ElevenLabsScribeV2Provider", lambda *args, **kwargs: primary)
    monkeypatch.setattr(ispot_stt, "DeepgramSTTProvider", lambda *args, **kwargs: fallback)
    monkeypatch.setenv("I_SPOT_STT_FALLBACK_PROVIDER", fallback_name)
    monkeypatch.setenv("I_SPOT_SINGLE_SPEAKER_FALLBACK", "off")
    # 로컬 .env(ispot_stt 가 import 때 읽음)에 화자 분리 설정이 있어도 이 시험에서는 끈다.
    monkeypatch.delenv("I_SPOT_SPEAKER_DIARIZATION_PROVIDER", raising=False)
    return Transcriber(provider="elevenlabs")


def _fallback_records(caplog):
    return [
        record for record in caplog.records
        if record.name == LOGGER_NAME and record.getMessage().startswith("stt_provider_fallback")
    ]


# ---------------------------------------------------------------------------
# 1) 공급자가 모두 실패하면 예외가 올라간다
# ---------------------------------------------------------------------------
def test_all_providers_failing_raises_instead_of_placeholder_segment(monkeypatch, tmp_path):
    primary = _Provider("elevenlabs", error=AudioProviderError("tok_primary"))
    fallback = _Provider("deepgram", error=AudioProviderError("tok_fallback"))
    transcriber = _transcriber_with(monkeypatch, primary, fallback)

    with pytest.raises(AudioProviderError) as excinfo:
        transcriber.transcribe(_audio(tmp_path))

    assert primary.calls == 1 and fallback.calls == 1
    assert excinfo.value.__cause__ is fallback.error  # 원인 예외 연결 유지
    assert PLACEHOLDER_TEXT not in str(excinfo.value)


def test_fallback_disabled_elevenlabs_failure_raises(monkeypatch, tmp_path):
    primary = _Provider("elevenlabs", error=AudioProviderError("tok_primary"))
    transcriber = _transcriber_with(monkeypatch, primary, fallback=None, fallback_name="none")

    assert transcriber._provider is primary  # 대체가 꺼져 있으면 감싸지 않는다
    with pytest.raises(AudioProviderError) as excinfo:
        transcriber.transcribe(_audio(tmp_path))
    assert excinfo.value is primary.error


# ---------------------------------------------------------------------------
# 2) 가짜 구간 문구가 어디에도 없다
# ---------------------------------------------------------------------------
def test_placeholder_segment_text_is_gone_from_module():
    assert PLACEHOLDER_TEXT not in inspect.getsource(ispot_stt)
    assert not hasattr(Transcriber, "_fallback_response")


# ---------------------------------------------------------------------------
# 3) 정상 응답에 발화가 없으면 빈 목록
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("segments", [[], None])
def test_empty_provider_result_returns_empty_segments(monkeypatch, tmp_path, segments):
    primary = _Provider("elevenlabs", result={"schema_version": "1.0", "segments": segments})
    fallback = _Provider("deepgram", result=_result())
    transcriber = _transcriber_with(monkeypatch, primary, fallback)

    result = transcriber.transcribe(_audio(tmp_path))

    assert result == {"schema_version": "1.0", "segments": []}
    assert fallback.calls == 0  # 빈 결과는 실패가 아니라서 대체하지 않는다


def test_empty_result_is_a_valid_backend_contract_payload():
    backend_dir = Path(__file__).resolve().parents[1] / "backend"
    sys.path.insert(0, str(backend_dir))
    try:
        from app.schemas.contracts import STTResult
    finally:
        sys.path.remove(str(backend_dir))

    parsed = STTResult.model_validate({"schema_version": "1.0", "segments": []})

    # Backend(transcript_service.process_stt)는 segments 가 비면 "발화를 찾지 못했습니다" 로 실패 마감한다.
    assert parsed.segments == []


# ---------------------------------------------------------------------------
# 4) 대체 경고 로그는 한 줄이고 예외 본문이 없다
# ---------------------------------------------------------------------------
def test_fallback_logs_one_warning_with_class_names_only(caplog):
    primary = _Provider("elevenlabs", error=_secret_error())
    fallback = _Provider("deepgram", result=_result())
    caplog.set_level(logging.DEBUG, logger=LOGGER_NAME)

    result = ProviderFailureFallbackSTTProvider(primary, fallback).transcribe("unused.wav")

    assert result["provider_fallback_used"] is True
    records = _fallback_records(caplog)
    assert len(records) == 1
    record = records[0]
    message = record.getMessage()
    assert record.levelno == logging.WARNING
    assert message == (
        "stt_provider_fallback from=elevenlabs to=deepgram error=AudioProviderError cause=RuntimeError status=none"
    )
    assert record.exc_info is None  # 스택(예외 본문 포함)을 붙이지 않는다
    for text in (message, *map(str, record.args or ())):
        assert "tok_secret_body" not in text and "tok_key_123" not in text and "https://" not in text
        assert "unused.wav" not in text


def test_fallback_warning_without_cause_uses_dash(caplog):
    primary = _Provider("elevenlabs", error=AudioProviderError("tok_no_cause"))
    fallback = _Provider("deepgram", result=_result())
    caplog.set_level(logging.WARNING, logger=LOGGER_NAME)

    ProviderFailureFallbackSTTProvider(primary, fallback).transcribe("unused.wav")

    messages = [record.getMessage() for record in _fallback_records(caplog)]
    assert messages == ["stt_provider_fallback from=elevenlabs to=deepgram error=AudioProviderError cause=- status=none"]


# ---------------------------------------------------------------------------
# 5) 합쳐진 예외 메시지에 본문이 없다
# ---------------------------------------------------------------------------
def test_combined_failure_message_has_class_names_only():
    primary = _Provider("elevenlabs", error=_secret_error())
    fallback_error = _secret_error()
    fallback = _Provider("deepgram", error=fallback_error)

    with pytest.raises(AudioProviderError) as excinfo:
        ProviderFailureFallbackSTTProvider(primary, fallback).transcribe("unused.wav")

    message = str(excinfo.value)
    assert message == (
        "All STT providers failed: elevenlabs=AudioProviderError<-RuntimeError, "
        "deepgram=AudioProviderError<-RuntimeError."
    )
    assert "tok_secret_body" not in message and "tok_key_123" not in message
    assert excinfo.value.__cause__ is fallback_error


def test_real_elevenlabs_adapter_error_body_does_not_reach_combined_message(tmp_path):
    class FailingSpeechToText:
        def convert(self, **kwargs):
            raise RuntimeError(SECRET)

    class Client:
        speech_to_text = FailingSpeechToText()

    audio = _audio(tmp_path)
    fallback = _Provider("deepgram", error=_secret_error())

    with pytest.raises(AudioProviderError) as excinfo:
        ProviderFailureFallbackSTTProvider(ElevenLabsScribeV2Provider(client=Client()), fallback).transcribe(str(audio))

    message = str(excinfo.value)
    assert message.startswith("All STT providers failed: elevenlabs=AudioProviderError<-RuntimeError, deepgram=")
    assert "tok_secret_body" not in message and str(audio) not in message


def test_provider_names_used_in_logs():
    assert ElevenLabsScribeV2Provider.name == "elevenlabs"
    assert DeepgramSTTProvider.name == "deepgram"


# ---------------------------------------------------------------------------
# 6) ElevenLabs 가 성공하면 Deepgram 을 부르지 않는다
# ---------------------------------------------------------------------------
def test_elevenlabs_success_does_not_call_deepgram_or_log_fallback(monkeypatch, tmp_path, caplog):
    primary = _Provider("elevenlabs", result=_result("tok_primary_text"))
    fallback = _Provider("deepgram", result=_result("tok_fallback_text"))
    transcriber = _transcriber_with(monkeypatch, primary, fallback)
    caplog.set_level(logging.WARNING, logger=LOGGER_NAME)

    result = transcriber.transcribe(_audio(tmp_path))

    assert fallback.calls == 0
    assert [segment["text"] for segment in result["segments"]] == ["tok_primary_text"]
    assert _fallback_records(caplog) == []


def test_fallback_success_through_transcriber_returns_fallback_segments(monkeypatch, tmp_path, caplog):
    primary = _Provider("elevenlabs", error=AudioProviderError("tok_primary"))
    fallback = _Provider("deepgram", result=_result("tok_fallback_text"))
    transcriber = _transcriber_with(monkeypatch, primary, fallback)
    caplog.set_level(logging.WARNING, logger=LOGGER_NAME)

    result = transcriber.transcribe(_audio(tmp_path))

    assert [segment["text"] for segment in result["segments"]] == ["tok_fallback_text"]
    assert len(_fallback_records(caplog)) == 1


def test_real_elevenlabs_adapter_success_does_not_call_fallback(tmp_path):
    class SpeechToText:
        def convert(self, **kwargs):
            return {"words": WORDS}

    class Client:
        speech_to_text = SpeechToText()

    fallback = _Provider("deepgram", result=_result())

    result = ProviderFailureFallbackSTTProvider(
        ElevenLabsScribeV2Provider(client=Client()), fallback
    ).transcribe(str(_audio(tmp_path)))

    assert fallback.calls == 0
    assert [segment["text"] for segment in result["segments"]] == ["tok_a", "tok_b"]


# ---------------------------------------------------------------------------
# 7) 대체 경고 로그의 상태 코드 (정수 100~599 만, 메시지 본문은 쓰지 않음)
# ---------------------------------------------------------------------------
STATUS_SECRET = "SECRET_BODY_xyz"


class _FakeApiError(Exception):
    """SDK 의 API 오류를 흉내 낸다. 메시지에는 일부러 가짜 비밀 문자열을 넣는다."""

    def __init__(self, status_code=None, status=None):
        super().__init__(f"{STATUS_SECRET} https://api.example.invalid/v1?key=tok_key_456")
        if status_code is not None:
            self.status_code = status_code
        if status is not None:
            self.status = status


def _fallback_message_for(primary_error, caplog):
    caplog.set_level(logging.WARNING, logger=LOGGER_NAME)
    primary = _Provider("elevenlabs", error=primary_error)
    fallback = _Provider("deepgram", result=_result())

    ProviderFailureFallbackSTTProvider(primary, fallback).transcribe("unused.wav")

    records = _fallback_records(caplog)
    assert len(records) == 1
    message = records[0].getMessage()
    assert STATUS_SECRET not in message and "tok_key_456" not in message and "https://" not in message
    for arg in records[0].args or ():
        assert STATUS_SECRET not in str(arg)
    return message


def _wrapped(cause):
    """실제 어댑터처럼 SDK 오류를 AudioProviderError 로 감싼다(문구에 본문 포함)."""
    try:
        raise cause
    except Exception as exc:
        try:
            raise AudioProviderError(f"provider failed: {exc}") from exc
        except AudioProviderError as error:
            return error


def test_fallback_log_reports_status_code_on_the_error_itself(caplog):
    error = AudioProviderError(f"provider failed: {STATUS_SECRET}")
    error.status_code = 401

    message = _fallback_message_for(error, caplog)

    assert message.endswith(" status=401")
    assert message.count("status=401") == 1


def test_fallback_log_reports_status_code_from_cause(caplog):
    message = _fallback_message_for(_wrapped(_FakeApiError(status_code=429)), caplog)

    assert message == (
        "stt_provider_fallback from=elevenlabs to=deepgram error=AudioProviderError cause=_FakeApiError status=429"
    )


def test_fallback_log_reads_status_attribute_too(caplog):
    message = _fallback_message_for(_wrapped(_FakeApiError(status=503)), caplog)

    assert message.endswith(" status=503")


def test_fallback_log_without_status_code_is_none(caplog):
    message = _fallback_message_for(_wrapped(_FakeApiError()), caplog)

    assert message.endswith(" status=none")


@pytest.mark.parametrize("value", ["401", 0, 99, 600, 999, -401, True, 401.0, None])
def test_fallback_log_rejects_non_integer_or_out_of_range_status(caplog, value):
    cause = _FakeApiError()
    cause.status_code = value

    message = _fallback_message_for(_wrapped(cause), caplog)

    assert message.endswith(" status=none")


def test_failing_status_property_does_not_block_fallback(caplog):
    class _BrokenStatusError(Exception):
        @property
        def status_code(self):
            raise RuntimeError(STATUS_SECRET)

    message = _fallback_message_for(_wrapped(_BrokenStatusError("tok_broken")), caplog)

    assert message.endswith(" status=none")  # 대체 공급자는 그대로 불렸다(_fallback_message_for 안에서 확인)


@pytest.mark.parametrize("depth, expected", [(5, "status=418"), (6, "status=none")])
def test_status_code_is_read_at_most_five_causes_deep(caplog, depth, expected):
    error = _FakeApiError(status_code=418)
    for _ in range(depth):  # depth 번 감싸면 상태 코드는 depth 번째 원인에 있다
        error = _wrapped(error)

    message = _fallback_message_for(error, caplog)

    assert message.endswith(" " + expected)


# ---------------------------------------------------------------------------
# 8) 1354.mp3 디버그 기록이 없어졌다
# ---------------------------------------------------------------------------
def test_deepgram_does_not_dump_raw_response_for_1354_mp3(monkeypatch, tmp_path):
    """옛 코드는 파일 이름이 1354.mp3 로 끝나면 test_sample/1354_deepgram_sdk_raw.json 에 원본 응답을 썼다."""

    work = tmp_path / "work"
    (work / "test_sample").mkdir(parents=True)  # 옛 코드라면 여기에 써졌을 자리
    audio = work / "tok_1354.mp3"
    audio.write_bytes(b"tok_audio")
    monkeypatch.chdir(work)  # 시험이 끝나면 monkeypatch 가 원래 작업 디렉터리로 돌려놓는다

    response = SimpleNamespace(
        results=SimpleNamespace(
            utterances=[
                SimpleNamespace(start=0.0, end=0.5, confidence=0.9, speaker=0, transcript="tok_dg", words=[]),
            ]
        )
    )
    calls = []

    def transcribe_file(**kwargs):
        calls.append(sorted(kwargs))
        return response

    provider = DeepgramSTTProvider.__new__(DeepgramSTTProvider)  # 실제 SDK 클라이언트를 만들지 않는다
    BaseSTTProvider.__init__(provider)
    provider.client = SimpleNamespace(
        listen=SimpleNamespace(v1=SimpleNamespace(media=SimpleNamespace(transcribe_file=transcribe_file)))
    )

    result = provider.transcribe(str(audio))

    assert len(calls) == 1
    assert [segment["text"] for segment in result["segments"]] == ["tok_dg"]
    assert sorted(path.name for path in work.iterdir()) == ["test_sample", "tok_1354.mp3"]
    assert list((work / "test_sample").iterdir()) == []
    assert "1354" not in inspect.getsource(DeepgramSTTProvider)
