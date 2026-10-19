# 늦은 AI 결과 · 작업 전체 마감 시험.
#
# 분석 작업이 멈춤 판정(session_service.expire_stale_processing)에 마감된 뒤 늦게 끝나도 그 결과(성공 · 실패)가
# 회차를 덮지 않는지, 준비 · 분석 제한 시간이 요청 시각부터 잰 작업 전체 마감 안에 드는지 본다.
#
# 분석은 서비스 함수로 예약만 하고 작업(process_analysis)은 따로 돌린다. TestClient 는 BackgroundTasks 를
# 응답 안에서 끝까지 돌려서 작업 도중에 조회를 끼워 넣을 수 없다.
# 무거운 모델 대신 가짜 어댑터를 쓰고, 저장은 실제 analysis_service 와 시험 DB(SQLite 등)로 한다.
# 녹취 · 결과 · 오류 문구는 모두 가상 데이터다.

import logging
import threading
import time
import types
import uuid
from datetime import timedelta
from typing import Any, Dict, List, Optional

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, update

from app.adapters.ai_adapter import (
    AI_TIMEOUT_MESSAGE,
    AIAnalysisBundle,
    AIError,
    set_ai_adapter_override,
)
from app.core.config import settings
from app.core.database import SessionLocal
from app.core.enums import AuditAction
from app.core.errors import ErrorCode
from app.models.analysis import AIAnalysis
from app.models.audit_log import AuditLog
from app.models.session import ConsultationSession
from app.models.summary import ConsultationSummary
from app.schemas.contracts import AIAnalysisResult
from app.services import analysis_service, session_service
from tests.test_analysis import _get_analysis, confirmed_session

# 이벤트 · thread 를 기다리는 최대 초. 정상이면 금방 끝난다.
WAIT_SECONDS = 10

LATE_FAILURE_TEXT = "가상 LLM 연결 실패 문구"


# =========================================================
# 테스트용 Adapter
# =========================================================

def _bundle(provider: str) -> AIAnalysisBundle:
    return AIAnalysisBundle(result=AIAnalysisResult(), provider=provider)


class _HeldAdapter:
    """첫 분석은 release 가 켜질 때까지 붙잡아 두었다가 outcome 대로 끝낸다. 그 뒤 분석은 바로 성공한다."""

    name = "held"

    def __init__(self, outcome: str) -> None:
        self.outcome = outcome
        self.entered = threading.Event()
        self.release = threading.Event()
        self.calls = 0

    def analyze(self, transcript_payload):
        self.calls += 1

        if self.calls > 1:
            return _bundle(self.name)

        self.entered.set()
        self.release.wait(timeout=WAIT_SECONDS)

        if self.outcome == "failure":
            raise AIError(LATE_FAILURE_TEXT, ErrorCode.AI_FAILED)

        return _bundle(self.name)


class _TimedAdapter:
    """준비(모델 로드)와 분석에 정해진 시간이 걸린다. 분석이 끝나면 done 이 켜진다."""

    name = "timed"

    def __init__(self, prepare_seconds: float, analyze_seconds: float) -> None:
        self.prepare_seconds = prepare_seconds
        self.analyze_seconds = analyze_seconds
        self.done = threading.Event()

    def prepare(self) -> None:
        time.sleep(self.prepare_seconds)

    def analyze(self, transcript_payload):
        try:
            time.sleep(self.analyze_seconds)

            return _bundle(self.name)
        finally:
            self.done.set()


class _RecordingAdapter:
    """준비 · 분석을 바로 끝내고, 분석이 받은 제한 시간을 남긴다."""

    name = "recording"

    def __init__(self) -> None:
        self.prepared = 0
        self.time_limits: List[Optional[float]] = []

    def prepare(self) -> None:
        self.prepared += 1

    def analyze(self, transcript_payload, *, time_limit_seconds: Optional[float] = None):
        self.time_limits.append(time_limit_seconds)

        return _bundle(self.name)


# =========================================================
# helper
# =========================================================

def _reserve(session_id: str, counselor_id: uuid.UUID) -> uuid.UUID:
    """분석을 예약만 한다(POST 가 부르는 서비스 함수와 같다). 작업은 돌리지 않는다."""

    with SessionLocal() as db:
        item = db.get(ConsultationSession, uuid.UUID(session_id))
        analysis = analysis_service.request_analysis(db, item, types.SimpleNamespace(id=counselor_id))

        return analysis.id


def _shift_requested_at(session_id: str, seconds: float) -> None:
    """요청 시각(ai_started_at)을 seconds 초 과거로 옮긴다. 요청 뒤 그만큼 시간이 흐른 것과 같다. 음수면 미래로."""

    with SessionLocal() as db:
        item = db.get(ConsultationSession, uuid.UUID(session_id))
        db.execute(
            update(ConsultationSession)
            .where(ConsultationSession.id == item.id)
            .values(ai_started_at=item.ai_started_at - timedelta(seconds=seconds))
        )
        db.commit()


