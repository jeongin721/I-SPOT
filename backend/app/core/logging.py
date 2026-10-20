# Logging 설정.
#
# docs/05_RULES.md 절대 금지: "상담 원문 전체를 일반 로그에 출력".
# 따라서 로그에는 식별자/개수/길이 등 metadata 만 남기고,
# 발화 텍스트는 redact_text() 를 거친 형태만 허용한다.
# 서버(uvicorn)의 접속 기록도 경로 · 상태 코드만 남기고 쿼리 값은 뺀다(install_server_log_filters).
# 예외 trace 는 예외 종류 · 호출 위치만 남기고 예외 문구는 뺀다(install_safe_exception_text).

import logging
import sys
import traceback
from types import TracebackType
from typing import List, Optional, Tuple, Type

from app.core.config import settings

_CONFIGURED = False

# uvicorn 이 요청 주소를 남기는 로거. 접속 기록은 uvicorn.access, WebSocket 연결 기록은 uvicorn.error 로 남는다.
_ACCESS_LOGGER = "uvicorn.access"
_SERVER_LOGGER = "uvicorn.error"

# uvicorn(protocols/websockets/*_impl.py)의 WebSocket 연결 기록은 모두 이 글자로 시작한다.
# 뒤에 ' [accepted]', ' 403', ' %d'(상태 코드)가 붙고, 인자는 (접속 주소, 요청 주소[, 상태 코드]) 다.
_WEBSOCKET_LOG_PREFIX = '%s - "WebSocket %s"'


def configure_logging() -> None:
    global _CONFIGURED

    if _CONFIGURED:
        return

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s %(levelname)s [%(name)s] %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S",
        )
    )

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(settings.LOG_LEVEL.upper())

    install_server_log_filters()
    install_safe_exception_text()

    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    configure_logging()
    return logging.getLogger(name)


def _without_query(target: str) -> str:
    """
    요청 주소에서 ? 뒤(쿼리 문자열)를 뺀다.

    uvicorn 은 경로를 urllib.parse.quote 로 적어 경로 안의 ? 는 %3F 가 되므로, 처음 나오는 ? 가 쿼리의 시작이다.
    """

    return target.split("?", 1)[0]


class AccessLogQueryFilter(logging.Filter):
    """
    uvicorn 접속 기록(uvicorn.access)의 요청 주소에서 쿼리 문자열을 뺀다.

    uvicorn 은 요청마다 주소 전체를 남기므로 사례 검색어(?search=) · 감사 기록 필터(?status= 등) 같은 입력 값이
    정상 요청이든 거절한 요청이든 서버 기록에 그대로 남는다. 경로 · method · 상태 코드는 그대로 둔다.

    uvicorn(protocols/http/*_impl.py)은 info('%s - "%s %s HTTP/%s" %d', 접속 주소, method, 경로+쿼리,
    HTTP 버전, 상태 코드) 로 남긴다. 인자가 이 모양(5개, 세 번째가 글자)이 아니면(uvicorn 버전이 바뀌는 등)
    아무것도 바꾸지 않는다. 어느 경우든 기록은 버리지 않는다(항상 True).
    """

    def filter(self, record: logging.LogRecord) -> bool:
        args = record.args

        if isinstance(args, tuple) and len(args) == 5 and isinstance(args[2], str):
            record.args = (*args[:2], _without_query(args[2]), *args[3:])

        return True


