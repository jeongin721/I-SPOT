# 서버 접속 기록(uvicorn)에 쿼리 값이 남지 않는지 확인하는 테스트.
#
# uvicorn 은 요청마다 요청 주소 전체(경로 + ? 뒤 쿼리)를 접속 기록에 남긴다. 쿼리에는 사례 검색어(?search=) ·
# 감사 기록 필터(?status=) 같은 입력 값이 그대로 들어 있어, 정상 요청이든 거절한 요청이든 서버 기록에 남았다.
# app/core/logging.py 의 필터가 ? 뒤를 빼고 경로 · 상태 코드만 남기는지 본다.

import base64
import logging
import os
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Iterator, List, Tuple

import httpx
import pytest
import uvicorn
from uvicorn.logging import AccessFormatter

from app.core.logging import (
    AccessLogQueryFilter,
    WebSocketLogQueryFilter,
    install_server_log_filters,
)
from app.main import app

BACKEND = Path(__file__).resolve().parents[1]

MARKER = "QUERY_VALUE_MARKER"

# uvicorn(protocols/http/*_impl.py)이 접속 기록을 남기는 모양. 인자는 (접속 주소, method, 경로+쿼리, HTTP 버전, 상태 코드).
ACCESS_FORMAT = '%s - "%s %s HTTP/%s" %d'


def _record(msg: object, args: object, name: str = "uvicorn.access") -> logging.LogRecord:
    return logging.LogRecord(name, logging.INFO, __file__, 0, msg, args, None)


# =========================================================
# 필터 단위
# =========================================================


def test_access_filter_removes_query_string() -> None:
    record = _record(ACCESS_FORMAT, ("127.0.0.1:50000", "GET", f"/api/v1/cases?search={MARKER}&page=2", "1.1", 200))

    assert AccessLogQueryFilter().filter(record) is True
    assert record.getMessage() == '127.0.0.1:50000 - "GET /api/v1/cases HTTP/1.1" 200'


def test_access_filter_keeps_path_without_query() -> None:
    args = ("127.0.0.1:50000", "POST", "/api/v1/auth/login", "1.1", 401)
    record = _record(ACCESS_FORMAT, args)

    assert AccessLogQueryFilter().filter(record) is True
    assert record.args == args


def test_access_filter_cuts_at_first_question_mark_only() -> None:
    # uvicorn 은 경로 안의 ? 를 %3F 로 적으므로(urllib.parse.quote) 처음 나오는 ? 가 쿼리의 시작이다.
    record = _record(ACCESS_FORMAT, ("127.0.0.1:50000", "GET", f"/a%3Fb?search={MARKER}?x", "1.1", 404))

    AccessLogQueryFilter().filter(record)

    assert record.getMessage() == '127.0.0.1:50000 - "GET /a%3Fb HTTP/1.1" 404'


@pytest.mark.parametrize(
    "args",
    [
        ("127.0.0.1:50000", "GET", f"/api/v1/cases?search={MARKER}", "1.1"),  # 4개
        ("127.0.0.1:50000", "GET", f"/api/v1/cases?search={MARKER}", "1.1", 200, "extra"),  # 6개
        ("127.0.0.1:50000", "GET", f"/api/v1/cases?search={MARKER}".encode(), "1.1", 200),  # 글자가 아님
        ("127.0.0.1:50000", "GET", None, "1.1", 200),
        [("127.0.0.1:50000", "GET", f"/api/v1/cases?search={MARKER}", "1.1", 200)],  # tuple 이 아님
    ],
    ids=["four-args", "six-args", "bytes-path", "none-path", "list-args"],
)
def test_access_filter_passes_unknown_shapes_unchanged(args: object) -> None:
    # uvicorn 버전이 바뀌어 인자 모양이 달라지면 고치지 않고 그대로 남긴다(기록은 잃지 않는다).
    record = _record("%s", args)

    assert AccessLogQueryFilter().filter(record) is True
    assert record.args is args


@pytest.mark.parametrize("args", [None, ()], ids=["none", "empty"])
def test_access_filter_passes_records_without_args(args: object) -> None:
    record = _record(f"plain message ?search={MARKER}", args)

    assert AccessLogQueryFilter().filter(record) is True
    assert record.args == args
    assert record.getMessage() == f"plain message ?search={MARKER}"


