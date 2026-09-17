# 처리 대기 업무 목록(/tasks) 테스트.
#
# 업무는 따로 저장하지 않고 회기 상태에서 계산한다. 그래서 테스트는 API 로
# 사례·회기를 만든 뒤, 원하는 상태와 시각을 DB 에 직접 넣어 계산 결과를 확인한다.

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, select

from app.core.config import settings
from app.core.database import SessionLocal, engine
from app.core.enums import SessionStatus
from app.models.audio import AudioFile
from app.models.session import ConsultationSession
from app.models.transcript import Transcript
from tests.conftest import create_case, create_session, upload_audio
from tests.test_analysis import confirmed_session

TASKS = "/api/v1/tasks"
SUMMARY = "/api/v1/tasks/summary"

STATUS_TO_TASK = {
    "CREATED": "UPLOAD_AUDIO",
    "AUDIO_UPLOADED": "REQUEST_STT",
    "STT_REVIEW_REQUIRED": "REVIEW_TRANSCRIPT",
    "STT_CONFIRMED": "REQUEST_ANALYSIS",
    "AI_REVIEW_REQUIRED": "REVIEW_ANALYSIS",
    "STT_FAILED": "RETRY_STT",
    "AI_FAILED": "RETRY_ANALYSIS",
}


# =========================================================
# helper
# =========================================================

def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))

    # 기존 Session 응답은 SQLite 에서 시간대 없이 나온다. 저장 값은 UTC 다.
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _set_session(session_id: str, **fields) -> None:
    with SessionLocal() as db:
        session = db.get(ConsultationSession, uuid.UUID(session_id))

        for name, value in fields.items():
            setattr(session, name, value)

        db.commit()


def _set_audio_times(session_id: str, *times: datetime) -> None:
    """업로드 순서대로 음성 파일의 업로드 시각을 바꾼다."""

    with SessionLocal() as db:
        audio_files = db.scalars(
            select(AudioFile)
            .where(AudioFile.session_id == uuid.UUID(session_id))
            .order_by(AudioFile.created_at)
        ).all()

        for audio_file, when in zip(audio_files, times, strict=True):
            audio_file.created_at = when

        db.commit()


def _set_confirmed_at(session_id: str, when: datetime) -> None:
    with SessionLocal() as db:
        transcript = db.scalar(
            select(Transcript)
            .where(
                Transcript.session_id == uuid.UUID(session_id),
                Transcript.is_confirmed.is_(True),
            )
        )
        transcript.confirmed_at = when
        db.commit()


def _get(client: TestClient, headers, **params):
    return client.get(TASKS, params=params, headers=headers)


def _list(client: TestClient, headers, **params) -> dict:
    response = _get(client, headers, **params)

    assert response.status_code == 200, response.text

    return response.json()["data"]


def _ids(data: dict) -> list:
    return [item["session_id"] for item in data["items"]]


def _waiting(data: dict) -> dict:
    return {item["session_id"]: _parse(item["waiting_since"]) for item in data["items"]}


def _same_time(left: datetime, right: datetime) -> bool:
    return abs((left - right).total_seconds()) < 0.001


# =========================================================
# 응답 형식 · 인증
# =========================================================

def test_requires_login(client: TestClient) -> None:
    assert client.get(TASKS).status_code == 401
    assert client.get(SUMMARY).status_code == 401


def test_no_cases_means_empty_list(client: TestClient, counselor_headers) -> None:
    data = _list(client, counselor_headers)

    assert data["items"] == []
    assert data["meta"]["total"] == 0


def test_task_item_carries_only_what_the_screen_needs(
    client: TestClient, counselor_headers, counselor_id, case, session
) -> None:
    """아동은 별칭만 내려주고, 상담 원문이나 오류 메시지 원문은 내려주지 않는다."""

    item = _list(client, counselor_headers)["items"][0]

    assert set(item) == {
        "session_id", "case_id", "case_number", "child_alias", "session_number",
        "session_title", "session_status", "task_type", "waiting_since", "is_overdue",
        "counselor_id", "counselor_name", "last_error_code",
    }
    assert item["case_id"] == case["id"]
    assert item["case_number"] == case["case_number"]
    assert item["child_alias"] == case["child_alias"]
    assert item["session_number"] == 1
    assert item["session_title"] == "1회기 상담"
    assert item["counselor_id"] == str(counselor_id)
    assert item["counselor_name"] == "상담사A"
    assert item["last_error_code"] is None

    # DB 가 시간대 없이 돌려줘도(SQLite) 응답은 항상 UTC 표시가 붙는다.
    assert item["waiting_since"].endswith("Z")


def test_page_past_the_end_is_empty(client: TestClient, counselor_headers, session) -> None:
    data = _list(client, counselor_headers, page=5, page_size=10)

    assert data["items"] == []
    assert data["meta"]["total"] == 1
    assert data["meta"]["page"] == 5


