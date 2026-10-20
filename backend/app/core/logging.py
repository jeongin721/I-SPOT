# Logging 설정.
#
# docs/05_RULES.md 절대 금지: "상담 원문 전체를 일반 로그에 출력".
# 따라서 로그에는 식별자/개수/길이 등 metadata 만 남기고,
# 발화 텍스트는 redact_text() 를 거친 형태만 허용한다.
# 서버(uvicorn)의 접속 기록도 경로 · 상태 코드만 남기고 쿼리 값은 뺀다(install_server_log_filters).

import logging
import sys
from typing import Optional

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


def redact_text(text: Optional[str]) -> str:
    """
    상담 발화 텍스트를 로그에 남겨야 할 때 반드시 이 함수를 거친다.
    내용은 남기지 않고 길이만 남긴다.
    """

    if text is None:
        return "<none>"

    return f"<redacted len={len(text)}>"
