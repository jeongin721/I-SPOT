# AI 분석 두 번 저장 시험(2026-11-04, I-SPOT_DOCS/docs/PROPOSAL_analysis_signals_first.md §6).
#
# 모듈이 학대 신호 확인(2단계) 값을 먼저 넘기면(on_signals_ready) 회차를 AI_REVIEW_REQUIRED 로 넘기고 초안을 PENDING 으로
# 저장하고, 모듈이 돌아오면 3 · 4단계 칸만 채워 DONE 으로 바꾸는지 본다. 실패 · 시간 초과 · 멈춤 · 409 · 경합도 본다.
#
# 무거운 모델 대신 콜백을 흉내 내는 가짜 어댑터를 쓰고, 저장은 실제 analysis_service 와 시험 DB(SQLite · PostgreSQL)로 한다.
# 분석은 서비스 함수로 예약만 하고 작업(process_analysis)은 따로 돌린다(test_analysis_late_results 와 같은 방식) —
# 첫 저장과 둘째 저장 사이에 조회 · 요청을 끼워 넣으려고. 녹취 · 결과 · 오류 문구는 모두 가상 데이터다.

import logging
import threading
import time
import types
import uuid
from datetime import timedelta
from typing import Any, Callable, Dict, List, Optional

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text, update
from sqlalchemy.exc import OperationalError

from app.adapters.ai_adapter import AIAnalysisBundle, AIError, set_ai_adapter_override
from app.core.config import settings
from app.core.database import SessionLocal, engine
from app.core.enums import AuditAction, DraftsStatus, SessionStatus
from app.core.errors import APIError, ErrorCode
from app.models.analysis import AIAnalysis
from app.models.audit_log import AuditLog
from app.models.session import ConsultationSession
from app.models.summary import ConsultationSummary
from app.schemas.contracts import AIAnalysisResult, SummaryEvidenceItem
from app.services import analysis_service, followup_checklist_service, session_service, summary_service
from tests.test_analysis import _get_analysis, confirmed_session

WAIT_SECONDS = 10

FAILURE_TEXT = "가상 3단계 호출 실패 문구"

# 2단계 칸(첫 저장 값 그대로 남아야 하는 칸). mock 전사본은 seg_001 ~ seg_006 이다.
STEP2_KEYS = ("risk_utterances", "abuse_signals", "risk_factors", "severity_ratings", "protective_factors")


# =========================================================
# 가상 결과
# =========================================================

def _signals_bundle() -> AIAnalysisBundle:
    """콜백이 넘기는 결과 — 2단계 칸만 찼고 3 · 4단계 칸은 비어 있다(#151 §5-3)."""

    result = AIAnalysisResult.model_validate(
        {
            "summary": {"overview": "", "key_points": ["가상 아동 진술 1"]},
            "risk_utterances": [
                {"segment_ids": ["seg_002"], "text": "가상 위험 발화", "abuse_type": "PHYSICAL", "subtype": "가상"}
            ],
            "abuse_signals": [
                {"abuse_type": "PHYSICAL", "detected": True, "segment_ids": ["seg_002"]},
                {"abuse_type": "NEGLECT", "detected": False, "segment_ids": []},
            ],
            "severity_ratings": [{"major_type": "신체학대", "level": 3, "segment_ids": ["seg_002"]}],
            "protective_factors": [{"category": "가상 자원", "text": "가상 보호요인", "segment_ids": ["seg_004"]}],
            "warnings": ["가상 법령 데이터 경고"],
        }
    )

    return AIAnalysisBundle(
        result=result,
        summary_evidence=[SummaryEvidenceItem(key_point="가상 아동 진술 1", segment_ids=["seg_002"], score=0.9)],
        provider="signals-fake",
        model="signals-model",
    )


def _final_bundle() -> AIAnalysisBundle:
    """모듈의 마지막 결과. 3 · 4단계 칸이 찼고, 2단계 칸은 일부러 콜백 값과 다르게 둔다(서버가 기대지 않는지 보려고)."""

    result = AIAnalysisResult.model_validate(
        {
            "summary": {
                "overview": "가상 상담 요약",
                "key_points": ["다른 아동 진술"],
                "assessment": {"desired_changes": {"text": "가상 원하는 변화", "segment_ids": ["seg_006"]}},
            },
            "risk_utterances": [
                {"segment_ids": ["seg_003"], "text": "다른 위험 발화", "abuse_type": "EMOTIONAL", "subtype": "다름"}
            ],
            "abuse_signals": [{"abuse_type": "EMOTIONAL", "detected": True, "segment_ids": ["seg_003"]}],
            "severity_ratings": [{"major_type": "정서학대", "level": 5, "segment_ids": ["seg_003"]}],
            "protective_factors": [],
            "warnings": ["가상 마지막 경고"],
            "session_change_notes": [{"text": "가상 회차 간 변화", "segment_ids": ["seg_001"]}],
            "followup_check_points": [{"text": "가상 확인 메모", "segment_ids": ["seg_005"]}],
            "followup_questions": [{"text": "가상 추가 질문", "kind": "OPEN", "segment_ids": ["seg_005"]}],
            "topic_tags": [{"topic": "가상 주제", "segment_ids": ["seg_001"]}],
        }
    )

    return AIAnalysisBundle(
        result=result,
        summary_evidence=[SummaryEvidenceItem(key_point="다른 아동 진술", segment_ids=["seg_003"], score=0.1)],
        provider="signals-fake",
        model="signals-model",
    )


# =========================================================
# 가짜 어댑터 — ModelingAIAdapter 처럼 on_signals_ready 를 키워드로 받는다
# =========================================================