def test_access_filter_passes_mapping_args_unchanged() -> None:
    record = _record("%(path)s", ({"path": f"/api/v1/cases?search={MARKER}"},))

    assert AccessLogQueryFilter().filter(record) is True
    assert MARKER in record.getMessage()


@pytest.mark.parametrize(
    ("msg", "args", "expected"),
    [
        (
            '%s - "WebSocket %s" [accepted]',
            ("127.0.0.1:50000", f"/ws?search={MARKER}"),
            '127.0.0.1:50000 - "WebSocket /ws" [accepted]',
        ),
        (
            '%s - "WebSocket %s" 403',
            ("127.0.0.1:50000", f"/api/v1/cases?search={MARKER}"),
            '127.0.0.1:50000 - "WebSocket /api/v1/cases" 403',
        ),
        (
            '%s - "WebSocket %s" %d',
            ("127.0.0.1:50000", f"/ws?status={MARKER}", 500),
            '127.0.0.1:50000 - "WebSocket /ws" 500',
        ),
    ],
    ids=["accepted", "rejected", "http-response"],
)
def test_websocket_filter_removes_query_string(msg: str, args: Tuple[object, ...], expected: str) -> None:
    record = _record(msg, args, name="uvicorn.error")

    assert WebSocketLogQueryFilter().filter(record) is True
    assert record.getMessage() == expected


@pytest.mark.parametrize(
    ("msg", "args"),
    [
        ("Started server process [%d]", (1234,)),
        ("%s %s", ("127.0.0.1:50000", f"/api/v1/cases?search={MARKER}")),
        ('%s - "WebSocket %s" 403', ("127.0.0.1:50000",)),
        ('%s - "WebSocket %s" 403', ("127.0.0.1:50000", b"/ws?x=1")),
        ({"not": "a string"}, None),
    ],
    ids=["other-message", "same-shape-other-message", "missing-path", "bytes-path", "non-string-msg"],
)
def test_websocket_filter_leaves_other_records(msg: object, args: object) -> None:
    # uvicorn.error 에는 시작 · 오류 기록도 오므로 WebSocket 연결 기록 모양만 고친다.
    record = _record(msg, args, name="uvicorn.error")

    assert WebSocketLogQueryFilter().filter(record) is True
    assert record.args is args


# =========================================================
# 앱 import 뒤 필터가 붙는지
# =========================================================


def _count(logger_name: str, filter_class: type) -> int:
    return sum(isinstance(item, filter_class) for item in logging.getLogger(logger_name).filters)


def test_app_import_installs_filters_once() -> None:
    # conftest 가 app.main 을 import 했으므로 이미 붙어 있어야 한다. 다시 불러도 겹쳐 붙지 않는다.
    assert _count("uvicorn.access", AccessLogQueryFilter) == 1
    assert _count("uvicorn.error", WebSocketLogQueryFilter) == 1

    install_server_log_filters()

    assert _count("uvicorn.access", AccessLogQueryFilter) == 1
    assert _count("uvicorn.error", WebSocketLogQueryFilter) == 1


# uvicorn 이 logging 을 설정(dictConfig)하는 때와 앱을 import 하는 때의 순서. 어느 쪽이든 필터가 남아야 한다.
_LOAD_ORDERS = {
    # `uvicorn app.main:app` 명령(Dockerfile · deploy/web-deploy.sh): Config 가 logging 을 먼저 설정하고 load 에서 앱을 import 한다.
    "command": "from uvicorn.config import Config\nConfig('app.main:app').load()\n",
    # uvicorn.run(app 객체): 앱을 먼저 import 하고 Config 가 그 뒤에 logging 을 설정한다.
    "app-object": "from app.main import app\nfrom uvicorn.config import Config\nConfig(app)\n",
}


@pytest.mark.parametrize("order", sorted(_LOAD_ORDERS))
def test_filter_survives_uvicorn_logging_config(order: str) -> None:
    # 이 프로세스의 logging 설정을 흐트리지 않도록 새 파이썬 프로세스에서 uvicorn 의 기본 logging 설정을 쓴다.
    code = (
        _LOAD_ORDERS[order]
        + "import logging\n"
        + f"logging.getLogger('uvicorn.access').info({ACCESS_FORMAT!r}, '127.0.0.1:50000', 'GET', "
        + f"'/api/v1/cases?search={MARKER}', '1.1', 200)\n"
    )

    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=BACKEND,
        env=dict(os.environ),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
    )

    assert result.returncode == 0, result.stderr
    assert '127.0.0.1:50000 - "GET /api/v1/cases HTTP/1.1" 200' in result.stdout
    assert MARKER not in result.stdout + result.stderr


