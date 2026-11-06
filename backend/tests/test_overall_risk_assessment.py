# 회차 전체 상담원 위험도 판단 테스트 (app/services/risk_assessment_service.py 의 회차 전체 판단, API_CONTRACT 11.1절).
#
# 회차마다 상담원 판단(상/중/하) 하나를 저장하고, 판단할 때의 AI 제안(severity_ratings 의 유형별
# 1~5 가운데 가장 높은 값)을 ai_level 로 함께 남기는지 본다. 유형별 판단(test_risk_assessments.py)과
# 서로 영향을 주지 않는지도 본다. 데이터는 모두 가상이다.

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.adapters.ai_adapter import set_ai_adapter_override
from app.core.enums import AuditAction, SessionStatus
from app.core.errors import APIError
from app.models.analysis import AIAnalysis
from app.models.audit_log import AuditLog
from app.models.risk_assessment import SessionOverallRiskAssessment, SessionRiskAssessment
from app.models.session import ConsultationSession
from app.models.user import User
from app.schemas.risk_assessment import RiskAssessmentSaveRequest
from app.services import risk_assessment_service
from tests.conftest import create_case, create_session
from tests.test_analysis import FailingAIAdapter, analyzed_session, confirmed_session

REASON = "가상 판단 이유: 반복 진술과 흔적 언급이 있어 회차 전체를 상으로 판단"

RESPONSE_KEYS = {
    "id",
    "session_id",
    "counselor_level",
    "reason",
    "ai_level",
    "assessed_by_id",
    "assessed_at",
    "created_at",
    "updated_at",
}


def _url(session_id: str) -> str:
    return f"/api/v1/sessions/{session_id}/risk-assessment"


def _types_url(session_id: str, abuse_type: str = "") -> str:
    base = f"/api/v1/sessions/{session_id}/risk-assessments"

    return f"{base}/{abuse_type}" if abuse_type else base


def _get(client: TestClient, headers, session_id: str):
    return client.get(_url(session_id), headers=headers)


def _put(client: TestClient, headers, session_id: str, **body):
    payload: Dict[str, Any] = {"counselor_level": "HIGH"}
    payload.update(body)

    return client.put(_url(session_id), json=payload, headers=headers)


def _set_status(db, session_id: str, status: SessionStatus) -> None:
    row = db.get(ConsultationSession, uuid.UUID(session_id))
    row.status = status
    db.commit()


def _set_severity_ratings(db, session_id: str, ratings: List[Dict[str, Any]]) -> None:
    """최신 분석 결과에 severity_ratings 를 넣는다. mock AI 는 이 필드를 만들지 않으므로 저장된 결과를 직접 고친다."""

    analysis = db.scalar(
        select(AIAnalysis)
        .where(AIAnalysis.session_id == uuid.UUID(session_id))
        .order_by(AIAnalysis.created_at.desc())
        .limit(1)
    )
    analysis.result = {**analysis.result, "severity_ratings": ratings}
    db.commit()


def _rows(db, session_id: str) -> List[SessionOverallRiskAssessment]:
    return db.scalars(
        select(SessionOverallRiskAssessment).where(
            SessionOverallRiskAssessment.session_id == uuid.UUID(session_id)
        )
    ).all()


@pytest.fixture
def ready_session(client: TestClient, counselor_headers, session: dict) -> dict:
    """원문을 확정해 판단을 받을 수 있는 회차."""

    confirmed_session(client, counselor_headers, session["id"])

    return session


# =========================================================
# 저장 · 수정 · 조회
# =========================================================

def _as_utc(value: str) -> datetime:
    """응답의 ISO 시각을 비교할 수 있게 UTC datetime 으로(SQLite 는 tz 없이, PostgreSQL 은 tz 를 붙여 준다)."""

    parsed = datetime.fromisoformat(value)

    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)


