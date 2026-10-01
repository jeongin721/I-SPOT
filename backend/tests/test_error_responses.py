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
from starlette.requests import Request

from app import main as app_main
from app.api.v1 import cases as cases_api
from app.core.config import settings
from app.core.security import create_access_token
from app.main import app
from app.services import case_service
from tests.conftest import make_wav_bytes, upload_audio


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

    # 본문 해석은 로그인 확인보다 먼저라, Token 없이 보내도 401 이 아니라 422 다.
    no_token = client.post(
        "/api/v1/cases", content=b'{"title":', headers={"Content-Type": "application/json"}
    )

    assert no_token.status_code == 422
    assert no_token.json()["error"]["details"] == {
        "fields": [{"field": "9", "reason": "JSON decode error"}]
    }


def test_json_body_that_is_not_utf8_is_400_before_login(client: TestClient) -> None:
    """
    Content-Type 이 JSON 인데 UTF-8 로 읽을 수 없는 바이트(예: CP949 로 인코딩한 한글)가 든 본문은
    문법 오류(422)가 아니라 400 VALIDATION_ERROR(details 없음)다(API_CONTRACT 1.2).

    FastAPI 는 본문 해석 오류 가운데 JSON 문법 오류만 입력값 오류(422)로 바꾸고, 그 밖의 오류는 400 으로
    바꾼다. 본문 해석은 의존성(로그인 확인)보다 먼저라 Token 이 없어도 401 이 아니라 400 이다.
    """

    malformed = {
        "error": {"code": "VALIDATION_ERROR", "message": "요청 형식이 올바르지 않습니다."}
    }
    json_header = {"Content-Type": "application/json"}

    login = client.post(
        "/api/v1/auth/login",
        content='{"email": "a@b.c", "password": "비밀번호"}'.encode("cp949"),
        headers=json_header,
    )

    assert login.status_code == 400
    assert login.json() == malformed

    title = '{"title": "사례"}'
    no_token = client.post("/api/v1/cases", content=title.encode("cp949"), headers=json_header)

    assert no_token.status_code == 400
    assert no_token.json() == malformed

    # 같은 본문을 UTF-8 로 보내면 본문을 읽은 뒤 로그인 확인에서 401 이다.
    assert client.post(
        "/api/v1/cases", content=title.encode("utf-8"), headers=json_header
    ).status_code == 401


# =========================================================
# 목록 page 상한
# =========================================================

def test_too_large_page_is_422_not_server_error(
    counselor_headers, admin_headers, case: dict
) -> None:
    """
    목록 창구의 page 는 MAX_PAGE 까지다. 상한이 없으면 건너뛸 행 수((page - 1) × page_size)가
    DB 정수 범위를 넘어 500 INTERNAL_ERROR(OverflowError)가 났다. 넘는 값은 입력값 오류(422)다.
    """

    max_page = cases_api.MAX_PAGE
    lists = [
        ("/api/v1/cases", counselor_headers),
        ("/api/v1/tasks", counselor_headers),
        (f"/api/v1/cases/{case['id']}/sessions", counselor_headers),
        ("/api/v1/auth/audit-logs", admin_headers),
    ]

    # 서버 오류를 테스트로 다시 던지지 않고 실제 응답을 본다.
    with TestClient(app, raise_server_exceptions=False) as raw_client:
        for path, headers in lists:
            # 상한 값까지는 받는다(끝을 넘은 page 라 빈 목록).
            last = raw_client.get(
                path, params={"page": max_page, "page_size": 100}, headers=headers
            )

            assert last.status_code == 200, path
            assert last.json()["data"]["items"] == [], path

            for page in (max_page + 1, 2**62, 10**30):
                response = raw_client.get(path, params={"page": page}, headers=headers)

                assert response.status_code == 422, (path, page, response.text)
                assert response.json()["error"]["code"] == "VALIDATION_ERROR"
                assert response.json()["error"]["details"]["fields"][0]["field"] == "query.page"


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


