# FastAPI Application.
#
# 모든 응답은 docs/02_ARCHITECTURE.md §5 의 Contract 를 따른다.
#   성공: {"data": {}}
#   실패: {"error": {"code": "ERROR_CODE", "message": "message"}}
#
# 예외 handler 를 한곳에 모아 어떤 경로로 실패해도 형식이 깨지지 않게 한다.

import re
from typing import Any, Dict, Optional, Tuple

import anyio
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.database import engine
from app.core.deps import bearer_scheme, verify_access_token
from app.core.errors import APIError, ErrorCode
from app.core.logging import configure_logging, get_logger
from app.core.responses import DataResponse
from app.schemas.common import HealthStatus

logger = get_logger(__name__)

# FastAPI · Starlette 가 직접 만드는 HTTP 오류(없는 경로, 허용되지 않은 method, 해석할 수 없는 multipart 본문 등)
# → 공통 오류 코드. 서비스 코드는 HTTPException 대신 APIError 를 쓰므로(core/errors.py) 여기로 오는 것은
# 프레임워크 오류뿐이다. JSON 문법 오류는 여기가 아니라 RequestValidationError(422)로 온다.
_STATUS_ERROR_CODES: Dict[int, ErrorCode] = {
    400: ErrorCode.VALIDATION_ERROR,
    401: ErrorCode.UNAUTHORIZED,
    403: ErrorCode.FORBIDDEN,
    404: ErrorCode.NOT_FOUND,
    405: ErrorCode.METHOD_NOT_ALLOWED,
    409: ErrorCode.DUPLICATE_RESOURCE,
    413: ErrorCode.AUDIO_TOO_LARGE,
    422: ErrorCode.VALIDATION_ERROR,
}

# 프레임워크 오류의 detail 은 영어 원문("Method Not Allowed", "Missing boundary in multipart." 등)이다.
# message 는 한국어로 그대로 보여 줄 수 있어야 하므로(API_CONTRACT 1.2) 상태 코드별 고정 문구를 쓴다.
_STATUS_MESSAGES: Dict[int, str] = {
    400: "요청 형식이 올바르지 않습니다.",
    401: "로그인이 필요합니다.",
    403: "권한이 없습니다.",
    404: "요청한 경로를 찾을 수 없습니다.",
    405: "허용되지 않는 요청 방식입니다.",
    413: "요청 크기가 너무 큽니다.",
}


def create_app() -> FastAPI:
    configure_logging()

    app = FastAPI(
        title=settings.APP_NAME,
        version="0.1.0",
        description=(
            "I-SPOT 아동 상담 지원 Backend API.\n\n"
            "모든 성공 응답은 `data`, 실패 응답은 `error` 로 감싸진다."
        ),
        docs_url="/docs",
        openapi_url="/openapi.json",
    )

    # 등록 순서가 중요하다. 나중에 등록한 미들웨어가 바깥에 놓이므로, 오류 처리를
    # 먼저 등록해야 CORS 가 그 바깥에서 500 응답에도 헤더를 붙인다.
    # 본문 크기 제한은 가장 안쪽이다. 거절 응답은 아래 handler 가 만들고 CORS 헤더도 붙는다.
    app.add_middleware(_BodySizeLimitMiddleware)
    app.add_middleware(_UnexpectedErrorMiddleware)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    _register_exception_handlers(app)

    app.include_router(api_router, prefix=settings.API_V1_PREFIX)

    @app.get("/health", response_model=DataResponse[HealthStatus], tags=["health"])
    def health() -> DataResponse[HealthStatus]:
        database = "ok"
        detail = None

        try:
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
        except Exception as error:
            database = "error"
            detail = {"database_error": type(error).__name__}

        return DataResponse(
            data=HealthStatus(
                status="ok" if database == "ok" else "degraded",
                app_name=settings.APP_NAME,
                env=settings.ENV,
                database=database,
                stt_provider=settings.STT_PROVIDER,
                ai_provider=settings.AI_PROVIDER,
                detail=detail,
            )
        )

    return app


def _internal_error_response() -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": ErrorCode.INTERNAL_ERROR.value,
                "message": "서버 내부 오류가 발생했습니다.",
            }
        },
    )


