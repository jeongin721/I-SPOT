# 상담원 위험도 판단 테스트 (app/services/risk_assessment_service.py).
#
# 회차 · 학대 유형마다 상담원 판단(상/중/하) 하나를 저장하고, 판단할 때의
# AI 제안(severity_ratings 의 1~5)을 ai_level 로 함께 남기는지 본다.
# 데이터는 모두 가상이다.

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.adapters.ai_adapter import set_ai_adapter_override
from app.core.enums import (
    AbuseType,
    AuditAction,
    SessionStatus,
    abuse_type_from_label,
    abuse_type_label,
)
from app.core.errors import APIError
from app.models.analysis import AIAnalysis
from app.models.audit_log import AuditLog
from app.models.risk_assessment import SessionRiskAssessment
from app.models.session import ConsultationSession
from app.models.user import User
from app.schemas.risk_assessment import RiskAssessmentSaveRequest
from app.services import risk_assessment_service
from tests.conftest import create_case, create_session
from tests.test_analysis import FailingAIAdapter, analyzed_session, confirmed_session

REASON = "가상 판단 이유: 반복 진술과 흔적 언급이 있어 상으로 판단"


def _url(session_id: str, abuse_type: str = "") -> str:
    base = f"/api/v1/sessions/{session_id}/risk-assessments"

    return f"{base}/{abuse_type}" if abuse_type else base


def _put(client: TestClient, headers, session_id: str, abuse_type: str, **body):
    payload: Dict[str, Any] = {"counselor_level": "HIGH"}
    payload.update(body)

    return client.put(_url(session_id, abuse_type), json=payload, headers=headers)


def _set_status(db, session_id: str, status: SessionStatus) -> None:
    row = db.get(ConsultationSession, uuid.UUID(session_id))
    row.status = status
    db.commit()


def _set_severity_ratings(db, session_id: str, ratings: List[Dict[str, Any]]) -> None:
    """
    최신 분석 결과에 severity_ratings 를 넣는다.

    mock AI 는 이 필드를 만들지 않으므로 저장된 결과를 직접 고친다(PR #48 의 modeling 결과 모양).
    """

    analysis = db.scalar(
        select(AIAnalysis)
        .where(AIAnalysis.session_id == uuid.UUID(session_id))
        .order_by(AIAnalysis.created_at.desc())
        .limit(1)
    )
    analysis.result = {**analysis.result, "severity_ratings": ratings}
    db.commit()


@pytest.fixture
def ready_session(client: TestClient, counselor_headers, session: dict) -> dict:
    """원문을 확정해 판단을 받을 수 있는 회차."""

    confirmed_session(client, counselor_headers, session["id"])

    return session


# =========================================================
# 저장 · 수정 · 목록
# =========================================================

def test_save_then_list(
    client: TestClient, counselor_headers, counselor_id, ready_session: dict
) -> None:
    response = _put(client, counselor_headers, ready_session["id"], "PHYSICAL", reason=REASON)

    assert response.status_code == 200, response.text
    saved = response.json()["data"]
    assert saved["session_id"] == ready_session["id"]
    assert saved["abuse_type"] == "PHYSICAL"
    assert saved["counselor_level"] == "HIGH"
    assert saved["reason"] == REASON
    assert saved["ai_level"] is None
    assert saved["assessed_by_id"] == str(counselor_id)
    assert saved["assessed_at"]

    listed = client.get(_url(ready_session["id"]), headers=counselor_headers)

    assert listed.status_code == 200
    assert listed.json()["data"] == [saved]


def test_list_is_empty_before_any_assessment(
    client: TestClient, counselor_headers, session: dict
) -> None:
    response = client.get(_url(session["id"]), headers=counselor_headers)

    assert response.status_code == 200
    assert response.json()["data"] == []


