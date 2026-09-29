# AI(요약/분석) Adapter.
#
# 호출 경로: router → service → ai_adapter → 팀 B AI Pipeline
#
# Frontend 가 LLM Provider 를 직접 호출하지 않게 하고,
# 팀 B 의 Structured JSON Contract 를 변형 없이 그대로 저장/전달한다.
# 예외: LangGraph 결과는 근거 발화가 없는 위험 항목을 빼고 저장한다
# (drop_ungrounded_risk_items 참고).

import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol, Tuple

from pydantic import ValidationError

from app.adapters.module_loader import ensure_repo_root_on_path
from app.core.config import settings
from app.core.errors import ErrorCode
from app.core.logging import get_logger
from app.schemas.contracts import AIAnalysisResult, SummaryEvidenceItem

logger = get_logger(__name__)


class AIError(Exception):
    """AI 분석 실패. error_code 로 API 오류 코드를 함께 전달한다."""

    def __init__(self, message: str, error_code: ErrorCode = ErrorCode.AI_FAILED) -> None:
        super().__init__(message)
        self.error_code = error_code


# 팀 B(ai/services/summary_service.py) Service Exception → Backend 오류 코드.
# 이 예외들은 고정 문구만 담으므로 문구를 그대로 저장해도 된다.
_KNOWN_AI_ERROR_CODES = {
    "SummaryTimeoutError": ErrorCode.AI_TIMEOUT,
    "SummaryAuthenticationError": ErrorCode.AI_AUTH_ERROR,
    "SummaryQuotaError": ErrorCode.AI_QUOTA_ERROR,
    "SummaryConnectionError": ErrorCode.AI_FAILED,
    "SummaryOutputError": ErrorCode.AI_INVALID_OUTPUT,
}


def map_ai_error(error: Exception) -> AIError:
    """AI 쪽에서 올라온 예외를 Backend 오류 코드로 변환한다.

    알 수 없는 예외는 문구를 버리고 고정 문구와 예외 종류 이름만 남긴다.
    예외 문구에는 상담 발화나 내부 경로가 섞일 수 있는데, AIError 의 문구는
    DB(error_message)와 API 응답까지 그대로 간다. 자세한 내용은
    analysis_service 가 session_id 와 함께 logger.exception 으로 남긴다.
    호출하는 쪽은 `raise map_ai_error(error) from error` 로 원인을 이어 둔다.
    """

    name = type(error).__name__
    code = _KNOWN_AI_ERROR_CODES.get(name)

    if code is not None:
        return AIError(str(error) or "AI 분석에 실패했습니다.", code)

    return AIError(f"AI 분석에 실패했습니다: {name}", ErrorCode.AI_FAILED)


def _to_summary_evidence(links: Any) -> List[SummaryEvidenceItem]:
    """AI 쪽 근거 연결 정보를 API 용 SummaryEvidenceItem 으로 옮긴다.

    팀 B 의 EvidenceLink(text/segment_ids/score) 와, 같은 키를 쓰는
    dict 를 모두 받는다. key_point 키로 와도 받아 준다.
    """

    evidence: List[SummaryEvidenceItem] = []

    for link in links or []:
        raw = link.model_dump() if hasattr(link, "model_dump") else dict(link)

        evidence.append(
            SummaryEvidenceItem(
                key_point=raw.get("text", "") or raw.get("key_point", ""),
                segment_ids=list(raw.get("segment_ids") or []),
                score=float(raw.get("score") or 0.0),
            )
        )

    return evidence


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
            raise map_ai_error(error) from error

        return self._to_bundle(pipeline_result)

    # -----------------------------------------------------
    # 내부 helper
    # -----------------------------------------------------

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

        evidence = _to_summary_evidence(getattr(pipeline_result, "summary_evidence", []))

        return AIAnalysisBundle(
            result=result,
            summary_evidence=evidence,
            provider=self.name,
            model=os.getenv("OPENAI_MODEL"),
        )


