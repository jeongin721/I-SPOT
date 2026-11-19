# 상담 전 브리핑 '확인할 사항' 체크(GET · PATCH /sessions/{id}/briefing-checks, API_CONTRACT 26절, 2026-11-11). 데이터는 모두 가상이다.

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.enums import AuditAction
from app.models.audit_log import AuditLog
from app.models.briefing_check import BRIEFING_CHECKS_MAX
from tests.conftest import create_case, create_session

TEXT_A = "등 · 팔 통증 치료 여부"
TEXT_B = "02:15 발화 화자 · 식사 상황"


def _url(session_id: str) -> str:
    return f"/api/v1/sessions/{session_id}/briefing-checks"


def _toggle(client: TestClient, headers, session_id: str, text: str, checked: bool):
    return client.patch(_url(session_id), json={"text": text, "checked": checked}, headers=headers)


def test_empty_then_check_uncheck(client: TestClient, counselor_headers, session: dict) -> None:
    empty = client.get(_url(session["id"]), headers=counselor_headers)
    assert empty.status_code == 200 and empty.json()["data"]["checked"] == [] and empty.json()["data"]["updated_at"] is None

    assert _toggle(client, counselor_headers, session["id"], TEXT_A, True).json()["data"]["checked"] == [TEXT_A]
    assert _toggle(client, counselor_headers, session["id"], "  " + TEXT_B + "  ", True).json()["data"]["checked"] == [TEXT_A, TEXT_B]
    # 같은 것을 또 켜도 한 번만.
    assert _toggle(client, counselor_headers, session["id"], TEXT_A, True).json()["data"]["checked"] == [TEXT_A, TEXT_B]
    assert _toggle(client, counselor_headers, session["id"], TEXT_A, False).json()["data"]["checked"] == [TEXT_B]
    # 없는 것을 꺼도 그대로.
    assert _toggle(client, counselor_headers, session["id"], "없는 문장", False).json()["data"]["checked"] == [TEXT_B]

    got = client.get(_url(session["id"]), headers=counselor_headers).json()["data"]
    assert got["checked"] == [TEXT_B] and got["updated_at"] is not None


def test_two_devices_do_not_overwrite_each_other(client: TestClient, counselor_headers, session: dict) -> None:
    # 웹 · 폰이 각자 하나씩 켜도 둘 다 남는다(목록을 통째로 보내지 않는다).
    _toggle(client, counselor_headers, session["id"], TEXT_A, True)
    _toggle(client, counselor_headers, session["id"], TEXT_B, True)
    assert client.get(_url(session["id"]), headers=counselor_headers).json()["data"]["checked"] == [TEXT_A, TEXT_B]


def test_only_people_who_can_see_the_session(
    client: TestClient, counselor_headers, other_counselor_headers, admin_headers, session: dict
) -> None:
    assert client.get(_url(session["id"]), headers=other_counselor_headers).status_code in (403, 404)
    assert _toggle(client, other_counselor_headers, session["id"], TEXT_A, True).status_code in (403, 404)
    # 관리자는 사례를 볼 수 있으니 브리핑 체크도 본다.
    assert client.get(_url(session["id"]), headers=admin_headers).status_code == 200


def test_validation_and_limit(client: TestClient, counselor_headers, session: dict) -> None:
    for body in ({"text": "", "checked": True}, {"text": "   ", "checked": True}, {"text": "가" * 301, "checked": True}, {"text": "a\x00b", "checked": True}, {"text": "a"}):
        assert client.patch(_url(session["id"]), json=body, headers=counselor_headers).status_code == 422, body

    for n in range(BRIEFING_CHECKS_MAX):
        assert _toggle(client, counselor_headers, session["id"], f"확인 {n}", True).status_code == 200
    # 상한에 닿아도 지금 켜는 줄은 켜진다 — 가장 오래 전에 켠 것을 밀어낸다(민규 #176 1).
    over = _toggle(client, counselor_headers, session["id"], "하나 더", True)
    checked = over.json()["data"]["checked"]
    assert over.status_code == 200 and len(checked) == BRIEFING_CHECKS_MAX
    assert checked[-1] == "하나 더" and "확인 0" not in checked and checked[0] == "확인 1"


def test_visible_drops_stale_lines(client: TestClient, counselor_headers, session: dict) -> None:
    # 목록을 고쳐 문장이 바뀌면 옛 문장 체크가 남는다 → 화면이 지금 보이는 문장을 같이 보내면 정리된다.
    _toggle(client, counselor_headers, session["id"], TEXT_A, True)
    _toggle(client, counselor_headers, session["id"], "고치기 전 문장", True)
    res = client.patch(
        _url(session["id"]),
        json={"text": TEXT_B, "checked": True, "visible": [TEXT_A, TEXT_B, "  ", "가" * 400]},
        headers=counselor_headers,
    )
    assert res.status_code == 200 and res.json()["data"]["checked"] == [TEXT_A, TEXT_B]
    # 끌 때도 정리한다.
    res = client.patch(_url(session["id"]), json={"text": TEXT_B, "checked": False, "visible": [TEXT_B]}, headers=counselor_headers)
    assert res.json()["data"]["checked"] == []


def test_audit_has_no_text(client: TestClient, counselor_headers, session: dict, db) -> None:
    _toggle(client, counselor_headers, session["id"], TEXT_A, True)
    _toggle(client, counselor_headers, session["id"], TEXT_A, False)
    logs = db.scalars(select(AuditLog).where(AuditLog.action == AuditAction.BRIEFING_CHECK_UPDATED).order_by(AuditLog.created_at)).all()
    assert [log.detail for log in logs] == [{"checked": True, "count": 1}, {"checked": False, "count": 0}]
    assert all(TEXT_A not in repr(log.detail) for log in logs)


def test_each_session_has_its_own_checks(client: TestClient, counselor_headers) -> None:
    case = create_case(client, counselor_headers)
    first = create_session(client, counselor_headers, case["id"])
    second = create_session(client, counselor_headers, case["id"])
    _toggle(client, counselor_headers, first["id"], TEXT_A, True)
    assert client.get(_url(second["id"]), headers=counselor_headers).json()["data"]["checked"] == []