# =========================================================
# 상태 → 업무 종류
# =========================================================

@pytest.mark.parametrize("status, task_type", STATUS_TO_TASK.items())
def test_each_waiting_status_becomes_a_task(
    client: TestClient, counselor_headers, session, status, task_type
) -> None:
    _set_session(session["id"], status=SessionStatus(status))

    items = _list(client, counselor_headers)["items"]

    assert [(i["session_id"], i["session_status"], i["task_type"]) for i in items] == [
        (session["id"], status, task_type)
    ]


@pytest.mark.parametrize("status", ["STT_PROCESSING", "AI_PROCESSING", "APPROVED"])
def test_system_turn_and_finished_sessions_are_not_tasks(
    client: TestClient, counselor_headers, session, status
) -> None:
    fields = {"status": SessionStatus(status)}

    # 제한 시간 안의 처리 중 상태는 살아 있는 작업이라 그대로 둔다.
    if status == "STT_PROCESSING":
        fields["stt_started_at"] = _now()
    if status == "AI_PROCESSING":
        fields["ai_started_at"] = _now()

    _set_session(session["id"], **fields)

    assert _list(client, counselor_headers)["items"] == []


def test_stale_processing_session_shows_up_as_retry(
    client: TestClient, counselor_headers, session
) -> None:
    """서버 재시작 등으로 멈춘 처리 중 회기는 조회할 때 실패로 마감되어 재시도 업무가 된다."""

    _set_session(
        session["id"],
        status=SessionStatus.STT_PROCESSING,
        stt_started_at=_now() - timedelta(hours=1),
    )

    items = _list(client, counselor_headers)["items"]

    assert [(i["task_type"], i["last_error_code"]) for i in items] == [
        ("RETRY_STT", "STT_FAILED")
    ]


# =========================================================
# 대기 시작 시각
# =========================================================

def test_waiting_since_for_simple_statuses(
    client: TestClient, counselor_headers, case
) -> None:
    base = _now() - timedelta(days=3)
    expected = {}

    not_scheduled = create_session(client, counselor_headers, case["id"])
    expected[not_scheduled["id"]] = _parse(not_scheduled["created_at"])

    scheduled = create_session(client, counselor_headers, case["id"])
    _set_session(scheduled["id"], consulted_at=base + timedelta(hours=1))
    expected[scheduled["id"]] = base + timedelta(hours=1)

    cases = [
        ("STT_REVIEW_REQUIRED", "stt_completed_at", 2),
        ("AI_REVIEW_REQUIRED", "ai_completed_at", 3),
        ("STT_FAILED", "stt_completed_at", 4),
        ("AI_FAILED", "ai_completed_at", 5),
    ]

    for status, field, hours in cases:
        created = create_session(client, counselor_headers, case["id"])
        _set_session(
            created["id"],
            status=SessionStatus(status),
            **{field: base + timedelta(hours=hours)},
        )
        expected[created["id"]] = base + timedelta(hours=hours)

    got = _waiting(_list(client, counselor_headers))

    assert set(got) == set(expected)

    for session_id, when in expected.items():
        assert _same_time(got[session_id], when), session_id


def test_waiting_since_for_uploaded_audio_is_latest_upload(
    client: TestClient, counselor_headers, session
) -> None:
    base = _now() - timedelta(days=2)

    assert upload_audio(client, counselor_headers, session["id"])[0] == 201
    assert upload_audio(client, counselor_headers, session["id"])[0] == 201

    _set_audio_times(session["id"], base, base + timedelta(hours=7))

    got = _waiting(_list(client, counselor_headers))

    assert _same_time(got[session["id"]], base + timedelta(hours=7))


def test_waiting_since_for_confirmed_transcript_is_confirmation(
    client: TestClient, counselor_headers, session
) -> None:
    base = _now() - timedelta(days=2)

    confirmed_session(client, counselor_headers, session["id"])
    _set_confirmed_at(session["id"], base)

    data = _list(client, counselor_headers)

    assert data["items"][0]["task_type"] == "REQUEST_ANALYSIS"
    assert _same_time(_waiting(data)[session["id"]], base)


def test_reopened_transcript_waits_from_confirmation(
    client: TestClient, counselor_headers, session
) -> None:
    """확정 후 다시 고치려고 되돌린 회기가 원래 STT 완료 시각 기준으로 "지연"이 되면 안 된다."""

    base = _now() - timedelta(days=5)

    confirmed_session(client, counselor_headers, session["id"])
    _set_confirmed_at(session["id"], base + timedelta(days=4))
    _set_session(
        session["id"],
        status=SessionStatus.STT_REVIEW_REQUIRED,
        stt_completed_at=base,
    )

    data = _list(client, counselor_headers)

    assert data["items"][0]["task_type"] == "REVIEW_TRANSCRIPT"
    assert _same_time(_waiting(data)[session["id"]], base + timedelta(days=4))


