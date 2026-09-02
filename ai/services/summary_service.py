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
from pydantic import BaseModel, Field

from ai.schemas.analysis import (
    AIAnalysisOutput,
    KeyPointItem,
    Summary,
    Transcript,
)
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

class LLMKeyPoint(BaseModel):
    point: str = Field(..., description="요약 핵심 내용")
    segment_ids: List[str] = Field(
        default_factory=list,
        description="근거 발화 segment ID 목록 (확인되지 않으면 빈 리스트)"
    )


class SummaryLLMBody(BaseModel):
    overview: str = Field(..., description="상담 전체 개요")
    key_points: List[LLMKeyPoint] = Field(
        default_factory=list,
        description="근거 segment ID가 포함된 핵심 요약 목록"
    )


class SummaryLLMOutput(BaseModel):
    schema_version: Literal["1.0"] = "1.0"
    summary: SummaryLLMBody
    risk_utterances: List[str] = Field(default_factory=list)
    abuse_signals: List[str] = Field(default_factory=list)
    risk_factors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


# =========================================================
# Prompt / Input
# =========================================================

def load_summary_prompt() -> str:
    if not PROMPT_PATH.exists():
        raise FileNotFoundError(f"프롬프트 파일을 찾을 수 없습니다: {PROMPT_PATH}")
    return PROMPT_PATH.read_text(encoding="utf-8")


def build_transcript_input(transcript: Transcript) -> str:
    return json.dumps(
        transcript.model_dump(),
        ensure_ascii=False,
        indent=2,
    )


# =========================================================
# Summary Service
# =========================================================

def summarize_consultation(transcript: Transcript) -> AIAnalysisOutput:
    api_key = os.getenv("OPENAI_API_KEY")
    model = (os.getenv("OPENAI_MODEL") or "gpt-4o-mini").strip()

    if not api_key:
        raise RuntimeError("OPENAI_API_KEY 환경변수가 설정되지 않았습니다.")

    client = OpenAI(api_key=api_key)
    system_prompt = load_summary_prompt()
    transcript_input = build_transcript_input(transcript)

    try:
        response = client.beta.chat.completions.parse(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": transcript_input},
            ],
            response_format=SummaryLLMOutput,
            temperature=0.0,
        )
    except APITimeoutError as error:
        raise SummaryTimeoutError("LLM 상담 요약 요청 시간이 초과되었습니다.") from error
    except AuthenticationError as error:
        raise SummaryAuthenticationError("LLM API 인증에 실패했습니다.") from error
    except RateLimitError as error:
        raise SummaryQuotaError("LLM API 사용량 제한 또는 크레딧을 확인해야 합니다.") from error
    except APIConnectionError as error:
        raise SummaryConnectionError("LLM API에 연결할 수 없습니다.") from error
    except Exception as error:
        raise SummaryServiceError("LLM 상담 요약 처리 중 오류가 발생했습니다.") from error

    parsed = response.choices[0].message.parsed
    if parsed is None:
        raise SummaryOutputError("LLM 응답을 Structured Output으로 변환하지 못했습니다.")

    if parsed.risk_utterances or parsed.abuse_signals or parsed.risk_factors:
        raise SummaryOutputError("요약 단계에서 허용되지 않은 위험 분석 결과가 생성되었습니다.")

    overview = parsed.summary.overview.strip()
    if not overview:
        overview = "추가 확인 필요"

    key_points = [
        KeyPointItem(point=item.point, segment_ids=item.segment_ids)
        for item in parsed.summary.key_points
    ]

    summary = Summary(
        overview=overview,
        key_points=key_points,
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