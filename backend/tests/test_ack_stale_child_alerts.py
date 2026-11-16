# 아이 앱 '확인 전' 알림 정리 script(scripts/ack_stale_child_alerts.py, 2026-11-16). 데이터는 모두 가상이다.

import uuid
from datetime import date, datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.enums import AuditAction, CaseStatus
from app.models.case import Case
from app.models.audit_log import AuditLog
from app.models.child_app import ChildAppEvent
from scripts import ack_stale_child_alerts as script
from tests.conftest import create_case
from tests.test_child_app import _alert, _limits, _linked, _open  # noqa: F401  (_limits 는 autouse 픽스처)

TODAY = datetime.now(timezone.utc).date()
TOMORROW = TODAY + timedelta(days=2)


def _age(db, alert_id: str, days: int) -> None:
    event = db.get(ChildAppEvent, uuid.UUID(alert_id))
    event.created_at = datetime.now(timezone.utc) - timedelta(days=days)
    db.commit()


def _two_alerts(client: TestClient, headers, db):
    old_case = create_case(client, headers)
    new_case = create_case(client, headers)
    _alert(client, _linked(client, headers, old_case["id"]))
    _alert(client, _linked(client, headers, new_case["id"]))
    by_case = {item["case_id"]: item["id"] for item in _open(client, headers)}
    _age(db, by_case[old_case["id"]], 10)

    return old_case, new_case, by_case


def test_list_is_read_only_and_respects_before(client: TestClient, counselor_headers, db) -> None:
    old_case, _, by_case = _two_alerts(client, counselor_headers, db)

    alerts = script.find_stale_alerts(db, TODAY - timedelta(days=3))

    assert [alert.id for alert in alerts] == [by_case[old_case["id"]]]
    assert alerts[0].case_number == old_case["case_number"] and alerts[0].kind == "ALERT"
    assert len(_open(client, counselor_headers)) == 2


def test_apply_acks_only_targets_and_records_audit(client: TestClient, counselor_headers, db) -> None:
    old_case, new_case, by_case = _two_alerts(client, counselor_headers, db)

    assert script.ack_stale_alerts(db, TODAY - timedelta(days=3), expect=1) == 1

    db.expire_all()
    assert [item["case_id"] for item in _open(client, counselor_headers)] == [new_case["id"]]
    log = db.scalar(select(AuditLog).where(AuditLog.action == AuditAction.CHILD_APP_ALERT_ACKED))
    assert log.actor_id is None and log.detail["via"] == script.VIA
    assert str(log.entity_id) == by_case[old_case["id"]]
    # 다시 돌려도 이미 확인한 알림은 건드리지 않는다.
    assert script.ack_stale_alerts(db, TODAY - timedelta(days=3)) == 0


def test_expect_mismatch_changes_nothing(client: TestClient, counselor_headers, db) -> None:
    _two_alerts(client, counselor_headers, db)

    with pytest.raises(script.CleanupError):
        script.ack_stale_alerts(db, TOMORROW, expect=1)

    assert len(_open(client, counselor_headers)) == 2


def test_case_filter(client: TestClient, counselor_headers, db) -> None:
    _, new_case, _ = _two_alerts(client, counselor_headers, db)

    assert script.ack_stale_alerts(db, TOMORROW, [new_case["case_number"]]) == 1
    assert len(_open(client, counselor_headers)) == 1


def test_main_rejects_bad_date(capsys) -> None:
    assert script.main(["--before", "어제"]) == 2
    assert "YYYY-MM-DD" in capsys.readouterr().err


def test_main_lists_without_changing(client: TestClient, counselor_headers, db, capsys) -> None:
    _two_alerts(client, counselor_headers, db)

    assert script.main(["--before", TOMORROW.isoformat()]) == 0
    out = capsys.readouterr().out
    assert "확인 전 알림 2건" in out and "--apply --expect 2" in out
    assert len(_open(client, counselor_headers)) == 2


def test_cutoff_is_korean_midnight() -> None:
    assert script._cutoff(date(2026, 11, 17)) == datetime(2026, 11, 16, 15, 0, tzinfo=timezone.utc)


def test_repressed_alert_counts_from_last_press(client: TestClient, counselor_headers, db, capsys) -> None:
    # 열흘 전 처음 누르고 오늘 다시 누른 긴급 알림은 대상이 아니다(민규 #179 리뷰).
    case = create_case(client, counselor_headers)
    device = _linked(client, counselor_headers, case["id"])
    _alert(client, device)
    alert_id = _open(client, counselor_headers)[0]["id"]
    _age(db, alert_id, 10)
    _alert(client, device)

    assert script.find_stale_alerts(db, TODAY - timedelta(days=3)) == []
    assert script.ack_stale_alerts(db, TODAY - timedelta(days=3), expect=0) == 0
    assert len(_open(client, counselor_headers)) == 1

    # 내일 기준이면 대상이고, 목록에 마지막 누른 시각 · 다시 누른 횟수가 나온다.
    assert script.main(["--before", TOMORROW.isoformat()]) == 0
    assert "다시 1번" in capsys.readouterr().out


def test_closed_case_alert_is_listed_with_status(client: TestClient, counselor_headers, db, capsys) -> None:
    old_case, _, _ = _two_alerts(client, counselor_headers, db)
    db.get(Case, uuid.UUID(old_case["id"])).status = CaseStatus.CLOSED
    db.commit()

    assert script.main(["--before", (TODAY - timedelta(days=3)).isoformat()]) == 0
    out = capsys.readouterr().out
    assert "확인 전 알림 1건" in out and f"{old_case['case_number']} (CLOSED)" in out


def test_main_apply_requires_expect(client: TestClient, counselor_headers, db, capsys) -> None:
    _two_alerts(client, counselor_headers, db)

    assert script.main(["--before", TOMORROW.isoformat(), "--apply"]) == 2
    assert "--expect" in capsys.readouterr().err
    assert len(_open(client, counselor_headers)) == 2
