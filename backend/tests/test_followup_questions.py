# 승인한 추가 질문 저장 테스트 (app/services/followup_question_service.py, API_CONTRACT 18절).
#
# 회차마다 상담사가 승인 · 고친 · 직접 쓴 질문 목록을 통째로 저장하고, 질문마다 서버가 승인 일시를 찍는지,
# 같은 질문의 승인 일시가 다시 저장해도 그대로인지, 근거 번호 · 상태 · 권한을 막는지 본다.
# AI 분석 결과의 followup_questions 에서 모르는 kind 를 버리는 것도 여기서 본다. 데이터는 모두 가상이다.

import uuid
from typing import Any, Dict, List

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.enums import AuditAction, SessionStatus
from app.models.audit_log import AuditLog
from app.models.followup_question import SessionFollowupQuestions
from app.models.session import ConsultationSession
from app.schemas.contracts import AIAnalysisResult
from tests.conftest import create_case, create_session
from tests.test_analysis import confirmed_session

AI_QUESTION = "등이랑 팔이 아팠던 건 지금은 어때?"
OWN_QUESTION = "요즘 학교 끝나고 집에 가면 보통 뭐 해?"


def _url(session_id: str) -> str:
    return f"/api/v1/sessions/{session_id}/followup-questions"


def _q(text: str = AI_QUESTION, **extra: Any) -> Dict[str, Any]:
    item: Dict[str, Any] = {"text": text, "kind": "OPEN", "source": "AI", "segment_ids": ["seg_001"]}
    item.update(extra)

    return item


def _put(client: TestClient, headers, session_id: str, questions: List[Dict[str, Any]]):
    return client.put(_url(session_id), json={"questions": questions}, headers=headers)


def _set_status(db, session_id: str, status: SessionStatus) -> None:
    row = db.get(ConsultationSession, uuid.UUID(session_id))
    row.status = status
    db.commit()


@pytest.fixture
def ready_session(client: TestClient, counselor_headers, session: dict) -> dict:
    """원문을 확정해 질문을 저장할 수 있는 회차(mock 전사본 seg_001 ~)."""

    confirmed_session(client, counselor_headers, session["id"])

    return session


# =========================================================
# 조회 · 저장
# =========================================================

def test_get_is_empty_before_any_save(client: TestClient, counselor_headers, ready_session: dict) -> None:
    response = client.get(_url(ready_session["id"]), headers=counselor_headers)

    assert response.status_code == 200
    assert response.json()["data"] == {
        "session_id": ready_session["id"],
        "questions": [],
        "updated_at": None,
        "updated_by_id": None,
    }


def test_save_then_get(client: TestClient, counselor_headers, counselor_id, ready_session: dict) -> None:
    saved = _put(
        client,
        counselor_headers,
        ready_session["id"],
        [_q(), _q(OWN_QUESTION, source="COUNSELOR", segment_ids=[])],
    )

    assert saved.status_code == 200, saved.text
    data = client.get(_url(ready_session["id"]), headers=counselor_headers).json()["data"]
    assert data == saved.json()["data"]
    assert [item["text"] for item in data["questions"]] == [AI_QUESTION, OWN_QUESTION]
    assert [item["source"] for item in data["questions"]] == ["AI", "COUNSELOR"]
    assert data["questions"][0]["segment_ids"] == ["seg_001"]
    assert data["questions"][0]["bank_code"] is None
    assert all(item["approved_at"] for item in data["questions"])
    assert data["updated_by_id"] == str(counselor_id)
    assert data["updated_at"] is not None


def test_save_replaces_the_whole_list_and_empty_list_clears(
    client: TestClient, counselor_headers, ready_session: dict, db
) -> None:
    _put(client, counselor_headers, ready_session["id"], [_q(), _q(OWN_QUESTION, source="COUNSELOR")])
    replaced = _put(client, counselor_headers, ready_session["id"], [_q(OWN_QUESTION, source="COUNSELOR")])
    cleared = _put(client, counselor_headers, ready_session["id"], [])

    assert [item["text"] for item in replaced.json()["data"]["questions"]] == [OWN_QUESTION]
    assert cleared.json()["data"]["questions"] == []
    # 회차마다 한 행만 둔다.
    rows = db.scalars(select(SessionFollowupQuestions)).all()
    assert len(rows) == 1


def test_unchanged_question_keeps_its_approved_at(
    client: TestClient, counselor_headers, ready_session: dict
) -> None:
    first = _put(client, counselor_headers, ready_session["id"], [_q()]).json()["data"]["questions"][0]
    # 앞에 새 질문을 더하고, 기존 질문은 그대로 둔다.
    second = _put(
        client,
        counselor_headers,
        ready_session["id"],
        [_q(OWN_QUESTION, source="COUNSELOR", segment_ids=[]), _q()],
    ).json()["data"]["questions"]

    assert second[1]["text"] == AI_QUESTION
    assert second[1]["approved_at"] == first["approved_at"]


