# 서버 기록의 예외 trace 에 예외 문구가 남지 않는지 보는 테스트.
#
# 예외 문구에는 상담 발화가 섞일 수 있다(SQL 오류의 매개변수 · 입력 검증 오류의 입력 값 · AI 쪽 원인 예외 문구).
# logger.exception 은 원인 예외까지 문구를 그대로 적으므로, 오류 응답 · DB 에서 문구를 빼도 서버 기록에 남았다.
# core/logging.install_safe_exception_text 가 기록을 만들 때 trace 를 예외 종류 · 호출 위치만으로 채운다.

import io
import logging
import sys
import threading
import traceback
import types
import uuid
from typing import Iterator, Tuple

import pytest
from fastapi.testclient import TestClient

from app.adapters.ai_adapter import AIError, set_ai_adapter_override
from app.adapters.stt_adapter import set_stt_adapter_override
from app.core.database import SessionLocal
from app.core.errors import ErrorCode
from app.core import logging as app_logging
from app.core.logging import install_safe_exception_text, safe_exception_text
from app.main import app
from app.models.session import ConsultationSession
from app.services import analysis_service, case_service, session_service
from tests.conftest import upload_audio
from tests.test_analysis import _get_analysis, _run_analysis, confirmed_session
from tests.test_analysis_late_results import WAIT_SECONDS, _pass_stale_time, _saved
from tests.test_stt_transcript import _get_transcript, _run_stt

# 가상 발화. 실제 상담 자료가 아니다.
MARKER = "가상 발화 원문 표식 LOGTRACE-7731"


# =========================================================
# safe_exception_text
# =========================================================

def _inner() -> None:
    raise ValueError(MARKER)


def _middle() -> None:
    try:
        _inner()
    except ValueError as error:
        raise RuntimeError(f"감쌈: {MARKER}") from error


def _outer() -> None:
    # 'from' 없이 다시 던져 처리 중 예외(__context__) 연결을 만든다.
    try:
        _middle()
    except RuntimeError:
        raise KeyError(MARKER)  # noqa: B904


def _caught(function) -> Tuple[type, BaseException, types.TracebackType]:
    try:
        function()
    except BaseException:
        return sys.exc_info()

    raise AssertionError("예외가 나야 한다")


def test_safe_text_keeps_types_and_call_sites_but_not_messages() -> None:
    exc_info = _caught(_outer)
    text = safe_exception_text(exc_info)

    assert MARKER not in text
    assert "LOGTRACE" not in text

    # 원인부터 파이썬 기본 trace 와 같은 순서 · 머리말이다.
    names = ["ValueError: <문구 생략>", "RuntimeError: <문구 생략>", "KeyError: <문구 생략>"]
    positions = [text.index(name) for name in names]

    assert positions == sorted(positions)
    assert "The above exception was the direct cause of the following exception:" in text
    assert "During handling of the above exception, another exception occurred:" in text

    # 호출 위치(함수 이름)는 남는다. trace 묶음 수도 기본 trace 와 같다.
    for function in ("_inner", "_middle", "_outer"):
        assert f"in {function}" in text

    standard = "".join(traceback.format_exception(*exc_info))

    assert text.count("Traceback (most recent call last):") == standard.count(
        "Traceback (most recent call last):"
    )
    assert MARKER in standard


def test_safe_text_hides_suppressed_context_notes_and_group_messages() -> None:
    def suppressed() -> None:
        try:
            _inner()
        except ValueError:
            raise LookupError(MARKER) from None

    text = safe_exception_text(_caught(suppressed))

    assert "ValueError" not in text
    assert text.endswith("LookupError: <문구 생략>")

    def noted() -> None:
        error = TypeError(MARKER)
        error.add_note(MARKER)
        raise error

    assert MARKER not in safe_exception_text(_caught(noted))

    def grouped() -> None:
        raise ExceptionGroup(MARKER, [ValueError(MARKER), TypeError(MARKER)])

    text = safe_exception_text(_caught(grouped))

    assert MARKER not in text
    assert "ExceptionGroup: <문구 생략> (하위 예외: ValueError, TypeError)" in text


def test_safe_text_handles_unraised_errors_and_cycles() -> None:
    error = RuntimeError(MARKER)

    assert safe_exception_text((RuntimeError, error, None)) == "RuntimeError: <문구 생략>"
    assert safe_exception_text((None, None, None)) == ""

    first = ValueError(MARKER)
    second = TypeError(MARKER)
    first.__context__ = second
    second.__context__ = first

    text = safe_exception_text((ValueError, first, None))

    assert MARKER not in text
    assert text.count("<문구 생략>") == 2


