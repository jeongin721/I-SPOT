# GET /cases/{case_id}/signal-history — 사례 단위 신호 이력(API_CONTRACT 4절, 2026-10-28).
import uuid
from typing import Any, Dict, List

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.models.analysis import AIAnalysis
from tests.conftest import create_session
from tests.test_analysis import analyzed_session, confirmed_session

TYPE_ORDER = ["PHYSICAL", "EMOTIONAL", "SEXUAL", "NEGLECT"]


def _get(client: TestClient, headers, case_id: str):
    return client.get(f"/api/v1/cases/{case_id}/signal-history", headers=headers)


def _put_assessment(client: TestClient, headers, session_id: str, abuse_type: str, level: str):
    return client.put(
        f"/api/v1/sessions/{session_id}/risk-assessments/{abuse_type}",
        json={"counselor_level": level},
        headers=headers,
    )


def _set_result(db, session_id: str, **fields: Any) -> None:
    """최신 분석 결과에 선택 필드를 넣는다. mock AI 는 abuse_signals · severity_ratings 를 이렇게 만들지 않으므로 직접 고친다."""

    analysis = db.scalar(
        select(AIAnalysis)
        .where(AIAnalysis.session_id == uuid.UUID(session_id))
        .order_by(AIAnalysis.created_at.desc())
        .limit(1)
    )
    analysis.result = {**analysis.result, **fields}
    db.commit()


