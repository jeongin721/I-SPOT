# 외부 Service(STT/LLM) 호출에 timeout 을 적용한다.
#
# 9월 MVP 는 Queue Infrastructure 를 도입하지 않는다.(03_BACKEND_PROMPT.md §11)
# 따라서 FastAPI BackgroundTasks + Thread timeout 조합만 사용한다.

from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from typing import Callable, TypeVar

T = TypeVar("T")


class OperationTimeout(Exception):
    """지정한 시간 안에 외부 호출이 끝나지 않은 경우."""


def run_with_timeout(func: Callable[[], T], timeout_seconds: float) -> T:
    """
    func 을 별도 thread 에서 실행하고 timeout 을 적용한다.

    Timeout 이 발생해도 thread 자체를 강제 종료할 수는 없으므로,
    호출 측은 결과를 버리고 실패로 처리한다.
    """

    executor = ThreadPoolExecutor(max_workers=1)

    try:
        future = executor.submit(func)

        try:
            return future.result(timeout=timeout_seconds)
        except FutureTimeoutError as error:
            future.cancel()
            raise OperationTimeout(
                f"외부 서비스 응답이 {timeout_seconds}초 안에 오지 않았습니다."
            ) from error
    finally:
        # 남은 thread 를 기다리지 않고 반환한다.
        executor.shutdown(wait=False, cancel_futures=True)