def test_long_chain_says_older_causes_were_left_out() -> None:
    error = RuntimeError(MARKER)

    for _ in range(25):
        wrapper = RuntimeError(MARKER)
        wrapper.__cause__ = error
        error = wrapper

    text = safe_exception_text((RuntimeError, error, None))

    assert MARKER not in text
    assert text.startswith("(더 앞선 원인 예외는 생략, 가까운 20개만 적음)")
    assert text.count("RuntimeError: <문구 생략>") == 20


def test_app_module_name_is_kept() -> None:
    error = AIError(MARKER, ErrorCode.AI_FAILED)

    assert safe_exception_text((AIError, error, None)) == "app.adapters.ai_adapter.AIError: <문구 생략>"


# =========================================================
# 모든 로거 · 형식에 걸리는지
# =========================================================

@pytest.fixture
def plain_handler() -> Iterator[Tuple[logging.Handler, io.StringIO]]:
    """앱 형식이 아닌 기본 Formatter 로 적는 handler. 어느 형식이든 같은 글이 나가는지 본다."""

    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(logging.Formatter("%(name)s %(message)s"))

    yield handler, stream


@pytest.mark.parametrize(
    "logger_name",
    ["app.services.analysis_service", "uvicorn.error", "sqlalchemy.engine", "asyncio"],
)
def test_every_logger_writes_trace_without_message(plain_handler, logger_name: str) -> None:
    handler, stream = plain_handler
    logger = logging.getLogger(logger_name)
    logger.addHandler(handler)

    try:
        try:
            _middle()
        except RuntimeError as error:
            logger.exception("처리 중 오류 session_id=%s", "abc")
            caught = error

        # except 밖에서 예외 객체를 넘겨도 같다(uvicorn 의 'Exception in ASGI application' 모양).
        logger.error("Exception in ASGI application", exc_info=caught)
    finally:
        logger.removeHandler(handler)

    written = stream.getvalue()

    assert MARKER not in written
    assert written.count("RuntimeError: <문구 생략>") == 2
    assert written.count("ValueError: <문구 생략>") == 2
    assert "session_id=abc" in written


def test_failure_while_writing_trace_does_not_escape_or_leak(
    plain_handler, monkeypatch: pytest.MonkeyPatch
) -> None:
    """trace 를 적다 실패해도 logger 를 부른 쪽으로 오류가 올라가지 않고, 원래 trace(문구 포함)로 돌아가지도 않는다."""

    def broken(exc_info):
        raise ValueError("trace 실패")

    monkeypatch.setattr(app_logging, "safe_exception_text", broken)

    handler, stream = plain_handler
    logger = logging.getLogger("app.services.analysis_service")
    logger.addHandler(handler)

    try:
        try:
            _inner()
        except ValueError:
            logger.exception("처리 중 오류 session_id=%s", "abc")
    finally:
        logger.removeHandler(handler)

    written = stream.getvalue()

    assert MARKER not in written
    assert "ValueError: <문구 생략> (trace 를 적지 못함)" in written


def test_install_is_done_once_at_import() -> None:
    factory = logging.getLogRecordFactory()

    assert getattr(factory, "_ispot_safe_exception_text", False)

    install_safe_exception_text()

    assert logging.getLogRecordFactory() is factory


# =========================================================
# 실제 경로 — AI 분석 · STT · 처리되지 않은 오류
# =========================================================

class _RaisingAdapter:
    """분석에서 원문 표식이 든 예외를 낸다. mapped 면 어댑터처럼 AIError(AI_FAILED)로 감싼다."""

    name = "raising"

    def __init__(self, flavor: str) -> None:
        self.flavor = flavor

    def analyze(self, transcript_payload):
        if self.flavor == "raw":
            raise RuntimeError(MARKER)

        try:
            raise RuntimeError(MARKER)
        except RuntimeError as cause:
            raise AIError("AI 분석에 실패했습니다: RuntimeError", ErrorCode.AI_FAILED) from cause


