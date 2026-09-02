"""STT adapter regression tests.

이 테스트 파일은 I-SPOT의 STT Contract가 실제로 지켜지는지 검증한다.
핵심 목적은 다음과 같다:
- 정상 wav 파일 입력 시 schema_version과 segment 구조가 맞는지 확인
- 빈 오디오나 잘못된 파일이 올 때 예외가 발생하는지 확인
- 지원하지 않는 확장자를 거부하는지 확인

즉, Backend가 import해서 안전하게 사용할 수 있는지 확인하는 테스트 모음이다.
"""

import wave

import pytest

from ispot_stt import (
    SpeakerDiarizer,
    Transcriber,
    InvalidAudioError,
    WhisperSTTProvider,
)


# 테스트용 가짜 WAV 파일을 생성한다.
# 실제 오디오 모델이 아니라도 입력 검증과 Contract 검증을 시뮬레이션할 수 있다.
def _write_wav(path, sample_rate=16000, duration_ms=250):
    frames = sample_rate * duration_ms // 1000
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)  # 오디오 채널을 1로 설정 (모노)
        wf.setsampwidth(2)  # 샘플 당 데이터 크기를 2바이트로 설정 (16비트)
        wf.setframerate(sample_rate)  # 초당 샘플 수를 16,000Hz로 설정
        wf.writeframes(b"\x00\x00" * frames)  # 무음데이터를 프레임 수만큼 파일에 적어넣어 무음 wave 파일을 생성


# 정상 동작 테스트.
# 입력된 wav 파일이 STT Contract를 만족하는 JSON으로 변환되는지 확인한다.
def test_transcribe_returns_schema_contract(tmp_path):
    audio_path = tmp_path / "demo.wav"
    _write_wav(audio_path)

    result = Transcriber().transcribe(str(audio_path))  # Transcriber 객체를 생성하고, 방금 만든 가짜 오디오 파일을 넣어서 변환 결과(result)를 받아옴

    assert result["schema_version"] == "1.0"  # assert는 조건이 참인지 확인하는 구문. 반환된 결과의 스키마 버전이 "1.0"이 맞는지 검증
    assert isinstance(result["segments"], list)  # segments가 리스트 타입인지 확인
    assert len(result["segments"]) >= 1  # segments 리스트에 최소한 하나 이상의 세그먼트(자막/음성)이 존재하는지 확인

    segment = result["segments"][0]
    assert segment["segment_id"].startswith("seg_")
    assert segment["speaker"] in {"COUNSELOR", "CHILD", "GUARDIAN", "OTHER", "UNKNOWN"}  # 화자 정보가 미리 약속된 5가지 열거형(상담사, 아동, 보호자, 기타, 알수없음) 중 하나에 포함되는지 검증
    assert segment["start_ms"] >= 0
    assert segment["end_ms"] >= segment["start_ms"]
    assert 0.0 <= segment["confidence"] <= 1.0  # AI의 인식 신뢰도 점수가 0.0에서 1.0 사이의 정유의 값인지 확인
    assert "is_low_confidence" in segment  # 세그먼트에 '신뢰도 낮음 여부' 플래그 키가 정상적으로 들어있는지 검증


# 빈 파일 입력 시 예외가 발생하는지 검증한다.
# 상담 음성 업로드 단계에서 손상된 파일을 안전하게 차단하는 역할을 한다.
def test_transcribe_rejects_empty_audio(tmp_path):  # 0바이트짜리 텅 빈 파일이 들어왔을 때 잘 막아내는지 검증
    audio_path = tmp_path / "empty.wav"
    audio_path.write_bytes(b"")  # 0바이트짜리 빈 파일을 생성

    with pytest.raises(InvalidAudioError):
        Transcriber().transcribe(str(audio_path))  # Transcriber 객체를 생성하고, 방금 만든 빈 오디오 파일을 넣어서 변환 시도. 이때 InvalidAudioError 예외가 발생하는지 확인


