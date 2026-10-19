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


def test_settings_error_does_not_print_input_values() -> None:
    """설정 검사 오류 문구에 입력값(API 키 등)이 찍히지 않는다. 서버 시작 실패는 로그에 그대로 남는다."""

    fake_key = "sk-SYNTHETIC-NOT-A-REAL-KEY-0123456789"

    with pytest.raises(ValidationError) as caught:
        _settings(
            ENV="production",
            JWT_SECRET_KEY=STRONG_SECRET,
            AI_PROVIDER="pipeline",
            OPENAI_API_KEY=fake_key,
        )

    message = str(caught.value)

    assert "AI_PIPELINE_ALLOW_UNMASKED=true" in message
    assert "0123456789" not in message
    assert STRONG_SECRET[-8:] not in message


# ---------------------------------------------------------
# AI_PROVIDER=modeling 은 가린 글을 OpenAI 로 보내지만 가리기가 아직 불완전하다
# (specs ai-analysis-connect-research-1013.md 3-3 ④ ⑥). 운영에서는 일부러 풀 때만 뜬다.
# ---------------------------------------------------------


def test_production_rejects_modeling_until_privacy_issues_are_fixed() -> None:
    with pytest.raises(ValidationError) as caught:
        _settings(ENV="production", JWT_SECRET_KEY=STRONG_SECRET, AI_PROVIDER="modeling")

    message = str(caught.value)

    # 막은 이유(개인정보 문제 해결 전)와 푸는 방법을 문구로 알려 준다.
    assert "AI_PROVIDER=modeling" in message
    assert "비식별" in message
    assert "개인정보 문제가 해결되기 전" in message
    assert "AI_MODELING_ALLOW_IN_PRODUCTION=true" in message


def test_production_allows_modeling_only_when_explicitly_allowed() -> None:
    settings = _settings(
        ENV="production",
        JWT_SECRET_KEY=STRONG_SECRET,
        AI_PROVIDER="modeling",
        AI_MODELING_ALLOW_IN_PRODUCTION=True,
    )

    assert settings.AI_PROVIDER == "modeling"


def test_modeling_flag_reads_true_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """서버 .env 에 적는 그대로(AI_MODELING_ALLOW_IN_PRODUCTION=true) 읽힌다."""

    monkeypatch.setenv("AI_MODELING_ALLOW_IN_PRODUCTION", "true")

    settings = _settings(ENV="production", JWT_SECRET_KEY=STRONG_SECRET, AI_PROVIDER="modeling")

    assert settings.AI_MODELING_ALLOW_IN_PRODUCTION is True


def test_modeling_flag_is_off_by_default() -> None:
    assert _settings().AI_MODELING_ALLOW_IN_PRODUCTION is False


def test_pipeline_flag_does_not_unlock_modeling() -> None:
    """두 허용 값은 서로를 풀지 않는다. pipeline 을 풀어 둔 서버에서 modeling 으로 바꿔도 막힌다."""

    with pytest.raises(ValidationError, match="AI_MODELING_ALLOW_IN_PRODUCTION=true"):
        _settings(
            ENV="production",
            JWT_SECRET_KEY=STRONG_SECRET,
            AI_PROVIDER="modeling",
            AI_PIPELINE_ALLOW_UNMASKED=True,
        )


def test_modeling_flag_does_not_unlock_pipeline() -> None:
    with pytest.raises(ValidationError, match="AI_PIPELINE_ALLOW_UNMASKED=true"):
        _settings(
            ENV="production",
            JWT_SECRET_KEY=STRONG_SECRET,
            AI_PROVIDER="pipeline",
            AI_MODELING_ALLOW_IN_PRODUCTION=True,
        )


@pytest.mark.parametrize("env", ["local", "test"])
def test_non_production_keeps_modeling(env: str) -> None:
    """개발 · 테스트 환경은 modeling 을 그대로 쓸 수 있다(가상 데이터 전용)."""

    settings = _settings(ENV=env, AI_PROVIDER="modeling")

    assert settings.AI_PROVIDER == "modeling"


def test_modeling_error_does_not_print_input_values() -> None:
    fake_key = "sk-SYNTHETIC-NOT-A-REAL-KEY-0123456789"

    with pytest.raises(ValidationError) as caught:
        _settings(
            ENV="production",
            JWT_SECRET_KEY=STRONG_SECRET,
            AI_PROVIDER="modeling",
            OPENAI_API_KEY=fake_key,
        )

    message = str(caught.value)

    assert "AI_MODELING_ALLOW_IN_PRODUCTION=true" in message
    assert "0123456789" not in message
    assert STRONG_SECRET[-8:] not in message


# ---------------------------------------------------------
# AI_DEADLINE_MARGIN_SECONDS 는 modeling 에 넘기는 마감 시각의 여유다
# (마감 시각 = 분석 시작 + AI_TIMEOUT_SECONDS - 여유). 제한 시간보다 짧아야 한다.
# ---------------------------------------------------------


@pytest.mark.parametrize("margin", [180.0, 200.0])
def test_modeling_rejects_deadline_margin_not_shorter_than_time_limit(margin: float) -> None:
    """여유가 제한 시간과 같거나 길면 마감 시각이 분석 시작 전이 되어 모든 분석이 바로 AI_TIMEOUT 으로 끝난다."""

    with pytest.raises(ValidationError) as caught:
        _settings(AI_PROVIDER="modeling", AI_TIMEOUT_SECONDS=180.0, AI_DEADLINE_MARGIN_SECONDS=margin)

    message = str(caught.value)

    # 막은 이유와 지금 값을 문구로 알려 준다.
    assert "AI_DEADLINE_MARGIN_SECONDS 는 AI_TIMEOUT_SECONDS 보다 작아야 합니다" in message
    assert "바로 AI_TIMEOUT 으로 끝납니다" in message
    assert f"AI_DEADLINE_MARGIN_SECONDS={margin}, AI_TIMEOUT_SECONDS=180.0" in message


def test_deadline_margin_must_not_be_negative() -> None:
    with pytest.raises(ValidationError, match="AI_DEADLINE_MARGIN_SECONDS"):
        _settings(AI_PROVIDER="modeling", AI_DEADLINE_MARGIN_SECONDS=-1.0)


def test_default_deadline_margin_passes_check(monkeypatch: pytest.MonkeyPatch) -> None:
    """기본값(제한 180초 · 여유 10초)은 검사를 통과한다. conftest 의 시험용 값은 지우고 본다."""

    monkeypatch.delenv("AI_TIMEOUT_SECONDS", raising=False)
    monkeypatch.delenv("AI_DEADLINE_MARGIN_SECONDS", raising=False)

    settings = _settings(AI_PROVIDER="modeling")

    assert (settings.AI_TIMEOUT_SECONDS, settings.AI_DEADLINE_MARGIN_SECONDS) == (180.0, 10.0)


@pytest.mark.parametrize("provider", ["mock", "pipeline", "langgraph"])
def test_other_providers_do_not_check_deadline_margin(provider: str) -> None:
    """여유는 modeling 만 쓴다. 다른 provider 는 제한 시간을 짧게 잡아도 그대로 뜬다."""

    settings = _settings(AI_PROVIDER=provider, AI_TIMEOUT_SECONDS=5.0, AI_DEADLINE_MARGIN_SECONDS=10.0)

    assert settings.AI_PROVIDER == provider
