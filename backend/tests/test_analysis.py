# AI 연동 / 결과 저장 테스트.
# AI Mock / AI Timeout / AI 실패 / 잘못된 출력 / 재시도를 확인한다.

import time
import uuid
from typing import Dict

import pytest
from fastapi.testclient import TestClient

from app.adapters.ai_adapter import (
    AI_TIMEOUT_MESSAGE,
    AIAnalysisBundle,
    AIError,
    map_ai_error,
    set_ai_adapter_override,
)
from app.core.config import settings
from app.core.errors import ErrorCode
from app.schemas.contracts import AIAnalysisResult
from app.services import analysis_service, session_service
from tests.test_stt_transcript import transcribed_session

AI_CONTRACT_KEYS = {
    "schema_version",
    "summary",
    "risk_utterances",
    "abuse_signals",
    "risk_factors",
    "warnings",
    # 선택 필드(없으면 빈 배열). API_CONTRACT.md 8절 "선택 필드".
    "severity_ratings",
    "protective_factors",
    "session_change_notes",
    "followup_check_points",
    # 2026-10-28 추가 질문 초안(8절, 18절과 짝).
    "followup_questions",
}


# =========================================================
# 테스트용 Adapter
# =========================================================

class FailingAIAdapter:
    name = "failing"

    def analyze(self, transcript_payload):
        raise AIError("LLM Provider 연결 실패", ErrorCode.AI_FAILED)


class InvalidOutputAIAdapter:
    """LLM 이 Contract 를 만족하지 않는 JSON 을 반환한 경우."""

    name = "invalid"

    def analyze(self, transcript_payload):
        raise AIError("LLM 응답을 파싱할 수 없습니다.", ErrorCode.AI_INVALID_OUTPUT)


class SlowAIAdapter:
    name = "slow"

    def analyze(self, transcript_payload):
        time.sleep(1.0)

        return AIAnalysisBundle(result=AIAnalysisResult(), provider="slow")


class SlowPrepareAIAdapter:
    """준비 단계(모델 로드)가 오래 걸리는 어댑터. 분석 자체는 바로 끝난다."""

    name = "slow-prepare"

    def __init__(self) -> None:
        self.analyzed = False

    def prepare(self) -> None:
        time.sleep(1.0)

    def analyze(self, transcript_payload):
        self.analyzed = True

        return AIAnalysisBundle(result=AIAnalysisResult(), provider=self.name)


# =========================================================
# helper
# =========================================================

def confirmed_session(
    client: TestClient, headers: Dict[str, str], session_id: str
) -> dict:
    """Audio → STT → 확정 까지 진행한다."""

    transcribed_session(client, headers, session_id)

    response = client.post(
        f"/api/v1/sessions/{session_id}/transcript/confirm", headers=headers
    )

    assert response.status_code == 200

    return response.json()["data"]


def _run_analysis(client: TestClient, headers: Dict[str, str], session_id: str):
    return client.post(f"/api/v1/sessions/{session_id}/analysis", headers=headers)


def _get_analysis(client: TestClient, headers: Dict[str, str], session_id: str):
    return client.get(f"/api/v1/sessions/{session_id}/analysis", headers=headers)


def analyzed_session(
    client: TestClient, headers: Dict[str, str], session_id: str
) -> dict:
    confirmed_session(client, headers, session_id)

    assert _run_analysis(client, headers, session_id).status_code == 202

    response = _get_analysis(client, headers, session_id)

    assert response.status_code == 200

    return response.json()["data"]


# =========================================================
# 사전 조건
# =========================================================

def test_analysis_requires_confirmed_transcript(
    client: TestClient, counselor_headers, session: dict
) -> None:
    transcribed_session(client, counselor_headers, session["id"])

    response = _run_analysis(client, counselor_headers, session["id"])

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "TRANSCRIPT_NOT_CONFIRMED"


def test_analysis_without_transcript_returns_not_found(
    client: TestClient, counselor_headers, session: dict
) -> None:
    response = _run_analysis(client, counselor_headers, session["id"])

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "TRANSCRIPT_NOT_FOUND"


def test_analysis_before_request_returns_null_analysis(
    client: TestClient, counselor_headers, session: dict
) -> None:
    response = _get_analysis(client, counselor_headers, session["id"])

    assert response.status_code == 200
    assert response.json()["data"]["analysis"] is None


# =========================================================
# 정상 Flow
# =========================================================

def test_analysis_request_returns_202_with_processing_status(
    client: TestClient, counselor_headers, session: dict
) -> None:
    confirmed_session(client, counselor_headers, session["id"])

    response = _run_analysis(client, counselor_headers, session["id"])

    assert response.status_code == 202

    data = response.json()["data"]

    assert data["session_status"] == "AI_PROCESSING"
    assert data["analysis_id"]


