# Audio Upload 검증 테스트.
# 확장자 / MIME / 크기 / 빈 파일 / 손상 파일 / Path Traversal 을 모두 확인한다.

import os
from pathlib import Path

from fastapi.testclient import TestClient

from tests.conftest import make_wav_bytes, upload_audio


def _storage_root() -> Path:
    return Path(os.environ["AUDIO_STORAGE_ROOT"])


def test_upload_valid_wav_saves_metadata_and_file(
    client: TestClient, counselor_headers, case: dict, session: dict
) -> None:
    status_code, body = upload_audio(client, counselor_headers, session["id"])

    assert status_code == 201, body

    data = body["data"]

    assert data["session_status"] == "AUDIO_UPLOADED"

    audio = data["audio"]

    assert audio["mime_type"] == "audio/wav"
    assert audio["size_bytes"] > 0
    assert audio["checksum_sha256"]
    # WAV 는 서버가 header 로 길이를 계산한다.
    assert audio["duration_ms"] == 1000

    # 저장 경로 규칙: storage/audio/{case_id}/{session_id}/
    assert audio["path"].startswith(f"{case['id']}/{session['id']}/")

    stored = _storage_root() / audio["path"]

    assert stored.is_file()
    assert stored.stat().st_size == audio["size_bytes"]


def test_upload_rejects_empty_file(
    client: TestClient, counselor_headers, session: dict
) -> None:
    status_code, body = upload_audio(
        client, counselor_headers, session["id"], content=b""
    )

    assert status_code == 400
    assert body["error"]["code"] == "AUDIO_EMPTY_FILE"


def test_upload_rejects_unsupported_extension(
    client: TestClient, counselor_headers, session: dict
) -> None:
    status_code, body = upload_audio(
        client,
        counselor_headers,
        session["id"],
        filename="notes.txt",
        content=b"just text",
        content_type="audio/wav",
    )

    assert status_code == 400
    assert body["error"]["code"] == "AUDIO_UNSUPPORTED_TYPE"


def test_upload_rejects_unsupported_mime_type(
    client: TestClient, counselor_headers, session: dict
) -> None:
    status_code, body = upload_audio(
        client,
        counselor_headers,
        session["id"],
        filename="consultation.wav",
        content=make_wav_bytes(),
        content_type="text/plain",
    )

    assert status_code == 400
    assert body["error"]["code"] == "AUDIO_UNSUPPORTED_TYPE"


def test_upload_rejects_corrupted_content(
    client: TestClient, counselor_headers, session: dict
) -> None:
    """확장자는 wav 지만 내용이 음성이 아닌 경우."""

    status_code, body = upload_audio(
        client,
        counselor_headers,
        session["id"],
        filename="broken.wav",
        content=b"NOT-AN-AUDIO-FILE" * 20,
        content_type="audio/wav",
    )

    assert status_code == 400
    assert body["error"]["code"] == "AUDIO_CORRUPTED"


def test_upload_rejects_extension_content_mismatch(
    client: TestClient, counselor_headers, session: dict
) -> None:
    """내용은 WAV 인데 확장자는 ogg 인 경우."""

    status_code, body = upload_audio(
        client,
        counselor_headers,
        session["id"],
        filename="mismatch.ogg",
        content=make_wav_bytes(),
        content_type="audio/ogg",
    )

    assert status_code == 400
    assert body["error"]["code"] == "AUDIO_UNSUPPORTED_TYPE"


def test_upload_rejects_file_over_size_limit(
    client: TestClient, counselor_headers, session: dict
) -> None:
    """테스트 환경 제한은 1MB 이다."""

    oversized = make_wav_bytes(duration_ms=200_000, sample_rate=16000)

    assert len(oversized) > 1024 * 1024

    status_code, body = upload_audio(
        client, counselor_headers, session["id"], content=oversized
    )

    assert status_code == 400
    assert body["error"]["code"] == "AUDIO_TOO_LARGE"