def test_analysis_request_after_ai_failure_waits_from_failure(
    client: TestClient, counselor_headers, session
) -> None:
    base = _now() - timedelta(days=5)

    confirmed_session(client, counselor_headers, session["id"])
    _set_confirmed_at(session["id"], base)
    _set_session(
        session["id"],
        status=SessionStatus.STT_CONFIRMED,
        ai_completed_at=base + timedelta(days=3),
    )

    data = _list(client, counselor_headers)

    assert _same_time(_waiting(data)[session["id"]], base + timedelta(days=3))


# =========================================================
# 정렬
# =========================================================

def test_oldest_task_comes_first_with_stable_tie_break(
    client: TestClient, counselor_headers
) -> None:
    case_a = create_case(client, counselor_headers)
    case_b = create_case(client, counselor_headers)
    assert case_a["case_number"] < case_b["case_number"]

    a1 = create_session(client, counselor_headers, case_a["id"])
    a2 = create_session(client, counselor_headers, case_a["id"])
    a3 = create_session(client, counselor_headers, case_a["id"])
    b1 = create_session(client, counselor_headers, case_b["id"])

    t0 = _now() - timedelta(days=3)
    t1 = t0 + timedelta(hours=1)
    t2 = t0 + timedelta(hours=2)

    _set_session(a1["id"], consulted_at=t0)
    _set_session(a2["id"], consulted_at=t1)
    _set_session(b1["id"], consulted_at=t1)
    _set_session(a3["id"], consulted_at=t2)

    assert _ids(_list(client, counselor_headers)) == [
        a1["id"], a2["id"], b1["id"], a3["id"],
    ]


# =========================================================
# 권한
# =========================================================

def test_counselor_sees_only_own_case_tasks(
    client: TestClient, counselor_headers, other_counselor_headers, session
) -> None:
    other_case = create_case(client, other_counselor_headers)
    other_session = create_session(client, other_counselor_headers, other_case["id"])

    assert _ids(_list(client, counselor_headers)) == [session["id"]]
    assert _ids(_list(client, other_counselor_headers)) == [other_session["id"]]


def test_reassigned_case_moves_tasks_to_new_counselor(
    client: TestClient,
    counselor_headers,
    other_counselor_headers,
    other_counselor_id,
    admin_headers,
    case,
    session,
) -> None:
    """회기의 담당자 칸은 사례 담당자를 바꿔도 그대로라, 사례 기준으로 걸러야 한다."""

    response = client.patch(
        f"/api/v1/cases/{case['id']}",
        json={"counselor_id": str(other_counselor_id)},
        headers=admin_headers,
    )
    assert response.status_code == 200

    assert _list(client, counselor_headers)["items"] == []

    items = _list(client, other_counselor_headers)["items"]

    assert [i["session_id"] for i in items] == [session["id"]]
    assert items[0]["counselor_id"] == str(other_counselor_id)
    assert items[0]["counselor_name"] == "상담사B"


def test_admin_sees_all_and_can_filter_by_counselor(
    client: TestClient,
    admin_headers,
    other_counselor_headers,
    counselor_id,
    session,
) -> None:
    other_case = create_case(client, other_counselor_headers)
    other_session = create_session(client, other_counselor_headers, other_case["id"])

    assert set(_ids(_list(client, admin_headers))) == {session["id"], other_session["id"]}
    assert _ids(_list(client, admin_headers, counselor_id=str(counselor_id))) == [
        session["id"]
    ]


def test_counselor_cannot_look_at_another_counselors_tasks(
    client: TestClient, counselor_headers, counselor_id, other_counselor_id, session
) -> None:
    for path in (TASKS, SUMMARY):
        response = client.get(
            path,
            params={"counselor_id": str(other_counselor_id)},
            headers=counselor_headers,
        )

        assert response.status_code == 403
        assert response.json()["error"]["code"] == "FORBIDDEN"

    own = _list(client, counselor_headers, counselor_id=str(counselor_id))

    assert _ids(own) == [session["id"]]


# =========================================================
# 필터 · 제외 규칙
# =========================================================

