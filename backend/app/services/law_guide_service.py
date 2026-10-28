# 법령 · 매뉴얼 AI 질문 — POST /law-guide/questions (API_CONTRACT 17절, 2026-10-28).
#
# 상담 회차 · 사례와 묶이지 않는 독립 질의다. 검증 · 사용자별 호출 한도 · 동시 실행 제한 · 시간 제한 · 감사 기록을
# 여기서 하고, 실제 답은 law_qa_adapter 가 만든다. 설계는 I-SPOT_DOCS/docs/PROPOSAL_law_guide_api.md §4 · §5.
#  - 동기 200(1.4 의 202 + polling 예외): 저장할 회차가 없고 한 번에 걸리는 시간이 분석보다 훨씬 짧다.
#  - 질문 · 답변은 DB 에 저장하지 않는다(§5-3) — 자유 입력에 아동 이름 같은 개인정보가 섞일 수 있어서.
#    감사 기록에도 사용자 · 시각 · 성공/실패 코드 · 걸린 시간 · provider · 모델 · 근거 수만 남긴다.
#  - 한도는 서버 메모리 기준이다(서버 1대 전제, §5-4). 여러 프로세스로 띄우면 프로세스마다 따로 센다.
import logging
import threading
import time
import uuid
from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Any, Deque, Dict, Optional

from sqlalchemy.orm import Session

from app.adapters.law_qa_adapter import (
    LawQAAdapter,
    LawQAAnswer,
    LawQAError,
    get_law_qa_adapter,
    map_law_qa_error,
)
from app.core.concurrency import OperationTimeout, run_with_timeout
from app.core.config import settings
from app.core.enums import AuditAction
from app.core.errors import APIError, ErrorCode
from app.models.user import User
from app.schemas.law_guide import (
    LawGuideAnswerResponse,
    LawGuideSourcesResponse,
    LawSourceResponse,
    ManualSourceResponse,
)
from app.services import audit_service

logger = logging.getLogger(__name__)

#: 사용자별 호출 한도를 세는 창(초). LAW_QA_RATE_LIMIT_PER_MINUTE 가 이 창 안의 상한이다.
RATE_WINDOW_SECONDS = 60.0

DISABLED_MESSAGE = "법령 · 매뉴얼 AI 질문이 꺼져 있습니다."
RATE_LIMITED_MESSAGE = "질문이 너무 잦습니다. 잠시 후 다시 시도해 주세요."

#: 감사 기록의 entity_type. entity_id 는 없다(질문을 저장하지 않으므로).
AUDIT_ENTITY_TYPE = "LawGuideQuestion"


class _Limits:
    """사용자별 호출 시각과 서버 전체 동시 실행 자리. 설정이 바뀌면 reset_limits 로 새로 만든다."""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.calls: Dict[uuid.UUID, Deque[float]] = defaultdict(deque)
        self.slots = threading.BoundedSemaphore(settings.LAW_QA_MAX_CONCURRENCY)


_limits = _Limits()


def reset_limits() -> None:
    """시험용. 호출 기록과 동시 실행 자리를 설정값으로 다시 만든다."""

    global _limits
    _limits = _Limits()


def _allow_call(user_id: uuid.UUID) -> bool:
    """지난 RATE_WINDOW_SECONDS 안의 호출이 한도 미만이면 이번 호출을 세고 True."""

    now = time.monotonic()
    limit = settings.LAW_QA_RATE_LIMIT_PER_MINUTE

    with _limits.lock:
        calls = _limits.calls[user_id]

        while calls and now - calls[0] >= RATE_WINDOW_SECONDS:
            calls.popleft()

        if len(calls) >= limit:
            return False

        calls.append(now)

    return True


def _record(
    db: Session,
    user: User,
    *,
    status: str,
    error_code: Optional[ErrorCode],
    detail: Dict[str, Any],
) -> None:
    """감사 기록 한 건. 질문 원문은 넣지 않는다."""

    audit_service.record(
        db,
        action=AuditAction.LAW_QA_ASKED,
        entity_type=AUDIT_ENTITY_TYPE,
        actor_id=user.id,
        detail=detail,
        status=status,
        error_code=error_code.value if error_code is not None else None,
    )
    db.commit()


def _fail(db: Session, user: User, error: LawQAError, *, provider: str, started: float) -> APIError:
    _record(
        db,
        user,
        status="FAILED",
        error_code=error.code,
        detail={
            "provider": provider,
            "duration_ms": int((time.monotonic() - started) * 1000),
            "cause": error.cause_name,
        },
    )

    return APIError(error.code, error.message, status_code=error.status_code)


