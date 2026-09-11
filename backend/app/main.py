# FastAPI Application.
#
# 모든 응답은 docs/02_ARCHITECTURE.md §5 의 Contract 를 따른다.
#   성공: {"data": {}}
#   실패: {"error": {"code": "ERROR_CODE", "message": "message"}}
#
# 예외 handler 를 한곳에 모아 어떤 경로로 실패해도 형식이 깨지지 않게 한다.

from typing import Any, Dict

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.database import engine
from app.core.errors import APIError, ErrorCode
from app.core.logging import configure_logging, get_logger
from app.core.responses import DataResponse
from app.schemas.common import HealthStatus

logger = get_logger(__name__)

# HTTP status code → 공통 오류 코드
_STATUS_ERROR_CODES: Dict[int, ErrorCode] = {
    401: ErrorCode.UNAUTHORIZED,
    403: ErrorCode.FORBIDDEN,
    404: ErrorCode.NOT_FOUND,
    405: ErrorCode.METHOD_NOT_ALLOWED,
    409: ErrorCode.DUPLICATE_RESOURCE,
    413: ErrorCode.AUDIO_TOO_LARGE,
    422: ErrorCode.VALIDATION_ERROR,
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


def _register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(APIError)
    async def handle_api_error(_: Request, exc: APIError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content=exc.to_payload())

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
        code = _STATUS_ERROR_CODES.get(exc.status_code, ErrorCode.INTERNAL_ERROR)

        # 404 는 리소스 종류를 알 수 없는 라우팅 실패이므로 일반 메시지를 사용한다.
        if exc.status_code == 404:
            message = "요청한 경로를 찾을 수 없습니다."
        else:
            message = str(exc.detail) if exc.detail else "요청을 처리할 수 없습니다."

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

        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": ErrorCode.INTERNAL_ERROR.value,
                    "message": "서버 내부 오류가 발생했습니다.",
                }
            },
        )


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
