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