def ask(
    db: Session,
    user: User,
    question: str,
    *,
    adapter: Optional[LawQAAdapter] = None,
) -> LawGuideAnswerResponse:
    """질문 하나에 답한다. 실패는 APIError(코드별 고정 문구 · HTTP 상태)로 올린다."""

    if settings.LAW_QA_PROVIDER == "off":
        raise APIError(ErrorCode.LAW_QA_DISABLED, DISABLED_MESSAGE, status_code=503)

    adapter = adapter or get_law_qa_adapter()
    timeout = settings.LAW_QA_TIMEOUT_SECONDS
    started = time.monotonic()

    if not _allow_call(user.id):
        _record(
            db,
            user,
            status="FAILED",
            error_code=ErrorCode.RATE_LIMITED,
            detail={"provider": adapter.name, "duration_ms": 0},
        )

        raise APIError(ErrorCode.RATE_LIMITED, RATE_LIMITED_MESSAGE, status_code=429)

    # 호출 하나가 큰 입력(법령 전문 약 9.8만 자)이라 서버 전체 동시 LAW_QA_MAX_CONCURRENCY 건으로 묶는다.
    # 자리가 나기를 제한 시간만큼 기다리고, 못 들어가면 AI_TIMEOUT. 얻은 자리는 같은 semaphore 객체에 돌려준다
    # (reset_limits 로 바뀐 뒤에도 — 뒤늦게 끝난 작업이 새 semaphore 를 늘리지 않게).
    slots = _limits.slots

    if not slots.acquire(timeout=timeout):
        raise _fail(db, user, LawQAError(ErrorCode.AI_TIMEOUT, "NoSlot"), provider=adapter.name, started=started)

    error: Optional[LawQAError] = None
    result: Optional[LawQAAnswer] = None

    # 자리는 **실제 작업이 끝날 때** 돌려준다. run_with_timeout 은 thread 를 멈추지 못해 시간을 넘긴 작업이 뒤에서
    # 계속 도는데, 그때 자리를 먼저 돌려주면 실제 작업 수가 LAW_QA_MAX_CONCURRENCY 를 넘는다(#109 교차검증 R2).
    # 그래서 작업 thread 가 자기 finally 에서 돌려주고, 서비스는 작업이 시작조차 못 한 경우(취소됨)만 돌려준다.
    work_started = threading.Event()
    release_lock = threading.Lock()
    released = False

    def release_slot() -> None:
        nonlocal released

        with release_lock:
            if released:
                return

            released = True
            slots.release()

    def work() -> LawQAAnswer:
        work_started.set()

        try:
            # 자리를 얻은 뒤부터 제한 시간을 다시 잰다(기다린 시간은 포함하지 않는다). thread 는 멈추지 못하므로
            # modeling 은 마감 시각을 받아 스스로 멈춘다(law_qa_adapter.ModelingLawQAAdapter).
            return adapter.answer(question, time_limit_seconds=timeout)
        finally:
            release_slot()

    try:
        result = run_with_timeout(work, timeout)
    except OperationTimeout:
        error = LawQAError(ErrorCode.AI_TIMEOUT, "OperationTimeout")
    except LawQAError as caught:
        error = caught
    except Exception as caught:  # noqa: BLE001 — 종류 이름만 남기고 고정 문구로 바꾼다
        logger.warning("법령 질의 처리 중 예상하지 못한 오류. type=%s", type(caught).__name__)
        error = map_law_qa_error(caught)

    if error is not None and not work_started.is_set():
        # 작업이 시작되기 전에 끝난 경우(시간 초과로 취소됨 · executor 오류)에만 서비스가 돌려준다.
        # 돌고 있는 작업은 끝날 때 스스로 돌려주고, 두 번 돌려주지 않게 release_slot 이 한 번만 센다.
        release_slot()

    if error is not None or result is None:
        raise _fail(
            db,
            user,
            error or LawQAError(ErrorCode.AI_FAILED, "NoResult"),
            provider=adapter.name,
            started=started,
        )

    answered_at = datetime.now(timezone.utc)

    _record(
        db,
        user,
        status="SUCCESS",
        error_code=None,
        detail={
            "provider": adapter.name,
            "model": result.model,
            "duration_ms": int((time.monotonic() - started) * 1000),
            "law_count": len(result.laws),
            "manual_count": len(result.manual),
        },
    )

    return LawGuideAnswerResponse(
        answer=result.answer,
        sources=LawGuideSourcesResponse(
            laws=[LawSourceResponse(**source) for source in result.laws],
            manual=[ManualSourceResponse(**source) for source in result.manual],
        ),
        model=result.model,
        answered_at=answered_at,
    )