def test_overdue_flag_and_filter(
    client: TestClient, counselor_headers, case, monkeypatch
) -> None:
    monkeypatch.setattr(settings, "TASK_OVERDUE_HOURS", 1)

    fresh = create_session(client, counselor_headers, case["id"])
    stale = create_session(client, counselor_headers, case["id"])
    now = _now()

    # 요청이 도는 동안 시간이 흐르므로 기준 앞뒤로 30초 여유를 둔다.
    _set_session(
        fresh["id"],
        status=SessionStatus.STT_REVIEW_REQUIRED,
        stt_completed_at=now - timedelta(hours=1) + timedelta(seconds=30),
    )
    _set_session(
        stale["id"],
        status=SessionStatus.STT_REVIEW_REQUIRED,
        stt_completed_at=now - timedelta(hours=1) - timedelta(seconds=30),
    )

    flags = {
        item["session_id"]: item["is_overdue"]
        for item in _list(client, counselor_headers)["items"]
    }

    assert flags == {fresh["id"]: False, stale["id"]: True}
    assert _ids(_list(client, counselor_headers, overdue_only="true")) == [stale["id"]]


def test_task_type_filter_and_unknown_value(
    client: TestClient, counselor_headers, case
) -> None:
    review = create_session(client, counselor_headers, case["id"])
    create_session(client, counselor_headers, case["id"])
    _set_session(review["id"], status=SessionStatus.STT_REVIEW_REQUIRED)

    assert _ids(_list(client, counselor_headers, task_type="REVIEW_TRANSCRIPT")) == [
        review["id"]
    ]

    response = _get(client, counselor_headers, task_type="NOT_A_TASK")

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_closed_case_and_future_consultation_are_not_tasks(
    client: TestClient, counselor_headers, case
) -> None:
    past = create_session(client, counselor_headers, case["id"])
    future = create_session(client, counselor_headers, case["id"])
    _set_session(past["id"], consulted_at=_now() - timedelta(days=1))
    _set_session(future["id"], consulted_at=_now() + timedelta(days=1))

    closed_case = create_case(client, counselor_headers)
    create_session(client, counselor_headers, closed_case["id"])
    response = client.patch(
        f"/api/v1/cases/{closed_case['id']}",
        json={"status": "CLOSED"},
        headers=counselor_headers,
    )
    assert response.status_code == 200

    assert _ids(_list(client, counselor_headers)) == [past["id"]]


# =========================================================
# 요약 숫자
# =========================================================

def test_summary_counts_match_the_list(
    client: TestClient, counselor_headers, case, monkeypatch
) -> None:
    monkeypatch.setattr(settings, "TASK_OVERDUE_HOURS", 1)
    old = _now() - timedelta(hours=5)

    create_session(client, counselor_headers, case["id"])

    fresh_review = create_session(client, counselor_headers, case["id"])
    _set_session(
        fresh_review["id"],
        status=SessionStatus.STT_REVIEW_REQUIRED,
        stt_completed_at=_now(),
    )

    old_review = create_session(client, counselor_headers, case["id"])
    _set_session(
        old_review["id"],
        status=SessionStatus.STT_REVIEW_REQUIRED,
        stt_completed_at=old,
    )

    old_retry = create_session(client, counselor_headers, case["id"])
    _set_session(old_retry["id"], status=SessionStatus.AI_FAILED, ai_completed_at=old)

    response = client.get(SUMMARY, headers=counselor_headers)
    assert response.status_code == 200
    summary = response.json()["data"]

    items = _list(client, counselor_headers)["items"]

    assert summary["total"] == len(items) == 4
    assert summary["overdue"] == sum(item["is_overdue"] for item in items) == 2
    assert summary["by_type"] == {
        "UPLOAD_AUDIO": 1,
        "REQUEST_STT": 0,
        "REVIEW_TRANSCRIPT": 2,
        "REQUEST_ANALYSIS": 0,
        "REVIEW_ANALYSIS": 0,
        "RETRY_STT": 0,
        "RETRY_ANALYSIS": 1,
    }


def test_summary_is_all_zero_without_tasks(client: TestClient, counselor_headers) -> None:
    summary = client.get(SUMMARY, headers=counselor_headers).json()["data"]

    assert summary["total"] == 0
    assert summary["overdue"] == 0
    assert set(summary["by_type"]) == set(STATUS_TO_TASK.values())
    assert set(summary["by_type"].values()) == {0}


# =========================================================
# 성능 — 업무 수만큼 쿼리가 늘지 않는다
# =========================================================

def test_query_count_does_not_grow_with_tasks(
    client: TestClient, counselor_headers, case
) -> None:
    def count_queries() -> int:
        statements = []

        def record(*args) -> None:
            statements.append(args[2])

        event.listen(engine, "before_cursor_execute", record)

        try:
            _list(client, counselor_headers)
        finally:
            event.remove(engine, "before_cursor_execute", record)

        return len(statements)

    for _ in range(2):
        create_session(client, counselor_headers, case["id"])

    few = count_queries()

    for _ in range(8):
        create_session(client, counselor_headers, case["id"])

    many = count_queries()

    assert len(_list(client, counselor_headers)["items"]) == 10
    assert many == few
