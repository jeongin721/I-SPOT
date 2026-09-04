# AI(요약/분석) Adapter.
#
# 호출 경로: router → service → ai_adapter → 팀 B AI Pipeline
#
# Frontend 가 LLM Provider 를 직접 호출하지 않게 하고,
# 팀 B 의 Structured JSON Contract 를 변형 없이 그대로 저장/전달한다.

import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol

from pydantic import ValidationError

from app.adapters.module_loader import ensure_repo_root_on_path
from app.core.config import settings
from app.core.errors import ErrorCode
from app.schemas.contracts import AIAnalysisResult, SummaryEvidenceItem


class AIError(Exception):
    """AI 분석 실패. error_code 로 API 오류 코드를 함께 전달한다."""

    def __init__(self, message: str, error_code: ErrorCode = ErrorCode.AI_FAILED) -> None:
        super().__init__(message)
        self.error_code = error_code


@dataclass
class AIAnalysisBundle:
    """Adapter 반환값. Contract 결과와 부가 근거 정보를 분리해서 담는다."""

    result: AIAnalysisResult
    summary_evidence: List[SummaryEvidenceItem] = field(default_factory=list)
    provider: str = "mock"
    model: Optional[str] = None


class AIAdapter(Protocol):
    name: str

    def analyze(self, transcript_payload: Dict[str, Any]) -> AIAnalysisBundle:
        ...


# =========================================================
# Mock Adapter
# =========================================================

class MockAIAdapter:
    """
    LLM 호출 없이 Backend/Frontend 통합을 진행하기 위한 Mock.

    실제 Transcript 의 segment 를 근거로 사용하므로
    "원문에 없는 내용 생성" 을 하지 않는다.
    """

    name = "mock"

    def analyze(self, transcript_payload: Dict[str, Any]) -> AIAnalysisBundle:
        segments = transcript_payload.get("segments") or []

        if not segments:
            raise AIError(
                "분석할 Transcript segment 가 없습니다.",
                ErrorCode.AI_INVALID_OUTPUT,
            )

        child_segments = [
            segment for segment in segments if segment.get("speaker") == "CHILD"
        ]

        key_points: List[str] = []
        evidence: List[SummaryEvidenceItem] = []

        for segment in child_segments[:3]:
            text = (segment.get("text") or "").strip()

            if not text:
                continue

            key_points.append(text)
            evidence.append(
                SummaryEvidenceItem(
                    key_point=text,
                    segment_ids=[segment.get("segment_id", "")],
                    score=1.0,
                )
            )

        overview = (
            f"상담 발화 {len(segments)}건에 대한 요약입니다. "
            "상담사 검토가 필요합니다."
        )

        warnings = ["Mock AI Provider 결과입니다. 실제 분석 결과가 아닙니다."]

        low_confidence = [
            segment
            for segment in segments
            if float(segment.get("confidence") or 0) < 0.7
        ]

        if low_confidence:
            warnings.append(
                f"저신뢰 구간 {len(low_confidence)}건이 있어 추가 확인이 필요합니다."
            )

        result = AIAnalysisResult(
            schema_version="1.0",
            summary={"overview": overview, "key_points": key_points},
            risk_utterances=[],
            abuse_signals=[],
            risk_factors=[],
            warnings=warnings,
        )

        return AIAnalysisBundle(
            result=result,
            summary_evidence=evidence,
            provider=self.name,
            model="mock-ai-1.0",
        )


# =========================================================
# Pipeline Adapter (팀 B run_analysis_pipeline)
# =========================================================

def export_llm_env() -> None:
    """
    팀 B pipeline 이 사용하는 LLM 설정을 process 환경변수로 넘긴다.

    ai/services/summary_service.py 는 OPENAI_API_KEY / OPENAI_MODEL 을
    os.getenv 로 직접 읽지만, pydantic-settings 의 .env 로딩은
    os.environ 을 채우지 않는다. 그래서 .env 에만 Key 를 넣으면
    pipeline 이 값을 찾지 못한다.

    이미 process 환경에 값이 있으면(배포 환경/Secret 주입) 그 값을 우선한다.
    """

    for name in ("OPENAI_API_KEY", "OPENAI_MODEL"):
        value = getattr(settings, name, "")

        if value and not os.getenv(name):
            os.environ[name] = value