def test_oversized_audio_upload_is_rejected_before_reaching_the_route(
    client: TestClient, counselor_headers
) -> None:
    """
    음성 업로드는 AUDIO_MAX_SIZE_MB 에 여유 1MB 를 더한 만큼까지 받는다. 넘으면 AUDIO_TOO_LARGE.

    없는 회기라 라우터까지 갔다면 404 다. 400 이면 본문 크기 제한이 먼저 막은 것이다.
    """

    too_big = settings.audio_max_size_bytes + MB + 1

    response = client.post(
        f"/api/v1/sessions/{uuid.uuid4()}/audio",
        files={"file": ("big.wav", b"0" * too_big, "audio/wav")},
        headers=counselor_headers,
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "AUDIO_TOO_LARGE"


# 음성 업로드의 큰 한도는 서명 · 만료가 맞는 토큰을 붙인 multipart 요청만 받는다.
# FastAPI 는 multipart 본문을 다 해석한 뒤에 로그인을 확인한다. 파일이 아닌 칸은 메모리에 쌓이므로,
# 토큰이 없거나 틀린 요청은 본문을 해석하기 전에 401 로 끝낸다.


def _spy_form_parsing(monkeypatch: pytest.MonkeyPatch) -> List[str]:
    """FastAPI 가 본문을 form 으로 해석하면 그 경로를 기록한다."""

    parsed: List[str] = []
    original = Request.form

    def spy(self, *args, **kwargs):
        parsed.append(self.url.path)

        return original(self, *args, **kwargs)

    monkeypatch.setattr(Request, "form", spy)

    return parsed


@pytest.mark.parametrize(
    ("authorization", "message"),
    [
        (None, "Authorization 헤더가 없습니다."),
        ("Basic YWJjOmRlZg==", "Authorization 헤더가 없습니다."),
        ("Bearer not.a.jwt", "유효하지 않은 토큰입니다."),
        ("expired", "토큰이 만료되었습니다. 다시 로그인해 주세요."),
    ],
)
def test_audio_upload_without_valid_token_is_401_before_parsing_body(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    authorization: Optional[str],
    message: str,
) -> None:
    """음성 한도 안의 본문이라도 토큰이 없거나 틀리면 본문을 해석하지 않고 로그인 확인과 같은 401 을 준다."""

    monkeypatch.setattr(settings, "AUDIO_MAX_SIZE_MB", 5)
    parsed = _spy_form_parsing(monkeypatch)

    if authorization == "expired":
        token = create_access_token(str(uuid.uuid4()), "COUNSELOR", expires_minutes=-1)
        authorization = f"Bearer {token}"

    origin = settings.CORS_ORIGINS[0]
    headers = {"Origin": origin}

    if authorization:
        headers["Authorization"] = authorization

    # 파일이 아닌 칸(칸마다 1MB 안쪽) 3개 — 해석하면 그대로 메모리에 올라간다.
    response = client.post(
        f"/api/v1/sessions/{uuid.uuid4()}/audio",
        data={f"note{index}": "a" * (MB - 1024) for index in range(3)},
        files={"file": ("ok.wav", b"0", "audio/wav")},
        headers=headers,
    )

    assert response.status_code == 401
    assert response.json() == {"error": {"code": "UNAUTHORIZED", "message": message}}
    assert response.headers.get("access-control-allow-origin") == origin  # 화면이 본문을 읽을 수 있다
    assert parsed == []


def test_urlencoded_body_to_audio_upload_uses_general_limit(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """음성 경로라도 urlencoded 본문은 음성이 아니다. 일반 본문 한도와 문구를 쓴다."""

    monkeypatch.setattr(settings, "AUDIO_MAX_SIZE_MB", 5)

    # 칸마다 1MB 안쪽인 칸 3개(약 3MB). 음성 한도로 받으면 다 해석해 메모리에 올린 뒤에야 401 이 난다.
    form = b"&".join(b"note%d=" % index + b"a" * (MB - 1024) for index in range(3))

    response = client.post(
        f"/api/v1/sessions/{uuid.uuid4()}/audio",
        content=form,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )

    assert response.status_code == 400
    assert response.json() == {
        "error": {"code": "VALIDATION_ERROR", "message": "요청 본문이 너무 큽니다(최대 2MB)."}
    }


@pytest.mark.parametrize(
    "content_type", ["application/json", "text/plain", "application/octet-stream", None]
)
def test_non_form_body_to_audio_upload_is_answered_without_size_limit(
    client: TestClient, counselor_headers, session: dict, content_type: Optional[str]
) -> None:
    """
    음성 경로에 form(multipart · urlencoded)이 아닌 본문을 보내면 이 창구는 본문을 읽지 않는다.

    그래서 본문이 일반 한도(2MB)를 넘어도 400 "요청 본문이 너무 큽니다" 가 아니다.
    토큰이 없으면 401, 있으면 file 칸이 없다는 422 다(계약서 1.2 · 6절).
    """

    body = b"a" * (3 * MB)
    headers = {"Content-Type": content_type} if content_type else {}
    path = f"/api/v1/sessions/{session['id']}/audio"

    anonymous = client.post(path, content=body, headers=headers)

    assert anonymous.status_code == 401
    assert anonymous.json() == {
        "error": {"code": "UNAUTHORIZED", "message": "Authorization 헤더가 없습니다."}
    }

    logged_in = client.post(path, content=body, headers={**headers, **counselor_headers})

    assert logged_in.status_code == 422
    error = logged_in.json()["error"]
    assert error["code"] == "VALIDATION_ERROR"
    assert [field["field"] for field in error["details"]["fields"]] == ["file"]


@pytest.mark.parametrize("multipart", [True, False], ids=["multipart", "urlencoded"])
def test_form_field_over_1mb_to_audio_upload_is_malformed_form(
    client: TestClient, counselor_headers, multipart: bool
) -> None:
    """
    form 의 파일이 아닌 칸 하나가 1MB(Starlette 기본값)를 넘으면, 본문 전체가 한도 안이라도
    해석 단계에서 400 "요청 형식이 올바르지 않습니다." 다(계약서 1.2).
    """

    value = b"a" * (MB + 1024)

    if multipart:
        content_type = "multipart/form-data; boundary=x"
        form = b'--x\r\nContent-Disposition: form-data; name="note"\r\n\r\n' + value + b"\r\n--x--\r\n"
    else:
        content_type = "application/x-www-form-urlencoded"
        form = b"note=" + value

    assert len(form) < 2 * MB  # 일반 본문 한도(2MB) 안

    response = client.post(
        f"/api/v1/sessions/{uuid.uuid4()}/audio",
        content=form,
        headers={**counselor_headers, "Content-Type": content_type},
    )

    assert response.status_code == 400
    assert response.json() == {
        "error": {"code": "VALIDATION_ERROR", "message": "요청 형식이 올바르지 않습니다."}
    }


def test_logged_in_audio_upload_over_general_limit_is_created(
    client: TestClient,
    counselor_headers,
    session: dict,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """로그인한 음성 업로드는 일반 본문 한도가 아니라 음성 한도를 쓴다."""

    monkeypatch.setattr(settings, "REQUEST_MAX_BODY_MB", 1)
    monkeypatch.setattr(settings, "AUDIO_MAX_SIZE_MB", 3)

    wav = make_wav_bytes(duration_ms=100_000)  # 약 1.5MB

    assert MB < len(wav) < 2 * MB

    status_code, body = upload_audio(client, counselor_headers, session["id"], content=wav)

    assert status_code == 201, body


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
    content_type: bytes = b"application/json",
) -> Tuple[int, dict, int]:
    """응답 상태 · 본문과, 앱이 읽어 간 본문 조각 수를 돌려준다. endless 면 본문이 끝나지 않는다."""

    headers = [(b"content-type", content_type)]

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


def test_audio_upload_without_token_is_read_to_the_end_before_401() -> None:
    """토큰 없는 음성 업로드도 본문을 버리며 끝까지 읽은 뒤 401 을 준다. 음성 한도를 넘어도 401 이다."""

    chunks = [b"a" * (MB // 2)] * 6  # 3MB — 테스트의 음성 한도(1MB + 여유 1MB)보다 크다

    status, body, delivered = _call_raw(
        f"/api/v1/sessions/{uuid.uuid4()}/audio",
        chunks,
        content_length=sum(len(chunk) for chunk in chunks),
        content_type=b"multipart/form-data; boundary=x",
    )

    assert (status, body) == (
        401,
        {"error": {"code": "UNAUTHORIZED", "message": "Authorization 헤더가 없습니다."}},
    )
    assert delivered == len(chunks)


def test_non_form_body_to_audio_upload_is_not_read() -> None:
    """음성 경로에 form 이 아닌 본문(JSON)을 보내면 한 조각도 읽지 않고 답한다. 그래서 크기 한도에 닿지 않는다."""

    chunks = [b"a" * (MB // 2)] * 6  # 3MB — 일반 본문 한도(2MB)보다 크다

    status, body, delivered = _call_raw(
        f"/api/v1/sessions/{uuid.uuid4()}/audio",
        chunks,
        content_length=sum(len(chunk) for chunk in chunks),
        content_type=b"application/json",
    )

    assert (status, body) == (
        401,
        {"error": {"code": "UNAUTHORIZED", "message": "Authorization 헤더가 없습니다."}},
    )
    assert delivered == 0


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