def test_mock_ai_stores_contract_compliant_result(
    client: TestClient, counselor_headers, session: dict
) -> None:
    envelope = analyzed_session(client, counselor_headers, session["id"])

    assert envelope["session_status"] == "AI_REVIEW_REQUIRED"

    analysis = envelope["analysis"]

    assert analysis["status"] == "COMPLETED"
    assert analysis["provider"] == "mock"
    assert analysis["error"] is None

    result = analysis["result"]

    # AI Output Contract 의 최상위 key 가 그대로 유지되어야 한다.
    assert set(result.keys()) == AI_CONTRACT_KEYS
    assert result["schema_version"] == "1.0"
    assert set(result["summary"].keys()) == {"overview", "key_points", "assessment"}
    assert result["summary"]["overview"]

    # 9월 범위에서는 위험 관련 항목이 빈 배열이다.
    assert result["risk_utterances"] == []
    assert result["abuse_signals"] == []
    assert result["risk_factors"] == []

    # 학대 확정 같은 판정 필드를 만들지 않는다.
    assert "abuse_confirmed" not in result


def test_analysis_tracks_transcript_version(
    client: TestClient, counselor_headers, session: dict
) -> None:
    envelope = analyzed_session(client, counselor_headers, session["id"])
    analysis = envelope["analysis"]

    assert analysis["transcript_version"] == 1
    assert analysis["transcript_id"]


def test_analysis_evidence_references_real_segment_ids(
    client: TestClient, counselor_headers, session: dict
) -> None:
    envelope = analyzed_session(client, counselor_headers, session["id"])

    transcript = client.get(
        f"/api/v1/sessions/{session['id']}/transcript", headers=counselor_headers
    ).json()["data"]["transcript"]

    valid_ids = {segment["segment_id"] for segment in transcript["segments"]}

    evidence = envelope["analysis"]["summary_evidence"]

    assert evidence

    for item in evidence:
        assert item["segment_ids"]

        for segment_id in item["segment_ids"]:
            # 근거는 반드시 실제 Transcript segment 여야 한다.
            assert segment_id in valid_ids


def test_analysis_creates_summary_draft(
    client: TestClient, counselor_headers, session: dict
) -> None:
    analyzed_session(client, counselor_headers, session["id"])

    response = client.get(
        f"/api/v1/sessions/{session['id']}/summary", headers=counselor_headers
    )

    assert response.status_code == 200

    summary = response.json()["data"]["summary"]

    assert summary is not None
    # AI 결과는 자동 승인되지 않고 항상 DRAFT 로 시작한다.
    assert summary["status"] == "DRAFT"
    assert summary["is_edited"] is False


def test_session_detail_reflects_analysis_progress(
    client: TestClient, counselor_headers, session: dict
) -> None:
    analyzed_session(client, counselor_headers, session["id"])

    detail = client.get(
        f"/api/v1/sessions/{session['id']}", headers=counselor_headers
    ).json()["data"]

    assert detail["status"] == "AI_REVIEW_REQUIRED"
    assert detail["has_analysis"] is True
    assert detail["has_summary"] is True
    assert detail["summary_approved"] is False


# =========================================================
# 실패 / Timeout / 재시도
# =========================================================

def test_ai_failure_sets_failed_state(
    client: TestClient, counselor_headers, session: dict
) -> None:
    confirmed_session(client, counselor_headers, session["id"])
    set_ai_adapter_override(FailingAIAdapter())

    assert _run_analysis(client, counselor_headers, session["id"]).status_code == 202

    envelope = _get_analysis(client, counselor_headers, session["id"]).json()["data"]

    assert envelope["session_status"] == "AI_FAILED"
    assert envelope["error"]["code"] == "AI_FAILED"
    assert envelope["analysis"]["status"] == "FAILED"
    assert envelope["analysis"]["result"] is None


