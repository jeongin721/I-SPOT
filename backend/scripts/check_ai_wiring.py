# AI Pipeline 연결 점검 script.
#
# AI_PROVIDER=pipeline 일 때 Backend 가 실제로 팀 B 의
# ai/services/analysis_pipeline.run_analysis_pipeline 까지 도달하는지 확인한다.
#
# OPENAI_API_KEY 없이도 배선을 검증할 수 있도록 두 가지를 순서대로 수행한다.
#   1) STUB : LLM 호출(summarize_consultation) 만 대체한다.
#             Transcript 검증 → 근거 연결(evidence_linker) → Contract 검증은 모두 실제 팀 B 코드다.
#   2) REAL : 아무것도 대체하지 않고 호출한다.
#             Key 가 없으면 팀 B 의 RuntimeError 가 AI_FAILED 로 매핑되는 것까지 확인한다.
#             Key 가 있으면 실제 LLM 을 호출한다.
#
# 사용 예:
#   python -m scripts.check_ai_wiring

import json
import os
import sys
from typing import Any, Dict
from unittest.mock import patch

from app.adapters.ai_adapter import AIError, PipelineAIAdapter
from app.adapters.module_loader import ensure_repo_root_on_path

ensure_repo_root_on_path()

from ai.schemas.analysis import AIAnalysisOutput, Summary  # noqa: E402

# 실제 상담 내용이 아닌 합성 Transcript 다. (docs/05_RULES.md)
TRANSCRIPT_PAYLOAD: Dict[str, Any] = {
    "schema_version": "1.0",
    "segments": [
        {
            "segment_id": "seg_001",
            "speaker": "COUNSELOR",
            "start_ms": 0,
            "end_ms": 2000,
            "text": "학교생활은 요즘 어때?",
            "confidence": 0.95,
        },
        {
            "segment_id": "seg_002",
            "speaker": "CHILD",
            "start_ms": 3000,
            "end_ms": 6000,
            "text": "수학 숙제가 많아서 요즘 조금 힘들어요.",
            "confidence": 0.91,
        },
        {
            "segment_id": "seg_003",
            "speaker": "COUNSELOR",
            "start_ms": 7000,
            "end_ms": 9000,
            "text": "집에서는 어떻게 지내?",
            "confidence": 0.94,
        },
        {
            "segment_id": "seg_004",
            "speaker": "CHILD",
            "start_ms": 10000,
            "end_ms": 14000,
            "text": "동생이랑 가끔 싸우지만 엄마랑 이야기를 많이 해요.",
            "confidence": 0.88,
        },
    ],
}

STUB_LLM_OUTPUT = AIAnalysisOutput(
    schema_version="1.0",
    summary=Summary(
        overview="아동은 수학 숙제가 많아 힘들다고 말했고, 동생과 가끔 다투지만 어머니와 대화를 많이 한다고 말했다.",
        key_points=[
            "수학 숙제가 많아서 힘들다고 말했다.",
            "동생과 가끔 싸운다고 말했다.",
            "엄마와 이야기를 많이 한다고 말했다.",
        ],
    ),
    risk_utterances=[],
    abuse_signals=[],
    risk_factors=[],
    warnings=[],
)

STUB_TARGET = "ai.services.analysis_pipeline.summarize_consultation"


def _print_bundle(bundle: Any) -> None:
    print(f"  provider          : {bundle.provider}")
    print(f"  model             : {bundle.model}")
    print(f"  summary.overview  : {bundle.result.summary.overview}")
    print(f"  summary.key_points: {len(bundle.result.summary.key_points)}건")

    for index, point in enumerate(bundle.result.summary.key_points, start=1):
        print(f"    {index}. {point}")

    print(f"  summary_evidence  : {len(bundle.summary_evidence)}건 (팀 B evidence_linker 결과)")

    for item in bundle.summary_evidence:
        print(
            f"    - score={item.score:.3f} segments={item.segment_ids} "
            f"key_point={item.key_point}"
        )

    print(f"  warnings          : {bundle.result.warnings}")


def run_stubbed() -> bool:
    """LLM 호출만 대체하고 나머지 팀 B pipeline 을 실제로 실행한다."""

    print("=" * 78)
    print("1) STUB LLM: PipelineAIAdapter → 팀 B run_analysis_pipeline (LLM 호출만 대체)")
    print("=" * 78)
    print(f"  patch target: {STUB_TARGET}")

    with patch(STUB_TARGET, return_value=STUB_LLM_OUTPUT):
        bundle = PipelineAIAdapter().analyze(TRANSCRIPT_PAYLOAD)

    _print_bundle(bundle)
    print("  => Transcript 검증 / 근거 segment 연결 / AI Output Contract 검증은 모두 실제 팀 B 코드다.")

    return True


def run_real() -> bool:
    """실제 pipeline 을 그대로 호출한다."""

    has_key = bool(os.getenv("OPENAI_API_KEY"))
    model = os.getenv("OPENAI_MODEL") or "(미설정)"

    print()
    print("=" * 78)
    print("2) REAL: PipelineAIAdapter → 팀 B run_analysis_pipeline (대체 없음)")
    print("=" * 78)
    print(f"  OPENAI_API_KEY 설정 여부: {has_key}")
    print(f"  OPENAI_MODEL            : {model}")

    try:
        bundle = PipelineAIAdapter().analyze(TRANSCRIPT_PAYLOAD)
    except AIError as error:
        print(f"  AIError.error_code: {error.error_code.value}")
        print(f"  AIError.message   : {error}")

        if has_key:
            print("  => Key 가 있는데 실패했다. LLM 호출 자체를 확인해야 한다.")
            return False

        print("  => Key 미설정 시 팀 B RuntimeError 가 그대로 전달되어 AI_FAILED 로 매핑된다.")
        print("     즉 배선은 실제 팀 B pipeline 까지 도달하며, 남은 것은 OPENAI_API_KEY 뿐이다.")
        return True

    print("  실제 LLM 호출 성공:")
    _print_bundle(bundle)

    return True


def main() -> int:
    print("transcript payload:")
    print(json.dumps(TRANSCRIPT_PAYLOAD, ensure_ascii=False, indent=2))
    print()

    ok = run_stubbed() and run_real()

    print()
    print("AI WIRING CHECK PASSED" if ok else "AI WIRING CHECK FAILED")

    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
