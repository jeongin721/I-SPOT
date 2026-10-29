# 다음 상담 체크리스트(추가 확인 · 질문 화면, API_CONTRACT 19절) 시험.
# AI 분석 뒤 자동 생성 · 조회 · 다시 만들기 · 실패 고정 문구 · 멈춤 판정 · 이전 회차 입력 · module 어댑터 변환을 확인한다.
# 외부 호출(OpenAI · rag 색인)은 하지 않는다. 상담 문장은 전부 합성 데이터다.

import time
import types
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.adapters.followup_adapter import (
    FOLLOWUP_MESSAGES,
    FollowupError,
    FollowupInput,
    ModuleFollowupAdapter,
    set_followup_adapter_override,
)
from app.core.config import Settings, settings
from app.core.enums import AnalysisStatus, ReviewStatus
from app.core.errors import ErrorCode
from app.models.followup_suggestion import FollowupSuggestion
from app.models.summary import ConsultationSummary
from app.services import followup_service
from tests.conftest import create_session
from tests.test_analysis import analyzed_session, confirmed_session


def _get(client: TestClient, headers, session_id: str):
    return client.get(f"/api/v1/sessions/{session_id}/followup-suggestions", headers=headers)


def _post(client: TestClient, headers, session_id: str):
    return client.post(f"/api/v1/sessions/{session_id}/followup-suggestions", headers=headers)


class RecordingAdapter:
    """받은 입력을 남기고 고정 결과를 돌려준다."""

    name = "recording"

    def __init__(self, result=None, error: Exception = None, delay: float = 0.0) -> None:
        self.payloads = []
        self.result = result or {"check_items": [], "items": [], "validation": {}, "speaker_check_items": [], "notice": None}
        self.error = error
        self.delay = delay

    def build(self, payload: FollowupInput):
        self.payloads.append(payload)
        if self.delay:
            time.sleep(self.delay)
        if self.error is not None:
            raise self.error
        return self.result


# =========================================================
# 자동 생성 · 조회
# =========================================================

def test_analysis_creates_followup_with_links_to_segments(
    client: TestClient, counselor_headers, session: dict
) -> None:
    analysis = analyzed_session(client, counselor_headers, session["id"])

    response = _get(client, counselor_headers, session["id"])

    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["status"] == "COMPLETED"
    assert data["provider"] == "mock"
    assert data["analysis_id"] == analysis["analysis"]["id"]
    assert data["error"] is None

    result = data["result"]
    assert {item["audience"] for item in result["items"]} == {"counselor", "child_app"}

    # 근거는 이번 회차 아동 발화를 가리킨다(STT 검수 링크: session_id + segment_id).
    basis = result["check_items"][0]["basis"][0]
    assert basis["session_id"] == session["id"]
    assert basis["label"].startswith("1회차 ")
    transcript = client.get(f"/api/v1/sessions/{session['id']}/transcript", headers=counselor_headers).json()["data"]
    child_ids = {s["segment_id"] for s in transcript["transcript"]["segments"] if s["speaker"] == "CHILD"}
    assert basis["segment_id"] in child_ids

    # 화자 미확정 발화는 내용 없이 확인할 사항으로만 온다.
    assert result["speaker_check_items"][0]["kind"] == "uncertain_speaker"
    assert result["speaker_check_items"][0]["basis"][0]["excerpt"] is None
    assert result["abuse_type"] is None  # mock AI 는 학대 유형을 내지 않는다


def test_get_before_analysis_is_null_and_post_requires_completed_analysis(
    client: TestClient, counselor_headers, session: dict
) -> None:
    confirmed_session(client, counselor_headers, session["id"])

    assert _get(client, counselor_headers, session["id"]).json() == {"data": None}

    response = _post(client, counselor_headers, session["id"])
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "INVALID_SESSION_STATE"


def test_other_counselor_cannot_read_or_request(
    client: TestClient, counselor_headers, other_counselor_headers, session: dict
) -> None:
    analyzed_session(client, counselor_headers, session["id"])

    assert _get(client, other_counselor_headers, session["id"]).status_code == 403
    assert _post(client, other_counselor_headers, session["id"]).status_code == 403


