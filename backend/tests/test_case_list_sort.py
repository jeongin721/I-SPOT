# 사례 목록의 상담원 위험도 · 정렬(API_CONTRACT 4절, 2026-11-06). 데이터는 모두 가상이다.

import uuid
from datetime import datetime, timezone
from typing import List, Optional

from fastapi.testclient import TestClient

from app.core.enums import RiskLevel, SessionStatus
from app.models.risk_assessment import SessionOverallRiskAssessment
from app.models.session import ConsultationSession
from tests.conftest import create_case, create_session


def _session(client, headers, db, case_id: str, status: SessionStatus, level: Optional[RiskLevel] = None) -> str:
    """회차를 만들어 상태를 맞추고, level 이 있으면 회차 전체 판단을 넣는다."""

    session_id = create_session(client, headers, case_id)["id"]
    row = db.get(ConsultationSession, uuid.UUID(session_id))
    row.status = status

    if level is not None:
        db.add(
            SessionOverallRiskAssessment(
                session_id=row.id,
                counselor_level=level,
                assessed_at=datetime.now(timezone.utc),
            )
        )

    db.commit()

    return session_id


def _list(client, headers, **params) -> List[dict]:
    response = client.get("/api/v1/cases", params=params, headers=headers)

    assert response.status_code == 200, response.text

    return response.json()["data"]["items"]


def test_risk_level_is_the_latest_analyzed_sessions_judgment(client: TestClient, counselor_headers, db) -> None:
    case = create_case(client, counselor_headers)
    _session(client, counselor_headers, db, case["id"], SessionStatus.APPROVED, RiskLevel.LOW)
    _session(client, counselor_headers, db, case["id"], SessionStatus.AI_REVIEW_REQUIRED, RiskLevel.HIGH)
    # 아직 분석 전인 새 회차는 건너뛴다(사례 상세 칩과 같다).
    _session(client, counselor_headers, db, case["id"], SessionStatus.STT_CONFIRMED)

    assert _list(client, counselor_headers)[0]["risk_level"] == "HIGH"


def test_unjudged_latest_session_stays_null(client: TestClient, counselor_headers, db) -> None:
    case = create_case(client, counselor_headers)
    _session(client, counselor_headers, db, case["id"], SessionStatus.APPROVED, RiskLevel.HIGH)
    _session(client, counselor_headers, db, case["id"], SessionStatus.AI_REVIEW_REQUIRED)

    assert _list(client, counselor_headers)[0]["risk_level"] is None


def test_case_without_sessions_has_no_risk_level(client: TestClient, counselor_headers) -> None:
    create_case(client, counselor_headers)

    assert _list(client, counselor_headers)[0]["risk_level"] is None


def test_sort_by_risk_puts_high_first_and_empty_last(client: TestClient, counselor_headers, db) -> None:
    ids = {}

    for name, level in (("none", None), ("low", RiskLevel.LOW), ("high", RiskLevel.HIGH), ("medium", RiskLevel.MEDIUM)):
        ids[create_case(client, counselor_headers)["id"]] = name
        case_id = next(key for key, value in ids.items() if value == name)

        if level is not None:
            _session(client, counselor_headers, db, case_id, SessionStatus.APPROVED, level)

    order = [ids[item["id"]] for item in _list(client, counselor_headers, sort="risk")]

    assert order == ["high", "medium", "low", "none"]


def test_sort_by_report_date_is_latest_first_and_empty_last(client: TestClient, counselor_headers) -> None:
    old = create_case(client, counselor_headers, report_date="2026-07-01")
    empty = create_case(client, counselor_headers)
    new = create_case(client, counselor_headers, report_date="2026-10-01")

    order = [item["id"] for item in _list(client, counselor_headers, sort="report_date")]

    assert order == [new["id"], old["id"], empty["id"]]


def test_unknown_sort_is_rejected(client: TestClient, counselor_headers) -> None:
    response = client.get("/api/v1/cases", params={"sort": "name"}, headers=counselor_headers)

    assert response.status_code == 422