def test_save_then_get(
    client: TestClient, counselor_headers, counselor_id, ready_session: dict, db
) -> None:
    before = datetime.now(timezone.utc) - timedelta(seconds=1)
    response = _put(client, counselor_headers, ready_session["id"], reason=REASON)
    after = datetime.now(timezone.utc) + timedelta(seconds=1)

    assert response.status_code == 200, response.text
    saved = response.json()["data"]
    assert set(saved) == RESPONSE_KEYS  # 유형별 응답과 달리 abuse_type 이 없다
    assert saved["session_id"] == ready_session["id"]
    assert saved["counselor_level"] == "HIGH"
    assert saved["reason"] == REASON
    assert saved["ai_level"] is None
    assert saved["assessed_by_id"] == str(counselor_id)
    # 저장한 시각은 요청 전후 사이다(값이 있다는 것만 보지 않는다).
    assert before <= _as_utc(saved["assessed_at"]) <= after

    fetched = _get(client, counselor_headers, ready_session["id"])

    assert fetched.status_code == 200
    assert fetched.json()["data"] == saved

    # ORM 관계(회차당 하나)도 같은 행을 가리킨다.
    session_row = db.get(ConsultationSession, uuid.UUID(ready_session["id"]))
    assert str(session_row.overall_risk_assessment.id) == saved["id"]


def test_get_is_null_before_any_assessment(
    client: TestClient, counselor_headers, session: dict
) -> None:
    response = _get(client, counselor_headers, session["id"])

    assert response.status_code == 200
    assert response.json() == {"data": None}


def test_save_again_updates_the_same_row(
    client: TestClient, counselor_headers, ready_session: dict, db
) -> None:
    first = _put(client, counselor_headers, ready_session["id"], reason=REASON)
    second = _put(client, counselor_headers, ready_session["id"], counselor_level="LOW")

    assert second.status_code == 200
    first_data = first.json()["data"]
    second_data = second.json()["data"]
    assert second_data["id"] == first_data["id"]
    assert second_data["counselor_level"] == "LOW"
    # 이유를 빼고 다시 저장하면 이유도 비운다(PUT 은 판단 전체를 바꾼다).
    assert second_data["reason"] is None
    assert _as_utc(second_data["assessed_at"]) >= _as_utc(first_data["assessed_at"])
    assert len(_rows(db, ready_session["id"])) == 1
    assert _get(client, counselor_headers, ready_session["id"]).json()["data"] == second_data


def test_blank_reason_is_saved_as_null(
    client: TestClient, counselor_headers, ready_session: dict
) -> None:
    response = _put(client, counselor_headers, ready_session["id"], reason="   ")

    assert response.status_code == 200
    assert response.json()["data"]["reason"] is None


def test_assessments_are_per_session(
    client: TestClient, counselor_headers, case: dict, ready_session: dict
) -> None:
    other = create_session(client, counselor_headers, case["id"])
    confirmed_session(client, counselor_headers, other["id"])

    assert _put(client, counselor_headers, ready_session["id"]).status_code == 200
    assert _get(client, counselor_headers, other["id"]).json()["data"] is None

    assert _put(client, counselor_headers, other["id"], counselor_level="LOW").status_code == 200

    first = _get(client, counselor_headers, ready_session["id"]).json()["data"]
    second = _get(client, counselor_headers, other["id"]).json()["data"]
    assert first["counselor_level"] == "HIGH" and first["session_id"] == ready_session["id"]
    assert second["counselor_level"] == "LOW" and second["session_id"] == other["id"]
    assert first["id"] != second["id"]


# =========================================================
# 권한
# =========================================================

def test_other_counselor_is_forbidden(
    client: TestClient, counselor_headers, other_counselor_headers, ready_session: dict
) -> None:
    _put(client, counselor_headers, ready_session["id"])

    fetched = _get(client, other_counselor_headers, ready_session["id"])
    saved = _put(client, other_counselor_headers, ready_session["id"])

    assert fetched.status_code == 403
    assert fetched.json()["error"]["code"] == "FORBIDDEN"
    assert saved.status_code == 403
    assert saved.json()["error"]["code"] == "FORBIDDEN"


def test_admin_can_get_and_save(
    client: TestClient, counselor_headers, admin_headers, admin_id, ready_session: dict
) -> None:
    _put(client, counselor_headers, ready_session["id"])

    fetched = _get(client, admin_headers, ready_session["id"])
    saved = _put(client, admin_headers, ready_session["id"], counselor_level="MEDIUM")

    assert fetched.status_code == 200
    assert fetched.json()["data"]["counselor_level"] == "HIGH"
    assert saved.status_code == 200
    assert saved.json()["data"]["counselor_level"] == "MEDIUM"
    assert saved.json()["data"]["assessed_by_id"] == str(admin_id)