class _SignalsAdapter:
    """콜백을 부른 뒤 release 가 켜질 때까지 기다렸다가 outcome 대로 끝낸다.

    outcome: "success"(마지막 결과) · "ai_error"(AIError) · "invalid_output" · "unexpected"(RuntimeError) · "sleep"(오래 잠) · "none"(콜백 안 부름 → 실패)
    hold: False 면 기다리지 않는다. calls: 콜백을 부르는 횟수.
    """

    name = "signals-fake"

    def __init__(self, outcome: str = "success", *, hold: bool = True, calls: int = 1, sleep: float = 0.0) -> None:
        self.outcome = outcome
        self.hold = hold
        self.calls = calls
        self.sleep = sleep
        self.signalled = threading.Event()
        self.release = threading.Event()
        self.done = threading.Event()
        self.analyzed = 0

    def analyze(self, transcript_payload, *, on_signals_ready: Optional[Callable[[AIAnalysisBundle], None]] = None):
        self.analyzed += 1

        try:
            if self.outcome == "late_callback":
                # 제한 시간이 지난 뒤에야 콜백을 부른다(바깥은 이미 시간 초과로 마감).
                time.sleep(self.sleep)
                on_signals_ready(_signals_bundle())
                return _final_bundle()

            if self.outcome == "none":
                raise AIError(FAILURE_TEXT, ErrorCode.AI_FAILED)

            for _ in range(self.calls):
                on_signals_ready(_signals_bundle())

            self.signalled.set()

            if self.hold:
                self.release.wait(timeout=WAIT_SECONDS)

            if self.outcome == "ai_error":
                raise AIError(FAILURE_TEXT, ErrorCode.AI_FAILED)
            if self.outcome == "invalid_output":
                raise AIError(FAILURE_TEXT, ErrorCode.AI_INVALID_OUTPUT)
            if self.outcome == "unexpected":
                raise RuntimeError(FAILURE_TEXT)
            if self.outcome == "sleep":
                time.sleep(self.sleep)

            return _final_bundle()
        finally:
            self.done.set()


class _OldAdapter:
    """on_signals_ready 를 받지 않는 예전 판(mock 과 같은 꼴). 마지막 결과만 돌려준다."""

    name = "old-fake"

    def analyze(self, transcript_payload):
        return _final_bundle()


# =========================================================
# helper
# =========================================================

def _reserve(session_id: str, counselor_id: uuid.UUID) -> uuid.UUID:
    with SessionLocal() as db:
        item = db.get(ConsultationSession, uuid.UUID(session_id))
        analysis = analysis_service.request_analysis(db, item, types.SimpleNamespace(id=counselor_id))

        return analysis.id


def _start_worker(session_id: str, analysis_id: uuid.UUID) -> threading.Thread:
    thread = threading.Thread(
        target=analysis_service.process_analysis,
        args=(uuid.UUID(session_id), analysis_id),
        daemon=True,
    )
    thread.start()

    return thread


def _finish(adapter: _SignalsAdapter, worker: threading.Thread) -> None:
    adapter.release.set()
    worker.join(timeout=WAIT_SECONDS)

    assert not worker.is_alive()


def _shift_requested_at(session_id: str, seconds: float) -> None:
    with SessionLocal() as db:
        item = db.get(ConsultationSession, uuid.UUID(session_id))
        db.execute(
            update(ConsultationSession)
            .where(ConsultationSession.id == item.id)
            .values(ai_started_at=item.ai_started_at - timedelta(seconds=seconds))
        )
        db.commit()


def _drafts_limit_seconds() -> float:
    return settings.AI_TIMEOUT_SECONDS + analysis_service.PREPARE_TIMEOUT_SECONDS + session_service.STALE_GRACE_SECONDS


def _state(session_id: str, analysis_id: uuid.UUID) -> Dict[str, Any]:
    with SessionLocal() as db:
        item = db.get(ConsultationSession, uuid.UUID(session_id))
        analysis = db.get(AIAnalysis, analysis_id)
        summary = db.scalar(select(ConsultationSummary).where(ConsultationSummary.session_id == item.id))
        audits = db.scalars(
            select(AuditLog).where(AuditLog.entity_id == analysis_id).order_by(AuditLog.created_at, AuditLog.id)
        ).all()

        return {
            "session_status": item.status,
            "analysis_status": analysis.status.value,
            "drafts_status": analysis.drafts_status,
            "drafts_error_code": analysis.drafts_error_code,
            "result": analysis.result,
            "summary_evidence": analysis.summary_evidence,
            "summary": None
            if summary is None
            else {"analysis_id": summary.analysis_id, "overview": summary.overview, "key_points": summary.key_points},
            "audits": [(row.action, row.detail) for row in audits],
        }


def _actions(state: Dict[str, Any]) -> List[AuditAction]:
    return [action for action, _ in state["audits"]]


def _sorted(actions: List[AuditAction]) -> List[str]:
    # 감사 기록 시각은 같은 밀리초일 수 있어(Windows 시계 단위) 순서 대신 종류 · 개수를 본다.
    return sorted(action.value for action in actions)


def _sorted_actions(state: Dict[str, Any]) -> List[str]:
    return _sorted(_actions(state))


def _detail(state: Dict[str, Any], action: AuditAction) -> Dict[str, Any]:
    details = [detail for recorded, detail in state["audits"] if recorded == action]

    assert len(details) == 1, details

    return details[0]


def _poll(client: TestClient, headers: Dict[str, str], session_id: str) -> dict:
    response = _get_analysis(client, headers, session_id)

    assert response.status_code == 200, response.text

    return response.json()["data"]


@pytest.fixture
def checklist_calls(monkeypatch: pytest.MonkeyPatch) -> List[Dict[str, Any]]:
    """19절 다음 상담 체크리스트 시작 기록. 불린 때의 초안 상태도 남긴다(둘째 저장 뒤에 불려야 한다)."""

    calls: List[Dict[str, Any]] = []

    def record(session_id: uuid.UUID, analysis_id: uuid.UUID) -> None:
        with SessionLocal() as db:
            analysis = db.get(AIAnalysis, analysis_id)
            calls.append({"analysis_id": analysis_id, "drafts_status": analysis.drafts_status})

    monkeypatch.setattr(followup_checklist_service, "generate_after_analysis", record)

    return calls


@pytest.fixture
def ready(client: TestClient, counselor_headers, session: dict) -> dict:
    confirmed_session(client, counselor_headers, session["id"])

    return session


# =========================================================
# 첫 저장 · 둘째 저장
# =========================================================

