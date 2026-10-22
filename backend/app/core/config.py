# 환경설정. Secret/API Key 는 코드에 하드코딩하지 않고 .env 로만 주입한다.

from functools import lru_cache
from pathlib import Path
from typing import Annotated, List, Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]
REPO_ROOT = BACKEND_DIR.parent

# 저장소에 공개된 JWT 비밀키 값들. 이 값으로 서명한 토큰은 누구나 만들 수 있다.
#   기본값(아래 Settings) · backend/.env.example · docker-compose.yml · backend/README.md
_PUBLIC_JWT_SECRETS = frozenset(
    {
        "change-me-in-env-file",
        "replace-this-with-a-long-random-value",
        "local-dev-only-change-me-0123456789abcdef",
        "local-dev-only-change-me-1234567890",
    }
)

# HS256 서명 키 권장 길이(32 byte).
_MIN_JWT_SECRET_LENGTH = 32

# 긴 비밀번호의 문자 종류 면제 길이로 받을 수 있는 범위. 0 은 면제 없음이다.
# 12자보다 짧으면 사실상 종류 규칙을 끄는 셈이고, 72 는 bcrypt 가 받는 최대 byte 다.
_PASSPHRASE_LENGTH_RANGE = (12, 72)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(REPO_ROOT / ".env", BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        # 설정 검사 오류에 입력값(.env 전체 — API 키 · JWT 비밀키 포함)을 찍지 않는다. 시작 실패는 서버 로그에 남는다.
        hide_input_in_errors=True,
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
    # Password Policy
    # ---------------------------------------------------------
    # 새로 정하는 비밀번호에만 적용한다. 로그인 검사에는 쓰지 않는다.
    # 기본값은 팀 회의 결정(2026-09-18) "8자 이상, 영문 · 숫자 · 특수문자 포함" 이다.
    # 종류는 글자 · 숫자 · 특수문자 3가지로 세므로 3 이면 전부 포함해야 한다.
    # PASSWORD_PASSPHRASE_LENGTH 는 이 길이 이상이면 종류를 보지 않는 설정이다.
    # 팀 결정에 없는 면제라 기본값은 0(면제 없음)이다. 켤 때는 12~72 로 준다.
    PASSWORD_MIN_LENGTH: int = Field(default=8, ge=8, le=72)
    PASSWORD_MIN_CLASSES: int = Field(default=3, ge=1, le=3)
    PASSWORD_PASSPHRASE_LENGTH: int = 0

    # ---------------------------------------------------------
    # Account State
    # ---------------------------------------------------------
    # 팀 회의 결정(2026-09-18): 5회 실패 잠금(관리자가 해제), 2개월 미접속 휴면.
    LOGIN_MAX_FAILURES: int = Field(default=5, ge=1)
    # 0 이면 시간이 지나도 풀리지 않고 관리자만 해제한다.(회의 결정)
    LOGIN_LOCK_MINUTES: int = Field(default=0, ge=0)
    DORMANT_AFTER_DAYS: int = Field(default=60, ge=1)
    TEMP_PASSWORD_VALID_HOURS: int = Field(default=72, ge=1)
    # 이전 비밀번호 재사용 금지에 쓸 보관 개수. 0 이면 검사하지 않는다.
    PASSWORD_HISTORY_COUNT: int = Field(default=3, ge=0, le=20)

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
    # 음성 업로드가 아닌 요청 본문의 최대 크기. 본문을 받는 창구(JSON · form)에서 로그인 확인보다 먼저 막는다
    # (main.py _BodySizeLimitMiddleware). 본문을 읽지 않는 창구(GET 등)는 보낸 본문을 무시한다.
    # 음성 업로드(서명 · 만료가 맞는 token 을 붙인 multipart 요청)는 AUDIO_MAX_SIZE_MB 에 multipart 여유 1MB 를
    # 더한 만큼까지 받는다. 음성 경로라도 urlencoded 본문은 이 한도를 쓰고, 그 밖의 multipart 아닌 본문(JSON 등)은
    # 음성 창구가 읽지 않는다(크기와 상관없이 401 또는 file 없음 422).
    REQUEST_MAX_BODY_MB: int = Field(default=2, ge=1)
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

    # mock     : Transcript 에서 파생한 합성 요약 반환
    # pipeline : ai/services/analysis_pipeline.run_analysis_pipeline 호출
    # langgraph: agent/graph.run 호출 (분석 → 근거판정 → RAG → 재분석)
    # modeling : ai/modeling/abuse/contract_adapter.analyze_audio_session_as_contract 호출
    #            (이경진 파이프라인 — 1차 분류 + 2차 세부유형 + 요약 · 기록 초안).
    #            Contract 에는 summary 와 위험 3필드만 담는다. 심각도 · 보호요인 · 회차 간 변화 ·
    #            다음 확인사항은 정식 선택 필드가 생길 때까지 담지 않고, risk_factors 는 빈 배열이다.
    #            근거 발화가 없는 위험 항목은 저장 전에 뺀다(langgraph 와 같음).
    #            모듈 import(모델 로드)는 아래 제한 시간 밖에서 하고, 서버 시작 때 백그라운드로 미리 한다
    #            (ai_adapter.start_ai_preload · analysis_service.PREPARE_TIMEOUT_SECONDS).
    AI_PROVIDER: Literal["mock", "pipeline", "langgraph", "modeling"] = "mock"
    # AI 분석 한 번의 제한 시간. 넘으면 AI_TIMEOUT 으로 실패한다. 작업 시작이 늦었거나 모델 준비가 길었으면
    # 요청 시각부터 잰 작업 전체 마감(준비 제한 45초 + 이 값)에 맞춰 짧아진다(analysis_service._job_deadline).
    # 다만 thread 는 멈추지 못해(run_with_timeout)
    # 외부 호출이 뒤에서 계속될 수 있다. 그래서 modeling 함수가 deadline 을 받으면 마감 시각을 넘겨
    # 스스로 멈추게 한다.
    # 180초는 10/16 이경진 님 측정(V100 GPU, 30분 합성 녹취 122~134초)으로 여유가 25~45초다.
    # 측정 장비가 실제 서버(t3.small, GPU 없음)와 달라, NER 수정 뒤 다시 재고 정한다.
    AI_TIMEOUT_SECONDS: float = 180.0
    # modeling 에 넘기는 마감 시각 = 분석 시작 + 분석 제한(AI_TIMEOUT_SECONDS, 위처럼 짧아졌으면 그 값) - 이 값.
    # 모듈이 스스로 멈춘 뒤 결과를 돌려줄 여유다. 함수가 deadline 을 받지 않으면 쓰지 않는다.
    # 10초인 이유: #57(이경진 님)의 _call_llm_with_retry(ai/modeling/abuse/second_stage_llm.py)는 마감에 걸린
    # LLM 호출의 응답을 '남은 시간 + 5초' 까지 기다린다. 여유가 5초 이하면 안쪽(모듈)과 바깥(run_with_timeout)
    # 제한이 같은 순간 끝나 바깥이 먼저 잡는다. 10초면 모듈이 약 5초 먼저 멈춰 고정 문구 AI_TIMEOUT 으로 끝난다.
    # AI_PROVIDER=modeling 이면 AI_TIMEOUT_SECONDS 보다 작아야 한다(아래 _deadline_margin_is_shorter_than_time_limit).
    AI_DEADLINE_MARGIN_SECONDS: float = Field(default=10.0, ge=0)
    # pipeline 은 상담 원문을 비식별(가리기) 없이 OpenAI 로 보낸다(ai/services/summary_service.py).
    # ENV=production 에서는 이 값이 true 일 때만 pipeline 으로 뜬다 — 가상 데이터로 일부러 시험할 때만 켠다.
    # local/test 에서는 보지 않는다.
    AI_PIPELINE_ALLOW_UNMASKED: bool = False
    # modeling 은 가린 글을 OpenAI 로 보내지만 가리기가 아직 완전하지 않다(이름 인식이 놓친 이름을 잡아 줄
    # 등록 실명 대조가 서버 경로에서는 돌지 않는다. 긴 상담 뒷부분을 못 가리던 문제는 10/20 겹치는 창으로 고쳤다).
    # ENV=production 에서는 이 값이 true 일 때만 modeling 으로 뜬다 — 가상 데이터로 일부러 시험할 때만 켠다.
    # local/test 에서는 보지 않는다.
    AI_MODELING_ALLOW_IN_PRODUCTION: bool = False

    # AI_PROVIDER=pipeline 일 때 팀 B pipeline 이 사용하는 LLM 설정.
    # 팀 B 코드는 os.getenv 로 직접 읽기 때문에 ai_adapter 가 process 환경으로 넘겨준다.
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = ""

    # ---------------------------------------------------------
    # 처리 대기 업무 목록 (/tasks)
    # ---------------------------------------------------------
    # 기다리기 시작한 뒤 이 시간이 지나면 "지연"으로 표시한다.
    # ASSUMPTION: 48시간은 임시값이다. 팀 확인 후 조정한다.
    TASK_OVERDUE_HOURS: float = Field(default=48.0, gt=0)

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

    @field_validator("PASSWORD_PASSPHRASE_LENGTH")
    @classmethod
    def _passphrase_length_is_off_or_in_range(cls, value: int) -> int:
        """0(면제 없음) 또는 12~72 만 받는다."""

        low, high = _PASSPHRASE_LENGTH_RANGE

        if value != 0 and not low <= value <= high:
            raise ValueError(
                f"PASSWORD_PASSPHRASE_LENGTH 는 0(면제 없음) 또는 {low}~{high} 여야 합니다. "
                f"지금 값: {value}"
            )

        return value

    @model_validator(mode="after")
    def _require_private_jwt_secret_in_production(self) -> "Settings":
        """운영에서 공개된 기본값·예시값이나 짧은 JWT 비밀키로 서버가 뜨지 않게 한다.

        .env 에 JWT_SECRET_KEY 를 빠뜨리면 기본값으로 조용히 기동되고, 저장소를 본 사람은
        다른 사용자(관리자 포함)의 UUID 로 유효한 토큰을 만들 수 있다.
        local/test 는 .env 없이 바로 실행되도록 검사하지 않는다.
        """

        if self.ENV != "production":
            return self

        secret = self.JWT_SECRET_KEY

        if secret in _PUBLIC_JWT_SECRETS or len(secret) < _MIN_JWT_SECRET_LENGTH:
            raise ValueError(
                "ENV=production 에서는 JWT_SECRET_KEY 를 저장소에 없는 "
                f"{_MIN_JWT_SECRET_LENGTH}자 이상 임의 값으로 설정해야 합니다. "
                'python -c "import secrets; print(secrets.token_urlsafe(48))" 로 만들 수 있습니다.'
            )

        return self

    @model_validator(mode="after")
    def _block_unmasked_pipeline_in_production(self) -> "Settings":
        """운영에서 상담 원문이 비식별 없이 외부(OpenAI)로 나가는 pipeline 으로 서버가 뜨지 않게 한다.

        외부 LLM 에는 비식별한 텍스트만 보낸다는 9/18 회의 결정과 어긋나는 경로다. 실제 상담 데이터가 들어오는
        운영에서 .env 의 AI_PROVIDER 만 바꿔 실수로 켜지 않도록, AI_PIPELINE_ALLOW_UNMASKED=true 를 함께 적어야만 뜬다.
        local/test 는 지금처럼 그대로 둔다(가상 데이터 전용).
        """

        if self.ENV != "production" or self.AI_PROVIDER != "pipeline" or self.AI_PIPELINE_ALLOW_UNMASKED:
            return self

        raise ValueError(
            "ENV=production 에서는 AI_PROVIDER=pipeline 으로 서버를 시작하지 않습니다. "
            "pipeline 은 상담 원문을 비식별(이름 · 학교 · 주소 가리기) 없이 OpenAI 로 보냅니다. "
            "실제 상담 데이터에는 AI_PROVIDER=mock 을 쓰세요. "
            "가상 데이터로 일부러 시험할 때만 AI_PIPELINE_ALLOW_UNMASKED=true 를 함께 적어 풀 수 있습니다."
        )

    @model_validator(mode="after")
    def _block_modeling_in_production(self) -> "Settings":
        """운영에서 비식별이 아직 불완전한 modeling 으로 서버가 뜨지 않게 한다.

        modeling 은 외부(OpenAI)로 보내기 전에 가리지만, 서버 경로는 case_id 를 넘기지 않아 등록 실명 대조(Privacy Gateway
        Tier 2)가 돌지 않는다. 그래서 이름 인식(NER)이 놓친 이름 · 기관 · 지역은 그대로 나간다(ai/modeling/abuse/contract_adapter.py
        '아직 못 채운 것' · privacy_gateway.py. 실명 저장 여부는 팀 결정 대기). 이름 인식이 글 앞 512토큰만 봐서 긴 상담 뒷부분을
        못 가리던 문제는 2026-10-20 겹치는 창으로 고쳤다(pii_masking._decode_ner_spans).
        이 문제가 해결되기 전에 .env 의 AI_PROVIDER 만 바꿔 실수로 켜지 않도록, AI_MODELING_ALLOW_IN_PRODUCTION=true 를
        함께 적어야만 뜬다. local/test 는 그대로 둔다(가상 데이터 전용).
        """

        if self.ENV != "production" or self.AI_PROVIDER != "modeling" or self.AI_MODELING_ALLOW_IN_PRODUCTION:
            return self

        raise ValueError(
            "ENV=production 에서는 AI_PROVIDER=modeling 으로 서버를 시작하지 않습니다. "
            "modeling 은 상담 내용을 외부(OpenAI)로 보내는데, 그 전에 하는 비식별(이름 · 학교 · 주소 가리기)이 "
            "아직 완전하지 않습니다 — 이름 인식이 놓친 이름을 등록 실명으로 한 번 더 잡는 대조가 서버에서는 돌지 않아, "
            "놓친 이름이 그대로 나갈 수 있습니다. "
            "이 개인정보 문제가 해결되기 전에는 실제 상담 데이터에 AI_PROVIDER=mock 을 쓰세요. "
            "가상 데이터로 일부러 시험할 때만 AI_MODELING_ALLOW_IN_PRODUCTION=true 를 함께 적어 풀 수 있습니다."
        )

    @model_validator(mode="after")
    def _deadline_margin_is_shorter_than_time_limit(self) -> "Settings":
        """modeling 의 마감 시각이 분석 시작보다 뒤에 오게 한다.

        마감 시각 = 분석 시작 + AI_TIMEOUT_SECONDS - AI_DEADLINE_MARGIN_SECONDS 라서, 여유가 제한 시간과 같거나
        길면 모듈이 첫 단계 전에 마감을 넘긴 것으로 보고 모든 분석이 바로 AI_TIMEOUT 으로 끝난다.
        여유는 modeling 만 쓰므로 다른 provider 는 보지 않는다(짧은 제한 시간으로 mock 을 돌리는 설정을 막지 않게).
        """

        if self.AI_PROVIDER != "modeling" or self.AI_DEADLINE_MARGIN_SECONDS < self.AI_TIMEOUT_SECONDS:
            return self

        raise ValueError(
            "AI_DEADLINE_MARGIN_SECONDS 는 AI_TIMEOUT_SECONDS 보다 작아야 합니다(AI_PROVIDER=modeling). "
            "같거나 크면 modeling 에 넘기는 마감 시각이 분석 시작과 같거나 그보다 앞서 "
            "모든 분석이 바로 AI_TIMEOUT 으로 끝납니다. "
            f"지금 값: AI_DEADLINE_MARGIN_SECONDS={self.AI_DEADLINE_MARGIN_SECONDS}, "
            f"AI_TIMEOUT_SECONDS={self.AI_TIMEOUT_SECONDS}"
        )

    @property
    def audio_max_size_bytes(self) -> int:
        return self.AUDIO_MAX_SIZE_MB * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
