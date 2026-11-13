# 고령자 회차 통합 요약 어댑터(2026-11-13, feature/senior, API_CONTRACT 27절).
#
# 고령자 사례(subject_type=SENIOR)의 회차는 analysis_service 가 학대 분석 어댑터(get_ai_adapter) 대신 이것을 쓴다.
# ai/modeling/senior/senior_session_llm 을 불러 결과를 아동 회차와 같은 AIAnalysisResult 에 담는다:
#   summary.overview · key_points ← 통합 요약, summary_evidence ← 발화 근거, senior ← 측정 근거 · 확인사항 초안 · 안전 발화.
# 학대 관련 칸(risk_utterances · abuse_signals · severity_ratings …)은 비우고, topic_tags · safety_flags 는 null 이다.

import time
from typing import Any, Callable, Dict, List, Optional

from app.adapters.ai_adapter import AIAnalysisBundle, AIError, map_ai_error
from app.adapters.module_loader import ModuleLoadError, load_callable
from app.core.config import settings
from app.core.errors import ErrorCode
from app.schemas.contracts import AIAnalysisResult, SummaryEvidenceItem

MODULE = "ai.modeling.senior.senior_session_llm"

SAFETY_WARNING = {
    "SELF_HARM": "자해 · 자살과 관련된 말이 있어요. 다음 방문으로 넘기지 말고 바로 확인해 주세요(AI 표시, 판정 아님).",
    "URGENT_HEALTH": "급한 건강 문제와 관련된 말이 있어요. 바로 확인해 주세요(AI 표시, 판정 아님).",
}


class SeniorAIAdapter:
    def __init__(self, provider: Optional[str] = None) -> None:
        self.provider = provider or settings.SENIOR_AI_PROVIDER
        self.name = f"senior-{self.provider}"

    def analyze(
        self,
        transcript_payload: Dict[str, Any],
        *,
        time_limit_seconds: Optional[float] = None,
        known_identifiers: Optional[List[str]] = None,
        senior_context: Optional[Dict[str, Any]] = None,
    ) -> AIAnalysisBundle:
        started = time.monotonic()
        segments = transcript_payload.get("segments") or []
        if not segments:
            raise AIError("분석할 Transcript segment 가 없습니다.", ErrorCode.AI_INVALID_OUTPUT)

        data = {**(senior_context or {}), "segments": segments}
        use_ai = self.provider == "modeling"

        try:
            if use_ai:
                run: Callable[..., Dict[str, Any]] = load_callable(MODULE, "summarize_senior_session")
                limit = time_limit_seconds if time_limit_seconds is not None else settings.AI_TIMEOUT_SECONDS
                raw = run(
                    data,
                    known_identifiers=list(known_identifiers or []),
                    deadline=started + limit - settings.AI_DEADLINE_MARGIN_SECONDS,
                )
            else:
                raw = load_callable(MODULE, "rule_based_session_summary")(data)
        except ModuleLoadError as error:
            raise AIError(f"고령자 요약 모듈을 불러오지 못했습니다: {type(error).__name__}", ErrorCode.AI_FAILED) from error
        except Exception as error:
            name = type(error).__name__
            if name == "SeniorSessionOutputError":
                raise AIError("AI 가 상담 요약을 만들지 못했습니다.", ErrorCode.AI_INVALID_OUTPUT) from error
            if name == "PrivacyGatewayBlocked":
                raise AIError("개인정보를 다 가리지 못해 AI 로 보내지 않았습니다.", ErrorCode.AI_PRIVACY_BLOCKED) from error
            raise map_ai_error(error) from error

        return self._to_bundle(raw, data, "AI" if use_ai else "RULE")

    def _to_bundle(self, raw: Dict[str, Any], data: Dict[str, Any], source: str) -> AIAnalysisBundle:
        key_points = raw.get("key_points") or []
        safety = raw.get("safety_mentions") or []
        evidence = []
        for point in key_points:
            segs = [seg for basis in point.get("basis") or [] if basis.get("kind") == "SEGMENT" for seg in basis.get("segment_ids") or []]
            if segs:
                evidence.append(SummaryEvidenceItem(key_point=point["text"], segment_ids=segs, score=1.0))

        warnings = [SAFETY_WARNING[kind] for kind in ("SELF_HARM", "URGENT_HEALTH") if any(s["kind"] == kind for s in safety)]
        if source == "RULE":
            warnings.append("규칙으로 옮긴 요약입니다. AI 요약이 아닙니다.")

        result = AIAnalysisResult(
            schema_version="1.0",
            summary={"overview": raw.get("overview") or "", "key_points": [point["text"] for point in key_points]},
            warnings=warnings,
            senior={
                "source": source,
                "visit_measurement_ids": [item["id"] for item in data.get("visit_measurements") or []],
                "key_point_basis": [point.get("basis") or [] for point in key_points],
                "next_check_drafts": raw.get("check_points") or [],
                "safety_mentions": safety,
            },
        )
        return AIAnalysisBundle(
            result=result,
            summary_evidence=evidence,
            provider=self.name,
            model=raw.get("model") if source == "AI" else "senior-rule",
        )


_override: Optional[Any] = None


def set_senior_ai_adapter_override(adapter: Optional[Any]) -> None:
    """시험에서 고령자 회차 어댑터를 바꿔 끼우는 hook."""

    global _override
    _override = adapter


def get_senior_ai_adapter() -> Any:
    return _override if _override is not None else SeniorAIAdapter()