def test_signals_are_saved_first_then_drafts_fill_in(
    client: TestClient, counselor_headers, counselor_id, ready: dict, checklist_calls
) -> None:
    adapter = _SignalsAdapter("success")
    set_ai_adapter_override(adapter)

    analysis_id = _reserve(ready["id"], counselor_id)
    worker = _start_worker(ready["id"], analysis_id)

    try:
        assert adapter.signalled.wait(timeout=WAIT_SECONDS)

        # 첫 저장: 회차는 사람이 볼 차례, 분석은 완료, 초안은 만드는 중.
        envelope = _poll(client, counselor_headers, ready["id"])
        first = _state(ready["id"], analysis_id)
    finally:
        _finish(adapter, worker)

    signals = _signals_bundle().result.model_dump()

    assert envelope["session_status"] == "AI_REVIEW_REQUIRED"
    assert envelope["analysis"]["status"] == "COMPLETED"
    assert envelope["analysis"]["drafts_status"] == "PENDING"
    assert envelope["analysis"]["drafts_error"] is None
    assert envelope["analysis"]["result"]["summary"]["overview"] == ""
    assert envelope["analysis"]["result"]["followup_questions"] == []
    for key in STEP2_KEYS:
        assert envelope["analysis"]["result"][key] == signals[key]

    assert first["session_status"] == SessionStatus.AI_REVIEW_REQUIRED
    assert first["summary"] is None
    assert _sorted_actions(first) == _sorted([AuditAction.ANALYSIS_REQUESTED, AuditAction.ANALYSIS_COMPLETED])

    # 둘째 저장: 3 · 4단계 칸 · overview · assessment · warnings 만 마지막 값, 2단계 칸 · key_points · 근거는 첫 저장 값.
    final = _final_bundle().result.model_dump()
    after = _state(ready["id"], analysis_id)
    result = after["result"]

    assert after["session_status"] == SessionStatus.AI_REVIEW_REQUIRED
    assert after["drafts_status"] == DraftsStatus.DONE
    assert after["drafts_error_code"] is None
    for key in STEP2_KEYS:
        assert result[key] == signals[key]
    assert result["summary"]["key_points"] == signals["summary"]["key_points"]
    assert result["summary"]["overview"] == final["summary"]["overview"]
    assert result["summary"]["assessment"] == final["summary"]["assessment"]
    for key in ("session_change_notes", "followup_check_points", "followup_questions", "topic_tags", "warnings"):
        assert result[key] == final[key]
    assert after["summary_evidence"] == [item.model_dump() for item in _signals_bundle().summary_evidence]

    # Summary 초안은 둘째 저장에서 만든다(key_points 는 첫 저장 값).
    assert after["summary"] == {
        "analysis_id": analysis_id,
        "overview": "가상 상담 요약",
        "key_points": ["가상 아동 진술 1"],
    }
    assert _sorted_actions(after) == _sorted([
        AuditAction.ANALYSIS_REQUESTED,
        AuditAction.ANALYSIS_COMPLETED,
        AuditAction.ANALYSIS_DRAFTS_COMPLETED,
    ])
    assert _detail(after, AuditAction.ANALYSIS_DRAFTS_COMPLETED) == {
        "warning_count": 1,
        "followup_question_count": 1,
        "followup_check_point_count": 1,
    }

    # 19절 체크리스트는 둘째 저장 뒤 한 번.
    assert checklist_calls == [{"analysis_id": analysis_id, "drafts_status": DraftsStatus.DONE}]

    done = _poll(client, counselor_headers, ready["id"])

    assert done["analysis"]["drafts_status"] == "DONE"
    assert done["analysis"]["drafts_error"] is None


def test_callback_called_twice_saves_once(
    client: TestClient, counselor_headers, counselor_id, ready: dict, checklist_calls
) -> None:
    """모듈이 콜백을 두 번 불러도 첫 저장은 한 번이다(두 번째는 회차가 처리 중이 아니라 버림)."""

    adapter = _SignalsAdapter("success", hold=False, calls=2)
    set_ai_adapter_override(adapter)

    analysis_id = _reserve(ready["id"], counselor_id)
    analysis_service.process_analysis(uuid.UUID(ready["id"]), analysis_id)

    state = _state(ready["id"], analysis_id)

    assert _actions(state).count(AuditAction.ANALYSIS_COMPLETED) == 1
    assert _actions(state).count(AuditAction.ANALYSIS_DRAFTS_COMPLETED) == 1
    assert state["drafts_status"] == DraftsStatus.DONE
    assert len(checklist_calls) == 1


def test_old_module_without_callback_saves_once_like_before(
    client: TestClient, counselor_headers, ready: dict, checklist_calls
) -> None:
    """on_signals_ready 를 받지 않는 어댑터(예전 판 · mock)는 지금처럼 끝에서 한 번에 저장하고 초안은 DONE 이다."""

    set_ai_adapter_override(_OldAdapter())

    response = client.post(f"/api/v1/sessions/{ready['id']}/analysis", headers=counselor_headers)

    assert response.status_code == 202, response.text

    envelope = _poll(client, counselor_headers, ready["id"])
    state = _state(ready["id"], uuid.UUID(envelope["analysis"]["id"]))

    assert envelope["session_status"] == "AI_REVIEW_REQUIRED"
    assert envelope["analysis"]["drafts_status"] == "DONE"
    assert envelope["analysis"]["drafts_error"] is None
    # 한 번에 저장하므로 2단계 칸도 마지막 결과 그대로다.
    assert envelope["analysis"]["result"] == _final_bundle().result.model_dump(mode="json")
    assert state["summary"]["overview"] == "가상 상담 요약"
    assert _sorted_actions(state) == _sorted([AuditAction.ANALYSIS_REQUESTED, AuditAction.ANALYSIS_COMPLETED])
    assert len(checklist_calls) == 1


# =========================================================
# 실패 · 시간 초과
# =========================================================

def test_failure_before_callback_fails_the_analysis_like_before(
    client: TestClient, counselor_headers, counselor_id, ready: dict, checklist_calls
) -> None:
    set_ai_adapter_override(_SignalsAdapter("none"))

    analysis_id = _reserve(ready["id"], counselor_id)
    analysis_service.process_analysis(uuid.UUID(ready["id"]), analysis_id)

    envelope = _poll(client, counselor_headers, ready["id"])
    state = _state(ready["id"], analysis_id)

    assert envelope["session_status"] == "AI_FAILED"
    assert envelope["analysis"]["status"] == "FAILED"
    assert envelope["analysis"]["drafts_status"] == "DONE"
    assert envelope["analysis"]["drafts_error"] is None
    assert _sorted_actions(state) == _sorted([AuditAction.ANALYSIS_REQUESTED, AuditAction.ANALYSIS_FAILED])
    assert checklist_calls == []


