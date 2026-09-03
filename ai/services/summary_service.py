# Transcript를 LLM에 전달해 상담 요약을 Structured Output으로 생성한다.
# API 오류 처리, 출력 검증 및 Grounding Validator 연결을 담당한다.

import json
import os
from pathlib import Path
from typing import List, Literal

from openai import (
    APIConnectionError,
    APITimeoutError,
    AuthenticationError,
    OpenAI,
    RateLimitError,
)
from pydantic import BaseModel

from ai.schemas.analysis import AIAnalysisOutput, Summary, Transcript

from ai.services.grounding_validator import validate_summary_grounding


PROMPT_PATH = (
    Path(__file__).resolve().parent.parent
    / "prompts"
    / "consultation_summary.txt"
)


# =========================================================
# Service Exceptions
# =========================================================

class SummaryServiceError(Exception):
    """상담 요약 서비스 기본 오류."""


class SummaryTimeoutError(SummaryServiceError):
    """LLM 응답 시간 초과."""


class SummaryAuthenticationError(SummaryServiceError):
    """LLM API 인증 오류."""


class SummaryQuotaError(SummaryServiceError):
    """LLM API 사용량 또는 크레딧 오류."""


class SummaryConnectionError(SummaryServiceError):
    """LLM API 연결 오류."""


class SummaryOutputError(SummaryServiceError):
    """LLM 출력 형식 또는 검증 오류."""


# =========================================================
# LLM Structured Output Schema
# =========================================================

class SummaryLLMBody(BaseModel):
    overview: str
    key_points: List[str]


class SummaryLLMOutput(BaseModel):
    """
    OpenAI Structured Output 전용 Schema.

    현재 1차 구현에서는 요약 기능만 수행하며
    위험 관련 필드는 빈 배열이어야 한다.
    """

    schema_version: Literal["1.0"]
    summary: SummaryLLMBody

    risk_utterances: List[str]
    abuse_signals: List[str]
    risk_factors: List[str]

    warnings: List[str]


# =========================================================
# Prompt / Input
# =========================================================

def load_summary_prompt() -> str:
    """상담 요약 프롬프트를 불러온다."""

    return PROMPT_PATH.read_text(
        encoding="utf-8"
    )


def build_transcript_input(
    transcript: Transcript,
) -> str:
    """Transcript를 LLM 입력용 JSON 문자열로 변환한다."""

    return json.dumps(
        transcript.model_dump(),
        ensure_ascii=False,
        indent=2,
    )


# =========================================================
# Summary Service
# =========================================================

def summarize_consultation(
    transcript: Transcript,
) -> AIAnalysisOutput:
    """
    상담 Transcript를 LLM에 전달하고
    I-SPOT AIAnalysisOutput 형식으로 반환한다.
    """

    api_key = os.getenv("OPENAI_API_KEY")
    model = os.getenv("OPENAI_MODEL")

    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY 환경변수가 설정되지 않았습니다."
        )

    if not model:
        raise RuntimeError(
            "OPENAI_MODEL 환경변수가 설정되지 않았습니다."
        )

    client = OpenAI(
        api_key=api_key
    )

    system_prompt = load_summary_prompt()

    transcript_input = build_transcript_input(
        transcript
    )

    try:
        response = client.responses.parse(
            model=model,
            input=[
                {
                    "role": "system",
                    "content": system_prompt,
                },
                {
                    "role": "user",
                    "content": transcript_input,
                },
            ],
            text_format=SummaryLLMOutput,
        )

    except APITimeoutError as error:
        raise SummaryTimeoutError(
            "LLM 상담 요약 요청 시간이 초과되었습니다."
        ) from error

    except AuthenticationError as error:
        raise SummaryAuthenticationError(
            "LLM API 인증에 실패했습니다."
        ) from error

    except RateLimitError as error:
        raise SummaryQuotaError(
            "LLM API 사용량 제한 또는 크레딧을 확인해야 합니다."
        ) from error

    except APIConnectionError as error:
        raise SummaryConnectionError(
            "LLM API에 연결할 수 없습니다."
        ) from error

    parsed = response.output_parsed

    if parsed is None:
        raise SummaryOutputError(
            "LLM 응답을 Structured Output으로 변환하지 못했습니다."
        )

    # 현재 1차 요약 단계에서는
    # 위험 분석 결과를 생성하지 않는다.
    if (
        parsed.risk_utterances
        or parsed.abuse_signals
        or parsed.risk_factors
    ):
        raise SummaryOutputError(
            "요약 단계에서 허용되지 않은 위험 분석 결과가 생성되었습니다."
        )

    summary = Summary(
    overview=parsed.summary.overview,
    key_points=parsed.summary.key_points,
)

    grounding_warnings = validate_summary_grounding(
        summary=summary,
        transcript=transcript,
    )

    warnings = list(
        dict.fromkeys(
            parsed.warnings
            + grounding_warnings
        )
    )

    return AIAnalysisOutput(
        schema_version="1.0",
        summary=summary,
        risk_utterances=[],
        abuse_signals=[],
        risk_factors=[],
        warnings=warnings,
    )