def test_unknown_session_is_not_found(client: TestClient, counselor_headers) -> None:
    missing = str(uuid.uuid4())

    fetched = _get(client, counselor_headers, missing)
    saved = _put(client, counselor_headers, missing)

    assert fetched.status_code == 404
    assert fetched.json()["error"]["code"] == "SESSION_NOT_FOUND"
    assert saved.status_code == 404
    assert saved.json()["error"]["code"] == "SESSION_NOT_FOUND"


def test_login_is_required(client: TestClient, ready_session: dict) -> None:
    assert client.get(_url(ready_session["id"])).status_code == 401
    assert _put(client, {}, ready_session["id"]).status_code == 401


# =========================================================
# 입력 검증
# =========================================================

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
    response = _put(client, counselor_headers, ready_session["id"], **body)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert _get(client, counselor_headers, ready_session["id"]).json()["data"] is None


def test_missing_level_is_rejected(
    client: TestClient, counselor_headers, ready_session: dict
) -> None:
    response = client.put(_url(ready_session["id"]), json={"reason": REASON}, headers=counselor_headers)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_reason_at_max_length_is_accepted(
    client: TestClient, counselor_headers, ready_session: dict
) -> None:
    response = _put(client, counselor_headers, ready_session["id"], reason="가" * 1000)

    assert response.status_code == 200
    assert response.json()["data"]["reason"] == "가" * 1000


@pytest.mark.parametrize(
    "raw_reason",
    # JSON 본문에 그대로 넣는 이스케이프 글자다(r"" 라 파이썬 문자열에는 역슬래시가 그대로 있다).
    [
        r"가상_이유\u0000_후반",  # NUL — PostgreSQL text 에 넣으면 DataError(500)
        r"가상_이유\ud800_후반",  # 짝 없는 서로게이트 — UTF-8 로 바꿀 수 없음
    ],
)
def test_reason_with_unstorable_character_is_rejected(
    client: TestClient, counselor_headers, ready_session: dict, raw_reason: str
) -> None:
    url = _url(ready_session["id"])
    headers = {**counselor_headers, "Content-Type": "application/json"}
    body = '{"counselor_level": "HIGH", "reason": "' + raw_reason + '"}'

    created = client.put(url, content=body.encode("utf-8"), headers=headers)

    assert created.status_code == 422, created.text
    assert created.json()["error"]["code"] == "VALIDATION_ERROR"
    assert "후반" not in created.text  # 응답에도 원문을 돌려주지 않는다
    assert _get(client, counselor_headers, ready_session["id"]).json()["data"] is None

    # 이미 있는 판단을 고칠 때도 같고, 저장된 판단은 그대로다.
    assert _put(client, counselor_headers, ready_session["id"], reason=REASON).status_code == 200
    updated = client.put(url, content=body.encode("utf-8"), headers=headers)

    assert updated.status_code == 422
    assert _get(client, counselor_headers, ready_session["id"]).json()["data"]["reason"] == REASON


def test_ai_level_in_body_is_ignored(
    client: TestClient, counselor_headers, ready_session: dict
) -> None:
    response = _put(client, counselor_headers, ready_session["id"], ai_level=5)

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

    response = _put(client, counselor_headers, session["id"])

    assert response.status_code == 409
    error = response.json()["error"]
    assert error["code"] == "INVALID_SESSION_STATE"
    assert error["details"]["current_status"] == status.value
    assert _rows(db, session["id"]) == []
    # 조회는 상태와 관계없이 된다.
    fetched = _get(client, counselor_headers, session["id"])
    assert fetched.status_code == 200
    assert fetched.json()["data"] is None


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

    response = _put(client, counselor_headers, session["id"])

    assert response.status_code == 200, response.text
    # 판단을 저장해도 회차 상태는 바뀌지 않는다.
    db.expire_all()
    assert db.get(ConsultationSession, uuid.UUID(session["id"])).status == status


