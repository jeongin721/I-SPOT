# AI(요약/분석) Adapter.
#
# 호출 경로: router → service → ai_adapter → 팀 B AI Pipeline
#
# Frontend 가 LLM Provider 를 직접 호출하지 않게 하고,
# 팀 B 의 Structured JSON Contract 를 변형 없이 그대로 저장/전달한다.
# 예외: LangGraph · Modeling 결과는 근거 발화가 없는 위험 항목을 빼고 저장한다
# (drop_ungrounded_risk_items 참고).

import inspect
import os
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Protocol, Tuple

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

AI_TIMEOUT_MESSAGE = "AI 분석이 제한 시간 안에 끝나지 않았습니다."


def map_ai_error(error: Exception) -> AIError:
    """AI 쪽에서 올라온 예외를 Backend 오류 코드로 변환한다.

    파이썬 내장 TimeoutError(와 그 하위 예외)는 AI_TIMEOUT 이다. modeling 은 마감 시각
    (deadline)을 넘기면 이 예외를 던진다. 문구에는 발화가 섞일 수 있어 고정 문구로 바꾼다.

    알 수 없는 예외는 문구를 버리고 고정 문구와 예외 종류 이름만 남긴다.
    예외 문구에는 상담 발화나 내부 경로가 섞일 수 있는데, AIError 의 문구는
    DB(error_message)와 API 응답까지 그대로 간다. 원인 예외의 종류와 호출 위치는
    analysis_service 가 session_id 와 함께 logger.exception 으로 남긴다(로그에도
    문구는 빠진다 — core/logging.install_safe_exception_text).
    호출하는 쪽은 `raise map_ai_error(error) from error` 로 원인을 이어 둔다.
    """

    name = type(error).__name__
    code = _KNOWN_AI_ERROR_CODES.get(name)

    if code is not None:
        return AIError(str(error) or "AI 분석에 실패했습니다.", code)

    if isinstance(error, TimeoutError):
        return AIError(AI_TIMEOUT_MESSAGE, ErrorCode.AI_TIMEOUT)

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
    """준비 단계가 있는 어댑터는 prepare() 도 둔다(선택, 지금은 ModelingAIAdapter 뿐).
    analysis_service 가 AI_TIMEOUT_SECONDS 를 재기 전에 부른다."""

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

        def is_explicitly_low_confidence(segment: Dict[str, Any]) -> bool:
            # ``is_low_confidence`` is internal provider metadata when it is
            # available before Contract serialization.  Persisted Contract
            # segments do not carry that field; in that case 0.0 means the
            # provider did not supply a compatible confidence score, not a
            # measured 0% confidence.  Keep warning behavior for actual,
            # positive low confidence values.
            if segment.get("is_low_confidence") is True:
                return True
            confidence = float(segment.get("confidence") or 0)
            return 0.0 < confidence < 0.7

        low_confidence = [
            segment for segment in segments if is_explicitly_low_confidence(segment)
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
# Modeling Adapter (ai/modeling/abuse 이경진 파이프라인)
# =========================================================

def accepts_keyword(func: Callable[..., Any], name: str) -> bool:
    """func 가 name 을 이름(키워드)으로 받는가. **kwargs 만 있는 함수는 받지 않는 것으로 본다.

    서명을 읽다가 어떤 예외가 나도(서명 정보가 망가진 호출 가능 객체 등) 받지 않는 것으로 본다.
    받지 않는 함수에 넘기면 TypeError 로 분석이 실패하므로, 모르면 넘기지 않는 쪽이 안전하다.
    """

    try:
        parameter = inspect.signature(func).parameters.get(name)
    except Exception:
        return False

    return parameter is not None and parameter.kind in (
        inspect.Parameter.POSITIONAL_OR_KEYWORD,
        inspect.Parameter.KEYWORD_ONLY,
    )


def _accepts_deadline(func: Callable[..., Any]) -> bool:
    """func 가 deadline 을 이름으로 받는가(accepts_keyword).

    deadline 은 time.monotonic() 기준 절대 시각(기본 None)이고, 넘으면 모듈이 남은 단계를
    건너뛰고 내장 TimeoutError 를 던진다(10/16 이경진 님께 제안한 모양).
    run_with_timeout 은 thread 를 멈추지 못해 시간이 지나도 OpenAI 호출이 계속되므로,
    모듈이 스스로 멈출 수 있게 마감 시각을 알려 준다.
    """

    return accepts_keyword(func, "deadline")


class ModelingAIAdapter:
    """ai/modeling/abuse/contract_adapter.analyze_audio_session_as_contract 을 호출한다.

    PipelineAIAdapter(ai/services/analysis_pipeline)와 같은 자리에
    꽂히는 또 다른 AI 구현체다 — 두 파트가 별도 branch에서 독립적으로
    만든 파이프라인이라, 이 adapter를 선택하면 ai/services/ 쪽은
    아예 호출되지 않는다. 심각도(severity_ratings)/보호요인
    (protective_factors)/회차 간 변화(session_change_notes)/다음
    상담 확인사항(followup_check_points)은 #49 의 정식 선택 필드에
    채운다(#57, risk_factors 는 빈 배열). summary는
    agent/summary_converter.convert_summary()를 그대로 쓴다 —
    contract_adapter.py 모듈 docstring 참고.

    근거 발화가 없는 위험 항목은 저장 전에 뺀다(drop_ungrounded_risk_items).
    LangGraphAIAdapter 와 같이 모듈이 돌려준 값이 아니라 어댑터가 받은
    Transcript 로 대조한다.

    모듈은 import 할 때 모델 가중치를 올린다(V100 측정 약 11초, 새 서버는 내려받기까지 더 걸림).
    그래서 import 는 prepare() 로 따로 뺀다. analysis_service 가 AI_TIMEOUT_SECONDS 를 재기 전에
    부르고, 서버 시작 때도 백그라운드로 한 번 부른다(start_ai_preload).
    """

    name = "modeling"

    def prepare(self) -> None:
        """모듈 import · 모델 로드. 이미 올라가 있으면 바로 끝난다(sys.modules)."""

        self._load_pipeline()

    def _load_pipeline(self) -> Tuple[Any, Callable[..., Any]]:
        ensure_repo_root_on_path()
        export_llm_env()

        try:
            from ai.schemas.analysis import Transcript
            from ai.modeling.abuse.contract_adapter import (
                analyze_audio_session_as_contract,
            )
        except ImportError as error:
            # 예외 문구에는 모듈 경로 · 내려받기 주소가 섞일 수 있다. 이 문구는 DB · API 응답까지 가므로
            # 예외 종류 이름만 싣는다(원인은 analysis_service 가 로그로 남긴다).
            raise AIError(
                f"Modeling Pipeline module 을 import 할 수 없습니다: {type(error).__name__}",
                ErrorCode.AI_FAILED,
            ) from error

        return Transcript, analyze_audio_session_as_contract

    def analyze(
        self,
        transcript_payload: Dict[str, Any],
        *,
        time_limit_seconds: Optional[float] = None,
    ) -> AIAnalysisBundle:
        """time_limit_seconds: 이 분석의 제한 시간. analysis_service 가 작업 전체 마감에 맞춰 줄인 값을
        넘긴다(run_with_timeout 에 준 값과 같다). 직접 부르면 AI_TIMEOUT_SECONDS 다.
        """

        # analysis_service 의 run_with_timeout 이 시간을 재기 시작한 직후다. 마감 시각은 이때부터 잰다.
        started = time.monotonic()

        if time_limit_seconds is None:
            time_limit_seconds = settings.AI_TIMEOUT_SECONDS

        Transcript, analyze_audio_session_as_contract = self._load_pipeline()

        try:
            transcript = Transcript.model_validate(transcript_payload)
        except ValidationError as error:
            raise AIError(
                f"Transcript 가 Modeling Pipeline 입력 형식을 만족하지 않습니다: {error.error_count()}건",
                ErrorCode.AI_INVALID_OUTPUT,
            ) from error

        # 마감 시각을 받는 판에만 넘긴다. 받지 않는 판에 넘기면 TypeError 로 분석이 실패한다.
        options: Dict[str, Any] = {}

        if _accepts_deadline(analyze_audio_session_as_contract):
            options["deadline"] = (
                started + time_limit_seconds - settings.AI_DEADLINE_MARGIN_SECONDS
            )

        try:
            (
                contract_payload,
                summary_evidence_raw,
                model_name,
            ) = analyze_audio_session_as_contract(
                stt_result=transcript.model_dump(),
                **options,
            )
        except Exception as error:
            raise map_ai_error(error) from error

        try:
            result = AIAnalysisResult.model_validate(contract_payload)
        except ValidationError as error:
            raise AIError(
                f"AI 결과가 AI Output Contract 를 만족하지 않습니다: {error.error_count()}건",
                ErrorCode.AI_INVALID_OUTPUT,
            ) from error

        result, dropped = drop_ungrounded_risk_items(result, transcript_payload)

        if dropped:
            logger.warning(
                "segment 근거가 없는 위험 항목을 제외했습니다. provider=%s count=%s",
                self.name,
                dropped,
            )

        return AIAnalysisBundle(
            result=result,
            summary_evidence=_to_summary_evidence(summary_evidence_raw),
            provider=self.name,
            model=model_name,
        )


# =========================================================
# 근거 없는 위험 항목 제외 (LangGraph · Modeling 결과의 마지막 관문)
# =========================================================

_RISK_FIELDS = ("risk_utterances", "abuse_signals", "risk_factors")


def _segment_refs(item: Dict[str, Any]) -> List[Any]:
    """항목이 근거로 든 발화 번호. segment_id(단수)와 segment_ids(복수)를 모두 본다.

    확정안(PROPOSAL_risk_fields.md §7, 2026-10-22)은 세 필드 모두 복수 segment_ids 를 쓴다.
    옛 결과 · langgraph 경로가 단수로 올 수 있어 어느 쪽으로 와도 읽는다.
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
            # 선택 필드. 지금 그래프는 만들지 않아 빈 배열이 된다.
            # 키가 없을 때만 기본값을 쓴다. `or []` 로 받으면 None · {} 같은
            # 잘못된 값이 빈 배열로 바뀌어 Contract 검사를 지나간다.
            "severity_ratings": state.get("severity_ratings", []),
            "protective_factors": state.get("protective_factors", []),
            "session_change_notes": state.get("session_change_notes", []),
            "followup_check_points": state.get("followup_check_points", []),
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

    if settings.AI_PROVIDER == "modeling":
        return ModelingAIAdapter()

    return MockAIAdapter()


def start_ai_preload() -> Optional[threading.Thread]:
    """준비 단계(prepare)가 있는 어댑터면 백그라운드 thread 로 미리 불러 둔다. 지금은 modeling 뿐이다.

    서버 시작 때 부른다(main.py lifespan). 기다리지 않으므로 /health 는 바로 응답한다.
    실패해도 서버는 그대로 뜨고, 첫 분석 요청 때 다시 불러 본다. 실패 로그에는 예외 종류
    이름만 남긴다(내려받기 주소 · 내부 경로가 문구에 섞일 수 있다).
    준비 단계가 없으면(mock · pipeline · langgraph) thread 를 만들지 않고 None 을 돌려준다.
    """

    adapter = get_ai_adapter()
    prepare = getattr(adapter, "prepare", None)

    if prepare is None:
        return None

    def run() -> None:
        try:
            prepare()
        except Exception as error:
            cause = error.__cause__ if isinstance(error, AIError) and error.__cause__ else error
            logger.warning(
                "AI 모듈을 미리 불러오지 못했습니다. 첫 분석 요청 때 다시 시도합니다. provider=%s type=%s",
                adapter.name,
                type(cause).__name__,
            )
        else:
            logger.info("AI 모듈을 미리 불러왔습니다. provider=%s", adapter.name)

    thread = threading.Thread(target=run, name="ai-preload", daemon=True)
    thread.start()

    return thread


__all__ = [
    "AI_TIMEOUT_MESSAGE",
    "AIAdapter",
    "AIAnalysisBundle",
    "AIError",
    "LangGraphAIAdapter",
    "MockAIAdapter",
    "ModelingAIAdapter",
    "PipelineAIAdapter",
    "accepts_keyword",
    "drop_ungrounded_risk_items",
    "export_llm_env",
    "get_ai_adapter",
    "map_ai_error",
    "set_ai_adapter_override",
    "start_ai_preload",
]
