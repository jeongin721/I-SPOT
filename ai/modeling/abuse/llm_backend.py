"""
2차 세부유형 분석/상담요약/체크리스트에 쓸 LLM 백엔드를 선택한다.

기본은 로컬 Ollama(qwen2.5:14b-instruct)이고, 환경변수로 외부 OpenAI
호출로 되돌릴 수 있다. Ollama는 http://localhost:11434/v1 에서 OpenAI
호환 API를 그대로 제공하므로, openai 파이썬 SDK의 base_url만 바꾸면 된다
(second_stage_llm.py/checklist_llm.py 등 호출부 코드는 그대로 둔다).

qwen2.5:14b-instruct / exaone3.5:7.8b / qwen2.5:32b 세 모델을 실사례
2건(신체학대, 방임-부정응답 오탐유발)으로 비교한 결과, 세 모델 모두 탐지
정확도는 동일했고 qwen2.5:14b-instruct가 가장 빨라(81.8s/55.3s) 기본값으로
선택했다.

환경변수:
    LLM_BACKEND      "ollama"(기본) 또는 "openai"
    OLLAMA_MODEL      LLM_BACKEND=ollama일 때 사용할 모델 태그
                       (기본값 "qwen2.5:14b-instruct")
    OLLAMA_BASE_URL   기본값 http://localhost:11434/v1
"""

import os
from typing import Optional, Tuple

from openai import OpenAI


DEFAULT_OLLAMA_BASE_URL = "http://localhost:11434/v1"
DEFAULT_OLLAMA_MODEL = "qwen2.5:14b-instruct"


def build_llm_client_and_model(
    default_openai_model: str,
) -> Tuple[OpenAI, str]:
    """
    (client, model_name)을 반환한다.

    LLM_BACKEND=ollama면 로컬 Ollama 서버를 가리키는 client와
    OLLAMA_MODEL을 반환하고, 그 외에는 기존과 동일하게 OpenAI를 쓴다.
    """

    backend = os.environ.get(
        "LLM_BACKEND",
        "ollama",
    ).lower()

    if backend == "openai":
        return _build_openai_client(), default_openai_model

    return _build_ollama_client_and_model()


def _build_ollama_client_and_model() -> Tuple[OpenAI, str]:
    model = os.environ.get(
        "OLLAMA_MODEL",
        DEFAULT_OLLAMA_MODEL,
    )

    base_url = os.environ.get(
        "OLLAMA_BASE_URL",
        DEFAULT_OLLAMA_BASE_URL,
    )

    # Ollama는 API 키를 검사하지 않지만, OpenAI SDK가 빈 키를 거부하므로
    # 더미 값을 넣는다.
    client = OpenAI(
        base_url=base_url,
        api_key="ollama",
    )

    return client, model


def _build_openai_client() -> OpenAI:
    api_key = os.environ.get(
        "OPENAI_API_KEY"
    )

    if not api_key:
        raise RuntimeError(
            "환경변수 OPENAI_API_KEY가 설정되어 있지 않습니다."
        )

    return OpenAI(
        api_key=api_key
    )