def _by_type(types: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    return {row["abuse_type"]: row for row in types}


def test_case_without_sessions_has_empty_history(client: TestClient, counselor_headers, case: dict) -> None:
    response = _get(client, counselor_headers, case["id"])

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["case_id"] == case["id"]
    assert data["sessions"] == []


def test_session_before_analysis_has_no_types(
    client: TestClient, counselor_headers, case: dict, session: dict
) -> None:
    """분석을 요청한 적이 없고 판단도 없으면 analysis_status 는 null, types 는 빈 목록이다."""

    rows = _get(client, counselor_headers, case["id"]).json()["data"]["sessions"]

    assert len(rows) == 1
    row = rows[0]
    assert row["session_id"] == session["id"]
    assert row["session_number"] == session["session_number"]
    assert row["status"] == session["status"]
    assert row["analysis_status"] is None
    assert row["types"] == []


def test_analyzed_session_rows_follow_contract_rules(
    client: TestClient, counselor_headers, db, case: dict, session: dict
) -> None:
    """detected 는 abuse_signals 첫 항목의 참/거짓만, ai_level 은 severity_ratings 첫 항목의 1~5 만, 판단은 11절 값."""

    analyzed_session(client, counselor_headers, session["id"])
    _set_result(
        db,
        session["id"],
        abuse_signals=[
            {"abuse_type": "PHYSICAL", "detected": True, "detection_source": "MODEL", "segment_ids": ["seg_001"]},
            {"abuse_type": "PHYSICAL", "detected": False},  # 같은 유형 둘째는 무시
            {"abuse_type": "NEGLECT", "detected": False, "detection_source": "FILTERED"},
            {"abuse_type": "EMOTIONAL", "detected": "yes"},  # 참/거짓이 아니면 null
        ],
        severity_ratings=[
            {"major_type": "신체학대", "level": 3, "reason": "", "matched_evidence": "", "segment_ids": []},
            {"major_type": "신체학대", "level": 5},  # 같은 유형 둘째는 무시
            {"major_type": "방 임", "level": None},  # 띄어쓰기 라벨 · 정보 부족
            {"major_type": "성학대", "level": 7},  # 범위 밖
        ],
    )
    assert _put_assessment(client, counselor_headers, session["id"], "PHYSICAL", "HIGH").status_code == 200

    rows = _get(client, counselor_headers, case["id"]).json()["data"]["sessions"]

    assert len(rows) == 1
    row = rows[0]
    assert row["analysis_status"] == "COMPLETED"
    assert [item["abuse_type"] for item in row["types"]] == TYPE_ORDER

    types = _by_type(row["types"])
    assert types["PHYSICAL"]["detected"] is True
    assert types["PHYSICAL"]["ai_level"] == 3
    assert types["PHYSICAL"]["counselor_level"] == "HIGH"
    assert types["PHYSICAL"]["assessed_at"] is not None
    assert types["EMOTIONAL"] == {
        "abuse_type": "EMOTIONAL",
        "detected": None,
        "ai_level": None,
        "counselor_level": None,
        "assessed_at": None,
    }
    assert types["SEXUAL"]["detected"] is None
    assert types["SEXUAL"]["ai_level"] is None
    assert types["NEGLECT"]["detected"] is False
    assert types["NEGLECT"]["ai_level"] is None
    assert types["NEGLECT"]["counselor_level"] is None


def test_sessions_are_in_number_order_and_include_unanalyzed(
    client: TestClient, counselor_headers, case: dict
) -> None:
    """회차는 session_number 오름차순으로 전부 온다. 분석 전 회차도 자리가 있다(추이 그래프)."""

    first = create_session(client, counselor_headers, case["id"])
    second = create_session(client, counselor_headers, case["id"])
    third = create_session(client, counselor_headers, case["id"])
    analyzed_session(client, counselor_headers, second["id"])

    rows = _get(client, counselor_headers, case["id"]).json()["data"]["sessions"]

    assert [row["session_id"] for row in rows] == [first["id"], second["id"], third["id"]]
    assert [row["session_number"] for row in rows] == sorted(row["session_number"] for row in rows)
    assert rows[0]["types"] == [] and rows[2]["types"] == []
    assert rows[1]["analysis_status"] == "COMPLETED"
    assert len(rows[1]["types"]) == 4


def test_assessment_without_completed_analysis_is_shown(
    client: TestClient, counselor_headers, case: dict, session: dict
) -> None:
    """원문 확정 뒤 분석 없이 판단만 저장해도 네 유형이 오고, AI 값은 모두 null 이다."""

    confirmed_session(client, counselor_headers, session["id"])
    assert _put_assessment(client, counselor_headers, session["id"], "NEGLECT", "LOW").status_code == 200

    row = _get(client, counselor_headers, case["id"]).json()["data"]["sessions"][0]

    assert row["analysis_status"] is None
    assert [item["abuse_type"] for item in row["types"]] == TYPE_ORDER
    types = _by_type(row["types"])
    assert types["NEGLECT"]["counselor_level"] == "LOW"
    assert types["NEGLECT"]["detected"] is None and types["NEGLECT"]["ai_level"] is None
    assert types["PHYSICAL"]["counselor_level"] is None


def test_malformed_result_fields_are_ignored(
    client: TestClient, counselor_headers, db, case: dict, session: dict
) -> None:
    """선택 필드가 이상한 모양이어도(문자열 · 숫자 유형 · 문자열 level) 500 없이 null 로 온다."""

    analyzed_session(client, counselor_headers, session["id"])
    _set_result(
        db,
        session["id"],
        abuse_signals="garbage",
        severity_ratings=[{"major_type": 5, "level": "3"}, "x", {"major_type": "신체학대", "level": True}],
    )

    response = _get(client, counselor_headers, case["id"])

    assert response.status_code == 200
    row = response.json()["data"]["sessions"][0]
    assert row["analysis_status"] == "COMPLETED"
    assert all(item["detected"] is None and item["ai_level"] is None for item in row["types"])


def test_other_counselor_is_forbidden_and_admin_is_allowed(
    client: TestClient, counselor_headers, other_counselor_headers, admin_headers, case: dict
) -> None:
    forbidden = _get(client, other_counselor_headers, case["id"])
    allowed = _get(client, admin_headers, case["id"])

    assert forbidden.status_code == 403
    assert forbidden.json()["error"]["code"] == "FORBIDDEN"
    assert allowed.status_code == 200


def test_unknown_case_is_404(client: TestClient, counselor_headers) -> None:
    response = _get(client, counselor_headers, str(uuid.uuid4()))

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "CASE_NOT_FOUND"