def _pass_stale_time(session_id: str) -> None:
    """멈춤 판정 시각(요청 + AI_TIMEOUT_SECONDS + STALE_GRACE_SECONDS)이 지난 것으로 만든다.

    작업이 아직 돌고 있는데 판정 시각이 지나는 경우(서버 시계 차이 · 아주 긴 대기 등)를 흉내 낸다.
    """

    _shift_requested_at(
        session_id, settings.AI_TIMEOUT_SECONDS + session_service.STALE_GRACE_SECONDS + 1
    )


def _start_worker(session_id: str, analysis_id: uuid.UUID) -> threading.Thread:
    thread = threading.Thread(
        target=analysis_service.process_analysis,
        args=(uuid.UUID(session_id), analysis_id),
        daemon=True,
    )
    thread.start()

    return thread


def _saved(session_id: str, analysis_id: uuid.UUID) -> Dict[str, Any]:
    """DB 에 남은 회차 · 분석 · 요약 초안 · 완료 감사 기록."""

    with SessionLocal() as db:
        item = db.get(ConsultationSession, uuid.UUID(session_id))
        analysis = db.get(AIAnalysis, analysis_id)
        summary = db.scalar(
            select(ConsultationSummary).where(ConsultationSummary.session_id == item.id)
        )
        completed = db.scalars(
            select(AuditLog.entity_id).where(AuditLog.action == AuditAction.ANALYSIS_COMPLETED)
        ).all()

        return {
            "session_status": item.status.value,
            "analysis_status": analysis.status.value,
            "analysis_error": analysis.error_code,
            "analysis_message": analysis.error_message,
            "has_result": analysis.result is not None,
            "summary_analysis_id": summary.analysis_id if summary else None,
            "completed_audits": list(completed),
        }


def _poll(client: TestClient, headers: Dict[str, str], session_id: str) -> dict:
    response = _get_analysis(client, headers, session_id)

    assert response.status_code == 200

    return response.json()["data"]


# =========================================================
# 늦은 결과 — 멈춤 판정이 마감한 작업
# =========================================================

