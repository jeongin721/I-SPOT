# 상담사 수정 / 승인 Flow 테스트.
# AI 결과가 자동 승인되지 않고, 수정 이력이 남는지 확인한다.

import uuid

from fastapi.testclient import TestClient

from app.adapters.ai_adapter import set_ai_adapter_override
from app.core.enums import AuditAction
from app.models.audit_log import AuditLog
from tests.test_analysis import FailingAIAdapter, analyzed_session, confirmed_session


def test_summary_before_analysis_is_null(
    client: TestClient, counselor_headers, session: dict
) -> None:
    response = client.get(
        f"/api/v1/sessions/{session['id']}/summary", headers=counselor_headers
    )

    assert response.status_code == 200
    assert response.json()["data"]["summary"] is None


def test_summary_includes_evidence_for_review(
    client: TestClient, counselor_headers, session: dict
) -> None:
    analyzed_session(client, counselor_headers, session["id"])

    response = client.get(
        f"/api/v1/sessions/{session['id']}/summary", headers=counselor_headers
    )

    data = response.json()["data"]

    assert data["summary"]["status"] == "DRAFT"
    # 검수 화면에서 근거 발화를 확인할 수 있어야 한다.
    assert data["summary_evidence"]


def test_counselor_can_edit_summary(
    client: TestClient, counselor_headers, session: dict
) -> None:
    analyzed_session(client, counselor_headers, session["id"])

    response = client.patch(
        f"/api/v1/sessions/{session['id']}/summary",
        json={
            "overview": "상담사가 검토한 요약입니다.",
            "key_points": ["확인된 내용 1", "추가 확인 필요"],
            "counselor_note": "다음 회기에 재확인 예정",
        },
        headers=counselor_headers,
    )

    assert response.status_code == 200

    summary = response.json()["data"]

    assert summary["overview"] == "상담사가 검토한 요약입니다."
    assert summary["key_points"] == ["확인된 내용 1", "추가 확인 필요"]
    assert summary["counselor_note"] == "다음 회기에 재확인 예정"
    assert summary["is_edited"] is True
    assert summary["status"] == "DRAFT"