def test_save_again_updates_the_same_row(
    client: TestClient, counselor_headers, ready_session: dict, db
) -> None:
    first = _put(client, counselor_headers, ready_session["id"], "EMOTIONAL", reason=REASON)
    second = _put(
        client, counselor_headers, ready_session["id"], "EMOTIONAL", counselor_level="LOW"
    )

    assert second.status_code == 200
    first_data = first.json()["data"]
    second_data = second.json()["data"]
    assert second_data["id"] == first_data["id"]
    assert second_data["counselor_level"] == "LOW"
    # 이유를 빼고 다시 저장하면 이유도 비운다(PUT 은 판단 전체를 바꾼다).
    assert second_data["reason"] is None
    assert second_data["assessed_at"] >= first_data["assessed_at"]

    rows = db.scalars(
        select(SessionRiskAssessment).where(
            SessionRiskAssessment.session_id == uuid.UUID(ready_session["id"])
        )
    ).all()
    assert len(rows) == 1


def test_list_is_in_abuse_type_order(
    client: TestClient, counselor_headers, ready_session: dict
) -> None:
    for abuse_type in ("NEGLECT", "PHYSICAL", "SEXUAL", "EMOTIONAL"):
        assert _put(client, counselor_headers, ready_session["id"], abuse_type).status_code == 200

    listed = client.get(_url(ready_session["id"]), headers=counselor_headers).json()["data"]

    assert [item["abuse_type"] for item in listed] == [
        "PHYSICAL",
        "EMOTIONAL",
        "SEXUAL",
        "NEGLECT",
    ]


def test_blank_reason_is_saved_as_null(
    client: TestClient, counselor_headers, ready_session: dict
) -> None:
    response = _put(client, counselor_headers, ready_session["id"], "SEXUAL", reason="   ")

    assert response.status_code == 200
    assert response.json()["data"]["reason"] is None


def test_assessments_are_per_session(
    client: TestClient, counselor_headers, case: dict, ready_session: dict
) -> None:
    other = create_session(client, counselor_headers, case["id"])
    confirmed_session(client, counselor_headers, other["id"])

    _put(client, counselor_headers, ready_session["id"], "PHYSICAL")

    listed = client.get(_url(other["id"]), headers=counselor_headers).json()["data"]

    assert listed == []


# =========================================================
# 권한
# =========================================================

def test_other_counselor_is_forbidden(
    client: TestClient, counselor_headers, other_counselor_headers, ready_session: dict
) -> None:
    _put(client, counselor_headers, ready_session["id"], "PHYSICAL")

    listed = client.get(_url(ready_session["id"]), headers=other_counselor_headers)
    saved = _put(client, other_counselor_headers, ready_session["id"], "PHYSICAL")

    assert listed.status_code == 403
    assert listed.json()["error"]["code"] == "FORBIDDEN"
    assert saved.status_code == 403
    assert saved.json()["error"]["code"] == "FORBIDDEN"


def test_admin_can_list_and_save(
    client: TestClient, counselor_headers, admin_headers, admin_id, ready_session: dict
) -> None:
    _put(client, counselor_headers, ready_session["id"], "PHYSICAL")

    listed = client.get(_url(ready_session["id"]), headers=admin_headers)
    saved = _put(
        client, admin_headers, ready_session["id"], "PHYSICAL", counselor_level="MEDIUM"
    )

    assert listed.status_code == 200
    assert len(listed.json()["data"]) == 1
    assert saved.status_code == 200
    assert saved.json()["data"]["counselor_level"] == "MEDIUM"
    assert saved.json()["data"]["assessed_by_id"] == str(admin_id)


def test_unknown_session_is_not_found(client: TestClient, counselor_headers) -> None:
    missing = str(uuid.uuid4())

    assert client.get(_url(missing), headers=counselor_headers).status_code == 404
    response = _put(client, counselor_headers, missing, "PHYSICAL")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "SESSION_NOT_FOUND"