def test_post_regenerates_new_row(client: TestClient, counselor_headers, session: dict) -> None:
    analyzed_session(client, counselor_headers, session["id"])
    first = _get(client, counselor_headers, session["id"]).json()["data"]

    adapter = RecordingAdapter(result={"check_items": [{"id": "check:1", "item": "새 항목"}], "items": []})
    set_followup_adapter_override(adapter)

    response = _post(client, counselor_headers, session["id"])

    assert response.status_code == 202, response.text
    assert response.json()["data"]["status"] == "PROCESSING"
    latest = _get(client, counselor_headers, session["id"]).json()["data"]
    assert latest["id"] != first["id"]
    assert latest["status"] == "COMPLETED"
    assert latest["result"]["check_items"] == [{"id": "check:1", "item": "새 항목"}]
    assert adapter.payloads[0].session_id == session["id"]
    assert adapter.payloads[0].session_no == 1


def test_post_while_processing_returns_same_row(
    client: TestClient, counselor_headers, session: dict, db
) -> None:
    analyzed_session(client, counselor_headers, session["id"])
    row = FollowupSuggestion(session_id=uuid.UUID(session["id"]), status=AnalysisStatus.PROCESSING, provider="mock")
    db.add(row)
    db.commit()

    response = _post(client, counselor_headers, session["id"])

    assert response.status_code == 202
    assert response.json()["data"]["id"] == str(row.id)
    count = len(db.scalars(select(FollowupSuggestion).where(FollowupSuggestion.session_id == row.session_id)).all())
    assert count == 2  # 분석 때 만든 행 + 처리 중 행. 새 행은 없다.


def test_disabled_provider_skips_generation_and_rejects_post(
    client: TestClient, counselor_headers, session: dict, monkeypatch
) -> None:
    monkeypatch.setattr(settings, "FOLLOWUP_PROVIDER", "off")
    analyzed_session(client, counselor_headers, session["id"])

    assert _get(client, counselor_headers, session["id"]).json() == {"data": None}
    response = _post(client, counselor_headers, session["id"])
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "FOLLOWUP_DISABLED"


# =========================================================
# 실패 · 멈춤
# =========================================================

@pytest.mark.parametrize(
    ("error", "code"),
    [
        (FollowupError(ErrorCode.AI_PRIVACY_BLOCKED, "RagPrivacyBlocked"), "AI_PRIVACY_BLOCKED"),
        (ValueError("아빠가 때렸어요 원문이 섞인 문구"), "AI_FAILED"),
    ],
)
def test_failure_keeps_fixed_message_and_session_state(
    client: TestClient, counselor_headers, session: dict, error, code
) -> None:
    set_followup_adapter_override(RecordingAdapter(error=error))
    analyzed_session(client, counselor_headers, session["id"])

    data = _get(client, counselor_headers, session["id"]).json()["data"]

    assert data["status"] == "FAILED"
    assert data["error"]["code"] == code
    assert data["error"]["message"] == FOLLOWUP_MESSAGES[ErrorCode(code)]
    assert "아빠" not in data["error"]["message"]
    assert data["result"] is None
    # 회차 상태(분석 완료)는 그대로다.
    analysis = client.get(f"/api/v1/sessions/{session['id']}/analysis", headers=counselor_headers).json()["data"]
    assert analysis["session_status"] == "AI_REVIEW_REQUIRED"


def test_timeout_records_ai_timeout(
    client: TestClient, counselor_headers, session: dict, monkeypatch
) -> None:
    monkeypatch.setattr(settings, "FOLLOWUP_TIMEOUT_SECONDS", 0.2)
    set_followup_adapter_override(RecordingAdapter(delay=1.0))
    analyzed_session(client, counselor_headers, session["id"])

    data = _get(client, counselor_headers, session["id"]).json()["data"]

    assert data["status"] == "FAILED"
    assert data["error"]["code"] == "AI_TIMEOUT"