class _UnexpectedErrorMiddleware:
    """처리되지 않은 예외를 CORS 미들웨어 안쪽에서 500 오류 응답으로 바꾼다.

    @app.exception_handler(Exception) 은 가장 바깥의 ServerErrorMiddleware 에서 실행되어
    CORSMiddleware 를 거치지 않는다. 그러면 500 응답에 CORS 헤더가 빠져 브라우저가
    본문을 막고, Frontend 는 원인 없는 CORS 오류만 보게 된다.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        response_started = False

        async def send_wrapper(message: Message) -> None:
            nonlocal response_started

            if message["type"] == "http.response.start":
                response_started = True

            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        except Exception as exc:
            # 응답을 이미 보내기 시작했으면(BackgroundTasks 등) 바꿀 수 없으므로 그대로 올린다.
            if response_started:
                raise

            # 상담 원문이 섞일 수 있는 request body 는 로그에 남기지 않는다.
            logger.exception(
                "처리되지 않은 오류 method=%s path=%s type=%s",
                scope.get("method"),
                scope.get("path"),
                type(exc).__name__,
            )

            await _internal_error_response()(scope, receive, send)


class _RequestBodyTooLarge(StarletteHTTPException):
    """
    본문이 크기 제한을 넘었다(_BodySizeLimitMiddleware). 400 으로 준다.

    본문을 읽다가 난 HTTPException 은 FastAPI 가 400("본문을 해석할 수 없음")으로 바꾸지 않고 그대로 올린다.
    그래서 HTTPException 으로 만들고, 아래 handler 가 공통 오류 형식으로 바꾼다.

    상태 코드는 413 이 아니라 400 이다. 음성은 저장할 때 재는 크기 초과(`400 AUDIO_TOO_LARGE`)와 같게,
    나머지는 해석할 수 없는 multipart 본문(`400 VALIDATION_ERROR`)과 같게 해서 API_CONTRACT 에 없는 상태 코드를 만들지 않는다.
    """

    def __init__(self, code: ErrorCode, message: str) -> None:
        super().__init__(status_code=400, detail=message)
        self.code = code
        self.message = message


_MB = 1024 * 1024

# 음성 업로드(POST /sessions/{session_id}/audio 에 multipart 본문)만 큰 본문을 받는다.
_AUDIO_UPLOAD_PATH = re.compile(rf"^{re.escape(settings.API_V1_PREFIX)}/sessions/[^/]+/audio/?$")


def _media_type(scope: Scope) -> str:
    """Content-Type 의 주 형식(소문자). boundary 같은 매개변수는 뺀다. 없으면 빈 문자열."""

    for name, value in scope.get("headers", []):
        if name == b"content-type":
            return value.decode("latin-1").split(";", 1)[0].strip().lower()

    return ""


def _is_audio_upload(scope: Scope) -> bool:
    """
    음성 업로드 요청인가. 음성 경로라도 multipart 가 아니면 음성 파일이 올 수 없으므로 아니다.

    urlencoded 본문은 Starlette 가 칸마다 메모리에 쌓아 해석한다. 이런 본문에 음성 한도(기본 201MB)를 주면
    로그인하지 않은 요청 하나로 그만큼 메모리를 쓸 수 있다. 그래서 일반 본문 한도를 쓴다.
    """

    return (
        scope.get("method") == "POST"
        and _AUDIO_UPLOAD_PATH.match(scope.get("path", "")) is not None
        and _media_type(scope) == "multipart/form-data"
    )


async def _token_error(scope: Scope) -> Optional[APIError]:
    """
    Authorization 의 Bearer 토큰이 서명 · 만료 검사를 통과하지 못하면 그 401 오류를 돌려준다.

    get_current_user 와 같은 함수(deps.verify_access_token)로 보므로 문구도 같다. DB 는 보지 않는다.
    정지 · 강제 로그아웃 여부는 본문을 받은 뒤 get_current_user 가 다시 본다.
    """

    try:
        verify_access_token(await bearer_scheme(Request(scope)))
    except APIError as error:
        return error

    return None


def _body_limit(audio_upload: bool) -> Tuple[int, ErrorCode, str]:
    """이 요청이 받을 수 있는 본문 크기(바이트)와, 넘었을 때의 오류 코드 · 문구."""

    if audio_upload:
        # 파일 크기는 저장할 때 정확히 다시 잰다(core/storage.py). 여기서는 multipart 머리글 등
        # 파일 밖의 몫으로 1MB 를 더 준다.
        return (
            settings.audio_max_size_bytes + _MB,
            ErrorCode.AUDIO_TOO_LARGE,
            f"음성 파일이 최대 허용 크기({settings.AUDIO_MAX_SIZE_MB}MB)를 초과했습니다.",
        )

    return (
        settings.REQUEST_MAX_BODY_MB * _MB,
        ErrorCode.VALIDATION_ERROR,
        f"요청 본문이 너무 큽니다(최대 {settings.REQUEST_MAX_BODY_MB}MB).",
    )


def _declared_length(scope: Scope) -> Optional[int]:
    for name, value in scope.get("headers", []):
        if name == b"content-length":
            try:
                return int(value)
            except ValueError:
                return None

    return None


# 한도를 넘은 본문을 버리며 읽는 최대 시간(초). nginx 의 lingering_time(기본 30초)과 같은 생각이다.
_DISCARD_SECONDS = 30.0


async def _discard_rest_of_body(receive: Receive) -> None:
    """
    남은 본문을 저장하지 않고 끝까지 읽어 버린다. _DISCARD_SECONDS 가 지나면 그만 읽는다.

    본문을 다 받지 않고 응답하면 서버(uvicorn)는 받지 않은 데이터가 남은 연결을 닫게 되어 TCP RST 가 나간다.
    Backend 에 바로 붙은 클라이언트는 400 을 받지만, 개발 프록시(vite)처럼 본문을 아직 보내는 중간 단계는
    쓰다가 끊겨(ECONNRESET) 응답을 받지 못한다. 그러면 화면은 400 문구 대신 연결 끊김(502 · Failed to fetch)을
    본다. 읽은 조각은 바로 버리므로 메모리 · 디스크에는 쌓이지 않는다.
    """

    with anyio.move_on_after(_DISCARD_SECONDS):
        while True:
            message = await receive()

            if message["type"] != "http.request" or not message.get("more_body", False):
                return


class _BodySizeLimitMiddleware:
    """
    본문을 받는 창구(JSON · form · multipart)에서 요청 본문 크기를 로그인 확인보다 먼저 제한한다.

    FastAPI 는 본문(JSON · form · multipart)을 끝까지 읽어 해석한 뒤에 의존성(get_current_user 포함)을 실행한다.
    제한이 없으면 로그인하지 않은 요청도 본문을 다 받는다. JSON · urlencoded 본문과 multipart 의 파일이 아닌 칸은
    메모리에, multipart 의 파일 칸은 1MB 를 넘으면 디스크 임시 파일에 쌓인다. 본문을 읽는 receive 를 감싸서
    Content-Length 가 한도를 넘으면 처음 읽을 때, 없으면(chunked) 받은 만큼 세다가 넘는 순간 400 을 준다.
    400 을 주기 전에 남은 본문은 버리며 읽는다(_discard_rest_of_body).

    음성 업로드(_is_audio_upload: 음성 경로 + multipart)만 큰 한도(AUDIO_MAX_SIZE_MB + 1MB)를 쓴다. 그 한도는
    서명 · 만료가 맞는 토큰을 붙인 요청에만 준다. 토큰이 없거나 틀리면 본문을 해석하기 전에, 남은 본문을 버리며
    읽은 뒤 get_current_user 와 같은 401 로 답한다. 음성 경로라도 multipart 가 아니면 일반 한도를 쓴다.

    receive 를 감싸는 것이라 본문을 읽지 않는 창구(GET, 본문 없는 POST)에는 걸리지 않는다. 그런 창구는
    보낸 본문을 읽지 않고 평소대로(401 이나 정상 응답) 답한다. 운영에서 앞단 프록시를 두면 그쪽에도 같은 제한을 둔다.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        audio_upload = _is_audio_upload(scope)

        if audio_upload:
            error = await _token_error(scope)

            if error is not None:
                # 여기서 바로 답한다(바깥의 CORS 미들웨어가 헤더를 붙인다). 본문을 다 받지 않고 답하면
                # 개발 프록시를 거친 화면이 401 대신 연결 끊김을 보므로 남은 본문은 버리며 읽는다.
                await _discard_rest_of_body(receive)

                response = JSONResponse(status_code=error.status_code, content=error.to_payload())
                await response(scope, receive, send)
                return

        limit, code, message = _body_limit(audio_upload)
        declared = _declared_length(scope)
        received = 0

        async def receive_with_limit() -> Message:
            nonlocal received

            if declared is not None and declared > limit:
                await _discard_rest_of_body(receive)

                raise _RequestBodyTooLarge(code, message)

            incoming = await receive()

            if incoming["type"] == "http.request":
                received += len(incoming.get("body", b""))

                if received > limit:
                    if incoming.get("more_body", False):
                        await _discard_rest_of_body(receive)

                    raise _RequestBodyTooLarge(code, message)

            return incoming

        await self.app(scope, receive_with_limit, send)