# =========================================================
# 근거 없는 위험 항목 제외 (LangGraph 결과의 마지막 관문)
# =========================================================

_RISK_FIELDS = ("risk_utterances", "abuse_signals", "risk_factors")


def _segment_refs(item: Dict[str, Any]) -> List[Any]:
    """항목이 근거로 든 발화 번호. segment_id(단수)와 segment_ids(복수)를 모두 본다.

    PROPOSAL_risk_fields.md §7 은 risk_utterances 만 단수, 나머지는 복수를 쓴다.
    구조가 확정되기 전이라 어느 쪽으로 와도 읽는다.
    """

    refs: List[Any] = []

    for key in ("segment_id", "segment_ids"):
        value = item.get(key)

        if value is None or value == "":
            continue

        if isinstance(value, (list, tuple)):
            refs.extend(value)
        else:
            refs.append(value)

    return refs


def _needs_grounding(field: str, item: Dict[str, Any]) -> bool:
    """근거 발화가 있어야 하는 항목인가.

    abuse_signals 는 네 유형을 모두 내보내고 detected 로 검출 여부를 적는다
    (PROPOSAL_risk_fields.md §7-2). detected 가 명시적으로 False 인 유형은
    위험 신호가 아니므로 근거를 요구하지 않는다. 요구하면 정상 상담마다
    "신호 4건을 제외" 경고가 붙고 유형별 확률도 사라진다.
    detected 가 없거나 False 가 아니면 신호로 보고 근거를 요구한다.
    """

    if field == "abuse_signals":
        return item.get("detected") is not False

    return True


def _is_grounded(item: Dict[str, Any], known_segment_ids: set) -> bool:
    refs = _segment_refs(item)

    return bool(refs) and all(
        isinstance(ref, str) and ref in known_segment_ids for ref in refs
    )


def drop_ungrounded_risk_items(
    result: AIAnalysisResult,
    transcript_payload: Dict[str, Any],
) -> Tuple[AIAnalysisResult, int]:
    """근거 발화가 없거나 Transcript 에 없는 번호를 가리키는 위험 항목을 뺀다.

    05_RULES.md §1 "근거(segment_id) 없는 위험 신호를 생성하지 않는다".
    그래프 안의 판정(evidence_verdict)은 재분석 여부만 정하고 항목을
    거르지 않으므로, 저장 직전에 여기서 한 번 더 막는다.

    한 항목이 여러 발화를 가리키면 하나라도 Transcript 에 없을 때 뺀다.
    없는 발화를 근거로 든 항목은 상담사가 원문을 확인할 수 없다.

    뺀 건수는 warnings 에 남긴다. 조용히 사라지면 상담사가 모른다.
    """

    known = {
        segment.get("segment_id")
        for segment in (transcript_payload or {}).get("segments") or []
        if isinstance(segment, dict) and segment.get("segment_id")
    }

    kept: Dict[str, List[Dict[str, Any]]] = {}
    dropped = 0

    for name in _RISK_FIELDS:
        items = getattr(result, name)
        grounded = [
            item
            for item in items
            if not _needs_grounding(name, item) or _is_grounded(item, known)
        ]

        dropped += len(items) - len(grounded)
        kept[name] = grounded

    if not dropped:
        return result, 0

    warnings = [*result.warnings, f"segment 근거가 없는 신호 {dropped}건을 제외했습니다."]

    return result.model_copy(update={**kept, "warnings": warnings}), dropped


# =========================================================
# LangGraph Agent Adapter
# =========================================================