def test_login_is_required(client: TestClient, ready_session: dict) -> None:
    assert client.get(_url(ready_session["id"])).status_code == 401
    assert _put(client, {}, ready_session["id"], "PHYSICAL").status_code == 401


# =========================================================
# 입력 검증
# =========================================================

@pytest.mark.parametrize("abuse_type", ["physical", "신체학대", "DOMESTIC", "1"])
def test_unknown_abuse_type_is_rejected(
    client: TestClient, counselor_headers, ready_session: dict, abuse_type: str
) -> None:
    response = _put(client, counselor_headers, ready_session["id"], abuse_type)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.parametrize(
    "body",
    [
        {"counselor_level": "상"},
        {"counselor_level": "MID"},
        {"counselor_level": "high"},
        {"counselor_level": 3},
        {"counselor_level": None},
        {"reason": "x" * 1001},
    ],
)
def test_bad_level_or_reason_is_rejected(
    client: TestClient, counselor_headers, ready_session: dict, body: dict
) -> None:
    response = _put(client, counselor_headers, ready_session["id"], "PHYSICAL", **body)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_missing_level_is_rejected(
    client: TestClient, counselor_headers, ready_session: dict
) -> None:
    response = client.put(
        _url(ready_session["id"], "PHYSICAL"), json={"reason": REASON}, headers=counselor_headers
    )

    assert response.status_code == 422


def test_reason_at_max_length_is_accepted(
    client: TestClient, counselor_headers, ready_session: dict
) -> None:
    response = _put(client, counselor_headers, ready_session["id"], "PHYSICAL", reason="가" * 1000)

    assert response.status_code == 200


def test_ai_level_in_body_is_ignored(
    client: TestClient, counselor_headers, ready_session: dict
) -> None:
    response = _put(client, counselor_headers, ready_session["id"], "PHYSICAL", ai_level=5)

    assert response.status_code == 200
    assert response.json()["data"]["ai_level"] is None


# =========================================================
# 회차 상태
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

    response = _put(client, counselor_headers, session["id"], "PHYSICAL")

    assert response.status_code == 409
    error = response.json()["error"]
    assert error["code"] == "INVALID_SESSION_STATE"
    assert error["details"]["current_status"] == status.value
    # 목록은 상태와 관계없이 볼 수 있다.
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
    client: TestClient, counselor_headers, session: dict, db, status: SessionStatus
) -> None:
    _set_status(db, session["id"], status)

    response = _put(client, counselor_headers, session["id"], "PHYSICAL")

    assert response.status_code == 200, response.text


# =========================================================
# ai_level — 판단 당시 AI 제안
# =========================================================

def test_ai_level_comes_from_latest_analysis(
    client: TestClient, counselor_headers, session: dict, db
) -> None:
    analyzed_session(client, counselor_headers, session["id"])
    _set_severity_ratings(
        db,
        session["id"],
        [
            {"major_type": "신체학대", "level": 4, "reason": "가상", "segment_ids": []},
            {"major_type": "정서 학대", "level": 2},
            {"major_type": "방임", "level": None},
        ],
    )

    physical = _put(client, counselor_headers, session["id"], "PHYSICAL").json()["data"]
    emotional = _put(client, counselor_headers, session["id"], "EMOTIONAL").json()["data"]
    neglect = _put(client, counselor_headers, session["id"], "NEGLECT").json()["data"]
    sexual = _put(client, counselor_headers, session["id"], "SEXUAL").json()["data"]

    assert physical["ai_level"] == 4
    assert emotional["ai_level"] == 2  # 띄어쓰기는 가리지 않는다
    assert neglect["ai_level"] is None  # 정보 부족(null)
    assert sexual["ai_level"] is None  # 항목 없음


