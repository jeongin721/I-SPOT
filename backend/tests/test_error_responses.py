# 예상하지 못한 오류 응답 테스트.
#
# 브라우저는 CORS 헤더가 없는 응답을 막는다. 500 응답에 CORS 헤더가 빠지면 Frontend 는
# {"error": {...}} 본문을 읽지 못하고 원인 없는 네트워크(CORS) 오류만 보게 된다.

import uuid

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app
from app.services import case_service


def test_unexpected_error_keeps_error_contract_and_cors_headers(
    counselor_headers, monkeypatch: pytest.MonkeyPatch
) -> None:
    origin = settings.CORS_ORIGINS[0]

    def broken_list_cases(*args, **kwargs):
        raise RuntimeError("예상하지 못한 오류")

    monkeypatch.setattr(case_service, "list_cases", broken_list_cases)

    # 기본 TestClient 는 서버 예외를 테스트로 다시 던지므로, 실제 응답을 보려면 끈다.
    with TestClient(app, raise_server_exceptions=False) as raw_client:
        response = raw_client.get(
            "/api/v1/cases",
            headers={**counselor_headers, "Origin": origin},
        )

    assert response.status_code == 500
    assert response.json() == {
        "error": {"code": "INTERNAL_ERROR", "message": "서버 내부 오류가 발생했습니다."}
    }
    assert response.headers.get("access-control-allow-origin") == origin


# =========================================================
# FastAPI · Starlette 가 직접 만드는 오류
# =========================================================
#
# 경로 · method · 본문 형식 오류는 라우터에 닿기 전에 프레임워크가 만든다. 이때도 message 는
# 한국어여야 하고(API_CONTRACT 1.2), INTERNAL_ERROR 는 5xx 에만 쓴다(12절).

def test_method_not_allowed_uses_korean_message(client: TestClient, counselor_headers) -> None:
    response = client.put("/api/v1/auth/me", headers=counselor_headers)

    assert response.status_code == 405
    assert response.json() == {
        "error": {"code": "METHOD_NOT_ALLOWED", "message": "허용되지 않는 요청 방식입니다."}
    }


def test_malformed_multipart_body_is_validation_error(
    client: TestClient, counselor_headers, session: dict
) -> None:
    """boundary 없는 multipart 는 Starlette 가 400 으로 막는다. 서버 오류(INTERNAL_ERROR)가 아니다."""

    response = client.post(
        f"/api/v1/sessions/{session['id']}/audio",
        content=b"abc",
        headers={**counselor_headers, "Content-Type": "multipart/form-data"},
    )

    assert response.status_code == 400
    assert response.json() == {
        "error": {"code": "VALIDATION_ERROR", "message": "요청 형식이 올바르지 않습니다."}
    }


# =========================================================
# 본문 크기 제한 — 로그인 확인보다 먼저
# =========================================================
#
# FastAPI 는 본문을 다 읽은 뒤에 의존성(로그인 확인 포함)을 실행한다. 크기 제한이 없으면
# 로그인하지 않은 요청도 본문을 끝까지 받아 메모리 · 디스크를 쓴다.

MB = 1024 * 1024


def test_oversized_json_body_is_rejected_before_login(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "REQUEST_MAX_BODY_MB", 1)

    response = client.post(
        "/api/v1/cases",
        content=b'{"title": "' + b"a" * MB + b'"}',
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 400
    assert response.json() == {
        "error": {"code": "VALIDATION_ERROR", "message": "요청 본문이 너무 큽니다(최대 1MB)."}
    }


def test_oversized_body_without_content_length_is_rejected(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Content-Length 없이(chunked) 보내도 받은 만큼 세어 막는다."""

    monkeypatch.setattr(settings, "REQUEST_MAX_BODY_MB", 1)

    def chunks():
        for _ in range(3):
            yield b"a" * (MB // 2)

    response = client.post(
        "/api/v1/auth/login",
        content=chunks(),
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_oversized_audio_upload_is_rejected_before_login(client: TestClient) -> None:
    """음성 업로드는 AUDIO_MAX_SIZE_MB 에 여유 1MB 를 더한 만큼까지 받는다. 넘으면 AUDIO_TOO_LARGE."""

    too_big = settings.audio_max_size_bytes + MB + 1

    response = client.post(
        f"/api/v1/sessions/{uuid.uuid4()}/audio",
        files={"file": ("big.wav", b"0" * too_big, "audio/wav")},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "AUDIO_TOO_LARGE"


def test_audio_upload_under_its_own_limit_still_reaches_login_check(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """음성 업로드는 일반 본문 한도가 아니라 음성 한도를 쓴다. 한도 안이면 평소처럼 로그인부터 본다."""

    monkeypatch.setattr(settings, "REQUEST_MAX_BODY_MB", 1)

    response = client.post(
        f"/api/v1/sessions/{uuid.uuid4()}/audio",
        files={"file": ("ok.wav", b"0" * (settings.audio_max_size_bytes + MB // 2), "audio/wav")},
    )

    assert response.status_code == 401


def test_small_body_still_reaches_login_check(client: TestClient) -> None:
    response = client.post("/api/v1/cases", json={"title": "작은 본문", "child_alias": "아동"})

    assert response.status_code == 401
