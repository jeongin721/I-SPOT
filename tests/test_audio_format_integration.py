"""Synthetic, offline audio-container regression tests."""
import io
import os
import sys
import uuid
import wave
from pathlib import Path

import pytest
from starlette.datastructures import UploadFile

BACKEND = Path(__file__).resolve().parents[1] / "backend"
# The repository's local .env may contain a deployment label for DEBUG.  Keep
# this isolated test importable without changing that environment file.
os.environ["DEBUG"] = "false"
sys.path.insert(0, str(BACKEND))
from app.services.audio_service import detect_audio_format, _validate_header
from app.core import storage
from stt.ispot_stt import Transcriber, InvalidAudioError


def wav_bytes():
    out=io.BytesIO()
    with wave.open(out,'wb') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(8000); w.writeframes(b'\0\0'*80)
    return out.getvalue()

def mp3_bytes(): return b'ID3\x04\x00\x00\x00\x00\x00\x00synthetic'
def m4a_bytes(): return b'\x00\x00\x00\x18ftypM4A \x00\x00\x00\x00isom'

@pytest.mark.parametrize('name,payload,extension,fmt', [
 ('a.wav',wav_bytes(),'.wav','wav'),('a.mp3',mp3_bytes(),'.mp3','mp3'),('a.m4a',m4a_bytes(),'.m4a','mp4'),
 ('a.WAV',wav_bytes(),'.wav','wav'),('a.MP3',mp3_bytes(),'.mp3','mp3'),('a.M4A',m4a_bytes(),'.m4a','mp4')])
def test_synthetic_container_headers_are_accepted(name,payload,extension,fmt):
    assert detect_audio_format(payload)==fmt
    _validate_header(payload,extension)

@pytest.mark.parametrize('payload,extension',[(mp3_bytes(),'.wav'),(wav_bytes(),'.mp3'),(m4a_bytes(),'.wav'),(b'text','.mp3'),(b'', '.wav')])
def test_mismatch_and_malformed_headers_rejected(payload,extension):
    with pytest.raises(Exception): _validate_header(payload,extension)

def test_transcriber_preserves_supported_suffix_and_rejects_empty(tmp_path,monkeypatch):
    class P:
        def transcribe(self,path): return {'schema_version':'1.0','segments':[{'segment_id':'s','speaker':'UNKNOWN','start_ms':0,'end_ms':1,'text':'x','confidence':0}]}
    monkeypatch.setattr(Transcriber,'_build_provider',lambda self:P())
    for suffix,data in [('.wav',wav_bytes()),('.mp3',mp3_bytes()),('.m4a',m4a_bytes())]:
        p=tmp_path/('synthetic'+suffix);p.write_bytes(data);assert Transcriber(provider='mock').transcribe(p)['schema_version']=='1.0'
    empty=tmp_path/'empty.wav';empty.write_bytes(b'')
    with pytest.raises(InvalidAudioError): Transcriber(provider='mock').transcribe(empty)


@pytest.mark.parametrize(
    "filename,payload",
    [
        ("../../evil.mp3", mp3_bytes()),
        (r"....\evil.wav", wav_bytes()),
        ("../../nested/evil.m4a", m4a_bytes()),
    ],
)
def test_storage_sanitizes_traversal_filenames_inside_storage_root(
    tmp_path, monkeypatch, filename, payload
):
    """Dangerous names must never control the final path outside storage."""
    root = (tmp_path / "storage-root").resolve()
    monkeypatch.setattr(storage, "storage_root", lambda: root)

    stored = storage.save_audio_chunks(
        case_id=uuid.uuid4(),
        session_id=uuid.uuid4(),
        filename=filename,
        chunks=[payload],
        max_bytes=1024 * 1024,
    )

    assert stored.absolute_path.is_relative_to(root)
    assert stored.absolute_path.exists()
    assert stored.absolute_path.name.endswith(Path(filename).suffix.lower())
    assert ".." not in stored.absolute_path.name
    assert not (tmp_path / "evil.mp3").exists()
    assert not (tmp_path / "evil.wav").exists()
    assert not (tmp_path / "evil.m4a").exists()


class _SuccessfulMainTranscriber:
    provider_name = "elevenlabs"

    def __init__(self, captured_paths):
        self.captured_paths = captured_paths

    def transcribe(self, path):
        candidate = Path(path)
        self.captured_paths.append(candidate)
        assert candidate.exists()
        return {
            "schema_version": "1.0",
            "segments": [
                {
                    "segment_id": "synthetic-0",
                    "speaker": "UNKNOWN",
                    "start_ms": 0,
                    "end_ms": 10,
                    "text": "synthetic",
                    "confidence": 0.0,
                }
            ],
        }