def test_ai_level_is_null_without_severity_ratings(
    client: TestClient, counselor_headers, session: dict
) -> None:
    # mock AI 결과에는 severity_ratings 가 없다(옛 결과와 같은 모양).
    analyzed_session(client, counselor_headers, session["id"])

    response = _put(client, counselor_headers, session["id"], "PHYSICAL")

    assert response.status_code == 200
    assert response.json()["data"]["ai_level"] is None


@pytest.mark.parametrize("level", [0, 6, True, "3", 3.0, -1])
def test_ai_level_ignores_values_outside_one_to_five(
    client: TestClient, counselor_headers, session: dict, db, level
) -> None:
    analyzed_session(client, counselor_headers, session["id"])
    _set_severity_ratings(db, session["id"], [{"major_type": "신체학대", "level": level}])

    response = _put(client, counselor_headers, session["id"], "PHYSICAL")

    assert response.status_code == 200
    assert response.json()["data"]["ai_level"] is None


def test_ai_level_uses_first_item_of_the_same_type(
    client: TestClient, counselor_headers, session: dict, db
) -> None:
    analyzed_session(client, counselor_headers, session["id"])
    _set_severity_ratings(
        db,
        session["id"],
        [
            "깨진 항목",
            {"major_type": "모르는 유형", "level": 5},
            {"major_type": "PHYSICAL", "level": 3},
            {"major_type": "신체학대", "level": 5},
        ],
    )

    response = _put(client, counselor_headers, session["id"], "PHYSICAL")

    assert response.json()["data"]["ai_level"] == 3


def test_ai_level_is_null_when_latest_analysis_failed(
    client: TestClient, counselor_headers, session: dict, db
) -> None:
    analyzed_session(client, counselor_headers, session["id"])
    _set_severity_ratings(db, session["id"], [{"major_type": "신체학대", "level": 4}])

    # 다시 분석했는데 실패하면 화면에 AI 제안이 없다. 판단 당시 제안도 없음(null)으로 남긴다.
    set_ai_adapter_override(FailingAIAdapter())
    rerun = client.post(f"/api/v1/sessions/{session['id']}/analysis", headers=counselor_headers)
    assert rerun.status_code == 202

    response = _put(client, counselor_headers, session["id"], "PHYSICAL")

    assert response.status_code == 200
    assert response.json()["data"]["ai_level"] is None


def test_resave_refreshes_ai_level(
    client: TestClient, counselor_headers, session: dict, db
) -> None:
    analyzed_session(client, counselor_headers, session["id"])

    first = _put(client, counselor_headers, session["id"], "PHYSICAL").json()["data"]
    _set_severity_ratings(db, session["id"], [{"major_type": "신체학대", "level": 5}])
    second = _put(client, counselor_headers, session["id"], "PHYSICAL").json()["data"]

    assert first["ai_level"] is None
    assert second["ai_level"] == 5


# =========================================================
# 삭제 연쇄 · 감사 기록
# =========================================================

def test_deleting_session_deletes_assessments(
    client: TestClient, counselor_headers, ready_session: dict, db
) -> None:
    _put(client, counselor_headers, ready_session["id"], "PHYSICAL")
    _put(client, counselor_headers, ready_session["id"], "NEGLECT")

    response = client.delete(
        f"/api/v1/sessions/{ready_session['id']}", headers=counselor_headers
    )

    assert response.status_code == 204
    remaining = db.scalars(
        select(SessionRiskAssessment).where(
            SessionRiskAssessment.session_id == uuid.UUID(ready_session["id"])
        )
    ).all()
    assert remaining == []


def test_deleting_case_deletes_assessments(
    client: TestClient, counselor_headers, admin_headers, db
) -> None:
    case = create_case(client, counselor_headers)
    session = create_session(client, counselor_headers, case["id"])
    confirmed_session(client, counselor_headers, session["id"])
    _put(client, counselor_headers, session["id"], "PHYSICAL")

    # 사례 삭제는 관리자만 한다.
    response = client.delete(f"/api/v1/cases/{case['id']}", headers=admin_headers)

    assert response.status_code == 204
    assert db.scalars(select(SessionRiskAssessment)).all() == []


