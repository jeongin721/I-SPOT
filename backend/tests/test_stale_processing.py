# "처리 중" 에 멈춘 Session 복구 테스트.
#
# STT · AI 처리는 같은 프로세스의 BackgroundTasks 에서만 돈다. 처리 도중 서버가
# 재시작·종료되면 작업이 사라지고, 처리 중 상태에서 벗어나는 API 경로가 없어
# Session 이 영원히 멈춘다.
#
# 제한 시간(STT/AI_TIMEOUT_SECONDS) + 여유 시간이 지나도 처리 중이면 작업이 사라진
# 것으로 보고 실패로 마감한 뒤 재시도를 허용한다. 제한 시간 안의 작업은 살아 있을
# 수 있으므로 건드리지 않는다.

import types
import uuid
from datetime import datetime, timedelta, timezone

from app.core.database import SessionLocal
from app.models.analysis import AIAnalysis
from app.models.session import ConsultationSession
from app.services import analysis_service, transcript_service
from tests.conftest import upload_audio
from tests.test_analysis import _get_analysis, _run_analysis, confirmed_session
from tests.test_stt_transcript import _get_transcript, _run_stt

# 제한 시간(conftest: 5초)과 여유 시간을 한참 넘긴 시각
LONG_AGO_SECONDS = 3600


# =========================================================
# helper — "요청은 기록됐는데 Background 작업이 사라진" 상태 만들기
# =========================================================

def _user(user_id: uuid.UUID) -> types.SimpleNamespace:
    return types.SimpleNamespace(id=user_id)


def _start_stt_without_worker(session_id: str, counselor_id: uuid.UUID) -> None:
    with SessionLocal() as db:
        session = db.get(ConsultationSession, uuid.UUID(session_id))
        transcript_service.request_stt(db, session, _user(counselor_id))


def _start_analysis_without_worker(session_id: str, counselor_id: uuid.UUID) -> None:
    with SessionLocal() as db:
        session = db.get(ConsultationSession, uuid.UUID(session_id))
        analysis_service.request_analysis(db, session, _user(counselor_id))


def _started(session_id: str, field: str, seconds_ago: int) -> None:
    with SessionLocal() as db:
        session = db.get(ConsultationSession, uuid.UUID(session_id))
        setattr(session, field, datetime.now(timezone.utc) - timedelta(seconds=seconds_ago))
        db.commit()


def _analysis_statuses(session_id: str) -> list:
    with SessionLocal() as db:
        return [
            analysis.status.value
            for analysis in db.query(AIAnalysis)
            .filter(AIAnalysis.session_id == uuid.UUID(session_id))
            .order_by(AIAnalysis.created_at)
        ]


# =========================================================
# STT
# =========================================================

def test_stale_stt_processing_fails_on_poll_and_can_be_retried(
    client, counselor_headers, counselor_id, session
) -> None:
    assert upload_audio(client, counselor_headers, session["id"])[0] == 201
    _start_stt_without_worker(session["id"], counselor_id)
    _started(session["id"], "stt_started_at", LONG_AGO_SECONDS)

    envelope = _get_transcript(client, counselor_headers, session["id"]).json()["data"]

    assert envelope["session_status"] == "STT_FAILED"
    assert envelope["error"]["code"] == "STT_FAILED"

    assert _run_stt(client, counselor_headers, session["id"]).status_code == 202

    envelope = _get_transcript(client, counselor_headers, session["id"]).json()["data"]
    assert envelope["session_status"] == "STT_REVIEW_REQUIRED"


def test_stt_processing_within_time_limit_is_left_alone(
    client, counselor_headers, counselor_id, session
) -> None:
    """살아 있을 수 있는 작업을 실패로 만들지 않는다."""

    assert upload_audio(client, counselor_headers, session["id"])[0] == 201
    _start_stt_without_worker(session["id"], counselor_id)

    envelope = _get_transcript(client, counselor_headers, session["id"]).json()["data"]

    assert envelope["session_status"] == "STT_PROCESSING"
    assert _run_stt(client, counselor_headers, session["id"]).status_code == 409


def test_session_detail_also_recovers_stale_processing(
    client, counselor_headers, counselor_id, session
) -> None:
    """Frontend 는 새로고침 후 Session 상세로 화면을 복원한다."""

    assert upload_audio(client, counselor_headers, session["id"])[0] == 201
    _start_stt_without_worker(session["id"], counselor_id)
    _started(session["id"], "stt_started_at", LONG_AGO_SECONDS)

    response = client.get(f"/api/v1/sessions/{session['id']}", headers=counselor_headers)

    assert response.status_code == 200
    assert response.json()["data"]["status"] == "STT_FAILED"


# =========================================================
# AI 분석
# =========================================================

def test_stale_ai_processing_fails_on_poll_and_can_be_retried(
    client, counselor_headers, counselor_id, session
) -> None:
    confirmed_session(client, counselor_headers, session["id"])
    _start_analysis_without_worker(session["id"], counselor_id)
    _started(session["id"], "ai_started_at", LONG_AGO_SECONDS)

    envelope = _get_analysis(client, counselor_headers, session["id"]).json()["data"]

    assert envelope["session_status"] == "AI_FAILED"
    assert envelope["error"]["code"] == "AI_FAILED"
    assert envelope["analysis"]["status"] == "FAILED"

    assert _run_analysis(client, counselor_headers, session["id"]).status_code == 202

    envelope = _get_analysis(client, counselor_headers, session["id"]).json()["data"]
    assert envelope["session_status"] == "AI_REVIEW_REQUIRED"
    assert _analysis_statuses(session["id"]) == ["FAILED", "COMPLETED"]


def test_retry_request_recovers_stale_ai_processing_without_poll(
    client, counselor_headers, counselor_id, session
) -> None:
    """조회를 거치지 않고 바로 재요청해도 복구된다."""

    confirmed_session(client, counselor_headers, session["id"])
    _start_analysis_without_worker(session["id"], counselor_id)
    _started(session["id"], "ai_started_at", LONG_AGO_SECONDS)

    assert _run_analysis(client, counselor_headers, session["id"]).status_code == 202
    assert _analysis_statuses(session["id"]) == ["FAILED", "COMPLETED"]