# =========================================================
# ai_level — 판단 당시 AI 제안(유형별 최고값)
# =========================================================

def test_ai_level_is_the_highest_type_level(
    client: TestClient, counselor_headers, session: dict, db
) -> None:
    analyzed_session(client, counselor_headers, session["id"])
    _set_severity_ratings(
        db,
        session["id"],
        [
            {"major_type": "신체학대", "level": 2, "reason": "가상", "segment_ids": []},
            {"major_type": "정서 학대", "level": 4},  # 띄어쓰기는 가리지 않는다
            {"major_type": "방임", "level": None},  # 정보 부족(null)은 값이 없는 것으로 본다
        ],
    )

    response = _put(client, counselor_headers, session["id"])

    assert response.status_code == 200
    assert response.json()["data"]["ai_level"] == 4


def test_ai_level_is_null_without_severity_ratings(
    client: TestClient, counselor_headers, session: dict
) -> None:
    # mock AI 결과에는 severity_ratings 가 없다(옛 결과와 같은 모양).
    analyzed_session(client, counselor_headers, session["id"])

    response = _put(client, counselor_headers, session["id"])

    assert response.status_code == 200
    assert response.json()["data"]["ai_level"] is None


def test_ai_level_is_null_when_severity_ratings_is_not_a_list(
    client: TestClient, counselor_headers, session: dict, db
) -> None:
    """목록이 아닌 severity_ratings(모양이 깨진 결과)는 읽지 않고 null 로 둔다."""

    analyzed_session(client, counselor_headers, session["id"])
    _set_severity_ratings(db, session["id"], {"신체학대": 5})  # type: ignore[arg-type]

    response = _put(client, counselor_headers, session["id"])

    assert response.status_code == 200
    assert response.json()["data"]["ai_level"] is None


@pytest.mark.parametrize("level", [0, 6, True, "3", 3.0, -1])
def test_ai_level_ignores_values_outside_one_to_five(
    client: TestClient, counselor_headers, session: dict, db, level
) -> None:
    analyzed_session(client, counselor_headers, session["id"])
    _set_severity_ratings(db, session["id"], [{"major_type": "신체학대", "level": level}])

    response = _put(client, counselor_headers, session["id"])

    assert response.status_code == 200
    assert response.json()["data"]["ai_level"] is None


def test_ai_level_skips_invalid_types_and_takes_the_highest_valid_one(
    client: TestClient, counselor_headers, session: dict, db
) -> None:
    """유효하지 않은 유형(범위 밖 · 문자열 · 모르는 유형 · 깨진 항목)은 빼고, 남은 유효한 값 중 가장 높은 값이다."""

    analyzed_session(client, counselor_headers, session["id"])
    _set_severity_ratings(
        db,
        session["id"],
        [
            "깨진 항목",
            {"major_type": "모르는 유형", "level": 5},
            {"major_type": "신체학대", "level": 7},  # 범위 밖 — 신체학대는 값 없음
            {"major_type": "성학대", "level": "5"},  # 문자열 — 성학대는 값 없음
            {"major_type": "정서학대", "level": 1},
            {"major_type": "NEGLECT", "level": 3},
        ],
    )

    response = _put(client, counselor_headers, session["id"])

    assert response.json()["data"]["ai_level"] == 3


def test_ai_level_uses_first_item_of_the_same_type(
    client: TestClient, counselor_headers, session: dict, db
) -> None:
    """같은 유형이 여럿이면 첫 항목이 정한다 — 둘째 항목의 더 높은 값은 쓰지 않는다."""

    analyzed_session(client, counselor_headers, session["id"])
    _set_severity_ratings(
        db,
        session["id"],
        [
            {"major_type": "PHYSICAL", "level": 3},
            {"major_type": "신체학대", "level": 5},  # 같은 유형 둘째 — 무시
            {"major_type": "정서학대", "level": None},
            {"major_type": "정서학대", "level": 4},  # 첫 항목이 정보 부족이면 그 유형은 값 없음
        ],
    )

    response = _put(client, counselor_headers, session["id"])

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

    response = _put(client, counselor_headers, session["id"])

    assert response.status_code == 200
    assert response.json()["data"]["ai_level"] is None