def test_save_and_update_are_audited_without_reason_text(
    client: TestClient, counselor_headers, counselor_id, session: dict, db
) -> None:
    analyzed_session(client, counselor_headers, session["id"])
    _set_severity_ratings(db, session["id"], [{"major_type": "신체학대", "level": 4}])

    created = _put(client, counselor_headers, session["id"], "PHYSICAL", reason=REASON)
    _put(
        client,
        counselor_headers,
        session["id"],
        "PHYSICAL",
        counselor_level="MEDIUM",
        reason=REASON + " (수정)",
    )

    logs = db.scalars(
        select(AuditLog)
        .where(
            AuditLog.action.in_(
                [AuditAction.RISK_ASSESSMENT_CREATED, AuditAction.RISK_ASSESSMENT_UPDATED]
            )
        )
        .order_by(AuditLog.created_at)
    ).all()

    assert [log.action for log in logs] == [
        AuditAction.RISK_ASSESSMENT_CREATED,
        AuditAction.RISK_ASSESSMENT_UPDATED,
    ]
    assert logs[0].detail == {
        "abuse_type": "PHYSICAL",
        "counselor_level": "HIGH",
        "ai_level": 4,
    }
    assert logs[1].detail == {
        "abuse_type": "PHYSICAL",
        "counselor_level": "MEDIUM",
        "ai_level": 4,
        "previous_level": "HIGH",
    }

    for log in logs:
        assert log.actor_id == counselor_id
        assert str(log.session_id) == session["id"]
        assert str(log.entity_id) == created.json()["data"]["id"]
        assert log.entity_type == "SessionRiskAssessment"

    # 판단 이유 원문은 감사 기록 어디에도 남지 않는다.
    every_detail = " ".join(str(log.detail) for log in db.scalars(select(AuditLog)).all())
    assert "가상 판단 이유" not in every_detail


# =========================================================
# 한글 유형명 대응
# =========================================================

@pytest.mark.parametrize(
    ("label", "expected"),
    [
        ("신체학대", AbuseType.PHYSICAL),
        ("정서학대", AbuseType.EMOTIONAL),
        ("성학대", AbuseType.SEXUAL),
        ("방임", AbuseType.NEGLECT),
        (" 신체 학대 ", AbuseType.PHYSICAL),
        ("NEGLECT", AbuseType.NEGLECT),
        ("emotional", AbuseType.EMOTIONAL),
        ("학대", None),
        ("", None),
        (None, None),
        (3, None),
    ],
)
def test_abuse_type_from_label(label, expected) -> None:
    assert abuse_type_from_label(label) == expected


def test_every_abuse_type_has_a_label_that_maps_back() -> None:
    for abuse_type in AbuseType:
        assert abuse_type_from_label(abuse_type_label(abuse_type)) == abuse_type


def test_concurrent_first_save_returns_conflict_instead_of_500(
    client: TestClient, counselor_headers, counselor_id, ready_session: dict, db
) -> None:
    """
    같은 유형을 두 요청이 동시에 처음 저장하면, 늦은 쪽은 "없음" 을 읽고 새 행을 넣다가
    유니크 제약에 걸린다. 그 경우 500 이 아니라 409 DUPLICATE_RESOURCE 여야 한다.
    """

    # 먼저 들어온 요청이 저장을 끝낸 상태
    assert _put(client, counselor_headers, ready_session["id"], "PHYSICAL").status_code == 200

    # 늦은 요청은 저장 전에 조회해 "없음" 을 본 것으로 만든다.
    real_scalar = db.scalar

    def stale_scalar(statement, *args, **kwargs):
        if "session_risk_assessments" in str(statement):
            return None

        return real_scalar(statement, *args, **kwargs)

    db.scalar = stale_scalar
    session_row = db.get(ConsultationSession, uuid.UUID(ready_session["id"]))
    user = db.get(User, counselor_id)

    with pytest.raises(APIError) as raised:
        risk_assessment_service.save_assessment(
            db,
            session_row,
            AbuseType.PHYSICAL,
            user,
            RiskAssessmentSaveRequest(counselor_level="LOW"),
        )

    assert raised.value.status_code == 409
    assert raised.value.code == "DUPLICATE_RESOURCE"

    # 먼저 저장한 판단은 그대로다.
    db.scalar = real_scalar
    listed = client.get(_url(ready_session["id"]), headers=counselor_headers).json()["data"]
    assert [item["counselor_level"] for item in listed] == ["HIGH"]