class LangGraphAIAdapter:
    """agent/ 의 LangGraph 를 호출한다.

    설계 근거: I-SPOT_DOCS/docs/PLAN_langgraph_agent.md §3

    LangGraph 를 최상위 오케스트레이터로 두지 않고 여기에 가둔다.
    Backend 가 이미 세션 상태로 흐름을 관리하므로, 밖에 두면
    "지금 어느 단계인가" 의 정답이 DB 와 그래프 두 곳이 된다.

    이 어댑터는 상태 전이를 하지 않는다. 실패하면 AIError 를 던지고,
    세션 마감은 analysis_service 가 한다. PipelineAIAdapter 와 같은 규약이다.
    """

    name = "langgraph"

    def analyze(self, transcript_payload: Dict[str, Any]) -> AIAnalysisBundle:
        # 빈 Transcript 는 상류(STT/검수)가 깨졌다는 뜻이므로 거부한다.
        # 그냥 통과시키면 "근거 부족" 경고만 달린 정상 결과처럼 저장되어
        # 원인이 묻힌다. MockAIAdapter 와 같은 규약을 유지한다.
        if not (transcript_payload or {}).get("segments"):
            raise AIError(
                "분석할 Transcript segment 가 없습니다.",
                ErrorCode.AI_INVALID_OUTPUT,
            )

        ensure_repo_root_on_path()
        export_llm_env()

        try:
            from agent.graph import run as run_graph
        except ImportError as error:
            raise AIError(
                f"LangGraph Agent module 을 import 할 수 없습니다: {error}",
                ErrorCode.AI_FAILED,
            ) from error

        try:
            final_state = run_graph(transcript_payload)
        except Exception as error:
            # 예외 문구를 그대로 싣지 않는다. 저장·응답까지 가기 때문이다.
            raise map_ai_error(error) from error

        return self._to_bundle(final_state, transcript_payload)

    # -----------------------------------------------------
    # 내부 helper
    # -----------------------------------------------------

    def _to_bundle(
        self,
        state: Dict[str, Any],
        transcript_payload: Dict[str, Any],
    ) -> AIAnalysisBundle:
        """그래프 최종 State 에서 Contract 에 해당하는 값만 추린다.

        rag_documents / retry_count / deidentified 는 중간 산물이므로 담지 않는다.
        05_RULES.md §3 "내부 chain-of-thought 를 결과 데이터로 저장하지 않음".

        근거 발화가 없는 위험 항목은 여기서 뺀다(drop_ungrounded_risk_items).
        Transcript 는 그래프 State 가 아니라 어댑터가 받은 입력으로 대조한다.
        마지막 관문이 그래프가 돌려준 값을 믿으면 관문이 되지 않는다.
        """

        payload = {
            "schema_version": "1.0",
            "summary": state.get("summary") or {},
            "risk_utterances": state.get("risk_utterances") or [],
            "abuse_signals": state.get("abuse_signals") or [],
            "risk_factors": state.get("risk_factors") or [],
            "warnings": state.get("warnings") or [],
        }

        try:
            result = AIAnalysisResult.model_validate(payload)
        except ValidationError as error:
            raise AIError(
                f"Agent 결과가 AI Output Contract 를 만족하지 않습니다: {error.error_count()}건",
                ErrorCode.AI_INVALID_OUTPUT,
            ) from error

        result, dropped = drop_ungrounded_risk_items(result, transcript_payload)

        if dropped:
            logger.warning(
                "segment 근거가 없는 위험 항목을 제외했습니다. provider=%s count=%s",
                self.name,
                dropped,
            )

        # ValidationError 는 ValueError 의 하위 클래스다.
        try:
            evidence = _to_summary_evidence(state.get("summary_evidence"))
        except (TypeError, ValueError) as error:
            raise AIError(
                "Agent 결과의 summary_evidence 가 형식을 만족하지 않습니다.",
                ErrorCode.AI_INVALID_OUTPUT,
            ) from error

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

    if settings.AI_PROVIDER == "langgraph":
        return LangGraphAIAdapter()

    if settings.AI_PROVIDER == "pipeline":
        return PipelineAIAdapter()

    return MockAIAdapter()


__all__ = [
    "AIAdapter",
    "AIAnalysisBundle",
    "AIError",
    "LangGraphAIAdapter",
    "MockAIAdapter",
    "PipelineAIAdapter",
    "drop_ungrounded_risk_items",
    "export_llm_env",
    "get_ai_adapter",
    "map_ai_error",
    "set_ai_adapter_override",
]