def test_sort_by_risk_falls_back_to_intake_level(client: TestClient, counselor_headers, db) -> None:
    """회차 판단이 없으면 서식 4 위험도(우선) 순서로, 회차 판단이 있으면 그 값이 이긴다 — 목록에 보이는 값과 같은 순서."""

    picked_high = create_case(client, counselor_headers, counselor_risk_level="HIGH")
    judged_low = create_case(client, counselor_headers, counselor_risk_level="HIGH")
    _session(client, counselor_headers, db, judged_low["id"], SessionStatus.APPROVED, RiskLevel.LOW)
    empty = create_case(client, counselor_headers)
    picked_medium = create_case(client, counselor_headers, counselor_risk_level="MEDIUM")

    order = [item["id"] for item in _list(client, counselor_headers, sort="risk")]

    assert order == [picked_high["id"], picked_medium["id"], judged_low["id"], empty["id"]]


def test_order_asc_reverses_date_and_keeps_empty_last(client: TestClient, counselor_headers) -> None:
    """↓(order=asc): 신고접수일 오래된순, 값 없는 사례는 그래도 맨 뒤."""

    old = create_case(client, counselor_headers, report_date="2026-01-01")["id"]
    new = create_case(client, counselor_headers, report_date="2026-06-01")["id"]
    empty = create_case(client, counselor_headers)["id"]

    order = [item["id"] for item in _list(client, counselor_headers, sort="report_date", order="asc")]

    assert order == [old, new, empty]


def test_order_asc_puts_low_risk_first_and_empty_last(client: TestClient, counselor_headers) -> None:
    high = create_case(client, counselor_headers, counselor_risk_level="HIGH")["id"]
    low = create_case(client, counselor_headers, counselor_risk_level="LOW")["id"]
    empty = create_case(client, counselor_headers)["id"]

    order = [item["id"] for item in _list(client, counselor_headers, sort="risk", order="asc")]

    assert order == [low, high, empty]


def test_unknown_order_is_rejected(client: TestClient, counselor_headers) -> None:
    response = client.get("/api/v1/cases", params={"sort": "risk", "order": "up"}, headers=counselor_headers)

    assert response.status_code == 422


# ---- 기본 순서(sort 없음 — 화면의 '전체'): 최근 수정순(2026-11-25) ----


def _ids(client, headers, **params) -> List[str]:
    return [item["id"] for item in _list(client, headers, **params)]


def _patch(client, headers, case_id: str, body: dict) -> None:
    response = client.patch(f"/api/v1/cases/{case_id}", json=body, headers=headers)

    assert response.status_code == 200, response.text


def test_default_order_puts_the_latest_modified_case_first(client: TestClient, counselor_headers) -> None:
    """방금 고친 사례가 맨 위다. 고치지 않은 사례끼리는 등록 최신순 그대로(등록도 수정으로 친다)."""

    first = create_case(client, counselor_headers)["id"]
    second = create_case(client, counselor_headers)["id"]
    third = create_case(client, counselor_headers)["id"]

    assert _ids(client, counselor_headers) == [third, second, first]

    _patch(client, counselor_headers, first, {"notes": "가상 메모"})

    assert _ids(client, counselor_headers) == [first, third, second]

    # 값이 그대로인 저장도 '저장한 사례' 로 올린다(화면에서 저장을 누른 순서와 같게).
    _patch(client, counselor_headers, second, {"title": "테스트 사례"})

    assert _ids(client, counselor_headers) == [second, first, third]


def test_saving_personal_info_moves_the_case_to_the_top(client: TestClient, counselor_headers) -> None:
    """이름만 고치면 사례 행은 그대로라, 따로 올려 주지 않으면 순서가 안 바뀐다."""

    old = create_case(client, counselor_headers)["id"]
    new = create_case(client, counselor_headers)["id"]
    url = f"/api/v1/cases/{old}/personal-info"

    assert client.put(url, json={"child_name": "한가람"}, headers=counselor_headers).status_code == 200
    assert _ids(client, counselor_headers) == [old, new]

    _patch(client, counselor_headers, new, {"notes": "가상 메모"})
    assert _ids(client, counselor_headers) == [new, old]

    # 같은 값을 다시 저장해도 올린다(사례 수정과 같은 기준).
    assert client.put(url, json={"child_name": "한가람"}, headers=counselor_headers).status_code == 200
    assert _ids(client, counselor_headers) == [old, new]