def test_resave_refreshes_ai_level_but_reanalysis_does_not(
    client: TestClient, counselor_headers, session: dict, db
) -> None:
    analyzed_session(client, counselor_headers, session["id"])

    first = _put(client, counselor_headers, session["id"]).json()["data"]
    _set_severity_ratings(db, session["id"], [{"major_type": "신체학대", "level": 5}])
    second = _put(client, counselor_headers, session["id"]).json()["data"]

    assert first["ai_level"] is None
    assert second["ai_level"] == 5

    # 저장한 뒤 다시 분석해도(mock 결과에는 severity_ratings 가 없다) 이미 저장한 값은 그대로다.
    rerun = client.post(f"/api/v1/sessions/{session['id']}/analysis", headers=counselor_headers)
    assert rerun.status_code == 202
    assert _get(client, counselor_headers, session["id"]).json()["data"]["ai_level"] == 5


# =========================================================
# 삭제 연쇄 · 감사 기록
# =========================================================

def test_deleting_session_deletes_assessment(
    client: TestClient, counselor_headers, ready_session: dict, db
) -> None:
    assert _put(client, counselor_headers, ready_session["id"]).status_code == 200

    response = client.delete(f"/api/v1/sessions/{ready_session['id']}", headers=counselor_headers)

    assert response.status_code == 204
    assert _rows(db, ready_session["id"]) == []


def test_deleting_case_deletes_assessment(
    client: TestClient, counselor_headers, admin_headers, db
) -> None:
    case = create_case(client, counselor_headers)
    session = create_session(client, counselor_headers, case["id"])
    confirmed_session(client, counselor_headers, session["id"])
    assert _put(client, counselor_headers, session["id"]).status_code == 200

    # 사례 삭제는 관리자만 한다.
    response = client.delete(f"/api/v1/cases/{case['id']}", headers=admin_headers)

    assert response.status_code == 204
    assert db.scalars(select(SessionOverallRiskAssessment)).all() == []


def test_save_and_update_are_audited_without_reason_text(
    client: TestClient, counselor_headers, counselor_id, session: dict, db
) -> None:
    analyzed_session(client, counselor_headers, session["id"])
    _set_severity_ratings(db, session["id"], [{"major_type": "신체학대", "level": 4}])

    created = _put(client, counselor_headers, session["id"], reason=REASON)
    _put(client, counselor_headers, session["id"], counselor_level="MEDIUM", reason=REASON + " (수정)")

    logs = db.scalars(
        select(AuditLog)
        .where(
            AuditLog.action.in_(
                [
                    AuditAction.OVERALL_RISK_ASSESSMENT_CREATED,
                    AuditAction.OVERALL_RISK_ASSESSMENT_UPDATED,
                ]
            )
        )
        .order_by(AuditLog.created_at)
    ).all()

    assert [log.action for log in logs] == [
        AuditAction.OVERALL_RISK_ASSESSMENT_CREATED,
        AuditAction.OVERALL_RISK_ASSESSMENT_UPDATED,
    ]
    assert logs[0].detail == {"counselor_level": "HIGH", "ai_level": 4}
    assert logs[1].detail == {"counselor_level": "MEDIUM", "ai_level": 4, "previous_level": "HIGH"}

    for log in logs:
        assert log.actor_id == counselor_id
        assert str(log.session_id) == session["id"]
        assert str(log.entity_id) == created.json()["data"]["id"]
        assert log.entity_type == "SessionOverallRiskAssessment"

    # 유형별 판단의 감사 기록은 남지 않는다.
    per_type_logs = db.scalars(
        select(AuditLog).where(
            AuditLog.action.in_(
                [AuditAction.RISK_ASSESSMENT_CREATED, AuditAction.RISK_ASSESSMENT_UPDATED]
            )
        )
    ).all()
    assert per_type_logs == []

    # 판단 이유 원문은 감사 기록 어디에도 남지 않는다.
    every_detail = " ".join(str(log.detail) for log in db.scalars(select(AuditLog)).all())
    assert "가상 판단 이유" not in every_detail


# =========================================================
# 동시 저장 · 지우기 없음
# =========================================================