@pytest.mark.parametrize(
    ("outcome", "expected_code"),
    [("ai_error", "AI_FAILED"), ("invalid_output", "AI_FAILED"), ("unexpected", "AI_FAILED")],
)
def test_failure_after_callback_marks_only_drafts_failed(
    client: TestClient,
    counselor_headers,
    counselor_id,
    ready: dict,
    checklist_calls,
    caplog,
    outcome: str,
    expected_code: str,
) -> None:
    adapter = _SignalsAdapter(outcome, hold=False)
    set_ai_adapter_override(adapter)

    analysis_id = _reserve(ready["id"], counselor_id)

    with caplog.at_level(logging.WARNING):
        analysis_service.process_analysis(uuid.UUID(ready["id"]), analysis_id)

    envelope = _poll(client, counselor_headers, ready["id"])
    state = _state(ready["id"], analysis_id)

    # 회차 · 2단계 결과는 그대로, 초안만 실패.
    assert envelope["session_status"] == "AI_REVIEW_REQUIRED"
    assert envelope["error"] is None
    assert envelope["analysis"]["status"] == "COMPLETED"
    assert envelope["analysis"]["error"] is None
    assert envelope["analysis"]["drafts_status"] == "FAILED"
    assert envelope["analysis"]["drafts_error"] == {
        "code": expected_code,
        "message": analysis_service.DRAFTS_ERROR_MESSAGES[expected_code],
    }
    assert envelope["analysis"]["result"] == _signals_bundle().result.model_dump(mode="json")
    assert state["summary"] is None
    assert _sorted_actions(state) == _sorted([
        AuditAction.ANALYSIS_REQUESTED,
        AuditAction.ANALYSIS_COMPLETED,
        AuditAction.ANALYSIS_DRAFTS_FAILED,
    ])
    assert _detail(state, AuditAction.ANALYSIS_DRAFTS_FAILED) == {"error_code": expected_code}
    assert checklist_calls == []

    # 원인 예외 문구는 응답 · 로그에 남지 않는다.
    assert FAILURE_TEXT not in str(envelope)
    assert FAILURE_TEXT not in caplog.text


def test_timeout_after_callback_marks_drafts_timeout(
    client: TestClient,
    counselor_headers,
    counselor_id,
    ready: dict,
    checklist_calls,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "AI_TIMEOUT_SECONDS", 1.0)
    adapter = _SignalsAdapter("sleep", hold=False, sleep=2.5)
    set_ai_adapter_override(adapter)

    analysis_id = _reserve(ready["id"], counselor_id)
    analysis_service.process_analysis(uuid.UUID(ready["id"]), analysis_id)

    # 버려진 분석(가짜)이 끝난 뒤에도 늦은 저장이 없어야 한다.
    assert adapter.done.wait(timeout=WAIT_SECONDS)
    time.sleep(0.1)

    envelope = _poll(client, counselor_headers, ready["id"])
    state = _state(ready["id"], analysis_id)

    assert envelope["session_status"] == "AI_REVIEW_REQUIRED"
    assert envelope["analysis"]["status"] == "COMPLETED"
    assert envelope["analysis"]["drafts_status"] == "FAILED"
    assert envelope["analysis"]["drafts_error"] == {
        "code": "AI_TIMEOUT",
        "message": analysis_service.DRAFTS_ERROR_MESSAGES["AI_TIMEOUT"],
    }
    assert envelope["analysis"]["result"] == _signals_bundle().result.model_dump(mode="json")
    assert state["summary"] is None
    assert AuditAction.ANALYSIS_DRAFTS_FAILED in _actions(state)
    assert checklist_calls == []