def test_stale_processing_row_is_closed_on_read(
    client: TestClient, counselor_headers, session: dict, db, monkeypatch
) -> None:
    monkeypatch.setattr(settings, "FOLLOWUP_PROVIDER", "off")
    analyzed_session(client, counselor_headers, session["id"])
    old = datetime.now(timezone.utc) - timedelta(seconds=settings.FOLLOWUP_TIMEOUT_SECONDS + 120)
    row = FollowupSuggestion(
        session_id=uuid.UUID(session["id"]), status=AnalysisStatus.PROCESSING, created_at=old, updated_at=old
    )
    db.add(row)
    db.commit()

    data = _get(client, counselor_headers, session["id"]).json()["data"]

    assert data["id"] == str(row.id)
    assert data["status"] == "FAILED"
    assert data["error"]["code"] == "AI_TIMEOUT"

    # 늦게 끝난 작업의 결과는 저장하지 않는다.
    assert followup_service._finish(db, row.id, AnalysisStatus.COMPLETED, result={"items": []}) is False


# =========================================================
# rag 입력
# =========================================================

def test_previous_session_summary_check_items_and_transcript_are_passed(
    client: TestClient, counselor_headers, case: dict, db
) -> None:
    first = create_session(client, counselor_headers, case["id"])
    analyzed_session(client, counselor_headers, first["id"])
    summary = db.scalar(select(ConsultationSummary).where(ConsultationSummary.session_id == uuid.UUID(first["id"])))
    summary.status = ReviewStatus.APPROVED
    summary.overview = "아동이 학교 생활을 이야기함"
    summary.assessment = {"strengths_resources": {"text": "조모가 자주 연락함", "segment_ids": []}}
    db.commit()

    second = create_session(client, counselor_headers, case["id"])
    adapter = RecordingAdapter()
    set_followup_adapter_override(adapter)
    analyzed_session(client, counselor_headers, second["id"])

    payload = adapter.payloads[0]
    assert payload.session_no == 2
    assert payload.session_id == second["id"]
    assert payload.child_app_responses == []
    [previous] = payload.previous_sessions
    assert previous["session_no"] == 1
    assert previous["session_id"] == first["id"]
    assert previous["summary"].startswith("아동이 학교 생활을 이야기함")
    assert "강점과 자원: 조모가 자주 연락함" in previous["summary"]
    # 1회차 체크리스트(mock)의 확인할 사항이 open 으로 넘어간다.
    assert previous["check_items"][0]["status"] == "open"
    assert previous["check_items"][0]["item"].startswith("(예시)")
    assert any(s["speaker"] == "CHILD" for s in previous["transcript"]["segments"])


def test_unapproved_previous_summary_is_not_passed(
    client: TestClient, counselor_headers, case: dict
) -> None:
    first = create_session(client, counselor_headers, case["id"])
    analyzed_session(client, counselor_headers, first["id"])
    second = create_session(client, counselor_headers, case["id"])
    adapter = RecordingAdapter()
    set_followup_adapter_override(adapter)
    analyzed_session(client, counselor_headers, second["id"])

    assert adapter.payloads[0].previous_sessions[0]["summary"] == ""


@pytest.mark.parametrize(
    ("result", "expected"),
    [
        ({}, None),
        ({"abuse_signals": [{"abuse_type": "PHYSICAL", "detected": False}]}, None),
        ({"abuse_signals": [{"abuse_type": "PHYSICAL", "detected": True}]}, "physical"),
        ({"severity_ratings": [{"major_type": "정서학대", "level": 3}]}, "emotional"),
        ({"severity_ratings": [{"major_type": "방임", "level": None}]}, None),
        ({"severity_ratings": [{"major_type": "방임", "level": True}]}, None),
        (
            {
                "abuse_signals": [{"abuse_type": "PHYSICAL", "detected": True}],
                "severity_ratings": [{"major_type": "방임", "level": 2}],
            },
            "multiple",
        ),
        ("not a dict", None),
    ],
)
def test_abuse_type_for_rag(result, expected) -> None:
    assert followup_service.abuse_type_for_rag(result) == expected


# =========================================================
# module 어댑터 (rag.session 을 가짜 모듈로)
# =========================================================

