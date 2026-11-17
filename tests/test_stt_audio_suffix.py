"""STT 확장자 검사 시험(#181에서 옮김). 가짜 공급자만 쓰고 외부 호출이 없다.

stt.ispot_stt 에서 필요한 것만 불러온다. 루트 main.py · torch · 모델 가중치를 불러오지 않으므로
STT CI(.github/workflows/stt-ci.yml)에서 돌 수 있다.
"""
from pathlib import Path

import pytest

from stt.ispot_stt import InvalidAudioError, Transcriber


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