# =========================================================
# 실제 uvicorn 서버
# =========================================================


class _ListHandler(logging.Handler):
    def __init__(self, formatter: logging.Formatter) -> None:
        super().__init__(level=logging.DEBUG)
        self.setFormatter(formatter)
        self.lines: List[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.lines.append(self.format(record))


@pytest.fixture(params=["h11", "httptools"])
def live_server(request: pytest.FixtureRequest) -> Iterator[Tuple[int, _ListHandler, _ListHandler]]:
    """
    이 테스트 프로세스 안에서 실제 uvicorn 서버를 띄운다. 접속 기록 · 서버 기록을 따로 모은다.

    HTTP 처리기 두 가지(h11, httptools — uvicorn[standard] 는 httptools 를 쓴다)가 접속 기록을 따로 남기므로 둘 다 본다.
    """

    http = request.param

    if http == "httptools":
        pytest.importorskip("httptools")

    access =_ListHandler(AccessFormatter('%(client_addr)s - "%(request_line)s" %(status_code)s', use_colors=False))
    server_log = _ListHandler(logging.Formatter("%(message)s"))
    loggers = [(logging.getLogger("uvicorn.access"), access), (logging.getLogger("uvicorn.error"), server_log)]
    saved_levels = [logger.level for logger, _ in loggers]

    for logger, handler in loggers:
        logger.setLevel(logging.INFO)
        logger.addHandler(handler)

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]

    # log_config=None: 이 프로세스의 logging 설정은 건드리지 않는다(dictConfig 순서는 위 시험이 본다).
    server = uvicorn.Server(uvicorn.Config(app, http=http, log_config=None, access_log=True, lifespan="off"))
    thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
    thread.start()

    try:
        deadline = time.monotonic() + 30

        while not server.started:
            assert thread.is_alive() and time.monotonic() < deadline, "uvicorn 서버가 뜨지 않았다"
            time.sleep(0.05)

        yield port, access, server_log
    finally:
        server.should_exit = True
        thread.join(timeout=15)
        sock.close()

        for (logger, handler), level in zip(loggers, saved_levels, strict=True):
            logger.removeHandler(handler)
            logger.setLevel(level)


def _websocket_status_line(port: int, target: str) -> str:
    key = base64.b64encode(os.urandom(16)).decode("ascii")
    request = (
        f"GET {target} HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
        f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n"
    )

    with socket.create_connection(("127.0.0.1", port), timeout=10) as conn:
        conn.sendall(request.encode("ascii"))

        return conn.recv(4096).split(b"\r\n", 1)[0].decode("latin-1")


def test_real_uvicorn_access_log_keeps_path_and_status_without_query(live_server) -> None:
    port, access, server_log = live_server

    with httpx.Client(base_url=f"http://127.0.0.1:{port}", trust_env=False, timeout=30) as client:
        health = client.get("/health")
        search = client.get("/api/v1/cases", params={"search": MARKER})
        audit = client.get("/api/v1/auth/audit-logs", params={"status": MARKER + "\x00"})

    # 앱에 WebSocket 창구는 없다. 그래도 uvicorn 은 거절(403)한 연결의 주소를 서버 기록에 남긴다.
    websocket = _websocket_status_line(port, f"/api/v1/cases?search={MARKER}")

    lines = access.lines + server_log.lines

    assert not [line for line in lines if MARKER in line], lines
    assert f'"GET /health HTTP/1.1" {health.status_code} OK' in "\n".join(access.lines)
    assert f'"GET /api/v1/cases HTTP/1.1" {search.status_code}' in "\n".join(access.lines)
    assert f'"GET /api/v1/auth/audit-logs HTTP/1.1" {audit.status_code}' in "\n".join(access.lines)
    assert " 403 " in websocket
    assert '"WebSocket /api/v1/cases" 403' in "\n".join(server_log.lines)