def test_summary_edit_requires_at_least_one_field(
    client: TestClient, counselor_headers, session: dict
) -> None:
    analyzed_session(client, counselor_headers, session["id"])

    response = client.patch(
        f"/api/v1/sessions/{session['id']}/summary", json={}, headers=counselor_headers
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_summary_edit_before_analysis_returns_not_found(
    client: TestClient, counselor_headers, session: dict
) -> None:
    confirmed_session(client, counselor_headers, session["id"])

    response = client.patch(
        f"/api/v1/sessions/{session['id']}/summary",
        json={"overview": "수정"},
        headers=counselor_headers,
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "SUMMARY_NOT_FOUND"


def test_approve_summary_moves_session_to_approved(
    client: TestClient, counselor_headers, session: dict
) -> None:
    analyzed_session(client, counselor_headers, session["id"])

    response = client.post(
        f"/api/v1/sessions/{session['id']}/summary/approve", headers=counselor_headers
    )

    assert response.status_code == 200

    summary = response.json()["data"]

    assert summary["status"] == "APPROVED"
    assert summary["approved_at"]
    assert summary["approved_by_id"]

    detail = client.get(
        f"/api/v1/sessions/{session['id']}", headers=counselor_headers
    ).json()["data"]

    assert detail["status"] == "APPROVED"
    assert detail["summary_approved"] is True
    assert detail["approved_at"]


def test_approve_twice_returns_already_approved(
    client: TestClient, counselor_headers, session: dict
) -> None:
    analyzed_session(client, counselor_headers, session["id"])

    client.post(
        f"/api/v1/sessions/{session['id']}/summary/approve", headers=counselor_headers
    )

    second = client.post(
        f"/api/v1/sessions/{session['id']}/summary/approve", headers=counselor_headers
    )

    assert second.status_code == 409
    assert second.json()["error"]["code"] == "ALREADY_APPROVED"


def test_approved_summary_cannot_be_edited(
    client: TestClient, counselor_headers, session: dict
) -> None:
    analyzed_session(client, counselor_headers, session["id"])

    client.post(
        f"/api/v1/sessions/{session['id']}/summary/approve", headers=counselor_headers
    )

    response = client.patch(
        f"/api/v1/sessions/{session['id']}/summary",
        json={"overview": "승인 후 수정 시도"},
        headers=counselor_headers,
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "ALREADY_APPROVED"


def test_approved_session_cannot_be_updated(
    client: TestClient, counselor_headers, session: dict
) -> None:
    analyzed_session(client, counselor_headers, session["id"])

    client.post(
        f"/api/v1/sessions/{session['id']}/summary/approve", headers=counselor_headers
    )

    response = client.patch(
        f"/api/v1/sessions/{session['id']}",
        json={"title": "승인 후 수정"},
        headers=counselor_headers,
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "ALREADY_APPROVED"


def test_approve_without_summary_returns_not_found(
    client: TestClient, counselor_headers, session: dict
) -> None:
    response = client.post(
        f"/api/v1/sessions/{session['id']}/summary/approve", headers=counselor_headers
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "SUMMARY_NOT_FOUND"


def test_reopen_approved_summary_keeps_content_and_allows_reapproval(
    client: TestClient, counselor_headers, session: dict
) -> None:
    analyzed_session(client, counselor_headers, session["id"])
    summary_url = f"/api/v1/sessions/{session['id']}/summary"
    session_url = f"/api/v1/sessions/{session['id']}"

    written = client.patch(
        summary_url,
        json={
            "overview": "처음 쓴 요약",
            "key_points": ["처음 쓴 요점"],
            "counselor_note": "처음 쓴 메모",
        },
        headers=counselor_headers,
    ).json()["data"]
    client.post(f"{summary_url}/approve", headers=counselor_headers)

    reopened = client.post(f"{summary_url}/reopen", headers=counselor_headers)

    assert reopened.status_code == 200
    data = reopened.json()["data"]
    assert data["status"] == "DRAFT"
    assert data["approved_at"] is None
    assert data["approved_by_id"] is None
    # 처음 쓴 내용은 그대로 남아 이어서 고칠 수 있다.
    for field in ("overview", "key_points", "counselor_note", "is_edited"):
        assert data[field] == written[field]

    # 회기도 검수 단계로 돌아가 승인 정보가 비워진다.
    detail = client.get(session_url, headers=counselor_headers).json()["data"]
    assert detail["status"] == "AI_REVIEW_REQUIRED"
    assert detail["summary_approved"] is False
    assert detail["approved_at"] is None

    edited = client.patch(summary_url, json={"overview": "고친 요약"}, headers=counselor_headers)
    assert edited.status_code == 200
    assert edited.json()["data"]["overview"] == "고친 요약"
    assert edited.json()["data"]["counselor_note"] == "처음 쓴 메모"

    approved = client.post(f"{summary_url}/approve", headers=counselor_headers)
    assert approved.status_code == 200
    assert approved.json()["data"]["status"] == "APPROVED"

    detail = client.get(session_url, headers=counselor_headers).json()["data"]
    assert detail["status"] == "APPROVED"
    assert detail["summary_approved"] is True
    assert detail["approved_at"]


def test_summary_reopen_does_not_offer_to_unlock_transcript(
    client: TestClient, counselor_headers, session: dict
) -> None:
    analyzed_session(client, counselor_headers, session["id"])
    root = f"/api/v1/sessions/{session['id']}"
    transcript = client.get(f"{root}/transcript", headers=counselor_headers).json()["data"][
        "transcript"
    ]
    assert client.post(f"{root}/summary/approve", headers=counselor_headers).status_code == 200
    payload = {
        "segments": [
            {"segment_id": transcript["segments"][0]["segment_id"], "text": "가상 수정 원문"}
        ]
    }

    blocked = client.patch(f"{root}/transcript", json=payload, headers=counselor_headers)
    assert blocked.status_code == 409
    assert blocked.json()["error"]["code"] == "INVALID_SESSION_STATE"
    assert "요약 수정" not in blocked.json()["error"]["message"]

    assert client.post(f"{root}/summary/reopen", headers=counselor_headers).status_code == 200
    still_blocked = client.patch(f"{root}/transcript", json=payload, headers=counselor_headers)
    assert still_blocked.status_code == 409
    assert still_blocked.json()["error"]["details"]["current_status"] == "AI_REVIEW_REQUIRED"
    unchanged = client.get(f"{root}/transcript", headers=counselor_headers).json()["data"][
        "transcript"
    ]
    assert unchanged == transcript


def test_reopen_unapproved_summary_returns_not_approved(
    client: TestClient, counselor_headers, session: dict
) -> None:
    analyzed_session(client, counselor_headers, session["id"])

    response = client.post(
        f"/api/v1/sessions/{session['id']}/summary/reopen", headers=counselor_headers
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "NOT_APPROVED"

    detail = client.get(
        f"/api/v1/sessions/{session['id']}", headers=counselor_headers
    ).json()["data"]
    assert detail["status"] == "AI_REVIEW_REQUIRED"


def test_reopen_without_summary_returns_not_found(
    client: TestClient, counselor_headers, session: dict
) -> None:
    response = client.post(
        f"/api/v1/sessions/{session['id']}/summary/reopen", headers=counselor_headers
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "SUMMARY_NOT_FOUND"


def test_other_counselor_cannot_reopen_summary(
    client: TestClient, counselor_headers, other_counselor_headers, session: dict
) -> None:
    analyzed_session(client, counselor_headers, session["id"])
    summary_url = f"/api/v1/sessions/{session['id']}/summary"
    client.post(f"{summary_url}/approve", headers=counselor_headers)

    response = client.post(f"{summary_url}/reopen", headers=other_counselor_headers)

    assert response.status_code == 403

    detail = client.get(
        f"/api/v1/sessions/{session['id']}", headers=counselor_headers
    ).json()["data"]
    assert detail["status"] == "APPROVED"


def test_reanalysis_preserves_counselor_edits(
    client: TestClient, counselor_headers, session: dict
) -> None:
    """
    상담사가 수정한 요약은 재분석으로 덮어써지지 않는다.
    (Human-in-the-loop 원칙)
    """

    analyzed_session(client, counselor_headers, session["id"])

    client.patch(
        f"/api/v1/sessions/{session['id']}/summary",
        json={"overview": "상담사 최종 판단이 반영된 요약"},
        headers=counselor_headers,
    )

    assert (
        client.post(
            f"/api/v1/sessions/{session['id']}/analysis", headers=counselor_headers
        ).status_code
        == 202
    )

    summary = client.get(
        f"/api/v1/sessions/{session['id']}/summary", headers=counselor_headers
    ).json()["data"]["summary"]

    assert summary["overview"] == "상담사 최종 판단이 반영된 요약"
    assert summary["is_edited"] is True


def test_summary_edit_and_approval_are_audited(
    client: TestClient, counselor_headers, session: dict, db
) -> None:
    analyzed_session(client, counselor_headers, session["id"])

    client.patch(
        f"/api/v1/sessions/{session['id']}/summary",
        json={"overview": "수정된 요약", "key_points": ["a", "b"]},
        headers=counselor_headers,
    )
    client.post(
        f"/api/v1/sessions/{session['id']}/summary/approve", headers=counselor_headers
    )

    logs = (
        db.query(AuditLog)
        .filter(AuditLog.session_id == uuid.UUID(session["id"]))
        .all()
    )
    actions = {log.action for log in logs}

    assert AuditAction.SUMMARY_UPDATED in actions
    assert AuditAction.SUMMARY_APPROVED in actions

    updated = next(log for log in logs if log.action == AuditAction.SUMMARY_UPDATED)

    assert updated.actor_id is not None
    assert updated.case_id is not None
    assert set(updated.detail["changed_fields"]) == {"overview", "key_points"}
    # 상담 원문/요약 본문이 Audit log 에 저장되지 않아야 한다.
    assert "수정된 요약" not in str(updated.detail)


def test_ai_failure_keeps_summary_absent(
    client: TestClient, counselor_headers, session: dict
) -> None:
    confirmed_session(client, counselor_headers, session["id"])
    set_ai_adapter_override(FailingAIAdapter())

    client.post(f"/api/v1/sessions/{session['id']}/analysis", headers=counselor_headers)

    response = client.get(
        f"/api/v1/sessions/{session['id']}/summary", headers=counselor_headers
    )

    assert response.status_code == 200
    assert response.json()["data"]["summary"] is None