def _fake_rag(monkeypatch, output):
    calls = []

    def analyze_reviewed_transcript(transcript, abuse_type, **kwargs):
        calls.append((transcript, abuse_type, kwargs))
        if isinstance(output, Exception):
            raise output
        return output

    monkeypatch.setitem(
        __import__("sys").modules,
        "rag.session",
        types.SimpleNamespace(analyze_reviewed_transcript=analyze_reviewed_transcript),
    )
    return calls


def _input() -> FollowupInput:
    return FollowupInput(
        transcript={"segments": []},
        abuse_type="physical",
        session_no=8,
        session_id="sess-8",
        previous_sessions=[{"session_no": 7, "session_id": "sess-7"}],
    )


def test_module_adapter_maps_rag_output(monkeypatch) -> None:
    calls = _fake_rag(
        monkeypatch,
        {
            "rag_analysis": {
                "next_session_checklist": {
                    "check_items": [{"id": "check:1"}],
                    "items": [{"question": "그때 이야기를 더 해 줄래?"}],
                    "validation": {"generated": 1},
                },
                "case_context_warning": "이번 회차 아동 발화만 썼습니다.",
                "related_laws": [{"law_name": "아동복지법"}],
            },
            "speaker_check_items": [{"id": "speaker:1"}],
            "manual_screen_references": {"references": {"followup": []}, "errors": {"closure": "ValueError: 원문"}},
        },
    )

    result = ModuleFollowupAdapter().build(_input())

    transcript, abuse_type, kwargs = calls[0]
    assert abuse_type == "physical"
    assert kwargs["session_id"] == "sess-8"
    assert kwargs["previous_sessions"] == [{"session_no": 7, "session_id": "sess-7"}]
    assert kwargs["known_identifiers"] == []
    assert result["check_items"] == [{"id": "check:1"}]
    assert result["items"] == [{"question": "그때 이야기를 더 해 줄래?"}]
    assert result["speaker_check_items"] == [{"id": "speaker:1"}]
    assert result["manual_screen_references"] == {"followup": []}  # 오류 칸은 싣지 않는다
    assert result["notice"] == "이번 회차 아동 발화만 썼습니다."
    assert "related_laws" not in result


def test_module_adapter_without_abuse_type_returns_notice(monkeypatch) -> None:
    _fake_rag(monkeypatch, {"rag_analysis": None, "speaker_check_items": [], "manual_screen_references": None})

    result = ModuleFollowupAdapter().build(_input())

    assert result["items"] == []
    assert "감지된 학대 유형이 없어" in result["notice"]


@pytest.mark.parametrize(
    ("output", "code"),
    [
        ({"rag_analysis": {"error": "...", "privacy_blocked": True, "reasons": ["text: NER"]}}, ErrorCode.AI_PRIVACY_BLOCKED),
        ({"rag_analysis": {"error": "RAG 근거자료 분석 중 오류가 발생했습니다: KeyError"}}, ErrorCode.AI_FAILED),
        (TimeoutError("원문"), ErrorCode.AI_TIMEOUT),
        (RuntimeError("아빠가 때렸어요"), ErrorCode.AI_FAILED),
    ],
)
def test_module_adapter_errors_use_fixed_codes(monkeypatch, output, code) -> None:
    _fake_rag(monkeypatch, output)

    with pytest.raises(FollowupError) as raised:
        ModuleFollowupAdapter().build(_input())

    assert raised.value.code == code
    assert "아빠" not in str(raised.value)


def test_module_provider_is_locked_in_production() -> None:
    with pytest.raises(ValueError, match="FOLLOWUP_ALLOW_IN_PRODUCTION"):
        Settings(_env_file=None, ENV="production", FOLLOWUP_PROVIDER="module")

    allowed = Settings(_env_file=None, ENV="production", FOLLOWUP_PROVIDER="module", FOLLOWUP_ALLOW_IN_PRODUCTION=True)
    assert allowed.FOLLOWUP_PROVIDER == "module"
    assert Settings(_env_file=None, ENV="production", FOLLOWUP_PROVIDER="mock").FOLLOWUP_PROVIDER == "mock"