def test_edited_question_gets_a_new_approved_at(
    client: TestClient, counselor_headers, ready_session: dict
) -> None:
    first = _put(client, counselor_headers, ready_session["id"], [_q()]).json()["data"]["questions"][0]
    edited = _put(
        client, counselor_headers, ready_session["id"], [_q(AI_QUESTION + " 누가 봐 준 적 있어?")]
    ).json()["data"]["questions"][0]

    assert edited["approved_at"] >= first["approved_at"]
    assert edited["text"] != first["text"]


def test_text_is_stripped_and_segment_ids_are_deduplicated(
    client: TestClient, counselor_headers, ready_session: dict
) -> None:
    response = _put(
        client,
        counselor_headers,
        ready_session["id"],
        [_q("  " + AI_QUESTION + "  ", segment_ids=["seg_002", "seg_001", "seg_002", " "])],
    )

    item = response.json()["data"]["questions"][0]
    assert item["text"] == AI_QUESTION
    assert item["segment_ids"] == ["seg_002", "seg_001"]


def test_bank_question_keeps_its_code(client: TestClient, counselor_headers, ready_session: dict) -> None:
    response = _put(
        client, counselor_headers, ready_session["id"], [_q(kind="BANK", bank_code="QB-N-01")]
    )

    assert response.status_code == 200, response.text
    assert response.json()["data"]["questions"][0]["bank_code"] == "QB-N-01"


# =========================================================
# 입력 검증
# =========================================================

@pytest.mark.parametrize(
    "item",
    [
        _q(""),
        _q("   "),
        _q("가" * 301),
        _q(kind="CLOSED"),
        _q(source="SYSTEM"),
        _q(kind="BANK"),
        _q(bank_code="QB-N-01"),
        _q(segment_ids=[f"seg_{index:03d}" for index in range(21)]),
        {"kind": "OPEN", "source": "AI"},
    ],
)
def test_bad_question_is_rejected(
    client: TestClient, counselor_headers, ready_session: dict, item: Dict[str, Any]
) -> None:
    response = _put(client, counselor_headers, ready_session["id"], [item])

    assert response.status_code == 422


def test_text_at_max_length_is_accepted(client: TestClient, counselor_headers, ready_session: dict) -> None:
    response = _put(client, counselor_headers, ready_session["id"], [_q("가" * 300)])

    assert response.status_code == 200, response.text


def test_more_than_twenty_questions_are_rejected(
    client: TestClient, counselor_headers, ready_session: dict
) -> None:
    twenty = [_q(f"{AI_QUESTION} {index}") for index in range(20)]

    assert _put(client, counselor_headers, ready_session["id"], twenty).status_code == 200
    assert _put(client, counselor_headers, ready_session["id"], twenty + [_q()]).status_code == 422


def test_segment_ids_must_be_in_the_transcript(
    client: TestClient, counselor_headers, ready_session: dict
) -> None:
    response = _put(client, counselor_headers, ready_session["id"], [_q(segment_ids=["seg_001", "seg_999"])])

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "VALIDATION_ERROR"
    # 문구에 받은 번호를 넣지 않는다.
    assert "seg_999" not in error["message"]
    assert client.get(_url(ready_session["id"]), headers=counselor_headers).json()["data"]["questions"] == []


def test_question_with_unstorable_character_is_rejected(
    client: TestClient, counselor_headers, ready_session: dict
) -> None:
    response = _put(client, counselor_headers, ready_session["id"], [_q(AI_QUESTION + "\u0000")])

    assert response.status_code == 422


# =========================================================
# 상태 · 권한
# =========================================================

@pytest.mark.parametrize(
    "status",
    [
        SessionStatus.CREATED,
        SessionStatus.AUDIO_UPLOADED,
        SessionStatus.STT_PROCESSING,
        SessionStatus.STT_REVIEW_REQUIRED,
        SessionStatus.STT_FAILED,
        SessionStatus.AI_PROCESSING,
    ],
)
def test_save_is_rejected_before_transcript_confirmed_or_while_analyzing(
    client: TestClient, counselor_headers, session: dict, db, status: SessionStatus
) -> None:
    _set_status(db, session["id"], status)

    response = _put(client, counselor_headers, session["id"], [_q(OWN_QUESTION, source="COUNSELOR", segment_ids=[])])

    assert response.status_code == 409
    error = response.json()["error"]
    assert error["code"] == "INVALID_SESSION_STATE"
    assert error["details"]["current_status"] == status.value
    # 조회는 상태와 관계없이 된다.
    assert client.get(_url(session["id"]), headers=counselor_headers).status_code == 200


@pytest.mark.parametrize(
    "status",
    [
        SessionStatus.STT_CONFIRMED,
        SessionStatus.AI_REVIEW_REQUIRED,
        SessionStatus.AI_FAILED,
        SessionStatus.APPROVED,
    ],
)
def test_save_is_allowed_after_transcript_confirmed(
    client: TestClient, counselor_headers, ready_session: dict, db, status: SessionStatus
) -> None:
    _set_status(db, ready_session["id"], status)

    response = _put(client, counselor_headers, ready_session["id"], [_q()])

    assert response.status_code == 200, response.text