@pytest.mark.parametrize("flavor", ["mapped", "raw"])
def test_analysis_failure_log_has_no_message(
    client: TestClient,
    counselor_headers,
    session: dict,
    caplog: pytest.LogCaptureFixture,
    flavor: str,
) -> None:
    confirmed_session(client, counselor_headers, session["id"])
    set_ai_adapter_override(_RaisingAdapter(flavor))

    with caplog.at_level(logging.ERROR):
        assert _run_analysis(client, counselor_headers, session["id"]).status_code == 202

    envelope = _get_analysis(client, counselor_headers, session["id"]).json()["data"]

    assert envelope["error"]["code"] == "AI_FAILED"
    assert MARKER not in caplog.text
    assert f"session_id={session['id']}" in caplog.text
    assert "RuntimeError: <문구 생략>" in caplog.text


class _HeldRaisingAdapter(_RaisingAdapter):
    """분석을 붙잡아 두었다가 풀리면 예외를 낸다. 멈춤 판정이 먼저 마감한 뒤의 늦은 실패를 만든다."""

    def __init__(self, flavor: str) -> None:
        super().__init__(flavor)
        self.entered = threading.Event()
        self.release = threading.Event()

    def analyze(self, transcript_payload):
        self.entered.set()
        self.release.wait(timeout=WAIT_SECONDS)

        return super().analyze(transcript_payload)


@pytest.mark.parametrize("flavor", ["mapped", "raw"])
def test_discarded_late_failure_log_has_no_message(
    client: TestClient,
    counselor_headers,
    counselor_id,
    session: dict,
    caplog: pytest.LogCaptureFixture,
    flavor: str,
) -> None:
    """멈춤 판정이 마감한 뒤 늦게 난 실패는 저장하지 않는다. 버리기 전에 남는 trace 에도 문구가 없다."""

    confirmed_session(client, counselor_headers, session["id"])
    adapter = _HeldRaisingAdapter(flavor)
    set_ai_adapter_override(adapter)

    with SessionLocal() as db:
        item = db.get(ConsultationSession, uuid.UUID(session["id"]))
        analysis_id = analysis_service.request_analysis(
            db, item, types.SimpleNamespace(id=counselor_id)
        ).id

    worker = threading.Thread(
        target=analysis_service.process_analysis,
        args=(uuid.UUID(session["id"]), analysis_id),
        daemon=True,
    )

    with caplog.at_level(logging.WARNING):
        worker.start()

        try:
            assert adapter.entered.wait(WAIT_SECONDS)
            _pass_stale_time(session["id"])

            with SessionLocal() as db:
                item = db.get(ConsultationSession, uuid.UUID(session["id"]))

                assert session_service.expire_stale_processing(db, item)
        finally:
            adapter.release.set()
            worker.join(WAIT_SECONDS)

    assert not worker.is_alive()

    stored = _saved(session["id"], analysis_id)

    assert stored["analysis_message"] == session_service._STALE_MESSAGE
    assert "늦은 실패를 버렸습니다" in caplog.text
    assert MARKER not in caplog.text
    # 버리기 전에 원인 trace 는 남는다(종류 · 위치만).
    assert "RuntimeError: <문구 생략>" in caplog.text


class _RaisingSTTAdapter:
    def transcribe(self, audio_path):
        raise RuntimeError(MARKER)


def test_stt_unexpected_error_log_has_no_message(
    client: TestClient,
    counselor_headers,
    session: dict,
    caplog: pytest.LogCaptureFixture,
) -> None:
    assert upload_audio(client, counselor_headers, session["id"])[0] == 201
    set_stt_adapter_override(_RaisingSTTAdapter())

    with caplog.at_level(logging.ERROR):
        assert _run_stt(client, counselor_headers, session["id"]).status_code == 202

    envelope = _get_transcript(client, counselor_headers, session["id"]).json()["data"]

    assert envelope["session_status"] == "STT_FAILED"
    assert MARKER not in caplog.text
    assert f"session_id={session['id']}" in caplog.text
    assert "RuntimeError: <문구 생략>" in caplog.text


def test_unhandled_request_error_log_has_no_message(
    counselor_headers,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    def broken_list_cases(*args, **kwargs):
        raise RuntimeError(MARKER)

    monkeypatch.setattr(case_service, "list_cases", broken_list_cases)

    with caplog.at_level(logging.ERROR):
        with TestClient(app, raise_server_exceptions=False) as raw_client:
            response = raw_client.get("/api/v1/cases", headers=counselor_headers)

    assert response.status_code == 500
    assert MARKER not in response.text
    assert MARKER not in caplog.text
    assert "처리되지 않은 오류" in caplog.text
    assert "RuntimeError: <문구 생략>" in caplog.text