def test_there_is_no_delete(client: TestClient, counselor_headers, ready_session: dict) -> None:
    _put(client, counselor_headers, ready_session["id"], "PHYSICAL")

    response = client.delete(_url(ready_session["id"], "PHYSICAL"), headers=counselor_headers)

    assert response.status_code == 405
    assert response.json()["error"]["code"] == "METHOD_NOT_ALLOWED"


# =========================================================
# 저장할 수 없는 문자 · 로그 보호 (Codex PR #51 교차검증 높음)
# =========================================================

@pytest.mark.parametrize(
    "raw_reason",
    # JSON 본문에 그대로 넣는 이스케이프 글자다(r"" 라 파이썬 문자열에는 역슬래시가 그대로 있다).
    [
        r"가상_이유\u0000_후반",  # NUL — PostgreSQL text 에 넣으면 DataError(500)
        r"가상_이유\ud800_후반",  # 짝 없는 서로게이트 — UTF-8 로 바꿀 수 없음
    ],
)
def test_reason_with_unstorable_character_is_rejected(
    client: TestClient, counselor_headers, ready_session: dict, db, raw_reason: str
) -> None:
    url = _url(ready_session["id"], "PHYSICAL")
    headers = {**counselor_headers, "Content-Type": "application/json"}
    body = '{"counselor_level": "HIGH", "reason": "' + raw_reason + '"}'

    created = client.put(url, content=body.encode("utf-8"), headers=headers)

    assert created.status_code == 422, created.text
    assert created.json()["error"]["code"] == "VALIDATION_ERROR"
    assert "후반" not in created.text  # 응답에도 원문을 돌려주지 않는다

    # 이미 있는 판단을 고칠 때도 같고, 저장된 판단은 그대로다.
    assert _put(client, counselor_headers, ready_session["id"], "PHYSICAL", reason=REASON).status_code == 200
    updated = client.put(url, content=body.encode("utf-8"), headers=headers)

    assert updated.status_code == 422
    listed = client.get(_url(ready_session["id"]), headers=counselor_headers).json()["data"]
    assert [item["reason"] for item in listed] == [REASON]


def test_db_errors_do_not_carry_sql_parameters(
    client: TestClient, counselor_headers, counselor_id, ready_session: dict, db
) -> None:
    """
    DB 오류가 나면 공통 500 처리가 traceback 을 로그에 남긴다(main.py).
    SQLAlchemy 는 기본으로 SQL 파라미터(판단 이유 원문 등)를 오류 문자열에 넣으므로 숨겨야 한다.
    """

    assert _put(client, counselor_headers, ready_session["id"], "PHYSICAL").status_code == 200

    db.add(
        SessionRiskAssessment(
            session_id=uuid.UUID(ready_session["id"]),
            abuse_type=AbuseType.PHYSICAL,
            counselor_level="LOW",
            reason="가상_로그에_남으면_안_되는_이유",
            assessed_by_id=counselor_id,
            assessed_at=datetime.now(timezone.utc),
        )
    )

    with pytest.raises(IntegrityError) as raised:
        db.flush()

    db.rollback()
    assert "가상_로그에_남으면_안_되는_이유" not in str(raised.value)
