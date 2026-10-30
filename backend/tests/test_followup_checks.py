# 다음 상담 전 확인할 사항 저장 테스트 (app/services/followup_check_service.py, API_CONTRACT 18.1절, 2026-10-30).
#
# 회차마다 상담사가 고친 · 직접 쓴 · 브리핑에 넣기로 고른 확인 사항 목록을 통째로 저장하는지, 근거 번호 · 상태 · 권한을
# 막는지, 감사 기록에 문장이 남지 않는지 본다. 추가 질문 저장(test_followup_questions.py)과 같은 규칙이다. 데이터는 모두 가상이다.

from typing import Any, Dict, List

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.enums import AuditAction, SessionStatus
from app.models.audit_log import AuditLog
from app.models.followup_check import SessionFollowupChecks
from tests.conftest import create_case, create_session
from tests.test_followup_questions import _set_status, ready_session  # noqa: F401 — 픽스처

AI_CHECK = "등 · 팔 통증 이후 치료 여부 확인 필요."
OWN_CHECK = "학교 담임과 통화해 최근 결석 여부 확인."


def _url(session_id: str) -> str:
    return f"/api/v1/sessions/{session_id}/followup-checks"


def _c(text: str = AI_CHECK, **extra: Any) -> Dict[str, Any]:
    item: Dict[str, Any] = {"text": text, "source": "AI", "segment_ids": ["seg_001"]}
    item.update(extra)
    return item


def _put(client: TestClient, headers, session_id: str, items: List[Dict[str, Any]]):
    return client.put(_url(session_id), json={"items": items}, headers=headers)


def test_get_before_any_save_is_not_saved(client: TestClient, counselor_headers, ready_session: dict) -> None:
    response = client.get(_url(ready_session["id"]), headers=counselor_headers)

    assert response.status_code == 200
    assert response.json()["data"] == {
        "session_id": ready_session["id"],
        "saved": False,
        "items": [],
        "updated_at": None,
        "updated_by_id": None,
    }


def test_save_then_get(client: TestClient, counselor_headers, counselor_id, ready_session: dict) -> None:
    saved = _put(
        client,
        counselor_headers,
        ready_session["id"],
        [
            _c(edited=True, in_briefing=True),
            _c(OWN_CHECK, source="COUNSELOR", segment_ids=[], in_briefing=True, edited=True),
            _c("  앞뒤 공백  ", segment_ids=["seg_001", " seg_001 ", ""]),
        ],
    )

    assert saved.status_code == 200, saved.text
    data = client.get(_url(ready_session["id"]), headers=counselor_headers).json()["data"]
    assert data["saved"] is True
    assert data["updated_by_id"] == str(counselor_id)
    assert data["items"] == [
        {"text": AI_CHECK, "source": "AI", "segment_ids": ["seg_001"], "edited": True, "in_briefing": True},
        # 상담사가 직접 쓴 것은 '고침' 이 아니다.
        {"text": OWN_CHECK, "source": "COUNSELOR", "segment_ids": [], "edited": False, "in_briefing": True},
        {"text": "앞뒤 공백", "source": "AI", "segment_ids": ["seg_001"], "edited": False, "in_briefing": False},
    ]


def test_empty_list_is_saved_as_no_checks(client: TestClient, counselor_headers, ready_session: dict) -> None:
    _put(client, counselor_headers, ready_session["id"], [_c()])

    response = _put(client, counselor_headers, ready_session["id"], [])

    assert response.status_code == 200
    assert response.json()["data"]["saved"] is True
    assert response.json()["data"]["items"] == []


@pytest.mark.parametrize(
    "item",
    [
        _c("   "),
        _c("가" * 301),
        _c(source="BANK"),
        _c(segment_ids=[f"seg_{n:03d}" for n in range(21)]),
    ],
)
def test_bad_items_are_rejected(client: TestClient, counselor_headers, ready_session: dict, item: Dict[str, Any]) -> None:
    assert _put(client, counselor_headers, ready_session["id"], [item]).status_code == 422


def test_too_many_items_are_rejected(client: TestClient, counselor_headers, ready_session: dict) -> None:
    assert _put(client, counselor_headers, ready_session["id"], [_c(f"확인 {n}") for n in range(21)]).status_code == 422


def test_segment_ids_must_be_in_the_transcript(client: TestClient, counselor_headers, ready_session: dict) -> None:
    response = _put(client, counselor_headers, ready_session["id"], [_c(segment_ids=["seg_999"])])

    assert response.status_code == 422
    assert "seg_999" not in response.text


@pytest.mark.parametrize("status", [SessionStatus.CREATED, SessionStatus.STT_REVIEW_REQUIRED, SessionStatus.AI_PROCESSING])
def test_save_is_rejected_before_confirm_or_while_analyzing(
    client: TestClient, counselor_headers, session: dict, db, status: SessionStatus
) -> None:
    _set_status(db, session["id"], status)

    response = _put(client, counselor_headers, session["id"], [_c(OWN_CHECK, source="COUNSELOR", segment_ids=[])])

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "INVALID_SESSION_STATE"
    assert client.get(_url(session["id"]), headers=counselor_headers).status_code == 200


@pytest.mark.parametrize("status", [SessionStatus.AI_REVIEW_REQUIRED, SessionStatus.AI_FAILED, SessionStatus.APPROVED])
def test_save_is_allowed_after_confirm(
    client: TestClient, counselor_headers, ready_session: dict, db, status: SessionStatus
) -> None:
    _set_status(db, ready_session["id"], status)

    assert _put(client, counselor_headers, ready_session["id"], [_c()]).status_code == 200


def test_other_counselor_is_forbidden(
    client: TestClient, counselor_headers, other_counselor_headers, ready_session: dict
) -> None:
    assert client.get(_url(ready_session["id"]), headers=other_counselor_headers).status_code == 403
    assert _put(client, other_counselor_headers, ready_session["id"], []).status_code == 403


def test_deleting_case_deletes_checks(client: TestClient, counselor_headers, admin_headers, db) -> None:
    case = create_case(client, counselor_headers)
    session = create_session(client, counselor_headers, case["id"])
    from tests.test_analysis import confirmed_session

    confirmed_session(client, counselor_headers, session["id"])
    assert _put(client, counselor_headers, session["id"], [_c()]).status_code == 200

    assert client.delete(f"/api/v1/cases/{case['id']}", headers=admin_headers).status_code == 204
    assert db.scalar(select(SessionFollowupChecks)) is None


def test_save_is_audited_with_counts_only(
    client: TestClient, counselor_headers, counselor_id, ready_session: dict, db
) -> None:
    _put(client, counselor_headers, ready_session["id"], [_c()])
    _put(
        client,
        counselor_headers,
        ready_session["id"],
        [_c(edited=True, in_briefing=True), _c(OWN_CHECK, source="COUNSELOR", segment_ids=[])],
    )

    logs = db.scalars(
        select(AuditLog).where(AuditLog.action == AuditAction.FOLLOWUP_CHECKS_UPDATED).order_by(AuditLog.created_at)
    ).all()

    assert [log.detail for log in logs] == [
        {"count": 1, "ai_count": 1, "counselor_count": 0, "edited_count": 0, "briefing_count": 0, "previous_count": 0},
        {"count": 2, "ai_count": 1, "counselor_count": 1, "edited_count": 1, "briefing_count": 1, "previous_count": 1},
    ]
    for log in logs:
        assert log.actor_id == counselor_id
        assert log.entity_type == "SessionFollowupChecks"
        assert AI_CHECK not in str(log.detail) and OWN_CHECK not in str(log.detail)
