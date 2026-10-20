# ai/modeling/abuse/second_stage_llm._call_llm_with_retry 가 stop_event 를 보고 재시도를 멈추는지 고정하는 테스트.
#
# analyze_audio_session 은 네 호출(상담기록 · 체크리스트 · 기록 초안 · 보호요인)을 동시에 돌리고, 하나가 실패하면
# 기다리지 않고 바로 실패를 돌려준다(PR #57). 그 뒤에도 남은 호출이 재시도를 계속 보내던 문제를 PR #66 이
# threading.Event 로 막았고, 재시도 사이 대기도 신호가 켜지면 바로 깨어나게 했다(이경진 님 ai-modeling 4f94554).
# 처음에는 저장소 최상위 tests/ 에 있었는데 CI 는 backend/ 의 pytest 만 돌리므로 여기로 옮겼다.
#
#   1) 신호가 이미 켜져 있으면 요청을 하나도 보내지 않는다.
#   2) 재시도 대기 중에 신호가 켜지면 대기를 다 채우지 않고 바로 멈춘다.
#   3) 신호를 안 넘기거나 끝까지 안 켜면 기존 재시도 동작 그대로다.
#
# OpenAI 호출은 가짜 client 로 바꾼다. CI 에는 openai 가 없어 설치되지 않았으면 가짜 모듈로 채운다
# (second_stage_llm 은 import 할 때 OpenAI 이름만 가져온다, test_modeling_ai_adapter.py 와 같은 방식).

import importlib
import importlib.util
import sys
import threading
import time
import types
from typing import Any, Callable

import pytest

from app.adapters.module_loader import ensure_repo_root_on_path

PACKAGE = "ai.modeling.abuse"
SECOND_STAGE = "ai.modeling.abuse.second_stage_llm"


class _FakeMessage:
    content = "{}"


class _FakeChoice:
    message = _FakeMessage()


class _FakeResponse:
    choices = [_FakeChoice()]


class _FakeCompletions:
    def __init__(self, fail_count: int = 0):
        self.calls = 0
        self.fail_count = fail_count

    def create(self, **kwargs: Any) -> _FakeResponse:
        self.calls += 1

        if self.calls <= self.fail_count:
            raise RuntimeError("일시적 오류(테스트)")

        return _FakeResponse()


class _FakeChat:
    def __init__(self, completions: _FakeCompletions):
        self.completions = completions


class _FakeClient:
    # _call_llm_with_retry 는 base_url 로 Ollama 와 OpenAI 를 가른다. OpenAI 경로를 타게 한다.
    base_url = "https://api.openai.com/v1"

    def __init__(self, fail_count: int = 0):
        self.completions = _FakeCompletions(fail_count)
        self.chat = _FakeChat(self.completions)


@pytest.fixture
def call_llm_with_retry(monkeypatch: pytest.MonkeyPatch) -> Callable[..., Any]:
    ensure_repo_root_on_path()

    if importlib.util.find_spec("openai") is None:
        fake_openai = types.ModuleType("openai")
        fake_openai.OpenAI = object
        monkeypatch.setitem(sys.modules, "openai", fake_openai)

    # 가짜 openai 로 import 한 모듈이 다른 시험에 남지 않게, sys.modules 와 부모 패키지 속성을
    # 비운 뒤 새로 import 하고 끝나면 원래대로 되돌린다.
    package = importlib.import_module(PACKAGE)
    saved_module = sys.modules.pop(SECOND_STAGE, None)
    saved_attr = package.__dict__.pop("second_stage_llm", None)

    module = importlib.import_module(SECOND_STAGE)

    yield module._call_llm_with_retry

    sys.modules.pop(SECOND_STAGE, None)
    package.__dict__.pop("second_stage_llm", None)

    if saved_module is not None:
        sys.modules[SECOND_STAGE] = saved_module

    if saved_attr is not None:
        package.second_stage_llm = saved_attr


def _call(call_llm_with_retry: Callable[..., Any], client: _FakeClient, **kwargs: Any) -> Any:
    return call_llm_with_retry(
        client=client,
        model="test-model",
        system_prompt="s",
        user_prompt="u",
        **kwargs,
    )


def test_stop_event_already_set_skips_request(call_llm_with_retry) -> None:
    client = _FakeClient(fail_count=0)
    stop_event = threading.Event()
    stop_event.set()

    with pytest.raises(RuntimeError):
        _call(call_llm_with_retry, client, max_retries=3, stop_event=stop_event)

    assert client.completions.calls == 0


def test_stop_event_set_during_backoff_wakes_immediately(call_llm_with_retry) -> None:
    # 첫 시도가 실패하면 1초 쉬고 다시 보낸다. 0.3초 뒤 신호를 켜면 1초를 다 채우지 않고 멈춰야 한다.
    # time.sleep 으로 쉬던 때는 1초를 다 채운 뒤에야 멈췄으므로 0.9초 안에 끝나는지로 가른다.
    client = _FakeClient(fail_count=10)
    stop_event = threading.Event()

    def set_after_delay() -> None:
        time.sleep(0.3)
        stop_event.set()

    threading.Thread(target=set_after_delay, daemon=True).start()

    started = time.monotonic()

    with pytest.raises(RuntimeError):
        _call(call_llm_with_retry, client, max_retries=5, stop_event=stop_event)

    elapsed = time.monotonic() - started

    assert elapsed < 0.9
    assert client.completions.calls == 1


def test_without_stop_event_retry_behavior_unchanged(call_llm_with_retry) -> None:
    client = _FakeClient(fail_count=1)

    result = _call(call_llm_with_retry, client, max_retries=3)

    assert result == {}
    assert client.completions.calls == 2


def test_stop_event_never_set_retry_behavior_unchanged(call_llm_with_retry) -> None:
    client = _FakeClient(fail_count=1)
    stop_event = threading.Event()

    result = _call(call_llm_with_retry, client, max_retries=3, stop_event=stop_event)

    assert result == {}
    assert client.completions.calls == 2