class _MainChildBuilder:
    def build(self, _result):
        return {"status": "UNRESOLVED_CHILD_SPEAKER", "role_mapping": {}}


class _MainTranscriptBuilder:
    def build(self, **_kwargs):
        return {"schema_version": "1.0", "segments": []}


def _main_upload(filename, payload):
    return UploadFile(filename=filename, file=io.BytesIO(payload))


def _capture_main_tempfile(monkeypatch, main_module, tmp_path):
    original = main_module.tempfile.NamedTemporaryFile
    captured = []

    def named_temporary_file(*args, **kwargs):
        kwargs["dir"] = tmp_path
        handle = original(*args, **kwargs)
        captured.append(Path(handle.name))
        return handle

    monkeypatch.setattr(main_module.tempfile, "NamedTemporaryFile", named_temporary_file)
    return captured


@pytest.mark.parametrize(
    "filename,payload",
    [("synthetic.wav", wav_bytes()), ("synthetic.mp3", mp3_bytes()), ("synthetic.m4a", m4a_bytes())],
)
def test_main_upload_temp_file_is_removed_after_success(tmp_path, monkeypatch, filename, payload):
    import main

    captured_paths = []
    monkeypatch.setattr(main, "stt_provider", _SuccessfulMainTranscriber(captured_paths))
    monkeypatch.setattr(main, "child_builder", _MainChildBuilder())
    monkeypatch.setattr(main, "transcript_builder", _MainTranscriptBuilder())
    created_paths = _capture_main_tempfile(monkeypatch, main, tmp_path)

    result = main.analyze_audio(_main_upload(filename, payload))

    assert result["status"] == "success"
    assert captured_paths and captured_paths[0].suffix == Path(filename).suffix
    assert created_paths and not created_paths[0].exists()


def test_main_upload_temp_file_is_removed_after_stt_exception(tmp_path, monkeypatch):
    import main
    from fastapi import HTTPException

    class FailingTranscriber:
        provider_name = "elevenlabs"

        def transcribe(self, path):
            assert Path(path).exists()
            raise RuntimeError("synthetic provider failure")

    monkeypatch.setattr(main, "stt_provider", FailingTranscriber())
    created_paths = _capture_main_tempfile(monkeypatch, main, tmp_path)

    with pytest.raises(HTTPException) as raised:
        main.analyze_audio(_main_upload("synthetic.mp3", mp3_bytes()))

    assert raised.value.status_code == 502
    assert created_paths and not created_paths[0].exists()


# 브라우저 녹음 창 형식(webm · ogg · mp4)도 STT 확장자 검사를 통과해야 한다(공급자는 가짜, 외부 호출 없음).
def webm_bytes(): return b'\x1a\x45\xdf\xa3\x9f\x42\x86\x81\x01\x42\x82\x84webm' + b'\x00' * 16
def ogg_bytes(): return b'OggS\x00\x02' + b'\x00' * 20 + b'OpusHead'
def mp4_bytes(): return b'\x00\x00\x00\x18ftypisom\x00\x00\x02\x00isomiso2'


@pytest.mark.parametrize('suffix,data', [('.webm', webm_bytes()), ('.ogg', ogg_bytes()), ('.mp4', mp4_bytes()),
                                         ('.WEBM', webm_bytes()), ('.OGG', ogg_bytes()), ('.MP4', mp4_bytes())])
def test_transcriber_accepts_browser_recording_suffixes(tmp_path, monkeypatch, suffix, data):
    seen = []

    class P:
        def transcribe(self, path):
            seen.append(Path(path).suffix)
            return {'schema_version': '1.0', 'segments': [{'segment_id': 's', 'speaker': 'UNKNOWN', 'start_ms': 0, 'end_ms': 1, 'text': 'x', 'confidence': 0}]}

    monkeypatch.setattr(Transcriber, '_build_provider', lambda self: P())
    p = tmp_path / ('synthetic' + suffix)
    p.write_bytes(data)
    assert Transcriber(provider='mock').transcribe(p)['schema_version'] == '1.0'
    assert seen == [suffix]  # 확장자 검사를 지나 공급자까지 갔다


@pytest.mark.parametrize('suffix', ['.xyz', '.opus', '.txt'])
def test_transcriber_rejects_unlisted_suffix_before_provider(tmp_path, monkeypatch, suffix):
    called = []

    class P:
        def transcribe(self, path):
            called.append(path)
            raise AssertionError('provider must not be called')

    monkeypatch.setattr(Transcriber, '_build_provider', lambda self: P())
    p = tmp_path / ('synthetic' + suffix)
    p.write_bytes(ogg_bytes())
    with pytest.raises(InvalidAudioError, match='Unsupported audio format'):
        Transcriber(provider='mock').transcribe(p)
    assert called == []
