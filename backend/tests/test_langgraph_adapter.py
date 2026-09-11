# LangGraph Agent Adapter 를 검증한다.
#
# 그래프 내부 동작은 최상위 tests/test_agent_graph.py 에서 본다.
# 여기서는 Backend 쪽 계약만 확인한다.
#
#   - AI_PROVIDER=langgraph 로 전환되는가
#   - 결과가 AI Output Contract 를 만족하는가
#   - 중간 산물이 Contract 밖으로 새지 않는가
#   - 실패가 AIError 로 변환되는가

import pytest
from pydantic import ValidationError

# langgraph 는 Backend 단독 실행에 필요 없는 선택 의존성이다.
# 설치되지 않은 환경에서는 이 파일을 통째로 건너뛴다.
#   pip install -r ../requirements-agent.txt
pytest.importorskip("langgraph")

from app.adapters.ai_adapter import (  # noqa: E402
    AIError,
    LangGraphAIAdapter,
    get_ai_adapter,
)
from app.core.config import Settings, settings  # noqa: E402
from app.core.errors import ErrorCode  # noqa: E402

TRANSCRIPT = {
    "schema_version": "1.0",
    "segments": [
        {"segment_id": "seg_001", "speaker": "COUNSELOR", "text": "오늘 어땠어요?"},
        {"segment_id": "seg_002", "speaker": "CHILD", "text": "아빠가 때렸어요."},
    ],
}


@pytest.fixture
def use_langgraph(monkeypatch):
    monkeypatch.setattr(settings, "AI_PROVIDER", "langgraph")


# =========================================================
# Provider 전환
# =========================================================

def test_factory_returns_langgraph_adapter(use_langgraph):
    assert get_ai_adapter().name == "langgraph"


def test_unknown_provider_is_rejected():
    """Literal 로 막아 두어 오타가 조용히 mock 으로 떨어지지 않는다."""

    with pytest.raises(ValidationError):
        Settings(AI_PROVIDER="langraph")  # 오타


# =========================================================
# Contract
# =========================================================

def test_result_satisfies_contract():
    bundle = LangGraphAIAdapter().analyze(TRANSCRIPT)

    assert bundle.provider == "langgraph"
    assert bundle.result.schema_version == "1.0"

    # 노드 본문이 비어 있는 동안에는 위험 필드가 빈 배열이다.
    assert bundle.result.risk_utterances == []
    assert bundle.result.abuse_signals == []
    assert bundle.result.risk_factors == []


def test_gives_up_with_reason_not_silently():
    """근거가 부족하면 억지로 채우지 않고 사유를 남긴다.

    05_RULES.md §3 "근거 부족 시 빈 결과 허용", "결과를 억지로 생성하지 않음".
    """

    bundle = LangGraphAIAdapter().analyze(TRANSCRIPT)

    assert bundle.result.warnings
    assert any("근거가 부족" in w for w in bundle.result.warnings)


def test_intermediate_state_does_not_leak():
    """rag_documents / retry_count 는 중간 산물이라 Contract 에 담지 않는다.

    05_RULES.md §3 "내부 chain-of-thought 를 결과 데이터로 저장하지 않음".
    """

    bundle = LangGraphAIAdapter().analyze(TRANSCRIPT)
    dumped = bundle.result.model_dump()

    assert "rag_documents" not in dumped
    assert "retry_count" not in dumped


# =========================================================
# 실패 처리
# =========================================================

def test_graph_failure_becomes_ai_error(monkeypatch):
    """어댑터는 상태 전이를 하지 않고 AIError 만 던진다.

    세션 마감은 analysis_service 가 한다.
    """

    def boom(_payload):
        raise RuntimeError("그래프 폭발")

    monkeypatch.setattr("agent.graph.run", boom)

    with pytest.raises(AIError) as exc:
        LangGraphAIAdapter().analyze(TRANSCRIPT)

    assert exc.value.error_code == ErrorCode.AI_FAILED