def test_concurrent_first_save_returns_conflict_instead_of_500(
    client: TestClient, counselor_headers, counselor_id, ready_session: dict, db
) -> None:
    """
    같은 회차를 두 요청이 동시에 처음 저장하면, 늦은 쪽은 "없음" 을 읽고 새 행을 넣다가
    유니크 제약에 걸린다. 그 경우 500 이 아니라 409 DUPLICATE_RESOURCE 여야 한다.
    """

    # 먼저 들어온 요청이 저장을 끝낸 상태
    assert _put(client, counselor_headers, ready_session["id"]).status_code == 200

    # 늦은 요청은 저장 전에 조회해 "없음" 을 본 것으로 만든다 — 한 번만. 유니크 제약에 걸린 뒤의 재확인은 실제 행을 봐야
    # 409 가 된다(행이 없으면 다른 무결성 오류라 그대로 올린다).
    real_scalar = db.scalar
    stale = {"pending": True}

    def stale_scalar(statement, *args, **kwargs):
        if stale["pending"] and "session_overall_risk_assessments" in str(statement):
            stale["pending"] = False
            return None

        return real_scalar(statement, *args, **kwargs)

    db.scalar = stale_scalar
    session_row = db.get(ConsultationSession, uuid.UUID(ready_session["id"]))
    user = db.get(User, counselor_id)

    with pytest.raises(APIError) as raised:
        risk_assessment_service.save_overall_assessment(
            db, session_row, user, RiskAssessmentSaveRequest(counselor_level="LOW")
        )

    assert raised.value.status_code == 409
    assert raised.value.code == "DUPLICATE_RESOURCE"

    # 먼저 저장한 판단은 그대로다.
    db.scalar = real_scalar
    assert _get(client, counselor_headers, ready_session["id"]).json()["data"]["counselor_level"] == "HIGH"
    assert len(_rows(db, ready_session["id"])) == 1


def test_there_is_no_delete(client: TestClient, counselor_headers, ready_session: dict) -> None:
    _put(client, counselor_headers, ready_session["id"])

    response = client.delete(_url(ready_session["id"]), headers=counselor_headers)

    assert response.status_code == 405
    assert response.json()["error"]["code"] == "METHOD_NOT_ALLOWED"
    assert _get(client, counselor_headers, ready_session["id"]).json()["data"]["counselor_level"] == "HIGH"


# =========================================================
# 유형별 판단과 독립
# =========================================================

def test_overall_and_per_type_assessments_do_not_affect_each_other(
    client: TestClient, counselor_headers, ready_session: dict, db
) -> None:
    session_id = ready_session["id"]

    # 회차 전체 판단만 저장하면 유형별 목록은 비어 있다.
    assert _put(client, counselor_headers, session_id, counselor_level="HIGH").status_code == 200
    assert client.get(_types_url(session_id), headers=counselor_headers).json()["data"] == []

    # 유형별 판단을 저장해도 회차 전체 판단은 그대로다.
    per_type = client.put(
        _types_url(session_id, "PHYSICAL"), json={"counselor_level": "LOW"}, headers=counselor_headers
    )
    assert per_type.status_code == 200
    overall = _get(client, counselor_headers, session_id).json()["data"]
    assert overall["counselor_level"] == "HIGH"
    assert overall["id"] != per_type.json()["data"]["id"]

    listed = client.get(_types_url(session_id), headers=counselor_headers).json()["data"]
    assert [(item["abuse_type"], item["counselor_level"]) for item in listed] == [("PHYSICAL", "LOW")]

    # 표도 따로다.
    assert len(_rows(db, session_id)) == 1
    per_type_rows = db.scalars(
        select(SessionRiskAssessment).where(SessionRiskAssessment.session_id == uuid.UUID(session_id))
    ).all()
    assert len(per_type_rows) == 1


def test_per_type_assessment_alone_leaves_overall_null(
    client: TestClient, counselor_headers, ready_session: dict
) -> None:
    per_type = client.put(
        _types_url(ready_session["id"], "NEGLECT"),
        json={"counselor_level": "MEDIUM"},
        headers=counselor_headers,
    )

    assert per_type.status_code == 200
    assert _get(client, counselor_headers, ready_session["id"]).json() == {"data": None}