def test_saving_a_case_form_moves_the_case_to_the_top(client: TestClient, counselor_headers) -> None:
    """서식을 새로 쓰기 · 임시 저장 · 확정할 때마다 그 사례가 맨 위로 온다."""

    target = create_case(client, counselor_headers)["id"]
    other = create_case(client, counselor_headers)["id"]
    forms = f"/api/v1/cases/{target}/forms"

    created = client.post(forms, json={"form_type": "RISK_SCALE", "values": {}}, headers=counselor_headers)
    assert created.status_code == 201, created.text
    form_id = created.json()["data"]["id"]
    assert _ids(client, counselor_headers) == [target, other]

    _patch(client, counselor_headers, other, {"notes": "가상 메모 1"})
    saved = client.patch(f"{forms}/{form_id}", json={"values": {}, "version": 1}, headers=counselor_headers)
    assert saved.status_code == 200, saved.text
    assert _ids(client, counselor_headers) == [target, other]

    _patch(client, counselor_headers, other, {"notes": "가상 메모 2"})
    confirmed = client.post(f"{forms}/{form_id}/confirm", json={"version": 2}, headers=counselor_headers)
    assert confirmed.status_code == 200, confirmed.text
    assert _ids(client, counselor_headers) == [target, other]


def test_stale_form_save_does_not_move_the_case(client: TestClient, counselor_headers) -> None:
    """옛 판 번호로 보내 409 가 난 서식 저장은 사례 순서를 바꾸지 않는다."""

    target = create_case(client, counselor_headers)["id"]
    forms = f"/api/v1/cases/{target}/forms"
    form_id = client.post(forms, json={"form_type": "RISK_SCALE", "values": {}}, headers=counselor_headers).json()["data"]["id"]
    other = create_case(client, counselor_headers)["id"]

    stale = client.patch(f"{forms}/{form_id}", json={"values": {}, "version": 9}, headers=counselor_headers)

    assert stale.status_code == 409
    assert _ids(client, counselor_headers) == [other, target]


def test_closure_review_moves_the_case_to_the_top(client: TestClient, counselor_headers) -> None:
    old = create_case(client, counselor_headers)["id"]
    new = create_case(client, counselor_headers)["id"]

    assert client.post(f"/api/v1/cases/{old}/closure-review", headers=counselor_headers).status_code == 200

    assert _ids(client, counselor_headers) == [old, new]


def test_reading_a_case_does_not_reorder(client: TestClient, counselor_headers) -> None:
    """열어 보기만 한 사례는 올라오지 않는다(열람 기록을 남기는 조회 포함)."""

    old = create_case(client, counselor_headers, personal_info={"child_name": "한가람"})["id"]
    new = create_case(client, counselor_headers)["id"]

    for url in (f"/api/v1/cases/{old}", f"/api/v1/cases/{old}/personal-info", f"/api/v1/cases/{old}/forms"):
        assert client.get(url, headers=counselor_headers).status_code == 200

    assert _ids(client, counselor_headers, with_child_name="true") == [new, old]
    assert _ids(client, counselor_headers) == [new, old]


def test_same_sort_value_ties_break_by_latest_modified(client: TestClient, counselor_headers) -> None:
    """위험도 · 신고접수일이 같은 사례끼리도 최근 수정순이다(↑ · ↓ 어느 쪽이든)."""

    first = create_case(client, counselor_headers, counselor_risk_level="HIGH", report_date="2026-07-01")["id"]
    second = create_case(client, counselor_headers, counselor_risk_level="HIGH", report_date="2026-07-01")["id"]
    low = create_case(client, counselor_headers, counselor_risk_level="LOW", report_date="2026-01-01")["id"]

    assert _ids(client, counselor_headers, sort="risk") == [second, first, low]

    _patch(client, counselor_headers, first, {"notes": "가상 메모"})

    assert _ids(client, counselor_headers, sort="risk") == [first, second, low]
    assert _ids(client, counselor_headers, sort="risk", order="asc") == [low, first, second]
    assert _ids(client, counselor_headers, sort="report_date") == [first, second, low]
    assert _ids(client, counselor_headers, sort="report_date", order="asc") == [low, first, second]