def test_ai_timeout_sets_timeout_error_code(
    client: TestClient, counselor_headers, session: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    confirmed_session(client, counselor_headers, session["id"])

    monkeypatch.setattr(settings, "AI_TIMEOUT_SECONDS", 0.2)
    set_ai_adapter_override(SlowAIAdapter())

    assert _run_analysis(client, counselor_headers, session["id"]).status_code == 202

    envelope = _get_analysis(client, counselor_headers, session["id"]).json()["data"]

    assert envelope["session_status"] == "AI_FAILED"
    assert envelope["error"]["code"] == "AI_TIMEOUT"


def test_slow_prepare_has_its_own_time_limit(
    client: TestClient, counselor_headers, session: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    """준비 단계는 AI_TIMEOUT_SECONDS 밖이지만 따로 제한이 있다. 넘으면 분석을 부르지 않고 AI_TIMEOUT."""

    confirmed_session(client, counselor_headers, session["id"])

    monkeypatch.setattr(analysis_service, "PREPARE_TIMEOUT_SECONDS", 0.2)
    adapter = SlowPrepareAIAdapter()
    set_ai_adapter_override(adapter)

    assert _run_analysis(client, counselor_headers, session["id"]).status_code == 202

    envelope = _get_analysis(client, counselor_headers, session["id"]).json()["data"]

    assert envelope["session_status"] == "AI_FAILED"
    assert envelope["error"] == {
        "code": "AI_TIMEOUT",
        "message": analysis_service.PREPARE_TIMEOUT_MESSAGE,
    }
    assert adapter.analyzed is False


def test_prepare_limit_ends_before_stale_processing_check() -> None:
    """작업 전체 마감(요청 시각 + 준비 제한 + 분석 제한)이 처리 중 멈춤 판정(요청 시각 + 분석 제한 + 여유 시간)보다 앞이다.

    뒤면 살아 있는 작업이 조회 때 '작업이 사라짐' 으로 실패 처리된다(그 뒤 늦은 결과는 저장하지 않는다).
    """

    assert 0 < analysis_service.PREPARE_TIMEOUT_SECONDS < session_service.STALE_GRACE_SECONDS


def test_ai_invalid_output_sets_invalid_output_code(
    client: TestClient, counselor_headers, session: dict
) -> None:
    confirmed_session(client, counselor_headers, session["id"])
    set_ai_adapter_override(InvalidOutputAIAdapter())

    assert _run_analysis(client, counselor_headers, session["id"]).status_code == 202

    envelope = _get_analysis(client, counselor_headers, session["id"]).json()["data"]

    assert envelope["error"]["code"] == "AI_INVALID_OUTPUT"


def test_ai_can_be_retried_after_failure(
    client: TestClient, counselor_headers, session: dict
) -> None:
    confirmed_session(client, counselor_headers, session["id"])
    set_ai_adapter_override(FailingAIAdapter())

    _run_analysis(client, counselor_headers, session["id"])

    set_ai_adapter_override(None)

    assert _run_analysis(client, counselor_headers, session["id"]).status_code == 202

    envelope = _get_analysis(client, counselor_headers, session["id"]).json()["data"]

    assert envelope["session_status"] == "AI_REVIEW_REQUIRED"
    assert envelope["error"] is None
    assert envelope["analysis"]["status"] == "COMPLETED"


def test_analysis_on_missing_session_returns_not_found(
    client: TestClient, counselor_headers
) -> None:
    response = _run_analysis(client, counselor_headers, str(uuid.uuid4()))

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "SESSION_NOT_FOUND"


# =========================================================
# 팀 B Pipeline 예외 매핑 (단위 테스트)
# =========================================================

@pytest.mark.parametrize(
    ("exception_name", "expected_code"),
    [
        ("SummaryTimeoutError", ErrorCode.AI_TIMEOUT),
        ("SummaryAuthenticationError", ErrorCode.AI_AUTH_ERROR),
        ("SummaryQuotaError", ErrorCode.AI_QUOTA_ERROR),
        ("SummaryConnectionError", ErrorCode.AI_FAILED),
        ("SummaryOutputError", ErrorCode.AI_INVALID_OUTPUT),
        ("SomeUnknownError", ErrorCode.AI_FAILED),
    ],
)
def test_pipeline_error_mapping(exception_name: str, expected_code: ErrorCode) -> None:
    """
    팀 B(ai/services/summary_service.py)의 Service Exception 이
    Backend 오류 코드로 정확히 변환되는지 확인한다.
    PipelineAIAdapter 와 LangGraphAIAdapter 가 같은 변환 함수를 쓴다.
    """

    exception_type = type(exception_name, (Exception,), {})

    mapped = map_ai_error(exception_type("오류 메시지"))

    assert mapped.error_code == expected_code


def test_known_ai_error_keeps_fixed_message() -> None:
    """팀 B 예외는 고정 문구만 담으므로 문구를 그대로 쓴다."""

    timeout = type("SummaryTimeoutError", (Exception,), {})

    mapped = map_ai_error(timeout("LLM 상담 요약 요청 시간이 초과되었습니다."))

    assert str(mapped) == "LLM 상담 요약 요청 시간이 초과되었습니다."


@pytest.mark.parametrize(
    "error",
    [
        TimeoutError("아빠가 때렸어요 발화를 분석하다 마감 시각을 넘음"),
        type("DeadlineExceeded", (TimeoutError,), {})("아빠가 때렸어요"),
    ],
)
def test_builtin_timeout_error_maps_to_ai_timeout_with_fixed_message(error: Exception) -> None:
    """파이썬 내장 TimeoutError(와 하위 예외)는 AI_TIMEOUT 이다. 문구는 버리고 고정 문구를 쓴다.

    modeling 은 마감 시각(deadline)을 넘기면 이 예외를 던진다.
    """

    mapped = map_ai_error(error)

    assert mapped.error_code == ErrorCode.AI_TIMEOUT
    assert str(mapped) == AI_TIMEOUT_MESSAGE


def test_unknown_ai_error_hides_exception_text() -> None:
    """알 수 없는 예외는 문구를 버리고 예외 종류 이름만 남긴다.

    AIError 문구는 error_message 로 저장되고 API 응답까지 간다. 예외 문구에는
    상담 발화나 내부 경로가 섞일 수 있다.
    """

    mapped = map_ai_error(ValueError("아빠가 때렸어요 발화를 처리하지 못했습니다"))

    assert mapped.error_code == ErrorCode.AI_FAILED
    assert "아빠가 때렸어요" not in str(mapped)
    assert "ValueError" in str(mapped)
