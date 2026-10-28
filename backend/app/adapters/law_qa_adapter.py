# 법령 · 매뉴얼 AI 질문 Adapter — LawGuide 화면의 'AI 에게 묻기' (API_CONTRACT 16절, 2026-10-28).
#
# ai/modeling/abuse/legal_manual_qa_llm.answer_legal_manual_question(이경진 님, PR #83)을 부른다. 분석 어댑터
# (ai_adapter)와 같은 모양(Protocol + mock + modeling + provider 스위치)이고 설계는 I-SPOT_DOCS/docs/PROPOSAL_law_guide_api.md §4 다.
#  - mock: OpenAI 없이 고정 답변 + 조문 1개를 돌려준다. 화면 개발 · CI 용.
#  - modeling: 처음 부를 때 모듈을 import 하고(prepare), OpenAI client 를 만들어 질문을 넘긴다. 질문 가리기
#    (mask_for_outbound)와 답변 끝의 참고용 안내는 모듈이 한다. 매뉴얼 사진은 기관 대외비라 모듈 설정
#    (manual/config.MANUAL_QA_ATTACH_IMAGES, 기본 끔)이 켜졌을 때만 첨부되고, 꺼져 있으면 법령만으로 답하고 매뉴얼 근거는 빈 목록이다.
#    실패는 예외 **종류**로 코드를 정하고 문구는 버린다 — 문구에 질문 원문 · 국가법령정보센터 인증값 · OpenAI SDK 원문이
#    섞일 수 있다(map_ai_error 와 같은 원칙).
# 질문 · 답변은 어디에도 저장하지 않는다(제안서 §5-3).
import logging
import os
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Protocol, Tuple

from app.adapters.module_loader import ensure_repo_root_on_path
from app.core.config import settings
from app.core.errors import ErrorCode

logger = logging.getLogger(__name__)

# 코드별 고정 문구. 화면 · 감사 기록으로 나가므로 질문 원문 · 예외 문구를 넣지 않는다.
LAW_QA_MESSAGES: Dict[ErrorCode, str] = {
    ErrorCode.AI_TIMEOUT: "법령 질의가 제한 시간 안에 끝나지 않았습니다. 잠시 후 다시 시도해 주세요.",
    ErrorCode.AI_INVALID_OUTPUT: "AI 가 답변을 만들지 못했습니다. 질문을 바꿔 다시 시도해 주세요.",
    ErrorCode.AI_FAILED: "AI 호출에 실패했습니다. 잠시 후 다시 시도해 주세요.",
    ErrorCode.LAW_SOURCE_UNAVAILABLE: "법령 자료를 불러올 수 없습니다. 잠시 후 다시 시도해 주세요.",
}

# 코드별 HTTP 상태(제안서 §3 표). 분석 API 와 달리 이 창구는 동기 응답이라 HTTP 상태로 돌려준다.
LAW_QA_STATUS: Dict[ErrorCode, int] = {
    ErrorCode.AI_TIMEOUT: 504,
    ErrorCode.AI_INVALID_OUTPUT: 502,
    ErrorCode.AI_FAILED: 502,
    ErrorCode.LAW_SOURCE_UNAVAILABLE: 503,
}

# 모듈 예외 종류 이름 → 코드. import 없이 이름으로 맞춘다(모듈이 없는 환경 · 가짜 모듈 시험에서도 같은 규칙).
#  - LawQAOutputError: LLM 응답에 답변이 없음 · LawQALLMError: 그 밖의 LLM 호출 실패(OpenAI 인증 · 연결 등, 종류 이름만 든 고정 문구)
#  - LawApiError(law.client): 법령 캐시가 없고 국가법령정보센터 조회도 실패
#  - 내장 TimeoutError: 마감(deadline)을 넘김
_ERROR_CODES_BY_NAME: Dict[str, ErrorCode] = {
    "LawQAOutputError": ErrorCode.AI_INVALID_OUTPUT,
    "LawQALLMError": ErrorCode.AI_FAILED,
    "LawApiError": ErrorCode.LAW_SOURCE_UNAVAILABLE,
}


class LawQAError(Exception):
    """법령 질의 실패. 문구는 코드별 고정 문구이고 원인은 예외 종류 이름(cause_name)만 남긴다."""

    def __init__(self, code: ErrorCode, cause_name: str = "") -> None:
        super().__init__(LAW_QA_MESSAGES[code])
        self.code = code
        self.status_code = LAW_QA_STATUS[code]
        self.cause_name = cause_name

    @property
    def message(self) -> str:
        return LAW_QA_MESSAGES[self.code]


def map_law_qa_error(error: Exception) -> LawQAError:
    """모듈에서 올라온 예외를 코드로 바꾼다. 모르는 예외는 AI_FAILED 이고 종류 이름만 남긴다."""

    if isinstance(error, LawQAError):
        return error

    name = type(error).__name__

    if isinstance(error, TimeoutError):
        return LawQAError(ErrorCode.AI_TIMEOUT, name)

    return LawQAError(_ERROR_CODES_BY_NAME.get(name, ErrorCode.AI_FAILED), name)