# 지원하지 않는 확장자 입력을 막는지 확인한다.
# 실제 서비스에서는 txt, csv 같은 비오디오 파일이 들어오면 처리하지 않아야 한다.
def test_transcribe_rejects_unsupported_extension(tmp_path):  # 오디오가 아닌 텍스트 파일 등을 업로드했을 때 거부하는지 확인
    bad_path = tmp_path / "note.txt"
    bad_path.write_text("not an audio file", encoding="utf-8")

    with pytest.raises(InvalidAudioError):
        Transcriber().transcribe(str(bad_path))  # 음성이 아닌 .txt 파일을 넣었을 때 InvalidAudioError 예외가 발생하는지 검증


# whisper segment 파싱 검증.
# Whisper는 각 문장 단위로 start/end/text를 제공하므로,
# 해당 값을 I-SPOT의 millisecond 기반 segment 구조로 변환하는지 확인한다.
def test_whisper_provider_splits_segments_with_timestamps():  # 실제 OpenAI Whisper AI가 내주는 원본 데이터 형태를 I-SPOT 백엔드에 맞게 변환하는 로직을 검증
    raw_segments = [
        {"start": 0.0, "end": 1.2, "text": "안녕하세요.", "confidence": 0.94},
        {"start": 1.2, "end": 2.4, "text": "오늘 기분이 좋네요.", "confidence": 0.89},
    ]  # Whisper API가 반환해 주는 초(second) 단위 원본 결과 데이터 예시를 생성

    result = WhisperSTTProvider._coerce_segments_to_contract(raw_segments)

    assert result[0]["segment_id"] == "seg_001"
    assert result[0]["start_ms"] == 0
    assert result[0]["end_ms"] == 1200
    assert result[0]["text"] == "안녕하세요."
    assert result[1]["segment_id"] == "seg_002"
    assert result[1]["start_ms"] == 1200
    assert result[1]["end_ms"] == 2400
    assert result[1]["is_low_confidence"] is False


# 화자 라벨 매핑 검증.
# diarization provider가 해당 값을 어떤 식으로 정규화하는지 확인한다.
def test_speaker_diarizer_maps_roles_to_contract_enum():  # 한국어 역할 이름이 백엔드 규격(영문 대문자)으로 잘 바뀌는지 검증
    diarizer = SpeakerDiarizer(provider="mock")  # 모의(mock) 화자 분리 객체를 생성

    assert diarizer.normalize_speaker_label("상담사") == "COUNSELOR"
    assert diarizer.normalize_speaker_label("아동") == "CHILD"
    assert diarizer.normalize_speaker_label("보호자") == "GUARDIAN"
    assert diarizer.normalize_speaker_label("speaker_99") == "UNKNOWN"


# diarization이 STT segment에 반영되는지 검증한다.
# 실제로는 speaker 값이 세그먼트에 덧씌워져야 backend로 전달될 수 있다.
def test_transcriber_applies_mock_diarization_labels(tmp_path):  # STT가 자른 텍스트 자막에 화자 분리 결과(누가 말했는지)가 최종적으로 잘 입혀지는지 검증
    audio_path = tmp_path / "demo.wav"
    audio_path.write_bytes(b"fake")

    transcriber = Transcriber(provider="mock")
    transcriber.speaker_diarizer = SpeakerDiarizer(provider="mock")

    segments = [
        {"segment_id": "seg_001", "speaker": "UNKNOWN", "start_ms": 0, "end_ms": 1000, "text": "안녕하세요", "confidence": 0.91, "is_low_confidence": False},
        {"segment_id": "seg_002", "speaker": "UNKNOWN", "start_ms": 1000, "end_ms": 2000, "text": "오늘 기분이 좋네요", "confidence": 0.88, "is_low_confidence": False},
    ]  # 아직 화자가 누군지 모르는 상태(UNKNOWN)의 세그먼트 데이터 2개를 가상으로 준비

    updated = transcriber.speaker_diarizer.apply_to_segments(segments, str(audio_path))
    assert updated[0]["speaker"] == "COUNSELOR"
    assert updated[1]["speaker"] == "CHILD"
