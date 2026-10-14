# 운영 환경 설정 안전장치 테스트.
#
# JWT 비밀키가 공개 저장소에 적힌 기본값·예시값이면 누구나 유효한 토큰을 만들 수 있다.
# ENV=production 에서는 그런 값으로 서버가 뜨지 않아야 한다.

import pytest
from pydantic import ValidationError

from app.core.config import Settings

# 저장소에 공개된 값들 — config.py 기본값, backend/.env.example, docker-compose.yml, README
PUBLIC_PLACEHOLDERS = [
    "change-me-in-env-file",
    "replace-this-with-a-long-random-value",
    "local-dev-only-change-me-0123456789abcdef",
    "local-dev-only-change-me-1234567890",
]

STRONG_SECRET = "k7Qp2vX9mL4rT8wZ1nB6yH3sD5fG0jCe"  # 32자, 테스트 전용


def _settings(**overrides) -> Settings:
    # 로컬 .env 파일의 영향을 받지 않도록 파일 로딩을 끈다.
    return Settings(_env_file=None, **overrides)


@pytest.mark.parametrize("secret", PUBLIC_PLACEHOLDERS)
def test_production_rejects_public_placeholder_secret(secret: str) -> None:
    with pytest.raises(ValidationError, match="JWT_SECRET_KEY"):
        _settings(ENV="production", JWT_SECRET_KEY=secret)


def test_production_rejects_short_secret() -> None:
    with pytest.raises(ValidationError, match="JWT_SECRET_KEY"):
        _settings(ENV="production", JWT_SECRET_KEY=STRONG_SECRET[:31])


def test_production_accepts_long_random_secret() -> None:
    settings = _settings(ENV="production", JWT_SECRET_KEY=STRONG_SECRET)

    assert settings.JWT_SECRET_KEY == STRONG_SECRET


@pytest.mark.parametrize("env", ["local", "test"])
def test_non_production_keeps_default_for_local_development(env: str) -> None:
    """로컬 개발은 .env 없이도 바로 실행되어야 하므로 기본값을 허용한다."""

    settings = _settings(ENV=env, JWT_SECRET_KEY="change-me-in-env-file")

    assert settings.ENV == env


# ---------------------------------------------------------
# AI_PROVIDER=pipeline 은 상담 원문을 비식별 없이 OpenAI 로 보낸다
# (specs ai-analysis-connect-research-1013.md 3-3 ①). 운영에서는 일부러 풀 때만 뜬다.
# ---------------------------------------------------------


def test_production_rejects_unmasked_pipeline() -> None:
    with pytest.raises(ValidationError) as caught:
        _settings(ENV="production", JWT_SECRET_KEY=STRONG_SECRET, AI_PROVIDER="pipeline")

    message = str(caught.value)

    # 막은 이유와 푸는 방법을 문구로 알려 준다.
    assert "AI_PROVIDER=pipeline" in message
    assert "비식별" in message
    assert "AI_PIPELINE_ALLOW_UNMASKED=true" in message


def test_production_allows_pipeline_only_when_explicitly_unmasked() -> None:
    settings = _settings(
        ENV="production",
        JWT_SECRET_KEY=STRONG_SECRET,
        AI_PROVIDER="pipeline",
        AI_PIPELINE_ALLOW_UNMASKED=True,
    )

    assert settings.AI_PROVIDER == "pipeline"


def test_unmasked_pipeline_flag_reads_true_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """서버 .env 에 적는 그대로(AI_PIPELINE_ALLOW_UNMASKED=true) 읽힌다."""

    monkeypatch.setenv("AI_PIPELINE_ALLOW_UNMASKED", "true")

    settings = _settings(ENV="production", JWT_SECRET_KEY=STRONG_SECRET, AI_PROVIDER="pipeline")

    assert settings.AI_PIPELINE_ALLOW_UNMASKED is True


def test_unmasked_pipeline_flag_is_off_by_default() -> None:
    assert _settings().AI_PIPELINE_ALLOW_UNMASKED is False


@pytest.mark.parametrize("provider", ["mock", "langgraph"])
def test_production_keeps_other_ai_providers(provider: str) -> None:
    settings = _settings(ENV="production", JWT_SECRET_KEY=STRONG_SECRET, AI_PROVIDER=provider)

    assert settings.AI_PROVIDER == provider


@pytest.mark.parametrize("env", ["local", "test"])
def test_non_production_keeps_pipeline_as_before(env: str) -> None:
    """개발 · 테스트 환경은 지금처럼 pipeline 을 그대로 쓸 수 있다(가상 데이터 전용)."""

    settings = _settings(ENV=env, AI_PROVIDER="pipeline")

    assert settings.AI_PROVIDER == "pipeline"
