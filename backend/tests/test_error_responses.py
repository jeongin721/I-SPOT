# 예상하지 못한 오류 응답 테스트.
#
# 브라우저는 CORS 헤더가 없는 응답을 막는다. 500 응답에 CORS 헤더가 빠지면 Frontend 는
# {"error": {...}} 본문을 읽지 못하고 원인 없는 네트워크(CORS) 오류만 보게 된다.

import asyncio
import json
import uuid
from typing import List, Optional, Tuple

import pytest
from fastapi.testclient import TestClient

from app import main as app_main
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


def test_malformed_json_body_is_422_with_fields(client: TestClient) -> None:
    """
    JSON 문법 오류는 400 이 아니라 422 VALIDATION_ERROR 이고 details.fields 로 온다(API_CONTRACT 1.2).

    FastAPI 가 JSON 해석 실패를 입력값 오류(RequestValidationError)로 바꾸기 때문이다. 이때 field 는
    필드 이름이 아니라 깨진 글자 위치다. 400(details 없음)은 multipart 처럼 형식 자체를 해석하지 못한 경우다.
    """

    response = client.post(
        "/api/v1/auth/login",
        content=b'{"email": "a@b.c", "password":',
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 422
    assert response.json() == {
        "error": {
            "code": "VALIDATION_ERROR",
            "message": "요청 값이 올바르지 않습니다.",
            "details": {"fields": [{"field": "30", "reason": "JSON decode error"}]},
        }
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


# =========================================================
# 본문 크기 제한 — 거절하기 전에 남은 본문을 읽어 버린다
# =========================================================
#
# 본문을 다 받지 않고 응답하면, 서버는 받지 않은 데이터가 남은 연결을 닫게 되어 TCP RST 가 나간다.
# Backend 에 바로 붙은 클라이언트는 400 을 받지만, 개발 프록시(vite)처럼 본문을 아직 보내고 있는
# 중간 단계는 쓰다가 끊겨 응답을 받지 못한다. 그러면 화면은 400 문구 대신 "서버에 연결할 수 없습니다" 를
# 본다. 그래서 거절하기 전에 남은 본문을 저장하지 않고 끝까지 읽는지 앱을 ASGI 로 직접 불러 본다.

def _call_raw(
    path: str,
    chunks: List[bytes],
    *,
    content_length: Optional[int] = None,
    endless: bool = False,
) -> Tuple[int, dict, int]:
    """응답 상태 · 본문과, 앱이 읽어 간 본문 조각 수를 돌려준다. endless 면 본문이 끝나지 않는다."""

    headers = [(b"content-type", b"application/json")]

    if content_length is not None:
        headers.append((b"content-length", str(content_length).encode()))

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": path,
        "raw_path": path.encode(),
        "root_path": "",
        "query_string": b"",
        "headers": headers,
        "client": ("127.0.0.1", 50000),
        "server": ("testserver", 80),
    }

    delivered = 0
    sent: List[dict] = []

    async def receive() -> dict:
        nonlocal delivered

        # 끝없는 본문도 시험이 멈추지 않게 조각 사이에 조금 쉬고, _ENDLESS_STOP 조각에서 끊는다.
        await asyncio.sleep(0.01 if endless else 0)

        total = _ENDLESS_STOP if endless else len(chunks)

        if delivered < total:
            chunk = chunks[delivered % len(chunks)]
            delivered += 1

            return {"type": "http.request", "body": chunk, "more_body": delivered < total}

        return {"type": "http.disconnect"}

    async def send(message: dict) -> None:
        sent.append(message)

    asyncio.run(app(scope, receive, send))

    status = next(message["status"] for message in sent if message["type"] == "http.response.start")
    body = b"".join(
        message.get("body", b"") for message in sent if message["type"] == "http.response.body"
    )

    return status, json.loads(body), delivered


_ENDLESS_STOP = 1000

TOO_LARGE_1MB = {"error": {"code": "VALIDATION_ERROR", "message": "요청 본문이 너무 큽니다(최대 1MB)."}}


def test_oversized_declared_body_is_read_to_the_end_before_rejecting(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Content-Length 가 한도를 넘어도 본문을 버리며 끝까지 읽은 뒤 400 을 준다."""

    monkeypatch.setattr(settings, "REQUEST_MAX_BODY_MB", 1)

    chunks = [b"a" * (MB // 2)] * 6

    status, body, delivered = _call_raw(
        "/api/v1/auth/login", chunks, content_length=sum(len(chunk) for chunk in chunks)
    )

    assert (status, body) == (400, TOO_LARGE_1MB)
    assert delivered == len(chunks)


def test_oversized_chunked_body_is_read_to_the_end_before_rejecting(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Content-Length 없이 받다가 한도를 넘은 경우도 남은 조각을 끝까지 읽은 뒤 400 을 준다."""

    monkeypatch.setattr(settings, "REQUEST_MAX_BODY_MB", 1)

    chunks = [b"a" * (MB // 2)] * 6

    status, body, delivered = _call_raw("/api/v1/auth/login", chunks)

    assert (status, body) == (400, TOO_LARGE_1MB)
    assert delivered == len(chunks)


def test_endless_oversized_body_is_read_only_for_a_limited_time(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """끝나지 않는 본문은 정해진 시간만 읽어 버리고 400 을 준다. 버리느라 연결을 끝없이 붙잡지 않는다."""

    monkeypatch.setattr(settings, "REQUEST_MAX_BODY_MB", 1)
    monkeypatch.setattr(app_main, "_DISCARD_SECONDS", 0.2)

    status, body, delivered = _call_raw(
        "/api/v1/auth/login", [b"a" * (MB // 2)], content_length=10 * MB, endless=True
    )

    assert (status, body) == (400, TOO_LARGE_1MB)
    assert 1 < delivered < _ENDLESS_STOP