class WebSocketLogQueryFilter(logging.Filter):
    """
    uvicorn.error 로 남는 WebSocket 연결 기록의 요청 주소에서 쿼리 문자열을 뺀다.

    앱에 WebSocket 창구는 없지만, 누가 WebSocket 으로 연결을 시도하면 uvicorn 은 거절(403)한 연결의 주소를
    쿼리까지 남긴다. uvicorn.error 에는 서버 시작 · 오류 기록도 오므로 WebSocket 연결 기록 모양
    (_WEBSOCKET_LOG_PREFIX 로 시작하고 두 번째 인자가 글자)만 고치고 나머지는 그대로 둔다. 기록은 버리지 않는다.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        args = record.args

        if (
            isinstance(record.msg, str)
            and record.msg.startswith(_WEBSOCKET_LOG_PREFIX)
            and isinstance(args, tuple)
            and len(args) >= 2
            and isinstance(args[1], str)
        ):
            record.args = (args[0], _without_query(args[1]), *args[2:])

        return True


def install_server_log_filters() -> None:
    """
    uvicorn 로거에 위 필터를 붙인다. 여러 번 불러도 한 번만 붙는다.

    앱을 import 할 때(configure_logging) 붙인다. `uvicorn app.main:app` 명령은 logging 을 먼저 설정(dictConfig)하고
    앱을 import 하므로(uvicorn/main.py run → Config.__init__ → configure_logging, 그 뒤 load_app) 설정에 지워지지 않는다.
    앱을 먼저 import 하고 uvicorn.run(app) 으로 띄워도, dictConfig 는 이미 있는 로거의 handler 만 바꾸고 filter 는
    지우지 않으므로 남는다. 로거에 붙인 filter 는 그 로거에 직접 남긴 기록에 handler 보다 먼저 걸리므로
    `--log-config` 로 형식을 바꿔도 쿼리는 빠진다.
    """

    for name, filter_class in (
        (_ACCESS_LOGGER, AccessLogQueryFilter),
        (_SERVER_LOGGER, WebSocketLogQueryFilter),
    ):
        logger = logging.getLogger(name)

        if not any(isinstance(existing, filter_class) for existing in logger.filters):
            logger.addFilter(filter_class())


# 원인을 몇 단계까지 따라갈지. 원인이 서로를 가리키는 고리가 있어도 끝나게 한다.
_MAX_EXCEPTION_CHAIN = 20

# 파이썬 기본 trace 와 같은 머리말(원인 예외 → 다음 예외 사이에 붙는다).
_CAUSE_HEADER = "The above exception was the direct cause of the following exception:"
_CONTEXT_HEADER = "During handling of the above exception, another exception occurred:"

_HIDDEN_MESSAGE = "<문구 생략>"

ExcInfo = Tuple[Optional[Type[BaseException]], Optional[BaseException], Optional[TracebackType]]


def _exception_name(error: BaseException) -> str:
    kind = type(error)

    if kind.__module__ in ("builtins", "__main__"):
        return kind.__qualname__

    return f"{kind.__module__}.{kind.__qualname__}"


def _previous_exception(error: BaseException) -> Tuple[Optional[BaseException], Optional[str]]:
    """파이썬 기본 trace 처럼 원인(__cause__)을 먼저, 없으면 감추지 않은 처리 중 예외(__context__)를 따라간다."""

    if error.__cause__ is not None:
        return error.__cause__, _CAUSE_HEADER

    if error.__context__ is not None and not error.__suppress_context__:
        return error.__context__, _CONTEXT_HEADER

    return None, None


def _exception_block(error: BaseException) -> str:
    lines: List[str] = []

    if error.__traceback__ is not None:
        lines.append("Traceback (most recent call last):\n")
        lines.extend(traceback.format_list(traceback.extract_tb(error.__traceback__)))

    last = f"{_exception_name(error)}: {_HIDDEN_MESSAGE}"

    if isinstance(error, BaseExceptionGroup):
        last += " (하위 예외: " + ", ".join(_exception_name(inner) for inner in error.exceptions) + ")"

    lines.append(last + "\n")

    return "".join(lines)


def safe_exception_text(exc_info: ExcInfo) -> str:
    """
    예외 trace 를 예외 문구 없이 적는다. 예외마다 종류 이름과 호출 위치(파일 · 줄 · 함수 · 그 줄의 코드)만 남긴다.

    원인 예외(raise ... from · 처리 중 다시 난 예외)도 파이썬 기본 trace 와 같은 순서 · 머리말로 적되, 가까운 쪽부터
    _MAX_EXCEPTION_CHAIN 개까지만 적고 더 앞선 원인이 있으면 생략했다고 맨 앞에 적는다.
    예외 문구 · 메모(add_note) · 변수 값은 적지 않는다. 하위 예외(ExceptionGroup)는 종류 이름만 적고 각자의 trace 는 적지 않는다.
    """

    error = exc_info[1]

    if error is None:
        return ""

    chain: List[BaseException] = []
    seen = set()
    current: Optional[BaseException] = error

    while current is not None and id(current) not in seen and len(chain) < _MAX_EXCEPTION_CHAIN:
        seen.add(id(current))
        chain.append(current)
        current, _ = _previous_exception(current)

    # 개수 제한으로 멈췄으면(고리로 멈춘 것이 아니면) 맨 앞 블록이 최초 원인처럼 보이지 않게 표시한다.
    truncated = current is not None and id(current) not in seen

    # 원인부터 적는다. 두 번째부터는 바로 앞에 적은 예외(= _previous_exception)와의 관계 머리말을 붙인다.
    chain.reverse()
    parts = [f"(더 앞선 원인 예외는 생략, 가까운 {_MAX_EXCEPTION_CHAIN}개만 적음)\n\n"] if truncated else []
    parts.append(_exception_block(chain[0]))

    for later in chain[1:]:
        _, header = _previous_exception(later)
        parts.append(f"\n{header}\n\n")
        parts.append(_exception_block(later))

    return "".join(parts).rstrip("\n")


_SAFE_FACTORY_MARK = "_ispot_safe_exception_text"


def install_safe_exception_text() -> None:
    """
    로그 기록을 만들 때 예외 trace(record.exc_text)를 safe_exception_text 로 미리 채운다. 여러 번 불러도 한 번만 건다.

    예외 문구에는 상담 발화가 섞일 수 있다(SQL 오류의 매개변수 · 입력 검증 오류의 입력 값 · AI 쪽 원인 예외 문구).
    logger.exception 은 원인 예외까지 문구를 그대로 적으므로, 오류 응답 · DB 에서 문구를 빼도 서버 기록에 남았다.

    logging.Formatter 는 record.exc_text 가 이미 있으면 그것을 쓰고 예외를 다시 적지 않는다. 기록을 만드는 단계
    (LogRecord factory)에서 채우므로 로거(app · uvicorn.error · sqlalchemy 등)와 handler 에 상관없이, 표준
    logging.Formatter 와 그 하위 형식(uvicorn 기본 형식, pytest caplog)이면 같은 글이 나간다. record.exc_info 는 그대로 둔다.

    막지 못하는 것: 로그 메시지 인자에 예외를 직접 넣은 기록(앱 코드는 예외 종류 이름만 넣는다), logging 을 거치지 않는
    출력(threading.excepthook · warnings · print), formatException 을 직접 부르는 형식(JSON 로거 등, 지금은 안 씀).
    """

    previous = logging.getLogRecordFactory()

    if getattr(previous, _SAFE_FACTORY_MARK, False):
        return

    def factory(*args, **kwargs) -> logging.LogRecord:
        record = previous(*args, **kwargs)

        if record.exc_info and record.exc_info[1] is not None and not record.exc_text:
            try:
                record.exc_text = safe_exception_text(record.exc_info)
            except Exception:
                # trace 를 적다 실패해도 로그를 남긴 쪽(except 블록 등)으로 오류를 올리지 않는다.
                # 비워 두면 Formatter 가 문구가 든 원래 trace 를 다시 만들므로 반드시 채운다.
                record.exc_text = f"{type(record.exc_info[1]).__qualname__}: {_HIDDEN_MESSAGE} (trace 를 적지 못함)"

        return record

    setattr(factory, _SAFE_FACTORY_MARK, True)
    logging.setLogRecordFactory(factory)


def redact_text(text: Optional[str]) -> str:
    """
    상담 발화 텍스트를 로그에 남겨야 할 때 반드시 이 함수를 거친다.
    내용은 남기지 않고 길이만 남긴다.
    """

    if text is None:
        return "<none>"

    return f"<redacted len={len(text)}>"
