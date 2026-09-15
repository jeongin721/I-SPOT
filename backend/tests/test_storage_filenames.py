# 음성 파일 이름·저장 경로 방어 테스트 (app/core/storage.py).
#
# 경로 조작("../../etc/passwd.wav")은 test_audio.py 에서 API 로 확인한다.
# 여기서는 그 외 경계값과, 저장 경로가 범위를 벗어났을 때의 최종 방어선을 확인한다.

import pytest

from app.core import storage
from app.core.errors import APIError, ErrorCode


@pytest.mark.parametrize(
    "filename, expected",
    [
        ("consultation.wav", "consultation.wav"),
        ("C:evil.wav", "evil.wav"),
        ("C:\\Users\\x\\record.WAV", "record.wav"),
        ("..\\..\\windows\\system32\\a.mp3", "a.mp3"),
        ("###.wav", "audio.wav"),
        ("상담 녹음(1).m4a", "1.m4a"),
        ("．．／．．／x.wav", "x.wav"),
    ],
)
def test_filename_is_reduced_to_safe_name(filename: str, expected: str) -> None:
    assert storage.sanitize_filename(filename) == expected


@pytest.mark.parametrize("filename", [None, "", "   ", ".", "..", "../", "noextension"])
def test_unusable_filename_is_rejected(filename) -> None:
    with pytest.raises(APIError) as raised:
        storage.sanitize_filename(filename)

    assert raised.value.code == ErrorCode.AUDIO_INVALID_FILENAME
    assert raised.value.status_code == 400


def test_sanitized_name_length_is_limited() -> None:
    name = storage.sanitize_filename("a" * 500 + ".wav")

    assert name == "a" * 60 + ".wav"


@pytest.mark.parametrize("relative_path", ["../outside.wav", "../../etc/passwd", "a/../../b.wav"])
def test_stored_path_outside_storage_root_is_rejected(relative_path: str) -> None:
    """DB 에 저장된 경로가 조작돼도 저장소 밖 파일에 접근하지 못한다."""

    with pytest.raises(APIError) as raised:
        storage.resolve_stored_path(relative_path)

    assert raised.value.code == ErrorCode.AUDIO_INVALID_FILENAME


def test_delete_stored_audio_ignores_paths_outside_storage(tmp_path) -> None:
    outside = tmp_path / "keep.wav"
    outside.write_bytes(b"RIFF")

    storage.delete_stored_audio(str(outside))

    assert outside.exists()