class PipelineAIAdapter:
    """ai/services/analysis_pipeline.run_analysis_pipeline 을 호출한다."""

    name = "pipeline"

    def analyze(self, transcript_payload: Dict[str, Any]) -> AIAnalysisBundle:
        ensure_repo_root_on_path()
        export_llm_env()

        try:
            from ai.schemas.analysis import Transcript
            from ai.services.analysis_pipeline import run_analysis_pipeline
        except ImportError as error:
            raise AIError(
                f"AI Pipeline module 을 import 할 수 없습니다: {error}",
                ErrorCode.AI_FAILED,
            ) from error

        try:
            transcript = Transcript.model_validate(transcript_payload)
        except ValidationError as error:
            raise AIError(
                f"Transcript 가 AI Pipeline 입력 형식을 만족하지 않습니다: {error.error_count()}건",
                ErrorCode.AI_INVALID_OUTPUT,
            ) from error

        try:
            pipeline_result = run_analysis_pipeline(transcript)
        except Exception as error:
            raise self._map_pipeline_error(error) from error

        return self._to_bundle(pipeline_result)

    # -----------------------------------------------------
    # 내부 helper
    # -----------------------------------------------------

    def _map_pipeline_error(self, error: Exception) -> AIError:
        """팀 B Service Exception 을 Backend 오류 코드로 변환한다."""

        name = type(error).__name__

        mapping = {
            "SummaryTimeoutError": ErrorCode.AI_TIMEOUT,
            "SummaryAuthenticationError": ErrorCode.AI_AUTH_ERROR,
            "SummaryQuotaError": ErrorCode.AI_QUOTA_ERROR,
            "SummaryConnectionError": ErrorCode.AI_FAILED,
            "SummaryOutputError": ErrorCode.AI_INVALID_OUTPUT,
        }

        code = mapping.get(name, ErrorCode.AI_FAILED)

        return AIError(str(error) or "AI 분석에 실패했습니다.", code)

    def _to_bundle(self, pipeline_result: Any) -> AIAnalysisBundle:
        analysis = getattr(pipeline_result, "analysis", None)

        if analysis is None:
            raise AIError(
                "AI Pipeline 결과에 analysis 가 없습니다.",
                ErrorCode.AI_INVALID_OUTPUT,
            )

        try:
            result = AIAnalysisResult.model_validate(
                analysis.model_dump() if hasattr(analysis, "model_dump") else analysis
            )
        except ValidationError as error:
            raise AIError(
                f"AI 결과가 AI Output Contract 를 만족하지 않습니다: {error.error_count()}건",
                ErrorCode.AI_INVALID_OUTPUT,
            ) from error

        evidence: List[SummaryEvidenceItem] = []

        for link in getattr(pipeline_result, "summary_evidence", []) or []:
            raw = link.model_dump() if hasattr(link, "model_dump") else dict(link)

            evidence.append(
                SummaryEvidenceItem(
                    key_point=raw.get("text", "") or raw.get("key_point", ""),
                    segment_ids=list(raw.get("segment_ids") or []),
                    score=float(raw.get("score") or 0.0),
                )
            )

        return AIAnalysisBundle(
            result=result,
            summary_evidence=evidence,
            provider=self.name,
            model=os.getenv("OPENAI_MODEL"),
        )


# =========================================================
# Factory
# =========================================================

_override: Optional[AIAdapter] = None


def set_ai_adapter_override(adapter: Optional[AIAdapter]) -> None:
    """테스트에서 AI 성공/실패/Timeout/잘못된 JSON 을 주입하기 위한 hook."""

    global _override
    _override = adapter


def get_ai_adapter() -> AIAdapter:
    if _override is not None:
        return _override

    if settings.AI_PROVIDER == "pipeline":
        return PipelineAIAdapter()

    return MockAIAdapter()


__all__ = [
    "AIAdapter",
    "AIAnalysisBundle",
    "AIError",
    "MockAIAdapter",
    "PipelineAIAdapter",
    "export_llm_env",
    "get_ai_adapter",
    "set_ai_adapter_override",
]