def test_queued_worker_with_slow_prepare_cannot_complete_expired_job(
    client: TestClient,
    counselor_headers,
    counselor_id,
    session: dict,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """요청 → 작업 시작 지연 → 준비 → 분석 중 멈춤 판정 → 늦은 성공. 회차 · 분석은 실패 그대로여야 한다.

    기본값(분석 제한 180 · 여유 60 · 준비 제한 45초)을 1/100 로 줄였다: 대기 50 · 준비 40 · 분석 160초.
    분석 제한을 준비 뒤에 새로 재면 분석이 요청 + 250초에 끝나, 멈춤 판정(요청 + 240초)이 실패로
    마감한 회차를 완료로 덮는다(Codex PR #62 교차검증 재현).
    """

    confirmed_session(client, counselor_headers, session["id"])

    scale = 0.01
    monkeypatch.setattr(settings, "AI_TIMEOUT_SECONDS", 180 * scale)
    monkeypatch.setattr(session_service, "STALE_GRACE_SECONDS", 60 * scale)
    monkeypatch.setattr(analysis_service, "PREPARE_TIMEOUT_SECONDS", 45 * scale)

    queue_seconds = 50 * scale
    stale_after = (180 + 60) * scale
    adapter = _TimedAdapter(prepare_seconds=40 * scale, analyze_seconds=160 * scale)
    set_ai_adapter_override(adapter)

    analysis_id = _reserve(session["id"], counselor_id)
    requested = time.monotonic()

    def worker() -> None:
        time.sleep(queue_seconds)
        analysis_service.process_analysis(uuid.UUID(session["id"]), analysis_id)

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()

    try:
        # 멈춤 판정 시각 바로 뒤에 조회한다.
        time.sleep(max(0.0, stale_after + 0.02 - (time.monotonic() - requested)))
        polled = _poll(client, counselor_headers, session["id"])

        thread.join(timeout=WAIT_SECONDS)
        # 제한 시간에 걸려 버려진 분석(가짜)도 끝날 때까지 기다린다. 그 뒤에도 늦은 저장이 없어야 한다.
        assert adapter.done.wait(timeout=WAIT_SECONDS)
    finally:
        thread.join(timeout=WAIT_SECONDS)

    assert not thread.is_alive()
    assert polled["session_status"] == "AI_FAILED"

    saved = _saved(session["id"], analysis_id)

    assert saved["session_status"] == "AI_FAILED"
    assert saved["analysis_status"] == "FAILED"
    assert not saved["has_result"]
    assert saved["summary_analysis_id"] is None
    assert analysis_id not in saved["completed_audits"]


def test_late_success_after_stale_expiry_is_discarded(
    client: TestClient, counselor_headers, counselor_id, session: dict, caplog
) -> None:
    """분석하는 사이 멈춤 판정이 실패로 마감하면, 늦게 온 성공 결과는 버린다(요약 초안 · 완료 기록도 없다)."""

    confirmed_session(client, counselor_headers, session["id"])
    adapter = _HeldAdapter("success")
    set_ai_adapter_override(adapter)

    analysis_id = _reserve(session["id"], counselor_id)
    worker = _start_worker(session["id"], analysis_id)

    with caplog.at_level(logging.WARNING):
        try:
            assert adapter.entered.wait(timeout=WAIT_SECONDS)

            _pass_stale_time(session["id"])
            assert _poll(client, counselor_headers, session["id"])["session_status"] == "AI_FAILED"

            adapter.release.set()
            worker.join(timeout=WAIT_SECONDS)
        finally:
            adapter.release.set()
            worker.join(timeout=WAIT_SECONDS)

    assert not worker.is_alive()

    saved = _saved(session["id"], analysis_id)

    assert saved["session_status"] == "AI_FAILED"
    assert saved["analysis_status"] == "FAILED"
    assert saved["analysis_message"] == session_service._STALE_MESSAGE
    assert not saved["has_result"]
    assert saved["summary_analysis_id"] is None
    assert analysis_id not in saved["completed_audits"]

    envelope = _poll(client, counselor_headers, session["id"])

    assert envelope["session_status"] == "AI_FAILED"
    assert envelope["error"] == {"code": "AI_FAILED", "message": session_service._STALE_MESSAGE}

    # 버린 사실은 분석 id 로만 남긴다.
    assert f"analysis_id={analysis_id}" in caplog.text


@pytest.mark.parametrize("outcome", ["success", "failure"])
def test_late_result_does_not_overwrite_retried_job(
    client: TestClient, counselor_headers, counselor_id, session: dict, caplog, outcome: str
) -> None:
    """멈춤 판정 뒤 상담사가 다시 시도해 새 작업이 처리 중이면, 옛 작업의 늦은 성공 · 실패가 새 작업을 덮지 않는다."""

    confirmed_session(client, counselor_headers, session["id"])
    adapter = _HeldAdapter(outcome)
    set_ai_adapter_override(adapter)

    first_id = _reserve(session["id"], counselor_id)
    worker = _start_worker(session["id"], first_id)

    with caplog.at_level(logging.WARNING):
        try:
            assert adapter.entered.wait(timeout=WAIT_SECONDS)

            _pass_stale_time(session["id"])
            assert _poll(client, counselor_headers, session["id"])["session_status"] == "AI_FAILED"

            # 다시 시도. 새 작업은 아직 돌지 않았다(처리 중).
            second_id = _reserve(session["id"], counselor_id)

            adapter.release.set()
            worker.join(timeout=WAIT_SECONDS)
        finally:
            adapter.release.set()
            worker.join(timeout=WAIT_SECONDS)

    assert not worker.is_alive()

    first = _saved(session["id"], first_id)
    second = _saved(session["id"], second_id)

    # 회차는 새 작업을 그대로 기다린다.
    assert first["session_status"] == "AI_PROCESSING"
    assert second["analysis_status"] == "PROCESSING"
    # 옛 작업은 멈춤 판정이 적은 실패 그대로다.
    assert first["analysis_status"] == "FAILED"
    assert first["analysis_error"] == "AI_FAILED"
    assert first["analysis_message"] == session_service._STALE_MESSAGE
    assert not first["has_result"]
    assert first["summary_analysis_id"] is None

    assert f"analysis_id={first_id}" in caplog.text
    assert LATE_FAILURE_TEXT not in caplog.text

    # 새 작업은 정상으로 끝난다.
    analysis_service.process_analysis(uuid.UUID(session["id"]), second_id)

    after = _saved(session["id"], second_id)

    assert after["session_status"] == "AI_REVIEW_REQUIRED"
    assert after["analysis_status"] == "COMPLETED"
    assert after["summary_analysis_id"] == second_id
    assert first_id not in after["completed_audits"]


def test_worker_started_after_job_was_replaced_does_not_run(
    client: TestClient, counselor_headers, counselor_id, session: dict
) -> None:
    """멈춤 판정 · 재시도 뒤에야 시작한 옛 작업은 준비 · 분석을 하지 않고 끝난다."""

    confirmed_session(client, counselor_headers, session["id"])
    adapter = _RecordingAdapter()
    set_ai_adapter_override(adapter)

    first_id = _reserve(session["id"], counselor_id)
    _pass_stale_time(session["id"])
    assert _poll(client, counselor_headers, session["id"])["session_status"] == "AI_FAILED"
    second_id = _reserve(session["id"], counselor_id)

    analysis_service.process_analysis(uuid.UUID(session["id"]), first_id)

    assert adapter.prepared == 0
    assert adapter.time_limits == []

    saved = _saved(session["id"], second_id)

    assert saved["session_status"] == "AI_PROCESSING"
    assert saved["analysis_status"] == "PROCESSING"
    assert _saved(session["id"], first_id)["analysis_status"] == "FAILED"


# =========================================================
# 작업 전체 마감 — 요청 시각부터 준비 제한 + 분석 제한
# =========================================================

def test_job_with_no_time_left_times_out_without_running(
    client: TestClient, counselor_headers, counselor_id, session: dict
) -> None:
    """작업 시작이 늦어 요청부터 잰 작업 전체 마감이 이미 지났으면 준비 · 분석 없이 바로 AI_TIMEOUT.

    멈춤 판정 시각 전이라도 시작하지 않는다(시작하면 판정 시각을 넘겨 끝난다).
    """

    confirmed_session(client, counselor_headers, session["id"])
    adapter = _RecordingAdapter()
    set_ai_adapter_override(adapter)

    analysis_id = _reserve(session["id"], counselor_id)
    _shift_requested_at(
        session["id"], settings.AI_TIMEOUT_SECONDS + analysis_service.PREPARE_TIMEOUT_SECONDS + 1
    )

    analysis_service.process_analysis(uuid.UUID(session["id"]), analysis_id)

    envelope = _poll(client, counselor_headers, session["id"])

    assert envelope["session_status"] == "AI_FAILED"
    assert envelope["error"] == {"code": "AI_TIMEOUT", "message": AI_TIMEOUT_MESSAGE}
    assert envelope["analysis"]["status"] == "FAILED"
    assert adapter.prepared == 0
    assert adapter.time_limits == []


# (요청 뒤 흐른 초, 기대 준비 제한, 기대 분석 제한). 시험 설정은 분석 제한 5초 · 준비 제한 45초라 작업 전체 50초.
# None 은 기본 제한 그대로(준비 45초 · 분석 5초)다.
@pytest.mark.parametrize(
    ("waited", "expected_prepare", "expected_analysis"),
    [
        (0, None, None),
        (20, 30.0, None),
        (47, 3.0, 3.0),
        # 요청 시각이 미래(서버 시계 차이)면 흐른 시간을 0 으로 본다. 기본 제한보다 늘리지 않는다.
        (-100, None, None),
    ],
)
def test_time_limits_fit_inside_job_deadline(
    client: TestClient,
    counselor_headers,
    counselor_id,
    session: dict,
    monkeypatch: pytest.MonkeyPatch,
    waited: float,
    expected_prepare: Optional[float],
    expected_analysis: Optional[float],
) -> None:
    """준비 제한 = min(준비 제한, 남은 시간), 분석 제한 = min(AI_TIMEOUT_SECONDS, 준비 뒤 남은 시간).

    분석 제한 시간을 받는 어댑터에는 줄어든 값을 넘긴다(modeling 이 마감 시각을 그 기준으로 잡는다).
    """

    confirmed_session(client, counselor_headers, session["id"])
    adapter = _RecordingAdapter()
    set_ai_adapter_override(adapter)

    limits: List[float] = []
    original = analysis_service.run_with_timeout

    def spy(func, timeout_seconds):
        limits.append(timeout_seconds)
        return original(func, timeout_seconds)

    monkeypatch.setattr(analysis_service, "run_with_timeout", spy)

    analysis_id = _reserve(session["id"], counselor_id)
    _shift_requested_at(session["id"], waited)

    analysis_service.process_analysis(uuid.UUID(session["id"]), analysis_id)

    prepare_limit, analysis_limit = limits
    expected_prepare = analysis_service.PREPARE_TIMEOUT_SECONDS if expected_prepare is None else expected_prepare
    expected_analysis = settings.AI_TIMEOUT_SECONDS if expected_analysis is None else expected_analysis

    # 남은 시간은 0.1초 단위로 내린다. 시험이 도는 사이 흐른 시간만큼 조금 짧을 수 있다.
    assert expected_prepare - 0.3 <= prepare_limit <= expected_prepare
    assert expected_analysis - 0.3 <= analysis_limit <= expected_analysis
    assert adapter.time_limits == [analysis_limit]
    assert _poll(client, counselor_headers, session["id"])["session_status"] == "AI_REVIEW_REQUIRED"