@dataclass
class LawQAAnswer:
    answer: str
    model: str
    # Contract 모양 그대로(law_name · article · title · content · effective_date · portal_url).
    laws: List[Dict[str, Any]] = field(default_factory=list)
    # {id, title, page}. 매뉴얼 첨부가 꺼져 있으면 늘 빈 목록.
    manual: List[Dict[str, Any]] = field(default_factory=list)


class LawQAAdapter(Protocol):
    name: str

    def answer(self, question: str, *, time_limit_seconds: float) -> LawQAAnswer: ...


# =========================================================
# Mock
# =========================================================

MOCK_MODEL = "mock"

MOCK_ANSWER = (
    "응급조치는 현장에서 피해아동을 보호하기 위해 바로 할 수 있는 조치이고, 72시간을 넘을 수 없습니다"
    "(아동학대범죄의 처벌 등에 관한 특례법 제12조). 실제 적용은 기관 내부 절차와 법률 자문을 따라야 합니다.\n\n"
    "※ 이 답변은 참고용입니다. 실제 적용 전 원본 자료를 직접 확인하고, 최종 판단은 상담사가 내려야 합니다."
)

MOCK_SOURCE: Dict[str, Any] = {
    "law_name": "아동학대범죄의 처벌 등에 관한 특례법",
    "article": "제12조",
    "title": "피해아동 등에 대한 응급조치",
    "content": "③ 제1항에 따른 응급조치는 72시간을 넘을 수 없다. (mock 고정 조문 — 실제 본문은 법령 캐시에서 온다)",
    "effective_date": None,
    "portal_url": "https://www.law.go.kr/법령/아동학대범죄의처벌등에관한특례법/제12조",
}


class MockLawQAAdapter:
    """OpenAI 없이 고정 답변을 돌려준다. 질문 내용은 보지 않는다. 매뉴얼 근거는 없다(기본 끔과 같은 모양)."""

    name = "mock"

    def answer(self, question: str, *, time_limit_seconds: float) -> LawQAAnswer:
        return LawQAAnswer(answer=MOCK_ANSWER, model=MOCK_MODEL, laws=[dict(MOCK_SOURCE)], manual=[])


# =========================================================
# Modeling (ai/modeling/abuse/legal_manual_qa_llm)
# =========================================================


def export_law_env() -> None:
    """law/config.py 는 import 할 때 os.getenv 로 읽는다(LAW_API_OC · LAW_CACHE_DIR). .env 에만 적으면 못 보므로
    process 환경으로 넘긴다. 이미 환경에 있으면 그 값을 우선한다(ai_adapter.export_llm_env 와 같음)."""

    for name in ("LAW_API_OC", "LAW_CACHE_DIR"):
        value = getattr(settings, name, "")

        if value and not os.getenv(name):
            os.environ[name] = value


def _text(value: Any) -> str:
    return str(value or "").strip()


def to_law_sources(cited: Any) -> List[Dict[str, Any]]:
    """모듈의 cited_articles 에서 Contract 키만 골라 옮긴다. dict 가 아닌 항목 · 법령명이나 조문이 없는 항목은 버린다."""

    sources: List[Dict[str, Any]] = []

    if not isinstance(cited, list):
        return sources

    for item in cited:
        if not isinstance(item, dict):
            continue

        law_name = _text(item.get("law_name"))
        article = _text(item.get("article"))

        if not law_name or not article:
            continue

        sources.append(
            {
                "law_name": law_name,
                "article": article,
                "title": _text(item.get("title")),
                "content": str(item.get("content") or ""),
                "effective_date": _text(item.get("effective_date")) or None,
                "portal_url": _text(item.get("portal_url")) or None,
            }
        )

    return sources


def to_manual_sources(references: Any) -> List[Dict[str, Any]]:
    """모듈의 manual_references({id, title, page})를 옮긴다. dict 가 아니거나 id · title 이 없으면 버린다."""

    sources: List[Dict[str, Any]] = []

    if not isinstance(references, list):
        return sources

    for item in references:
        if not isinstance(item, dict):
            continue

        ref_id = _text(item.get("id"))
        title = _text(item.get("title"))

        if not ref_id or not title:
            continue

        sources.append({"id": ref_id, "title": title, "page": _text(item.get("page")) or "?"})

    return sources


