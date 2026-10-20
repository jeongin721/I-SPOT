# _call_llm_with_retry가 stop_event를 보고 재시도를 멈추는지 테스트한다
# (2026-10-20 Mingyu 리뷰 — PR #66). 세 가지를 검증한다: (1) stop_event가
# 이미 켜진 상태면 요청 자체를 보내지 않고 즉시 실패, (2) 백오프 대기
# 중간에 stop_event가 켜지면 대기를 다 채우지 않고 바로 멈춤, (3)
# stop_event가 끝까지 안 켜지면 기존 재시도 동작이 그대로 유지됨.

import threading
import time

import pytest

from ai.modeling.abuse.second_stage_llm import _call_llm_with_retry


class _FakeMessage:
    content = "{}"


class _FakeChoice:
    message = _FakeMessage()


class _FakeResponse:
    choices = [_FakeChoice()]


class _FakeCompletions:
    def __init__(self, fail_count=0):
        self.calls = 0
        self.fail_count = fail_count

    def create(self, **kwargs):
        self.calls += 1
        if self.calls <= self.fail_count:
            raise RuntimeError("일시적 오류(테스트)")
        return _FakeResponse()


class _FakeChat:
    def __init__(self, completions):
        self.completions = completions


class _FakeClient:
    # _call_llm_with_retry가 base_url로 Ollama/OpenAI를 구분하므로
    # OpenAI 경로(temperature/seed를 안 붙이는 경로)를 타게 한다.
    base_url = "https://api.openai.com/v1"

    def __init__(self, fail_count=0):
        self.completions = _FakeCompletions(fail_count)
        self.chat = _FakeChat(self.completions)


def test_stop_event_already_set_skips_request():
    client = _FakeClient(fail_count=0)
    stop_event = threading.Event()
    stop_event.set()

    with pytest.raises(RuntimeError):
        _call_llm_with_retry(
            client=client,
            model="gpt-5.6-luna",
            system_prompt="s",
            user_prompt="u",
            max_retries=3,
            stop_event=stop_event,
        )

    assert client.completions.calls == 0


def test_stop_event_set_during_backoff_wakes_immediately():
    client = _FakeClient(fail_count=10)
    stop_event = threading.Event()

    def set_after_delay():
        time.sleep(0.3)
        stop_event.set()

    threading.Thread(target=set_after_delay, daemon=True).start()

    t0 = time.monotonic()
    with pytest.raises(RuntimeError):
        # attempt 1 실패 -> 백오프 1초 대기 예정. 0.3초 뒤 stop_event가
        # 켜지므로 1초를 다 기다리지 않고 멈춰야 한다.
        _call_llm_with_retry(
            client=client,
            model="gpt-5.6-luna",
            system_prompt="s",
            user_prompt="u",
            max_retries=5,
            stop_event=stop_event,
        )
    elapsed = time.monotonic() - t0

    assert elapsed < 0.6
    assert client.completions.calls == 1


def test_without_stop_event_retry_behavior_unchanged():
    client = _FakeClient(fail_count=1)

    result = _call_llm_with_retry(
        client=client,
        model="gpt-5.6-luna",
        system_prompt="s",
        user_prompt="u",
        max_retries=3,
    )

    assert result == {}
    assert client.completions.calls == 2


def test_stop_event_never_set_retry_behavior_unchanged():
    client = _FakeClient(fail_count=1)
    stop_event = threading.Event()

    result = _call_llm_with_retry(
        client=client,
        model="gpt-5.6-luna",
        system_prompt="s",
        user_prompt="u",
        max_retries=3,
        stop_event=stop_event,
    )

    assert result == {}
    assert client.completions.calls == 2
