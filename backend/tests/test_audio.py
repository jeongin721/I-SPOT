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


# ---------------------------------------------------------------------------
# 다시 듣기: GET /sessions/{id}/audio/file (파일 본문 · Range)
# ---------------------------------------------------------------------------


def _get_audio_file(client: TestClient, headers: dict, session_id: str, **extra_headers):
    return client.get(
        f"/api/v1/sessions/{session_id}/audio/file",
        headers={**headers, **extra_headers},
    )


def test_get_audio_file_returns_whole_file_for_playback(
    client: TestClient, counselor_headers, session: dict
) -> None:
    content = make_wav_bytes(duration_ms=500)
    status_code, _ = upload_audio(
        client, counselor_headers, session["id"], filename="recording.wav", content=content
    )

    assert status_code == 201

    response = _get_audio_file(client, counselor_headers, session["id"])

    assert response.status_code == 200
    assert response.content == content
    assert response.headers["content-type"] == "audio/wav"
    assert response.headers["content-length"] == str(len(content))
    # 화면이 구간 위치로 건너뛸 수 있게 Range 를 받는다.
    assert response.headers["accept-ranges"] == "bytes"
    # 상담 음성은 브라우저 캐시에 남기지 않는다.
    assert response.headers["cache-control"] == "no-store"
    # 내려받기 창이 아니라 재생용이고, 원래 파일 이름을 알려 준다.
    assert response.headers["content-disposition"] == 'inline; filename="recording.wav"'


def test_get_audio_file_supports_range_requests(
    client: TestClient, counselor_headers, session: dict
) -> None:
    content = make_wav_bytes(duration_ms=500)
    upload_audio(client, counselor_headers, session["id"], content=content)
    size = len(content)

    head = _get_audio_file(client, counselor_headers, session["id"], Range="bytes=0-99")

    assert head.status_code == 206
    assert head.content == content[:100]
    assert head.headers["content-range"] == f"bytes 0-99/{size}"
    assert head.headers["content-length"] == "100"

    tail = _get_audio_file(client, counselor_headers, session["id"], Range="bytes=-50")

    assert tail.status_code == 206
    assert tail.content == content[-50:]
    assert tail.headers["content-range"] == f"bytes {size - 50}-{size - 1}/{size}"

    beyond = _get_audio_file(
        client, counselor_headers, session["id"], Range=f"bytes={size + 10}-"
    )

    assert beyond.status_code == 416
    assert beyond.headers["content-range"] == f"bytes */{size}"


def test_get_audio_file_before_upload_returns_not_found(
    client: TestClient, counselor_headers, session: dict
) -> None:
    response = _get_audio_file(client, counselor_headers, session["id"])

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "AUDIO_NOT_FOUND"


def test_get_audio_file_missing_on_disk_returns_not_found(
    client: TestClient, counselor_headers, session: dict
) -> None:
    _, body = upload_audio(client, counselor_headers, session["id"])
    (_storage_root() / body["data"]["audio"]["path"]).unlink()

    response = _get_audio_file(client, counselor_headers, session["id"])

    assert response.status_code == 404
    error = response.json()["error"]
    assert error["code"] == "AUDIO_NOT_FOUND"
    assert error["message"] == "음성 파일이 저장소에 없습니다. 다시 올려 주세요."


def test_get_audio_file_requires_login_and_case_access(
    client: TestClient, counselor_headers, other_counselor_headers, session: dict
) -> None:
    upload_audio(client, counselor_headers, session["id"])
    url = f"/api/v1/sessions/{session['id']}/audio/file"

    assert client.get(url).status_code == 401

    forbidden = client.get(url, headers=other_counselor_headers)

    assert forbidden.status_code == 403
    assert forbidden.json()["error"]["code"] == "FORBIDDEN"


def test_get_audio_file_returns_latest_upload(
    client: TestClient, counselor_headers, session: dict
) -> None:
    first = make_wav_bytes(duration_ms=200)
    second = make_wav_bytes(duration_ms=300)
    upload_audio(client, counselor_headers, session["id"], filename="first.wav", content=first)
    upload_audio(client, counselor_headers, session["id"], filename="second.wav", content=second)

    response = _get_audio_file(client, counselor_headers, session["id"])

    assert response.status_code == 200
    assert response.content == second
    assert response.headers["content-disposition"] == 'inline; filename="second.wav"'