def test_oversized_upload_does_not_leave_partial_file(
    client: TestClient, counselor_headers, case: dict, session: dict
) -> None:
    oversized = make_wav_bytes(duration_ms=200_000, sample_rate=16000)

    upload_audio(client, counselor_headers, session["id"], content=oversized)

    session_dir = _storage_root() / case["id"] / session["id"]

    remaining = list(session_dir.glob("*")) if session_dir.exists() else []

    assert remaining == []


def test_upload_sanitizes_path_traversal_filename(
    client: TestClient, counselor_headers, case: dict, session: dict
) -> None:
    status_code, body = upload_audio(
        client,
        counselor_headers,
        session["id"],
        filename="../../../../etc/passwd.wav",
    )

    assert status_code == 201, body

    audio = body["data"]["audio"]

    # 저장 경로가 Session 디렉터리 밖으로 나가지 않아야 한다.
    assert ".." not in audio["path"]
    assert audio["path"].startswith(f"{case['id']}/{session['id']}/")
    assert "passwd" in audio["original_filename"]

    resolved = (_storage_root() / audio["path"]).resolve()

    assert resolved.is_relative_to(_storage_root().resolve())


def test_upload_rejects_filename_without_extension(
    client: TestClient, counselor_headers, session: dict
) -> None:
    status_code, body = upload_audio(
        client, counselor_headers, session["id"], filename="recording"
    )

    assert status_code == 400
    assert body["error"]["code"] in {
        "AUDIO_INVALID_FILENAME",
        "AUDIO_UNSUPPORTED_TYPE",
    }


def test_get_audio_before_upload_returns_not_found(
    client: TestClient, counselor_headers, session: dict
) -> None:
    response = client.get(
        f"/api/v1/sessions/{session['id']}/audio", headers=counselor_headers
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "AUDIO_NOT_FOUND"


def test_reupload_returns_latest_audio(
    client: TestClient, counselor_headers, session: dict
) -> None:
    upload_audio(client, counselor_headers, session["id"], filename="first.wav")
    status_code, body = upload_audio(
        client, counselor_headers, session["id"], filename="second.wav"
    )

    assert status_code == 201

    response = client.get(
        f"/api/v1/sessions/{session['id']}/audio", headers=counselor_headers
    )

    assert response.status_code == 200
    assert response.json()["data"]["original_filename"] == "second.wav"


def test_upload_accepts_webm_from_media_recorder(
    client: TestClient, counselor_headers, session: dict
) -> None:
    """브라우저 MediaRecorder 기본 출력(webm)을 허용한다."""

    webm = b"\x1a\x45\xdf\xa3" + b"\x42\x82\x84webm" + b"\x00" * 64

    status_code, body = upload_audio(
        client,
        counselor_headers,
        session["id"],
        filename="recording.webm",
        content=webm,
        content_type="audio/webm",
    )

    assert status_code == 201, body
    assert body["data"]["audio"]["mime_type"] == "audio/webm"


def test_upload_uses_client_duration_when_server_cannot_compute(
    client: TestClient, counselor_headers, session: dict
) -> None:
    webm = b"\x1a\x45\xdf\xa3" + b"\x42\x82\x84webm" + b"\x00" * 64

    response = client.post(
        f"/api/v1/sessions/{session['id']}/audio",
        files={"file": ("recording.webm", webm, "audio/webm")},
        data={"duration_ms": "45000"},
        headers=counselor_headers,
    )

    assert response.status_code == 201
    assert response.json()["data"]["audio"]["duration_ms"] == 45000


def test_upload_to_missing_session_returns_not_found(
    client: TestClient, counselor_headers
) -> None:
    import uuid

    status_code, body = upload_audio(client, counselor_headers, str(uuid.uuid4()))

    assert status_code == 404
    assert body["error"]["code"] == "SESSION_NOT_FOUND"