def _register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(APIError)
    async def handle_api_error(_: Request, exc: APIError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content=exc.to_payload())

    @app.exception_handler(_RequestBodyTooLarge)
    async def handle_body_too_large(_: Request, exc: _RequestBodyTooLarge) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": exc.code.value, "message": exc.message}},
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        _: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": ErrorCode.VALIDATION_ERROR.value,
                    "message": "요청 값이 올바르지 않습니다.",
                    "details": {"fields": _summarize_validation_errors(exc)},
                }
            },
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_exception(
        _: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        # INTERNAL_ERROR 는 서버 오류(5xx)에만 쓴다. 표에 없는 4xx 는 요청 쪽 문제다.
        code = _STATUS_ERROR_CODES.get(
            exc.status_code,
            ErrorCode.VALIDATION_ERROR if exc.status_code < 500 else ErrorCode.INTERNAL_ERROR,
        )
        message = _STATUS_MESSAGES.get(
            exc.status_code,
            "요청을 처리할 수 없습니다." if exc.status_code < 500 else "서버 내부 오류가 발생했습니다.",
        )

        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": code.value, "message": message}},
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        # 상담 원문이 섞일 수 있는 request body 는 로그에 남기지 않는다.
        logger.exception(
            "처리되지 않은 오류 method=%s path=%s type=%s",
            request.method,
            request.url.path,
            type(exc).__name__,
        )

        return _internal_error_response()


def _summarize_validation_errors(exc: RequestValidationError) -> Any:
    """검증 실패 위치와 사유만 전달한다. 입력 값 자체는 포함하지 않는다."""

    summary = []

    for error in exc.errors()[:20]:
        location = ".".join(str(part) for part in error.get("loc", ()) if part != "body")

        summary.append(
            {
                "field": location or "body",
                "reason": error.get("msg", "invalid value"),
            }
        )

    return summary


app = create_app()