def test_other_counselor_is_forbidden(
    client: TestClient, counselor_headers, other_counselor_headers, ready_session: dict
) -> None:
    _put(client, counselor_headers, ready_session["id"], [_q()])

    listed = client.get(_url(ready_session["id"]), headers=other_counselor_headers)
    saved = _put(client, other_counselor_headers, ready_session["id"], [])

    assert listed.status_code == 403
    assert listed.json()["error"]["code"] == "FORBIDDEN"
    assert saved.status_code == 403
    assert saved.json()["error"]["code"] == "FORBIDDEN"


def test_admin_can_get_and_save(
    client: TestClient, counselor_headers, admin_headers, admin_id, ready_session: dict
) -> None:
    _put(client, counselor_headers, ready_session["id"], [_q()])

    listed = client.get(_url(ready_session["id"]), headers=admin_headers)
    saved = _put(client, admin_headers, ready_session["id"], [])

    assert listed.status_code == 200
    assert len(listed.json()["data"]["questions"]) == 1
    assert saved.status_code == 200
    assert saved.json()["data"]["updated_by_id"] == str(admin_id)


def test_unknown_session_is_not_found(client: TestClient, counselor_headers) -> None:
    missing = str(uuid.uuid4())

    assert client.get(_url(missing), headers=counselor_headers).status_code == 404
    response = _put(client, counselor_headers, missing, [])

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "SESSION_NOT_FOUND"


def test_login_is_required(client: TestClient, ready_session: dict) -> None:
    assert client.get(_url(ready_session["id"])).status_code == 401
    assert _put(client, {}, ready_session["id"], []).status_code == 401


# =========================================================
# 삭제 · 감사 기록
# =========================================================

def test_deleting_session_deletes_questions(
    client: TestClient, counselor_headers, ready_session: dict, db
) -> None:
    _put(client, counselor_headers, ready_session["id"], [_q()])

    response = client.delete(f"/api/v1/sessions/{ready_session['id']}", headers=counselor_headers)

    assert response.status_code == 204
    assert db.scalars(select(SessionFollowupQuestions)).all() == []


def test_deleting_case_deletes_questions(client: TestClient, counselor_headers, admin_headers, db) -> None:
    case = create_case(client, counselor_headers)
    session = create_session(client, counselor_headers, case["id"])
    confirmed_session(client, counselor_headers, session["id"])
    _put(client, counselor_headers, session["id"], [_q()])

    response = client.delete(f"/api/v1/cases/{case['id']}", headers=admin_headers)

    assert response.status_code == 204
    assert db.scalars(select(SessionFollowupQuestions)).all() == []


def test_save_is_audited_with_counts_only(
    client: TestClient, counselor_headers, counselor_id, ready_session: dict, db
) -> None:
    _put(client, counselor_headers, ready_session["id"], [_q()])
    saved = _put(
        client,
        counselor_headers,
        ready_session["id"],
        [_q(), _q(OWN_QUESTION, source="COUNSELOR", segment_ids=[])],
    )

    logs = db.scalars(
        select(AuditLog)
        .where(AuditLog.action == AuditAction.FOLLOWUP_QUESTIONS_UPDATED)
        .order_by(AuditLog.created_at)
    ).all()

    assert [log.detail for log in logs] == [
        {"count": 1, "ai_count": 1, "counselor_count": 0, "previous_count": 0},
        {"count": 2, "ai_count": 1, "counselor_count": 1, "previous_count": 1},
    ]
    row = db.scalar(select(SessionFollowupQuestions))
    for log in logs:
        assert log.actor_id == counselor_id
        assert str(log.session_id) == ready_session["id"]
        assert log.entity_id == row.id
        assert log.entity_type == "SessionFollowupQuestions"
        # 질문 문장은 감사 기록에 남지 않는다.
        assert AI_QUESTION not in str(log.detail)
        assert OWN_QUESTION not in str(log.detail)

    assert saved.status_code == 200


# =========================================================
# AI 분석 결과의 followup_questions(초안)
# =========================================================

def test_analysis_result_drops_unknown_question_kinds() -> None:
    result = AIAnalysisResult.model_validate(
        {
            "followup_questions": [
                {"text": AI_QUESTION, "kind": "OPEN", "segment_ids": ["seg_001"], "reason": "가상"},
                {"text": "아빠가 때렸어?", "kind": "CLOSED"},
                {"text": "   ", "kind": "OPEN"},
                "문자열 질문",
                {"text": OWN_QUESTION},
                {"text": "은행 질문", "kind": "BANK", "bank_code": "QB-N-01"},
            ]
        }
    )

    assert [(item.text, item.kind) for item in result.followup_questions] == [
        (AI_QUESTION, "OPEN"),
        (OWN_QUESTION, "OPEN"),
        ("은행 질문", "BANK"),
    ]


def test_analysis_result_without_followup_questions_is_still_valid() -> None:
    assert AIAnalysisResult.model_validate({}).followup_questions == []
