# 고령자 후속관리(API_CONTRACT 27절, 2026-11-16) — 기본정보 복약 · 돌봄 필요, 돌봄 상태, 확인 · 조치사항과 재방문 일정,
# 방문 전 한 화면 브리핑, 현황. 데이터는 모두 가상이다.

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.adapters.module_loader import ensure_repo_root_on_path

ensure_repo_root_on_path()

from ai.modeling.senior import senior_brief_llm as brief_llm  # noqa: E402
from app.core.enums import AuditAction  # noqa: E402
from app.models.audit_log import AuditLog  # noqa: E402
from app.services import senior_service  # noqa: E402
from tests.conftest import create_case, create_session  # noqa: E402


@pytest.fixture(autouse=True)
def _fresh_limits():
    senior_service.reset_limits()
    yield
    senior_service.reset_limits()


def _senior(client: TestClient, headers, alias: str = "어르신_001") -> dict:
    return create_case(client, headers, subject_type="SENIOR", child_alias=alias, child_birth_year=1944)


def _checks(client: TestClient, headers, case_id: str, items: list) -> list:
    response = client.post(f"/api/v1/cases/{case_id}/next-checks", json={"items": items}, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()["data"]


def _today() -> date:
    return senior_service._today()


# ---------------------------------------------------------------- 기본정보 · 돌봄 상태


def test_profile_medication_and_care_needs(client: TestClient, counselor_headers, db) -> None:
    case = _senior(client, counselor_headers)
    url = f"/api/v1/cases/{case['id']}/senior-profile"

    data = client.patch(
        url,
        json={
            "takes_medication": True,
            "medication_notes": " 아침 혈압약 ",
            "care_needs": ["MEAL", "MEDICATION", "MEAL"],
            "care_needs_note": "반찬 배달 원하심",
        },
        headers=counselor_headers,
    ).json()["data"]
    assert data["takes_medication"] is True and data["medication_notes"] == "아침 혈압약"
    assert data["care_needs"] == ["MEAL", "MEDICATION"] and data["care_status"] is None

    # 같은 값이면 바뀐 칸 없음, null 이면 비움
    client.patch(url, json={"care_needs": ["MEAL", "MEDICATION"]}, headers=counselor_headers)
    data = client.patch(url, json={"care_needs": None, "takes_medication": None}, headers=counselor_headers).json()["data"]
    assert data["care_needs"] == [] and data["takes_medication"] is None
    logs = db.scalars(select(AuditLog).where(AuditLog.action == AuditAction.SENIOR_PROFILE_UPDATED)).all()
    assert [sorted(log.detail["changed_fields"]) for log in logs] == [
        ["care_needs", "care_needs_note", "medication_notes", "takes_medication"],
        ["care_needs", "takes_medication"],
    ]
    assert "혈압약" not in str([log.detail for log in logs])

    assert client.patch(url, json={"care_needs": ["LAUNDRY"]}, headers=counselor_headers).status_code == 422


def test_care_status(client: TestClient, counselor_headers, other_counselor_headers, db) -> None:
    case = _senior(client, counselor_headers)
    url = f"/api/v1/cases/{case['id']}/care-status"

    data = client.put(url, json={"status": "REVISIT_NEEDED", "note": "다리 통증 다시 보기"}, headers=counselor_headers).json()["data"]
    assert data["care_status"] == "REVISIT_NEEDED" and data["care_status_note"] == "다리 통증 다시 보기"
    first_changed = data["care_status_changed_at"]
    assert first_changed is not None

    # 같은 값이면 그대로(감사 기록 · 시각 안 바뀜)
    again = client.put(url, json={"status": "REVISIT_NEEDED", "note": "다리 통증 다시 보기"}, headers=counselor_headers).json()["data"]
    assert again["care_status_changed_at"] == first_changed

    data = client.put(url, json={"status": "SERVICE_ENDED"}, headers=counselor_headers).json()["data"]
    assert data["care_status"] == "SERVICE_ENDED" and data["care_status_note"] is None
    # 사례는 닫지 않는다
    assert client.get(f"/api/v1/cases/{case['id']}", headers=counselor_headers).json()["data"]["status"] == "ACTIVE"
    # 프로필 조회에도 보인다
    assert client.get(f"/api/v1/cases/{case['id']}/senior-profile", headers=counselor_headers).json()["data"]["care_status"] == "SERVICE_ENDED"

    logs = db.scalars(select(AuditLog).where(AuditLog.action == AuditAction.CARE_STATUS_CHANGED)).all()
    assert [(log.detail["from"], log.detail["to"]) for log in logs] == [(None, "REVISIT_NEEDED"), ("REVISIT_NEEDED", "SERVICE_ENDED")]
    assert "다리" not in str([log.detail for log in logs])

    assert client.put(url, json={"status": "CLOSED"}, headers=counselor_headers).status_code == 422
    assert client.put(url, json={"status": "CONSULT_DONE"}, headers=other_counselor_headers).status_code == 403
    child = create_case(client, counselor_headers)
    assert client.put(f"/api/v1/cases/{child['id']}/care-status", json={"status": "CONSULT_DONE"}, headers=counselor_headers).status_code == 409


# ---------------------------------------------------------------- 확인 · 조치사항과 재방문 일정


def test_check_kind_due_date_and_followup_visit(client: TestClient, counselor_headers, db) -> None:
    case = _senior(client, counselor_headers)
    due = (_today() + timedelta(days=3)).isoformat()
    check, action, done = _checks(
        client,
        counselor_headers,
        case["id"],
        [
            {"text": "무릎 통증 여쭤 보기"},
            {"kind": "ACTION", "text": "복지관 반찬 배달 연계", "due_date": due},
            {"text": "끝난 것"},
        ],
    )
    assert check["kind"] == "CHECK" and check["due_date"] is None and check["schedule_event_id"] is None
    assert action["kind"] == "ACTION" and action["due_date"] == due
    client.patch(f"/api/v1/cases/{case['id']}/next-checks/{done['id']}", json={"status": "DONE"}, headers=counselor_headers)

    visit_date = (_today() + timedelta(days=5)).isoformat()
    url = f"/api/v1/cases/{case['id']}/followup-visits"
    # 이미 확인한 것 · 남의 사례 것은 이을 수 없다(일정도 만들지 않는다)
    assert client.post(url, json={"consult_type": "VISIT", "date": visit_date, "check_ids": [done["id"]]}, headers=counselor_headers).status_code == 400
    other = _senior(client, counselor_headers, "어르신_002")
    (other_check,) = _checks(client, counselor_headers, other["id"], [{"text": "x"}])
    assert client.post(url, json={"consult_type": "VISIT", "date": visit_date, "check_ids": [other_check["id"]]}, headers=counselor_headers).status_code == 400
    assert client.post(url, json={"consult_type": "CLOSING", "date": visit_date}, headers=counselor_headers).status_code == 422
    assert client.post(url, json={"consult_type": "VISIT", "date": visit_date, "time": "25:00"}, headers=counselor_headers).status_code == 422

    response = client.post(
        url,
        json={"consult_type": "VISIT", "date": visit_date, "time": "10:30", "place": " 댁 ", "check_ids": [check["id"], action["id"]]},
        headers=counselor_headers,
    )
    assert response.status_code == 201, response.text
    data = response.json()["data"]
    visit = data["visit"]
    assert visit["date"] == visit_date and visit["time"] == "10:30" and visit["consult_type"] == "VISIT" and visit["place"] == "댁"
    assert {c["id"] for c in data["checks"]} == {check["id"], action["id"]}
    assert all(c["schedule_event_id"] == visit["schedule_event_id"] and c["due_date"] == visit_date for c in data["checks"])

    # 일정 화면에도 상담 일정으로 보인다
    events = client.get(
        "/api/v1/schedule/events", params={"from": visit_date, "to": visit_date}, headers=counselor_headers
    ).json()["data"]["items"]
    assert any(e["id"] == visit["schedule_event_id"] and e["kind"] == "CONSULT" and e["case_id"] == case["id"] for e in events)

    log = db.scalar(select(AuditLog).where(AuditLog.action == AuditAction.FOLLOWUP_VISIT_SCHEDULED))
    assert log.detail == {"consult_type": "VISIT", "check_count": 2}

    # PATCH 로 떼고 붙이기 · 기한 바꾸기 · 종류 바꾸기
    patch = f"/api/v1/cases/{case['id']}/next-checks/{check['id']}"
    data = client.patch(patch, json={"schedule_event_id": None, "due_date": None, "kind": "ACTION"}, headers=counselor_headers).json()["data"]
    assert data["schedule_event_id"] is None and data["due_date"] is None and data["kind"] == "ACTION"
    data = client.patch(patch, json={"schedule_event_id": visit["schedule_event_id"]}, headers=counselor_headers).json()["data"]
    assert data["schedule_event_id"] == visit["schedule_event_id"] and data["due_date"] == visit_date
    # 다른 사례의 일정은 못 붙인다
    other_visit = client.post(
        f"/api/v1/cases/{other['id']}/followup-visits", json={"consult_type": "PHONE", "date": visit_date}, headers=counselor_headers
    ).json()["data"]["visit"]
    assert client.patch(patch, json={"schedule_event_id": other_visit["schedule_event_id"]}, headers=counselor_headers).status_code == 400

    # 일정을 지우면 연결만 풀린다
    assert client.delete(f"/api/v1/schedule/events/{visit['schedule_event_id']}", headers=counselor_headers).status_code == 204
    db.expire_all()
    checks = client.get(f"/api/v1/cases/{case['id']}/next-checks", headers=counselor_headers).json()["data"]
    assert all(c["schedule_event_id"] is None for c in checks)


# ---------------------------------------------------------------- 방문 전 한 화면 브리핑


def test_brief_collects_status_open_checks_changes_and_next_visit(client: TestClient, counselor_headers) -> None:
    case = _senior(client, counselor_headers)
    first = create_session(client, counselor_headers, case["id"])
    second = create_session(client, counselor_headers, case["id"])
    put = lambda sid, items: client.put(f"/api/v1/sessions/{sid}/care-domains", json={"items": items}, headers=counselor_headers)  # noqa: E731
    assert put(first["id"], [{"domain": "OUTING", "change": "NEW", "text": "매일 산책"}, {"domain": "MEAL", "change": "NEW", "text": "세 끼"}]).status_code == 200
    assert put(
        second["id"],
        [
            {"domain": "OUTING", "change": "CHANGED", "text": "거의 안 나가심", "change_note": "매일 산책 → 거의 안 나감"},
            {"domain": "MEAL", "change": "SIMILAR", "text": "세 끼"},
        ],
    ).status_code == 200
    client.put(f"/api/v1/cases/{case['id']}/care-status", json={"status": "REVISIT_NEEDED"}, headers=counselor_headers)
    later, sooner, nodue = _checks(
        client,
        counselor_headers,
        case["id"],
        [
            {"text": "나중 기한", "due_date": (_today() + timedelta(days=9)).isoformat()},
            {"kind": "ACTION", "text": "이른 기한", "due_date": (_today() + timedelta(days=1)).isoformat()},
            {"text": "기한 없음"},
        ],
    )
    client.post(f"/api/v1/cases/{case['id']}/followup-visits", json={"consult_type": "PHONE", "date": (_today() + timedelta(days=2)).isoformat()}, headers=counselor_headers)
    client.post(f"/api/v1/cases/{case['id']}/followup-visits", json={"consult_type": "VISIT", "date": (_today() - timedelta(days=1)).isoformat()}, headers=counselor_headers)

    data = client.post(f"/api/v1/cases/{case['id']}/senior-brief", headers=counselor_headers).json()["data"]

    assert data["care_status"] == "REVISIT_NEEDED"
    assert [c["id"] for c in data["open_checks"]] == [sooner["id"], later["id"], nodue["id"]]
    assert [(c["domain"], c["label"], c["session_number"], c["change_note"]) for c in data["recent_changes"]] == [
        ("OUTING", "외출", second["session_number"], "매일 산책 → 거의 안 나감")
    ]
    assert data["next_visit"]["consult_type"] == "PHONE"  # 지난 일정은 빼고 가장 가까운 것
    # 규칙 확인사항 맨 앞에 영역 변화
    assert data["check_items"][0]["text"].startswith(f"지난 상담({second['session_number']}회차)에서 외출이 달라졌어요 — 매일 산책 → 거의 안 나감.")
    basis = data["check_items"][0]["basis"]
    assert [(b["kind"], b["session_number"]) for b in basis] == [("SESSION", second["session_number"])]


def test_brief_module_profile_and_change_lines() -> None:
    data = {
        "today": "2026-11-16",
        "profile": {"takes_medication": False, "medication_notes": "없음", "care_needs": ["MEAL", "SAFETY_CHECK"], "care_needs_note": "혼자 사심"},
        "metrics": [],
        "sessions": [],
        "recent_changes": [{"domain": "MEAL", "label": "식사", "session_number": 3, "text": "한 끼", "change_note": None}],
    }
    text, refs = brief_llm.format_input(data)
    assert "- 복약: 드시는 약 없음" in text and "- 돌봄 필요사항: 식사, 안부 · 안전 확인" in text
    assert "S3 식사: 한 끼" in text and refs["S3"] == {"kind": "SESSION", "session_number": 3}
    items = brief_llm.rule_based_brief(data)["check_items"]
    assert items[0]["text"].startswith("지난 상담(3회차)에서 식사가 달라졌어요 — 한 끼.")
    assert brief_llm._subject("수면") == "수면이" and brief_llm._subject("정서") == "정서가"


# ---------------------------------------------------------------- 현황


def test_overview_counts_and_scope(client: TestClient, counselor_headers, other_counselor_headers, admin_headers) -> None:
    mine = _senior(client, counselor_headers, "어르신_A")
    calm = _senior(client, counselor_headers, "어르신_B")
    theirs = _senior(client, other_counselor_headers, "어르신_C")
    create_case(client, counselor_headers)  # 아동 사례는 빠진다

    client.put(f"/api/v1/cases/{mine['id']}/care-status", json={"status": "FOLLOWUP_IN_PROGRESS"}, headers=counselor_headers)
    client.put(f"/api/v1/cases/{calm['id']}/care-status", json={"status": "REVISIT_NEEDED"}, headers=counselor_headers)
    _checks(
        client,
        counselor_headers,
        mine["id"],
        [{"text": "기한 지남", "due_date": (_today() - timedelta(days=2)).isoformat()}, {"text": "기한 없음"}],
    )
    client.post(
        f"/api/v1/cases/{calm['id']}/followup-visits",
        json={"consult_type": "VISIT", "date": (_today() + timedelta(days=3)).isoformat()},
        headers=counselor_headers,
    )
    client.post(
        f"/api/v1/cases/{calm['id']}/health-measurements",
        json={"measured_at": f"{_today().isoformat()}T09:00:00+09:00", "systolic": 130, "diastolic": 80},
        headers=counselor_headers,
    )

    data = client.get("/api/v1/senior-overview", headers=counselor_headers).json()["data"]
    assert [row["alias"] for row in data["rows"]] == ["어르신_A", "어르신_B"]  # 기한 지난 것 먼저, 남의 사례 · 아동 빠짐
    a, b = data["rows"]
    assert a["open_checks"] == 2 and a["overdue_checks"] == 1 and a["measurement_stale"] is True and a["next_visit"] is None
    assert b["care_status"] == "REVISIT_NEEDED" and b["measurement_stale"] is False and b["next_visit"]["consult_type"] == "VISIT"
    assert b["counselor_name"] and b["last_measured_at"] is not None
    assert data["counts"] == {
        "total": 2,
        "by_care_status": {"CONSULT_DONE": 0, "REVISIT_NEEDED": 1, "FOLLOWUP_IN_PROGRESS": 1, "SERVICE_ENDED": 0, "NONE": 0},
        "open_checks": 2,
        "overdue_checks": 1,
        "visits_next_7_days": 1,
        "measurement_stale": 1,
    }

    admin = client.get("/api/v1/senior-overview", headers=admin_headers).json()["data"]
    assert {row["alias"] for row in admin["rows"]} == {"어르신_A", "어르신_B", "어르신_C"}
    assert admin["counts"]["by_care_status"]["NONE"] == 1
    assert theirs["id"] in {row["case_id"] for row in admin["rows"]}