class ModelingLawQAAdapter:
    """ai.modeling.abuse.legal_manual_qa_llm.answer_legal_manual_question 을 부른다.

    모듈 import 는 가볍지만(openai · law · manual 패키지) 첫 질문 때 법령 캐시가 없으면 국가법령정보센터 조회까지
    한다. 그래서 서버 시작 때 start_law_qa_preload 가 import 와 캐시 받기를 미리 한다(제안서 §5-5).
    """

    name = "modeling"

    def prepare(self) -> None:
        self._load()

    def _load(self) -> Tuple[Callable[..., Any], Callable[..., Any], str]:
        ensure_repo_root_on_path()

        # OPENAI_API_KEY · LAW_API_OC 같은 값은 모듈 쪽이 os.getenv 로 읽는다.
        from app.adapters.ai_adapter import export_llm_env

        export_llm_env()
        export_law_env()

        try:
            from ai.modeling.abuse.legal_manual_qa_llm import (
                DEFAULT_MODEL,
                answer_legal_manual_question,
            )
            from ai.modeling.abuse.llm_backend import build_openai_client_and_model
        except ImportError as error:
            # 문구에 모듈 경로 · 내려받기 주소가 섞일 수 있어 종류 이름만 남긴다.
            raise LawQAError(ErrorCode.AI_FAILED, type(error).__name__) from error

        return answer_legal_manual_question, build_openai_client_and_model, str(DEFAULT_MODEL)

    def answer(self, question: str, *, time_limit_seconds: float) -> LawQAAnswer:
        # law_guide_service 의 run_with_timeout 이 시간을 재기 시작한 직후다. 마감 시각은 여기서부터 잰다.
        started = time.monotonic()
        answer_question, build_client, default_model = self._load()

        # 마감 = 시작 + 제한 − 여유(AI_DEADLINE_MARGIN_SECONDS). 모듈이 스스로 멈춰 고정 문구 TimeoutError 를 내게 한다
        # (run_with_timeout 은 thread 를 멈추지 못한다). 분석의 ModelingAIAdapter 와 같은 규칙.
        deadline = started + time_limit_seconds - settings.AI_DEADLINE_MARGIN_SECONDS

        try:
            # 모델 이름은 모듈 쪽(DEFAULT_MODEL)이 정한다 — 분석 modeling 과 같다.
            client, model = build_client(default_model)
            result = answer_question(client, model, question, deadline=deadline)
        except Exception as error:
            raise map_law_qa_error(error) from error

        text = _text(result.get("answer")) if isinstance(result, dict) else ""

        if not text:
            raise LawQAError(ErrorCode.AI_INVALID_OUTPUT, "EmptyAnswer")

        return LawQAAnswer(
            answer=text,
            model=str(model),
            laws=to_law_sources(result.get("cited_articles")),
            manual=to_manual_sources(result.get("manual_references")),
        )


# =========================================================
# Provider 선택 · 서버 시작 준비
# =========================================================

_override: Optional[LawQAAdapter] = None


def set_law_qa_adapter_override(adapter: Optional[LawQAAdapter]) -> None:
    """시험용. None 이면 설정대로 돌아간다."""

    global _override
    _override = adapter


def get_law_qa_adapter() -> LawQAAdapter:
    """LAW_QA_PROVIDER 로 고른다. off 는 law_guide_service 가 먼저 막는다(여기까지 오면 mock)."""

    if _override is not None:
        return _override

    if settings.LAW_QA_PROVIDER == "modeling":
        return ModelingLawQAAdapter()

    return MockLawQAAdapter()


def warm_law_cache() -> None:
    """대상 법령을 캐시에 받아 둔다. 없거나 오래됐으면 국가법령정보센터를 조회한다(LAW_API_OC 필요)."""

    ensure_repo_root_on_path()
    export_law_env()

    from law.client import LawApiClient
    from law.config import LAW_TARGET_LAWS

    client = LawApiClient()

    for law_name in LAW_TARGET_LAWS:
        client.get_law_by_name(law_name)


def start_law_qa_preload() -> Optional[threading.Thread]:
    """LAW_QA_PROVIDER=modeling 이면 백그라운드 thread 로 모듈 import 와 법령 캐시 받기를 미리 한다(제안서 §5-5).

    서버 시작 때 부른다(main.py lifespan). 기다리지 않으므로 /health 는 바로 응답하고, 실패해도 서버는 뜨며
    첫 질문 때 다시 시도한다. 실패 로그에는 예외 종류 이름만 남긴다. 다른 provider 는 None 을 돌려준다.
    """

    if settings.LAW_QA_PROVIDER != "modeling":
        return None

    adapter = get_law_qa_adapter()

    def run() -> None:
        try:
            prepare = getattr(adapter, "prepare", None)

            if prepare is not None:
                prepare()

            warm_law_cache()
        except Exception as error:  # noqa: BLE001 — 종류 이름만 남긴다
            cause = error.__cause__ if isinstance(error, LawQAError) and error.__cause__ else error
            logger.warning(
                "법령 질의 모듈 · 법령 캐시를 미리 준비하지 못했습니다. 첫 질문 때 다시 시도합니다. type=%s",
                type(cause).__name__,
            )
        else:
            logger.info("법령 질의 모듈 · 법령 캐시를 미리 준비했습니다.")

    thread = threading.Thread(target=run, name="law-qa-preload", daemon=True)
    thread.start()

    return thread


__all__ = [
    "LAW_QA_MESSAGES",
    "LAW_QA_STATUS",
    "LawQAAdapter",
    "LawQAAnswer",
    "LawQAError",
    "MOCK_ANSWER",
    "MOCK_MODEL",
    "MOCK_SOURCE",
    "MockLawQAAdapter",
    "ModelingLawQAAdapter",
    "export_law_env",
    "get_law_qa_adapter",
    "map_law_qa_error",
    "set_law_qa_adapter_override",
    "start_law_qa_preload",
    "to_law_sources",
    "to_manual_sources",
    "warm_law_cache",
]
