# 환경설정. Secret/API Key 는 코드에 하드코딩하지 않고 .env 로만 주입한다.

from functools import lru_cache
from pathlib import Path
from typing import Annotated, List, Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]
REPO_ROOT = BACKEND_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(REPO_ROOT / ".env", BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ---------------------------------------------------------
    # App
    # ---------------------------------------------------------
    APP_NAME: str = "I-SPOT Backend"
    API_V1_PREFIX: str = "/api/v1"
    ENV: Literal["local", "test", "production"] = "local"
    DEBUG: bool = False

    # ---------------------------------------------------------
    # Database
    # ---------------------------------------------------------
    # 운영/개발 기본값은 PostgreSQL. 테스트는 conftest 에서 SQLite 로 override 한다.
    DATABASE_URL: str = (
        "postgresql+psycopg://ispot:ispot@localhost:5432/ispot"
    )
    DB_ECHO: bool = False

    # ---------------------------------------------------------
    # Auth
    # ---------------------------------------------------------
    # 운영에서는 반드시 .env 로 주입한다. 기본값은 local 개발 전용이다.
    JWT_SECRET_KEY: str = "change-me-in-env-file"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 720

    # ---------------------------------------------------------
    # CORS
    # ---------------------------------------------------------
    # NoDecode: pydantic-settings 가 env 값을 JSON 으로 먼저 decode 하지 않게 해서
    # 아래 _split_comma_separated validator 가 콤마 구분 문자열을 처리할 수 있게 한다.
    CORS_ORIGINS: Annotated[List[str], NoDecode] = Field(
        default_factory=lambda: [
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ]
    )

    # ---------------------------------------------------------
    # Audio Storage
    # ---------------------------------------------------------
    # 9월 MVP 는 Local Storage 를 사용한다. (docs/02_ARCHITECTURE.md)
    AUDIO_STORAGE_ROOT: Path = REPO_ROOT / "storage" / "audio"
    AUDIO_MAX_SIZE_MB: int = 200
    AUDIO_ALLOWED_EXTENSIONS: Annotated[List[str], NoDecode] = Field(
        default_factory=lambda: [
            ".wav",
            ".mp3",
            ".m4a",
            ".mp4",
            ".ogg",
            ".flac",
            ".webm",
        ]
    )

    # ---------------------------------------------------------
    # STT / AI Service
    # ---------------------------------------------------------
    # mock  : 팀 A/B 산출물 없이도 Backend 단독 실행/테스트 가능
    # module: 실제 STT 함수를 import 해서 호출
    STT_PROVIDER: Literal["mock", "module"] = "mock"
    STT_MODULE: str = "stt.transcribe_service"
    STT_FUNCTION: str = "transcribe"
    STT_TIMEOUT_SECONDS: float = 600.0

    # mock    : 고정된 합성 요약 반환
    # pipeline: ai/services/analysis_pipeline.run_analysis_pipeline 호출
    AI_PROVIDER: Literal["mock", "pipeline"] = "mock"
    AI_TIMEOUT_SECONDS: float = 180.0

    # ---------------------------------------------------------
    # Logging
    # ---------------------------------------------------------
    LOG_LEVEL: str = "INFO"

    @field_validator("CORS_ORIGINS", "AUDIO_ALLOWED_EXTENSIONS", mode="before")
    @classmethod
    def _split_comma_separated(cls, value: object) -> object:
        """.env 에서 콤마 구분 문자열로도 설정할 수 있게 한다."""

        if isinstance(value, str) and not value.strip().startswith("["):
            return [item.strip() for item in value.split(",") if item.strip()]

        return value

    @property
    def audio_max_size_bytes(self) -> int:
        return self.AUDIO_MAX_SIZE_MB * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
