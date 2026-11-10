# 기관 서식(GET/POST/PATCH /cases/{case_id}/forms, API_CONTRACT 22절, 2026-11-02). 데이터는 모두 가상이다.

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.enums import AuditAction
from app.models.audit_log import AuditLog
from tests.conftest import create_case


def _url(case_id: str, *parts: str) -> str:
    return "/".join([f"/api/v1/cases/{case_id}/forms", *parts])


def _create(client: TestClient, headers, case_id: str, form_type: str, values=None) -> dict:
    response = client.post(_url(case_id), json={"form_type": form_type, "values": values or {}}, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()["data"]


def test_draft_save_and_reopen_returns_same_values(client: TestClient, counselor_headers, case: dict) -> None:
    created = _create(client, counselor_headers, case["id"], "MANAGEMENT_CHECKLIST", {"place": "기관 면담실 B"})

    assert created["round"] == 1 and created["status"] == "DRAFT"
    # 보내지 않은 칸은 빈 칸으로 채워 저장한다.
    assert created["values"] == {"place": "기관 면담실 B", "checks": [None] * 9, "opinion": "", "plan": ""}

    values = {"place": "가정방문", "checks": ["NO", "YES"] + [None] * 7, "opinion": "상담원 소견", "plan": "재사정"}
    patched = client.patch(_url(case["id"], created["id"]), json={"values": values, "version": 1}, headers=counselor_headers)
    assert patched.status_code == 200, patched.text
    assert patched.json()["data"]["totals"] == {"answered": 2} and patched.json()["data"]["version"] == 2

    listed = client.get(_url(case["id"]), headers=counselor_headers).json()["data"]["items"]
    assert [item["id"] for item in listed] == [created["id"]]
    assert listed[0]["values"] == values
    assert client.get(_url(case["id"], created["id"]), headers=counselor_headers).json()["data"]["values"] == values


def test_only_one_draft_and_confirm_opens_next_round(client: TestClient, counselor_headers, case: dict) -> None:
    first = _create(client, counselor_headers, case["id"], "RISK_SCALE")

    again = client.post(_url(case["id"]), json={"form_type": "RISK_SCALE"}, headers=counselor_headers)
    assert again.status_code == 409 and again.json()["error"]["code"] == "DUPLICATE_RESOURCE"

    # 다른 서식 종류는 따로 센다.
    assert _create(client, counselor_headers, case["id"], "FAMILY_SCALE")["round"] == 1

    confirmed = client.post(_url(case["id"], first["id"], "confirm"), json={"version": 1}, headers=counselor_headers)
    assert confirmed.status_code == 200
    assert confirmed.json()["data"]["status"] == "APPROVED" and confirmed.json()["data"]["confirmed_at"]

    locked = client.patch(_url(case["id"], first["id"]), json={"values": {}, "version": 2}, headers=counselor_headers)
    assert locked.status_code == 409 and locked.json()["error"]["code"] == "ALREADY_APPROVED"
    assert client.post(_url(case["id"], first["id"], "confirm"), json={"version": 2}, headers=counselor_headers).status_code == 409

    second = _create(client, counselor_headers, case["id"], "RISK_SCALE")
    assert second["round"] == 2
    rounds = client.get(_url(case["id"]), params={"form_type": "RISK_SCALE"}, headers=counselor_headers).json()["data"]
    assert [item["round"] for item in rounds["items"]] == [2, 1]


def test_totals_are_calculated_not_judged(client: TestClient, counselor_headers, case: dict) -> None:
    scores = [None] * 43
    scores[3], scores[20], scores[21], scores[42] = 2, 3, 1, 2
    risk = _create(client, counselor_headers, case["id"], "RISK_SCALE", {"scores": scores})
    assert risk["totals"] == {"risk_sum": 5, "protect_sum": 3, "filled": 4}

    family = _create(
        client, counselor_headers, case["id"], "FAMILY_SCALE", {"respondent": "MOTHER", "answers": [5, 4] + [None] * 13}
    )
    assert family["totals"] == {"sum": 9, "answered": 2}

    safety = _create(
        client,
        counselor_headers,
        case["id"],
        "SAFETY_ASSESSMENT",
        {"items": ["HIGH"] + [None] * 10, "scores": [{"score": 7, "reason": "이유"}, {}, {}], "result": "GENERAL"},
    )
    assert safety["values"]["scores"][1] == {"score": None, "reason": ""}
    assert safety["values"]["key_person"] is None and safety["totals"] == {"answered": 1}


@pytest.mark.parametrize(
    ("form_type", "values"),
    [
        ("RISK_SCALE", {"scores": [4] + [None] * 42}),
        ("RISK_SCALE", {"scores": [0] * 42}),
        ("FAMILY_SCALE", {"answers": [0] + [None] * 14}),
        ("FAMILY_SCALE", {"respondent": "UNCLE"}),
        ("SAFETY_ASSESSMENT", {"items": ["매우 높음"] + [None] * 10}),
        ("SAFETY_ASSESSMENT", {"scores": [{"score": 11}, {}, {}]}),
        ("SAFETY_ASSESSMENT", {"ai_suggestion": "HIGH"}),
        ("MANAGEMENT_CHECKLIST", {"opinion": "가" * 5001}),
        ("MANAGEMENT_CHECKLIST", {"checks": ["MAYBE"] + [None] * 8}),
        # 타입을 바꿔 받지 않는다(민규 #140 교차검증 L2): true → 1 · "3" → 3
        ("RISK_SCALE", {"scores": [True] + [None] * 42}),
        ("FAMILY_SCALE", {"answers": ["3"] + [None] * 14}),
    ],
)
def test_bad_values_are_rejected(client: TestClient, counselor_headers, case: dict, form_type: str, values) -> None:
    response = client.post(_url(case["id"]), json={"form_type": form_type, "values": values}, headers=counselor_headers)

    assert response.status_code == 422, response.text
    # 받은 글은 오류 응답에 싣지 않는다.
    assert "가가가" not in response.text


def test_bad_form_type_and_unstorable_text(client: TestClient, counselor_headers, case: dict) -> None:
    assert client.post(_url(case["id"]), json={"form_type": "INTAKE"}, headers=counselor_headers).status_code == 422
    nul = {"form_type": "MANAGEMENT_CHECKLIST", "values": {"opinion": "a\u0000b"}}
    assert client.post(_url(case["id"]), json=nul, headers=counselor_headers).status_code == 422


def test_other_counselor_cannot_see_or_write(
    client: TestClient, counselor_headers, other_counselor_headers, admin_headers, case: dict
) -> None:
    form = _create(client, counselor_headers, case["id"], "FAMILY_SCALE")

    assert client.get(_url(case["id"]), headers=other_counselor_headers).status_code == 403
    assert client.post(_url(case["id"]), json={"form_type": "RISK_SCALE"}, headers=other_counselor_headers).status_code == 403
    assert client.patch(_url(case["id"], form["id"]), json={"values": {}, "version": 1}, headers=other_counselor_headers).status_code == 403
    assert client.get(_url(case["id"]), headers=admin_headers).status_code == 200

    # 다른 사례 주소로는 그 서식을 찾지 못한다.
    others = create_case(client, counselor_headers, child_alias="아동_002")
    assert client.get(_url(others["id"], form["id"]), headers=counselor_headers).status_code == 404


def test_audit_keeps_type_and_round_only(client: TestClient, counselor_headers, case: dict, db) -> None:
    form = _create(client, counselor_headers, case["id"], "MANAGEMENT_CHECKLIST", {"opinion": "비밀 소견"})
    client.patch(_url(case["id"], form["id"]), json={"values": {"plan": "계획"}, "version": 1}, headers=counselor_headers)
    client.post(_url(case["id"], form["id"], "confirm"), json={"version": 2}, headers=counselor_headers)

    logs = list(db.scalars(select(AuditLog).where(AuditLog.entity_type == "CaseForm").order_by(AuditLog.created_at)))
    assert [log.action for log in logs] == [
        AuditAction.CASE_FORM_CREATED,
        AuditAction.CASE_FORM_UPDATED,
        AuditAction.CASE_FORM_CONFIRMED,
    ]
    assert all(log.detail == {"form_type": "MANAGEMENT_CHECKLIST", "round": 1} for log in logs)


def test_stale_tab_cannot_overwrite_or_confirm(client: TestClient, counselor_headers, case: dict) -> None:
    """오래된 창(판 1)은 다른 창이 저장한 판 2 를 덮거나 확정하지 못한다(민규 #140 H2 · H3)."""

    form = _create(client, counselor_headers, case["id"], "MANAGEMENT_CHECKLIST", {"place": "처음"})
    newer = client.patch(_url(case["id"], form["id"]), json={"values": {"place": "새 값"}, "version": 1}, headers=counselor_headers)
    assert newer.status_code == 200

    stale_save = client.patch(_url(case["id"], form["id"]), json={"values": {"place": "옛 값"}, "version": 1}, headers=counselor_headers)
    stale_confirm = client.post(_url(case["id"], form["id"], "confirm"), json={"version": 1}, headers=counselor_headers)
    assert stale_save.status_code == 409 and stale_save.json()["error"]["code"] == "STALE_VERSION"
    assert stale_confirm.status_code == 409 and stale_confirm.json()["error"]["code"] == "STALE_VERSION"

    current = client.get(_url(case["id"], form["id"]), headers=counselor_headers).json()["data"]
    assert current["values"]["place"] == "새 값" and current["status"] == "DRAFT" and current["version"] == 2


def test_double_confirm_and_save_after_confirm(client: TestClient, counselor_headers, case: dict, db) -> None:
    """같은 판으로 확정 두 번 · 확정 뒤 저장은 하나만 성공하고 감사 기록도 하나(민규 #140 H3, SQLite 에서도)."""

    form = _create(client, counselor_headers, case["id"], "RISK_SCALE")
    first = client.post(_url(case["id"], form["id"], "confirm"), json={"version": 1}, headers=counselor_headers)
    second = client.post(_url(case["id"], form["id"], "confirm"), json={"version": 1}, headers=counselor_headers)
    late_save = client.patch(_url(case["id"], form["id"]), json={"values": {"scores": [3] * 43}, "version": 1}, headers=counselor_headers)

    assert first.status_code == 200
    assert second.status_code == 409 and second.json()["error"]["code"] == "ALREADY_APPROVED"
    assert late_save.status_code == 409 and late_save.json()["error"]["code"] == "ALREADY_APPROVED"
    assert client.get(_url(case["id"], form["id"]), headers=counselor_headers).json()["data"]["values"]["scores"] == [None] * 43
    confirms = db.scalars(select(AuditLog).where(AuditLog.action == AuditAction.CASE_FORM_CONFIRMED)).all()
    assert len(confirms) == 1


def test_only_one_draft_even_if_app_check_is_skipped(client: TestClient, counselor_headers, case: dict, monkeypatch) -> None:
    """동시에 만들어 앞 확인을 둘 다 지나도 DB 유일 인덱스가 임시 저장 차수 둘을 막는다(민규 #140 M1)."""

    from app.services import case_form_service

    _create(client, counselor_headers, case["id"], "FAMILY_SCALE")
    real_scalar = case_form_service.Session.scalar

    def skip_draft_check(self, statement, *args, **kwargs):
        # 임시 저장 차수가 있는지 보는 조회만 '없음' 으로 — 차수 계산은 그대로 두어 다음 차수(2)로 만들게 한다.
        if "case_forms.id" in str(statement) and "status" in str(statement) and "max" not in str(statement):
            return None
        return real_scalar(self, statement, *args, **kwargs)

    monkeypatch.setattr(case_form_service.Session, "scalar", skip_draft_check)
    second = client.post(_url(case["id"]), json={"form_type": "FAMILY_SCALE"}, headers=counselor_headers)

    assert second.status_code == 409 and second.json()["error"]["code"] == "DUPLICATE_RESOURCE"
    assert "다른 창에서" in second.json()["error"]["message"]  # 앞 확인이 아니라 DB 인덱스에서 막힘


def test_deeply_nested_value_is_422_not_500(client: TestClient, counselor_headers, case: dict) -> None:
    """480단으로 겹친 값도 422(민규 #140 교차검증 L5 — 글자 검사 재귀가 한도를 넘어 500 이었다)."""

    deep: object = "x"
    for _ in range(480):
        deep = {"a": deep}

    response = client.post(
        _url(case["id"]), json={"form_type": "MANAGEMENT_CHECKLIST", "values": {"place": deep}}, headers=counselor_headers
    )

    assert response.status_code == 422, response.text
