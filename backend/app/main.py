from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

from app import __version__
from app.config import settings
from app.database import Base, engine
from app.errors import (
    AppError,
    app_error_handler,
    http_exception_handler,
    validation_exception_handler,
)
from app.routers import cases


@asynccontextmanager
async def lifespan(_: FastAPI):
    # MVP: create_all is sufficient before Alembic migrations are introduced.
    Base.metadata.create_all(bind=engine)
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="I-SPOT API", version=__version__, lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)

    @app.get("/health", tags=["meta"])
    def health() -> dict:
        return {"data": {"status": "ok", "version": __version__}}

    app.include_router(cases.router, prefix=settings.api_v1_prefix)

    return app


app = create_app()
