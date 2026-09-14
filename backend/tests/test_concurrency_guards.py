# 동시 요청 안전장치 테스트.
#
# 두 요청이 같은 상태를 읽은 뒤 거의 동시에 들어오는 상황을 DB Session 두 개로 재현한다.
# TestClient 는 요청을 하나씩 처리하므로 API 호출만으로는 이 경합을 만들 수 없다.

import types
import uuid

import pytest
from sqlalchemy import func, select

from app.core.database import SessionLocal
from app.core.enums import SessionStatus
from app.core.errors import APIError, ErrorCode
from app.models.analysis import AIAnalysis
from app.models.session import ConsultationSession
from app.models.transcript import Transcript
from app.schemas.transcript import TranscriptUpdateRequest
from app.services import analysis_service, transcript_service
from tests.conftest import upload_audio
from tests.test_analysis import confirmed_session
from tests.test_stt_transcript import transcribed_session


@pytest.fixture
def two_db_sessions():
    """동시에 들어온 두 요청 각각의 DB Session."""

    first, second = SessionLocal(), SessionLocal()

    try:
        yield first, second
    finally:
        first.close()
        second.close()


def _load(db, session_id: str) -> ConsultationSession:
    """요청이 Session 을 읽는 시점을 흉내 낸다. 상태 값을 이때 읽어 둔다."""

    session = db.get(ConsultationSession, uuid.UUID(session_id))
    assert session is not None

    return session


def _count(model, session_id: str) -> int:
    with SessionLocal() as check:
        return check.scalar(
            select(func.count()).select_from(model).where(
                model.session_id == uuid.UUID(session_id)
            )
        )


# =========================================================
# AI 분석 / STT 요청을 동시에 두 번 보낸 경우
# =========================================================

def test_concurrent_analysis_requests_start_only_once(
    client, counselor_headers, counselor_id, session, two_db_sessions
) -> None:
    """두 번째 요청은 409 로 거절되고 분석은 하나만 만들어진다.

    막지 않으면 늦게 도는 Background 작업이 상태 불일치로 조기 종료하면서
    분석 하나가 PROCESSING 으로 영원히 남고, 최신 분석으로 조회되어
    완료된 결과를 가린다.
    """

    confirmed_session(client, counselor_headers, session["id"])

    first_db, second_db = two_db_sessions
    user = types.SimpleNamespace(id=counselor_id)

    first = _load(first_db, session["id"])
    second = _load(second_db, session["id"])
    assert first.status == second.status == SessionStatus.STT_CONFIRMED

    analysis_service.request_analysis(first_db, first, user)

    with pytest.raises(APIError) as raised:
        analysis_service.request_analysis(second_db, second, user)

    assert raised.value.status_code == 409
    assert raised.value.code == ErrorCode.INVALID_SESSION_STATE
    assert _count(AIAnalysis, session["id"]) == 1


def test_concurrent_stt_requests_start_only_once(
    client, counselor_headers, counselor_id, session, two_db_sessions
) -> None:
    """STT 도 같다. 막지 않으면 외부 STT 가 두 번 호출된다."""

    status_code, _ = upload_audio(client, counselor_headers, session["id"])
    assert status_code == 201

    first_db, second_db = two_db_sessions
    user = types.SimpleNamespace(id=counselor_id)

    first = _load(first_db, session["id"])
    second = _load(second_db, session["id"])
    assert first.status == second.status == SessionStatus.AUDIO_UPLOADED

    transcript_service.request_stt(first_db, first, user)

    with pytest.raises(APIError) as raised:
        transcript_service.request_stt(second_db, second, user)

    assert raised.value.status_code == 409
    assert raised.value.code == ErrorCode.INVALID_SESSION_STATE


# =========================================================
# Transcript 를 동시에 수정한 경우
# =========================================================

def test_concurrent_transcript_edits_return_conflict_not_server_error(
    client, counselor_headers, counselor_id, session, two_db_sessions, monkeypatch
) -> None:
    """같은 version 을 보고 동시에 저장하면 두 번째는 500 이 아니라 409 를 받는다."""

    transcribed_session(client, counselor_headers, session["id"])

    first_db, second_db = two_db_sessions
    user = types.SimpleNamespace(id=counselor_id)

    first = _load(first_db, session["id"])
    second = _load(second_db, session["id"])

    # 두 번째 요청은 첫 번째가 저장하기 전에 version 1 을 읽어 둔 상태다.
    stale_latest = transcript_service.get_latest_transcript(second_db, second.id)
    assert stale_latest.version == 1
    segment_id = stale_latest.segments[0].segment_id

    transcript_service.update_transcript(
        first_db,
        first,
        user,
        TranscriptUpdateRequest(segments=[{"segment_id": segment_id, "text": "첫 번째 수정"}]),
    )

    monkeypatch.setattr(
        transcript_service, "get_latest_transcript", lambda db, session_id: stale_latest
    )

    with pytest.raises(APIError) as raised:
        transcript_service.update_transcript(
            second_db,
            second,
            user,
            TranscriptUpdateRequest(segments=[{"segment_id": segment_id, "text": "두 번째 수정"}]),
        )

    assert raised.value.status_code == 409
    assert raised.value.code == ErrorCode.DUPLICATE_RESOURCE

    # 먼저 저장한 수정은 그대로 남는다.
    assert _count(Transcript, session["id"]) == 2