def test_callback_after_timeout_is_discarded(
    client: TestClient,
    counselor_headers,
    counselor_id,
    ready: dict,
    checklist_calls,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """바깥이 시간 초과로 AI_FAILED 마감한 뒤에 늦게 불린 콜백은 첫 저장을 하지 않는다."""

    monkeypatch.setattr(settings, "AI_TIMEOUT_SECONDS", 0.5)
    adapter = _SignalsAdapter("late_callback", sleep=1.5)
    set_ai_adapter_override(adapter)

    analysis_id = _reserve(ready["id"], counselor_id)
    analysis_service.process_analysis(uuid.UUID(ready["id"]), analysis_id)

    assert adapter.done.wait(timeout=WAIT_SECONDS)

    state = _state(ready["id"], analysis_id)

    assert state["session_status"] == SessionStatus.AI_FAILED
    assert state["analysis_status"] == "FAILED"
    assert state["drafts_status"] == DraftsStatus.DONE
    assert state["result"] is None
    assert _sorted_actions(state) == _sorted([AuditAction.ANALYSIS_REQUESTED, AuditAction.ANALYSIS_FAILED])


def test_first_save_failure_falls_back_to_one_save(
    client: TestClient,
    counselor_headers,
    counselor_id,
    ready: dict,
    checklist_calls,
    monkeypatch: pytest.MonkeyPatch,
    caplog,
) -> None:
    """콜백 안 첫 저장이 DB 오류로 실패하면 분석은 계속되고, 끝에서 지금처럼 한 번에 저장한다."""

    original = analysis_service._save_analysis_result

    def broken_first_save(db, *, drafts_pending: bool = False, **kwargs):
        if drafts_pending:
            raise OperationalError("UPDATE ai_analyses", {}, Exception("가상 DB 오류 문구"))

        return original(db, drafts_pending=drafts_pending, **kwargs)

    monkeypatch.setattr(analysis_service, "_save_analysis_result", broken_first_save)
    set_ai_adapter_override(_SignalsAdapter("success", hold=False))

    analysis_id = _reserve(ready["id"], counselor_id)

    with caplog.at_level(logging.WARNING):
        analysis_service.process_analysis(uuid.UUID(ready["id"]), analysis_id)

    state = _state(ready["id"], analysis_id)

    assert state["session_status"] == SessionStatus.AI_REVIEW_REQUIRED
    assert state["analysis_status"] == "COMPLETED"
    assert state["drafts_status"] == DraftsStatus.DONE
    assert state["result"] == _final_bundle().result.model_dump()
    assert state["summary"]["overview"] == "가상 상담 요약"
    assert _sorted_actions(state) == _sorted([AuditAction.ANALYSIS_REQUESTED, AuditAction.ANALYSIS_COMPLETED])
    assert len(checklist_calls) == 1
    assert "OperationalError" in caplog.text
    assert "가상 DB 오류 문구" not in caplog.text


# =========================================================
# 멈춤 판정 · 회차 삭제 · 재분석
# =========================================================

def test_stale_pending_drafts_are_failed_and_late_drafts_discarded(
    client: TestClient, counselor_headers, counselor_id, ready: dict, checklist_calls
) -> None:
    adapter = _SignalsAdapter("success")
    set_ai_adapter_override(adapter)

    analysis_id = _reserve(ready["id"], counselor_id)
    worker = _start_worker(ready["id"], analysis_id)

    try:
        assert adapter.signalled.wait(timeout=WAIT_SECONDS)

        # 기준 시각(요청 + 준비 제한 + AI_TIMEOUT_SECONDS + 여유) 전이면 그대로다.
        _shift_requested_at(ready["id"], _drafts_limit_seconds() - 5)
        assert _poll(client, counselor_headers, ready["id"])["analysis"]["drafts_status"] == "PENDING"

        _shift_requested_at(ready["id"], 10)
        stale = _poll(client, counselor_headers, ready["id"])
    finally:
        _finish(adapter, worker)

    assert stale["session_status"] == "AI_REVIEW_REQUIRED"
    assert stale["analysis"]["status"] == "COMPLETED"
    assert stale["analysis"]["drafts_status"] == "FAILED"
    assert stale["analysis"]["drafts_error"]["code"] == "AI_FAILED"

    # 늦게 끝난 작업의 둘째 저장은 버린다.
    state = _state(ready["id"], analysis_id)

    assert state["drafts_status"] == DraftsStatus.FAILED
    assert state["result"] == _signals_bundle().result.model_dump()
    assert state["summary"] is None
    assert AuditAction.ANALYSIS_DRAFTS_COMPLETED not in _actions(state)
    assert _detail(state, AuditAction.ANALYSIS_DRAFTS_FAILED) == {
        "error_code": "AI_FAILED",
        "reason": "stale_processing",
        "limit_seconds": _drafts_limit_seconds(),
    }
    assert checklist_calls == []


def test_stale_pending_drafts_do_not_block_saves(
    client: TestClient, counselor_headers, counselor_id, ready: dict, checklist_calls
) -> None:
    """화면이 분석을 다시 조회하지 않아도, 멈춘 초안은 저장 요청에서 마감하고 받는다."""

    adapter = _SignalsAdapter("success")
    set_ai_adapter_override(adapter)

    analysis_id = _reserve(ready["id"], counselor_id)
    worker = _start_worker(ready["id"], analysis_id)

    try:
        assert adapter.signalled.wait(timeout=WAIT_SECONDS)
        _shift_requested_at(ready["id"], _drafts_limit_seconds() + 5)

        response = client.put(
            f"/api/v1/sessions/{ready['id']}/followup-questions",
            json={"questions": [{"text": "가상 질문", "kind": "OPEN", "source": "COUNSELOR", "segment_ids": []}]},
            headers=counselor_headers,
        )
    finally:
        _finish(adapter, worker)

    assert response.status_code == 200, response.text
    assert _state(ready["id"], analysis_id)["drafts_status"] == DraftsStatus.FAILED


def test_session_deleted_while_pending_discards_drafts(
    client: TestClient, admin_headers, counselor_id, ready: dict, checklist_calls, caplog
) -> None:
    adapter = _SignalsAdapter("success")
    set_ai_adapter_override(adapter)

    analysis_id = _reserve(ready["id"], counselor_id)
    worker = _start_worker(ready["id"], analysis_id)

    with caplog.at_level(logging.WARNING):
        try:
            assert adapter.signalled.wait(timeout=WAIT_SECONDS)

            # 원문을 확정한 뒤의 회차는 관리자만 지운다(2026-11-11).
            response = client.delete(f"/api/v1/sessions/{ready['id']}", headers=admin_headers)

            assert response.status_code == 204, response.text
        finally:
            _finish(adapter, worker)

    with SessionLocal() as db:
        assert db.get(AIAnalysis, analysis_id) is None
        assert db.scalar(select(ConsultationSummary)) is None

    assert checklist_calls == []
    assert "예상하지 못한 오류" not in caplog.text
    assert f"analysis_id={analysis_id}" in caplog.text


def test_retry_after_stale_drafts_is_not_overwritten_by_old_job(
    client: TestClient, counselor_headers, counselor_id, ready: dict, checklist_calls
) -> None:
    """멈춤 판정으로 초안이 마감된 뒤 다시 분석을 요청했으면, 옛 작업의 늦은 결과는 새 작업을 덮지 않는다."""

    adapter = _SignalsAdapter("success")
    set_ai_adapter_override(adapter)

    first_id = _reserve(ready["id"], counselor_id)
    worker = _start_worker(ready["id"], first_id)

    try:
        assert adapter.signalled.wait(timeout=WAIT_SECONDS)
        _shift_requested_at(ready["id"], _drafts_limit_seconds() + 5)

        # 초안이 FAILED 면 재분석을 받는다(멈춘 초안은 요청이 먼저 마감한다).
        second_id = _reserve(ready["id"], counselor_id)
    finally:
        _finish(adapter, worker)

    first = _state(ready["id"], first_id)
    second = _state(ready["id"], second_id)

    assert first["session_status"] == SessionStatus.AI_PROCESSING
    assert second["analysis_status"] == "PROCESSING"
    assert second["result"] is None
    assert first["drafts_status"] == DraftsStatus.FAILED
    assert first["result"] == _signals_bundle().result.model_dump()
    assert first["summary"] is None
    assert checklist_calls == []


# =========================================================
# PENDING 동안 막는 것 · 받는 것
# =========================================================

def test_pending_drafts_block_five_requests_but_accept_risk_assessment(
    client: TestClient, counselor_headers, counselor_id, ready: dict, checklist_calls
) -> None:
    adapter = _SignalsAdapter("success")
    set_ai_adapter_override(adapter)

    analysis_id = _reserve(ready["id"], counselor_id)
    worker = _start_worker(ready["id"], analysis_id)
    base = f"/api/v1/sessions/{ready['id']}"

    try:
        assert adapter.signalled.wait(timeout=WAIT_SECONDS)

        blocked = {
            "reanalysis": client.post(f"{base}/analysis", headers=counselor_headers),
            "summary_patch": client.patch(f"{base}/summary", json={"overview": "가상 고침"}, headers=counselor_headers),
            "summary_approve": client.post(f"{base}/summary/approve", headers=counselor_headers),
            "followup_questions": client.put(
                f"{base}/followup-questions",
                json={"questions": [{"text": "가상 질문", "kind": "OPEN", "source": "COUNSELOR", "segment_ids": []}]},
                headers=counselor_headers,
            ),
            "followup_checks": client.put(
                f"{base}/followup-checks",
                json={"items": [{"text": "가상 확인", "source": "COUNSELOR", "segment_ids": []}]},
                headers=counselor_headers,
            ),
        }
        risk = client.put(f"{base}/risk-assessment", json={"counselor_level": "HIGH"}, headers=counselor_headers)
        state_while_pending = _state(ready["id"], analysis_id)
    finally:
        _finish(adapter, worker)

    for name, response in blocked.items():
        assert response.status_code == 409, (name, response.text)
        assert response.json()["error"] == {
            "code": "ANALYSIS_DRAFTS_PENDING",
            "message": session_service.DRAFTS_PENDING_MESSAGE,
        }, name

    assert risk.status_code == 200, risk.text

    # 막힌 요청은 아무것도 바꾸지 않았다(새 분석 없음 · 회차 그대로).
    assert state_while_pending["session_status"] == SessionStatus.AI_REVIEW_REQUIRED
    with SessionLocal() as db:
        assert len(db.scalars(select(AIAnalysis)).all()) == 1

    # 초안이 끝나면 풀린다.
    after = client.put(
        f"{base}/followup-questions",
        json={"questions": [{"text": "가상 질문", "kind": "OPEN", "source": "COUNSELOR", "segment_ids": []}]},
        headers=counselor_headers,
    )

    assert after.status_code == 200, after.text
    assert client.patch(f"{base}/summary", json={"overview": "가상 고침"}, headers=counselor_headers).status_code == 200


def test_failed_drafts_accept_reanalysis(
    client: TestClient, counselor_headers, counselor_id, ready: dict, checklist_calls
) -> None:
    """초안이 FAILED 면 막지 않는다 — 지금 있는 재분석(2단계부터 전부 다시)으로 다시 한다."""

    set_ai_adapter_override(_SignalsAdapter("ai_error", hold=False))

    analysis_id = _reserve(ready["id"], counselor_id)
    analysis_service.process_analysis(uuid.UUID(ready["id"]), analysis_id)

    assert _state(ready["id"], analysis_id)["drafts_status"] == DraftsStatus.FAILED

    set_ai_adapter_override(_SignalsAdapter("success", hold=False))
    response = client.post(f"/api/v1/sessions/{ready['id']}/analysis", headers=counselor_headers)

    assert response.status_code == 202, response.text

    envelope = _poll(client, counselor_headers, ready["id"])

    assert envelope["analysis"]["id"] != str(analysis_id)
    assert envelope["analysis"]["drafts_status"] == "DONE"
    assert envelope["session_status"] == "AI_REVIEW_REQUIRED"


# =========================================================
# ModelingAIAdapter — 모듈의 on_signals_ready 를 받는 판에만 넘긴다
# =========================================================

ADAPTER_TRANSCRIPT = {
    "schema_version": "1.0",
    "segments": [
        {"segment_id": "seg_001", "speaker": "COUNSELOR", "start_ms": 0, "end_ms": 1000, "text": "가상 질문", "confidence": 0.9},
        {"segment_id": "seg_002", "speaker": "CHILD", "start_ms": 1000, "end_ms": 2000, "text": "가상 답", "confidence": 0.9},
    ],
}


class _StubTranscript:
    """ai.schemas.analysis.Transcript 대신(모듈 import 없이 어댑터만 본다)."""

    def __init__(self, payload: Dict[str, Any]) -> None:
        self.payload = payload

    @classmethod
    def model_validate(cls, payload: Dict[str, Any]) -> "_StubTranscript":
        return cls(payload)

    def model_dump(self) -> Dict[str, Any]:
        return self.payload


def _signals_contract() -> Dict[str, Any]:
    """모듈이 콜백으로 넘기는 계약 모양. 근거 없는 위험 발화 하나를 섞는다(어댑터가 빼야 한다)."""

    return {
        "schema_version": "1.0",
        "summary": {"overview": "", "key_points": ["가상 진술"]},
        "risk_utterances": [
            {"segment_ids": ["seg_002"], "text": "가상 위험 발화", "abuse_type": "PHYSICAL"},
            {"segment_ids": ["seg_999"], "text": "근거 없는 발화", "abuse_type": "PHYSICAL"},
        ],
        "abuse_signals": [],
        "risk_factors": [],
        "warnings": [],
    }


def _use_module(monkeypatch: pytest.MonkeyPatch, func: Callable[..., Any]) -> None:
    from app.adapters.ai_adapter import ModelingAIAdapter

    monkeypatch.setattr(ModelingAIAdapter, "_load_pipeline", lambda self: (_StubTranscript, func))


def test_modeling_adapter_hands_checked_signals_to_callback(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.adapters.ai_adapter import ModelingAIAdapter

    def module(stt_result, deadline=None, on_signals_ready=None):
        on_signals_ready(_signals_contract(), [{"text": "가상 진술", "segment_ids": ["seg_002"], "score": 0.8}], "signals-m")
        return {"schema_version": "1.0", "summary": {"overview": "가상 요약"}}, [], "final-m"

    _use_module(monkeypatch, module)
    received: List[AIAnalysisBundle] = []

    bundle = ModelingAIAdapter().analyze(ADAPTER_TRANSCRIPT, on_signals_ready=received.append)

    assert bundle.result.summary.overview == "가상 요약"
    assert len(received) == 1

    signals = received[0]

    # 마지막 결과와 같은 검사를 거친다 — 근거 없는 항목은 빠지고 경고가 붙는다.
    assert [item["segment_ids"] for item in signals.result.risk_utterances] == [["seg_002"]]
    assert signals.result.warnings == ["segment 근거가 없는 신호 1건을 제외했습니다."]
    assert signals.summary_evidence == [SummaryEvidenceItem(key_point="가상 진술", segment_ids=["seg_002"], score=0.8)]
    assert (signals.provider, signals.model) == ("modeling", "signals-m")


def test_modeling_adapter_does_not_pass_callback_to_old_module(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.adapters.ai_adapter import ModelingAIAdapter

    seen: List[Dict[str, Any]] = []

    def old_module(stt_result, deadline=None):
        seen.append({"stt_result": stt_result})
        return {"schema_version": "1.0"}, [], "old-m"

    _use_module(monkeypatch, old_module)
    received: List[AIAnalysisBundle] = []

    bundle = ModelingAIAdapter().analyze(ADAPTER_TRANSCRIPT, on_signals_ready=received.append)

    assert bundle.model == "old-m"
    assert len(seen) == 1
    assert received == []


@pytest.mark.parametrize("failure", ["invalid_contract", "callback_raises"])
def test_modeling_adapter_never_leaks_callback_errors_to_module(
    monkeypatch: pytest.MonkeyPatch, caplog, failure: str
) -> None:
    """모듈은 콜백 예외를 잡지 않는다. 계약 위반 · 받는 쪽 예외가 새면 분석 전체가 실패하므로 어댑터가 막는다."""

    from app.adapters.ai_adapter import ModelingAIAdapter

    def module(stt_result, deadline=None, on_signals_ready=None):
        payload = {"summary": "계약 위반"} if failure == "invalid_contract" else _signals_contract()
        on_signals_ready(payload, [], "signals-m")
        return {"schema_version": "1.0"}, [], "final-m"

    def broken_receiver(bundle: AIAnalysisBundle) -> None:
        raise RuntimeError(FAILURE_TEXT)

    _use_module(monkeypatch, module)
    received: List[AIAnalysisBundle] = []
    receiver = received.append if failure == "invalid_contract" else broken_receiver

    with caplog.at_level(logging.WARNING):
        bundle = ModelingAIAdapter().analyze(ADAPTER_TRANSCRIPT, on_signals_ready=receiver)

    assert bundle.model == "final-m"
    assert received == []
    assert ("AIError" if failure == "invalid_contract" else "RuntimeError") in caplog.text
    assert FAILURE_TEXT not in caplog.text


# =========================================================
# 경합 — 확인과 쓰기 사이 · 오래된 조회 · 잠금 순서(Codex #154 M1 · M2 · M3)
# =========================================================

def _one_shot_analysis(session_id: str, counselor_id: uuid.UUID) -> uuid.UUID:
    """한 번에 저장한 분석 하나(초안 DONE)와 Summary 초안을 만든다."""

    set_ai_adapter_override(_OldAdapter())
    analysis_id = _reserve(session_id, counselor_id)
    analysis_service.process_analysis(uuid.UUID(session_id), analysis_id)

    return analysis_id


def _pause_after_guard(monkeypatch: pytest.MonkeyPatch, thread_name: str):
    """assert_drafts_not_pending 를 통과한 바로 뒤(쓰기 전)에 thread_name 스레드만 멈춘다."""

    passed, release = threading.Event(), threading.Event()
    original = session_service.assert_drafts_not_pending

    def guard(db, session) -> None:
        original(db, session)

        if threading.current_thread().name == thread_name:
            passed.set()
            release.wait(timeout=WAIT_SECONDS)

    monkeypatch.setattr(session_service, "assert_drafts_not_pending", guard)

    return passed, release


def _run(name: str, target: Callable[[], Any], outcome: Dict[str, Any]) -> threading.Thread:
    def body() -> None:
        try:
            outcome[name] = target()
        except APIError as error:
            outcome[name] = (error.status_code, error.code.value)

    thread = threading.Thread(target=body, name=name, daemon=True)
    thread.start()

    return thread


def _reanalyse_and_save_signals(session_id: str, counselor_id: uuid.UUID) -> uuid.UUID:
    """다른 요청 B: 재분석을 요청하고 그 작업이 2단계를 먼저 저장한다."""

    analysis_id = _reserve(session_id, counselor_id)
    analysis_service._SignalsSave(uuid.UUID(session_id), analysis_id)(_signals_bundle())

    return analysis_id


def _drafts_by_status(session_id: str) -> Dict[str, int]:
    with SessionLocal() as db:
        rows = db.scalars(select(AIAnalysis).where(AIAnalysis.session_id == uuid.UUID(session_id))).all()

    counts: Dict[str, int] = {}

    for row in rows:
        counts[row.drafts_status.value] = counts.get(row.drafts_status.value, 0) + 1

    return counts


def test_approve_holds_the_session_so_reanalysis_cannot_slip_in(
    client: TestClient, counselor_headers, counselor_id, ready: dict, checklist_calls, monkeypatch: pytest.MonkeyPatch
) -> None:
    """승인 A 가 PENDING 확인을 통과한 뒤 쓰기 전에 다른 요청 B 가 재분석을 시작해 2단계를 저장하면, PENDING 인 채 승인됐다
    (M1 재현 B). 이제 확인이 회차 행을 잡아 B 는 A 가 끝날 때까지 기다렸다가 409 로 끝난다."""

    _one_shot_analysis(ready["id"], counselor_id)
    passed, release = _pause_after_guard(monkeypatch, "approve")
    outcome: Dict[str, Any] = {}

    def approve() -> str:
        with SessionLocal() as db:
            item = db.get(ConsultationSession, uuid.UUID(ready["id"]))
            return summary_service.approve_summary(db, item, types.SimpleNamespace(id=counselor_id)).status.value

    first = _run("approve", approve, outcome)

    try:
        assert passed.wait(timeout=WAIT_SECONDS)

        second = _run("reanalysis", lambda: _reanalyse_and_save_signals(ready["id"], counselor_id), outcome)
        time.sleep(0.5)

        # B 는 A 가 잡은 회차 행을 기다린다.
        assert second.is_alive()
    finally:
        release.set()
        first.join(timeout=WAIT_SECONDS)

    second.join(timeout=WAIT_SECONDS)

    assert not first.is_alive() and not second.is_alive()
    assert outcome["approve"] == "APPROVED"
    assert outcome["reanalysis"] == (409, "INVALID_SESSION_STATE")

    with SessionLocal() as db:
        assert db.get(ConsultationSession, uuid.UUID(ready["id"])).status == SessionStatus.APPROVED

    assert _drafts_by_status(ready["id"]) == {"DONE": 1}


def test_reanalysis_holds_the_session_so_a_second_one_cannot_make_two_pending(
    client: TestClient, counselor_headers, counselor_id, ready: dict, checklist_calls, monkeypatch: pytest.MonkeyPatch
) -> None:
    """재분석 A 가 확인을 통과한 뒤 B 가 재분석 · 첫 저장을 마치면 A 도 통과해 PENDING 이 둘이 됐다(M1 재현 A).
    이제 B 는 A 의 요청이 끝날 때까지 기다렸다가 409 로 끝나고, 처리 중인 분석은 A 의 것 하나다."""

    _one_shot_analysis(ready["id"], counselor_id)
    passed, release = _pause_after_guard(monkeypatch, "first")
    outcome: Dict[str, Any] = {}

    first = _run("first", lambda: _reserve(ready["id"], counselor_id), outcome)

    try:
        assert passed.wait(timeout=WAIT_SECONDS)

        second = _run("second", lambda: _reanalyse_and_save_signals(ready["id"], counselor_id), outcome)
        time.sleep(0.5)

        assert second.is_alive()
    finally:
        release.set()
        first.join(timeout=WAIT_SECONDS)

    second.join(timeout=WAIT_SECONDS)

    assert not first.is_alive() and not second.is_alive()
    assert isinstance(outcome["first"], uuid.UUID)
    assert outcome["second"] == (409, "INVALID_SESSION_STATE")

    with SessionLocal() as db:
        assert db.get(AIAnalysis, outcome["first"]).status.value == "PROCESSING"
        assert db.get(ConsultationSession, uuid.UUID(ready["id"])).status == SessionStatus.AI_PROCESSING

    assert _drafts_by_status(ready["id"]) == {"DONE": 2}


def test_stale_check_with_an_old_read_does_not_fail_new_drafts(
    client: TestClient, counselor_headers, counselor_id, ready: dict, checklist_calls
) -> None:
    """하루 전 요청 시각으로 읽어 둔 회차로 멈춤 판정을 하는 사이 새 재분석이 2단계를 저장했으면, 옛 시각으로 잰 경과 시간으로
    새 초안을 마감하지 않는다(M2 — Codex 재현 시험을 옮김)."""

    sid = uuid.UUID(ready["id"])
    _one_shot_analysis(ready["id"], counselor_id)
    _shift_requested_at(ready["id"], 24 * 60 * 60)

    with SessionLocal() as polling_db:
        stale_row = polling_db.get(ConsultationSession, sid)
        old_started = stale_row.ai_started_at

        new_id = _reanalyse_and_save_signals(ready["id"], counselor_id)

        with SessionLocal() as fresh:
            assert fresh.get(ConsultationSession, sid).ai_started_at > old_started

        expired = session_service.expire_stale_processing(polling_db, stale_row)

    assert expired is False
    assert _state(ready["id"], new_id)["drafts_status"] == DraftsStatus.PENDING


def test_second_save_locks_the_session_first_so_delete_waits(
    client: TestClient, counselor_headers, counselor_id, ready: dict, checklist_calls, monkeypatch: pytest.MonkeyPatch
) -> None:
    """둘째 저장이 분석 행을 먼저 잡으면 Summary INSERT 의 회차 외래 키 확인이 회차 삭제와 PostgreSQL 에서 교착했다(M3 —
    Codex 재현 시험을 옮김). 이제 둘째 저장이 회차 행을 먼저 잡아 삭제는 기다렸다가 지운다."""

    if engine.dialect.name != "postgresql":
        pytest.skip("PostgreSQL 행 잠금 · 외래 키 잠금 순서 확인")

    sid = uuid.UUID(ready["id"])
    analysis_id = _reserve(ready["id"], counselor_id)
    analysis_service._SignalsSave(sid, analysis_id)(_signals_bundle())

    with SessionLocal() as db:
        requested_at = db.get(ConsultationSession, sid).ai_started_at

    paused, release = threading.Event(), threading.Event()
    errors: List[str] = []
    outcomes: Dict[str, Any] = {}
    pids: Dict[str, int] = {}
    real_sync = analysis_service._sync_summary_draft

    def sync(db, **kwargs):
        pids["draft"] = db.scalar(text("select pg_backend_pid()"))
        paused.set()
        release.wait(timeout=WAIT_SECONDS)
        return real_sync(db, **kwargs)

    monkeypatch.setattr(analysis_service, "_sync_summary_draft", sync)

    def draft() -> None:
        with SessionLocal() as db:
            outcomes["draft"] = analysis_service._save_drafts(
                db, session_id=sid, analysis_id=analysis_id, requested_at=requested_at, bundle=_final_bundle()
            )

    def delete() -> None:
        with SessionLocal() as db:
            pids["delete"] = db.scalar(text("select pg_backend_pid()"))
            session_service.delete_session(db, db.get(ConsultationSession, sid), types.SimpleNamespace(id=counselor_id))
            outcomes["delete"] = True

    def guarded(target: Callable[[], None]) -> Callable[[], None]:
        def body() -> None:
            try:
                target()
            except Exception as error:  # noqa: BLE001 — 교착이면 여기로 온다
                errors.append(type(error).__name__)

        return body

    first = threading.Thread(target=guarded(draft), daemon=True)
    first.start()
    assert paused.wait(timeout=WAIT_SECONDS)

    second = threading.Thread(target=guarded(delete), daemon=True)
    second.start()

    blocked = False
    deadline = time.monotonic() + 8

    try:
        while time.monotonic() < deadline:
            if "delete" in pids:
                with engine.connect() as connection:
                    blockers = connection.scalar(text("select pg_blocking_pids(:pid)"), {"pid": pids["delete"]})

                if pids["draft"] in blockers:
                    blocked = True
                    break

            time.sleep(0.05)
    finally:
        release.set()
        first.join(timeout=WAIT_SECONDS)
        second.join(timeout=WAIT_SECONDS)

    assert blocked
    assert errors == []
    assert outcomes == {"draft": True, "delete": True}

    with SessionLocal() as db:
        assert db.get(ConsultationSession, sid) is None
        assert db.get(AIAnalysis, analysis_id) is None
