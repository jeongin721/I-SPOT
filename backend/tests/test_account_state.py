# 계정 상태 관리 테스트.
#
# 임시 비밀번호 · 강제 변경 · 로그인 실패 잠금 · 휴면 · 강제 로그아웃 ·
# 계정 관리 창구 · 감사 로그 · 이전 비밀번호 재사용 금지.
#
# 팀 회의 결정(2026-09-18): 5회 실패 잠금은 관리자가 해제, 2개월 미접속은 휴면,
# 이전 비밀번호 재사용 금지.

import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import settings
from app.core.enums import AuditAction
from app.models.audit_log import AuditLog
from app.models.user import User
from app.models.user_password_history import UserPasswordHistory
from tests.conftest import ADMIN_PASSWORD, COUNSELOR_PASSWORD

COUNSELOR_EMAIL = "counselor.a@ispot.example.com"
ADMIN_EMAIL = "admin@ispot.example.com"
NEW_PASSWORD = "Violet-Ferry-62"
OTHER_PASSWORD = "Copper-Meadow-31"


def _login(client: TestClient, email: str, password: str):
    return client.post("/api/v1/auth/login", json={"email": email, "password": password})


def _headers(client: TestClient, email: str, password: str) -> Dict[str, str]:
    response = _login(client, email, password)

    assert response.status_code == 200, response.text

    return {"Authorization": f"Bearer {response.json()['data']['access_token']}"}


def _age_last_login(db, user_id: uuid.UUID, days: float) -> None:
    user = db.get(User, user_id)
    user.last_login_at = datetime.now(timezone.utc) - timedelta(days=days)
    db.commit()


# =========================================================
# 임시 비밀번호와 강제 변경
# =========================================================

def test_admin_can_reset_password_and_gets_temporary_one_once(
    client: TestClient, admin_headers, counselor_id: uuid.UUID, db
) -> None:
    response = client.post(
        f"/api/v1/auth/users/{counselor_id}/password-reset", headers=admin_headers
    )

    assert response.status_code == 200

    temporary = response.json()["data"]["temporary_password"]

    assert temporary

    user = db.get(User, counselor_id)
    db.refresh(user)

    assert user.must_change_password is True
    assert user.hashed_password != temporary  # 원문이 아니라 해시가 저장된다

    assert _login(client, COUNSELOR_EMAIL, temporary).status_code == 200


def test_counselor_cannot_reset_other_password(
    client: TestClient, counselor_headers, admin_id: uuid.UUID
) -> None:
    response = client.post(
        f"/api/v1/auth/users/{admin_id}/password-reset", headers=counselor_headers
    )

    assert response.status_code == 403


def test_temporary_password_blocks_everything_but_password_change(
    client: TestClient, admin_headers, counselor_id: uuid.UUID
) -> None:
    temporary = client.post(
        f"/api/v1/auth/users/{counselor_id}/password-reset", headers=admin_headers
    ).json()["data"]["temporary_password"]

    headers = _headers(client, COUNSELOR_EMAIL, temporary)

    blocked = client.get("/api/v1/cases", headers=headers)

    assert blocked.status_code == 403
    assert blocked.json()["error"]["code"] == "PASSWORD_CHANGE_REQUIRED"

    changed = client.post(
        "/api/v1/auth/me/password",
        json={"current_password": temporary, "new_password": NEW_PASSWORD},
        headers=headers,
    )

    assert changed.status_code == 204

    # 바꾸고 나면 막혔던 기능이 열린다
    reopened = _headers(client, COUNSELOR_EMAIL, NEW_PASSWORD)

    assert client.get("/api/v1/cases", headers=reopened).status_code == 200


# =========================================================
# 로그인 실패 잠금
# =========================================================

def test_account_locks_after_five_failures(
    client: TestClient, counselor_id: uuid.UUID
) -> None:
    for _ in range(settings.LOGIN_MAX_FAILURES):
        assert _login(client, COUNSELOR_EMAIL, "Wrong-Password-11").status_code == 401

    locked = _login(client, COUNSELOR_EMAIL, COUNSELOR_PASSWORD)

    assert locked.status_code == 403
    assert locked.json()["error"]["code"] == "ACCOUNT_LOCKED"


def test_successful_login_clears_failure_count(
    client: TestClient, counselor_id: uuid.UUID, db
) -> None:
    for _ in range(settings.LOGIN_MAX_FAILURES - 1):
        _login(client, COUNSELOR_EMAIL, "Wrong-Password-11")

    assert _login(client, COUNSELOR_EMAIL, COUNSELOR_PASSWORD).status_code == 200

    user = db.get(User, counselor_id)
    db.refresh(user)

    assert user.failed_login_count == 0


def test_admin_can_unlock_account(
    client: TestClient, admin_headers, counselor_id: uuid.UUID
) -> None:
    for _ in range(settings.LOGIN_MAX_FAILURES):
        _login(client, COUNSELOR_EMAIL, "Wrong-Password-11")

    unlocked = client.post(
        f"/api/v1/auth/users/{counselor_id}/unlock", headers=admin_headers
    )

    assert unlocked.status_code == 204
    assert _login(client, COUNSELOR_EMAIL, COUNSELOR_PASSWORD).status_code == 200


# =========================================================
# 휴면 계정
# =========================================================

def test_account_becomes_dormant_after_threshold(
    client: TestClient, counselor_id: uuid.UUID, db
) -> None:
    _age_last_login(db, counselor_id, settings.DORMANT_AFTER_DAYS + 1)

    response = _login(client, COUNSELOR_EMAIL, COUNSELOR_PASSWORD)

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "ACCOUNT_DORMANT"

    user = db.get(User, counselor_id)
    db.refresh(user)

    assert user.dormant_at is not None


def test_account_just_inside_threshold_still_logs_in(
    client: TestClient, counselor_id: uuid.UUID, db
) -> None:
    _age_last_login(db, counselor_id, settings.DORMANT_AFTER_DAYS - 1)

    assert _login(client, COUNSELOR_EMAIL, COUNSELOR_PASSWORD).status_code == 200


def test_never_logged_in_account_uses_created_at(
    client: TestClient, counselor_id: uuid.UUID, db
) -> None:
    user = db.get(User, counselor_id)
    user.last_login_at = None
    user.created_at = datetime.now(timezone.utc) - timedelta(
        days=settings.DORMANT_AFTER_DAYS + 1
    )
    db.commit()

    response = _login(client, COUNSELOR_EMAIL, COUNSELOR_PASSWORD)

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "ACCOUNT_DORMANT"


def test_last_active_admin_is_not_made_dormant(
    client: TestClient, admin_id: uuid.UUID, db
) -> None:
    """관리자가 전부 휴면이 되면 아무도 풀 수 없다."""

    _age_last_login(db, admin_id, settings.DORMANT_AFTER_DAYS + 10)

    assert _login(client, ADMIN_EMAIL, ADMIN_PASSWORD).status_code == 200


def test_admin_can_reactivate_dormant_account(
    client: TestClient, admin_headers, counselor_id: uuid.UUID, db
) -> None:
    _age_last_login(db, counselor_id, settings.DORMANT_AFTER_DAYS + 1)
    _login(client, COUNSELOR_EMAIL, COUNSELOR_PASSWORD)  # 휴면 처리 발생

    response = client.post(
        f"/api/v1/auth/users/{counselor_id}/reactivate", headers=admin_headers
    )

    assert response.status_code == 200

    temporary = response.json()["data"]["temporary_password"]

    assert _login(client, COUNSELOR_EMAIL, temporary).status_code == 200


def test_reactivated_old_account_does_not_go_dormant_again(
    client: TestClient, admin_headers, counselor_id: uuid.UUID, db
) -> None:
    """오래 전에 만든 계정이라도 휴면을 풀면 바로 다시 잠기면 안 된다."""

    user = db.get(User, counselor_id)
    user.created_at = datetime.now(timezone.utc) - timedelta(days=365)
    db.commit()

    _age_last_login(db, counselor_id, settings.DORMANT_AFTER_DAYS + 1)
    _login(client, COUNSELOR_EMAIL, COUNSELOR_PASSWORD)  # 휴면 처리

    temporary = client.post(
        f"/api/v1/auth/users/{counselor_id}/reactivate", headers=admin_headers
    ).json()["data"]["temporary_password"]

    first = _login(client, COUNSELOR_EMAIL, temporary)

    assert first.status_code == 200

    # 두 번째 로그인에서도 휴면으로 되돌아가지 않아야 한다.
    second = _login(client, COUNSELOR_EMAIL, temporary)

    assert second.status_code == 200


def test_password_before_admin_reset_cannot_be_reused(
    client: TestClient, admin_headers, counselor_id: uuid.UUID
) -> None:
    """관리자가 초기화해도 초기화 전 비밀번호는 재사용할 수 없어야 한다."""

    temporary = client.post(
        f"/api/v1/auth/users/{counselor_id}/password-reset", headers=admin_headers
    ).json()["data"]["temporary_password"]

    headers = _headers(client, COUNSELOR_EMAIL, temporary)

    response = client.post(
        "/api/v1/auth/me/password",
        json={"current_password": temporary, "new_password": COUNSELOR_PASSWORD},
        headers=headers,
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "PASSWORD_REUSED"


# =========================================================
# 강제 로그아웃
# =========================================================

def test_admin_logout_all_invalidates_existing_token(
    client: TestClient, admin_headers, counselor_headers, counselor_id: uuid.UUID
) -> None:
    assert client.get("/api/v1/auth/me", headers=counselor_headers).status_code == 200

    client.post(f"/api/v1/auth/users/{counselor_id}/logout-all", headers=admin_headers)

    assert client.get("/api/v1/auth/me", headers=counselor_headers).status_code == 401


def test_password_change_invalidates_existing_token(
    client: TestClient, counselor_headers
) -> None:
    client.post(
        "/api/v1/auth/me/password",
        json={"current_password": COUNSELOR_PASSWORD, "new_password": NEW_PASSWORD},
        headers=counselor_headers,
    )

    assert client.get("/api/v1/auth/me", headers=counselor_headers).status_code == 401
    assert _login(client, COUNSELOR_EMAIL, NEW_PASSWORD).status_code == 200


# =========================================================
# 계정 관리 창구
# =========================================================

def test_admin_can_deactivate_account(
    client: TestClient, admin_headers, counselor_headers, counselor_id: uuid.UUID
) -> None:
    response = client.patch(
        f"/api/v1/auth/users/{counselor_id}",
        json={"is_active": False},
        headers=admin_headers,
    )

    assert response.status_code == 200
    assert response.json()["data"]["is_active"] is False

    blocked = client.get("/api/v1/auth/me", headers=counselor_headers)

    assert blocked.status_code == 403
    assert blocked.json()["error"]["code"] == "INACTIVE_USER"


def test_admin_can_change_role(
    client: TestClient, admin_headers, counselor_id: uuid.UUID
) -> None:
    response = client.patch(
        f"/api/v1/auth/users/{counselor_id}",
        json={"role": "ADMIN"},
        headers=admin_headers,
    )

    assert response.status_code == 200
    assert response.json()["data"]["role"] == "ADMIN"

    # 권한이 실제로 바뀐다
    headers = _headers(client, COUNSELOR_EMAIL, COUNSELOR_PASSWORD)

    assert client.get("/api/v1/auth/users", headers=headers).status_code == 200


def test_last_active_admin_cannot_be_deactivated_or_demoted(
    client: TestClient, admin_headers, admin_id: uuid.UUID
) -> None:
    deactivate = client.patch(
        f"/api/v1/auth/users/{admin_id}", json={"is_active": False}, headers=admin_headers
    )

    assert deactivate.status_code == 409

    demote = client.patch(
        f"/api/v1/auth/users/{admin_id}", json={"role": "COUNSELOR"}, headers=admin_headers
    )

    assert demote.status_code == 409


def test_counselor_cannot_use_account_endpoints(
    client: TestClient, counselor_headers, admin_id: uuid.UUID
) -> None:
    assert (
        client.patch(
            f"/api/v1/auth/users/{admin_id}",
            json={"is_active": False},
            headers=counselor_headers,
        ).status_code
        == 403
    )
    assert client.get("/api/v1/auth/audit-logs", headers=counselor_headers).status_code == 403


# =========================================================
# 감사 로그
# =========================================================

def test_successful_login_is_recorded_with_client_info(
    client: TestClient, counselor_id: uuid.UUID, db
) -> None:
    _login(client, COUNSELOR_EMAIL, COUNSELOR_PASSWORD)

    log = db.scalar(
        select(AuditLog)
        .where(AuditLog.action == AuditAction.LOGIN)
        .order_by(AuditLog.created_at.desc())
    )

    assert log is not None
    assert log.status == "SUCCESS"
    assert log.actor_id == counselor_id
    assert log.ip_address
    assert log.user_agent


def test_failed_login_is_recorded_without_email(
    client: TestClient, counselor_id: uuid.UUID, db
) -> None:
    _login(client, COUNSELOR_EMAIL, "Wrong-Password-11")

    log = db.scalar(
        select(AuditLog).where(AuditLog.status == "FAILURE").order_by(AuditLog.created_at.desc())
    )

    assert log is not None
    assert log.action == AuditAction.LOGIN
    assert log.error_code == "INVALID_CREDENTIALS"
    assert COUNSELOR_EMAIL not in str(log.detail)


def test_unknown_account_failure_has_no_actor(client: TestClient, db) -> None:
    _login(client, "nobody@ispot.example.com", "Wrong-Password-11")

    log = db.scalar(
        select(AuditLog).where(AuditLog.status == "FAILURE").order_by(AuditLog.created_at.desc())
    )

    assert log is not None
    assert log.actor_id is None
    assert "nobody@ispot.example.com" not in str(log.detail)


def test_admin_can_read_audit_logs_with_filters(
    client: TestClient, admin_headers, counselor_id: uuid.UUID
) -> None:
    _login(client, COUNSELOR_EMAIL, COUNSELOR_PASSWORD)
    _login(client, COUNSELOR_EMAIL, "Wrong-Password-11")

    response = client.get("/api/v1/auth/audit-logs", headers=admin_headers)

    assert response.status_code == 200

    body = response.json()["data"]

    assert body["items"]
    assert body["meta"]["total"] >= 2

    failures = client.get(
        "/api/v1/auth/audit-logs", params={"status": "FAILURE"}, headers=admin_headers
    ).json()["data"]["items"]

    assert failures
    assert all(item["status"] == "FAILURE" for item in failures)

    by_action = client.get(
        "/api/v1/auth/audit-logs", params={"action": "LOGIN"}, headers=admin_headers
    ).json()["data"]["items"]

    assert all(item["action"] == "LOGIN" for item in by_action)


# =========================================================
# 이전 비밀번호 재사용 금지
# =========================================================

def test_previous_password_cannot_be_reused(
    client: TestClient, counselor_headers
) -> None:
    first = client.post(
        "/api/v1/auth/me/password",
        json={"current_password": COUNSELOR_PASSWORD, "new_password": NEW_PASSWORD},
        headers=counselor_headers,
    )

    assert first.status_code == 204

    headers = _headers(client, COUNSELOR_EMAIL, NEW_PASSWORD)

    reused = client.post(
        "/api/v1/auth/me/password",
        json={"current_password": NEW_PASSWORD, "new_password": COUNSELOR_PASSWORD},
        headers=headers,
    )

    assert reused.status_code == 422
    assert reused.json()["error"]["code"] == "PASSWORD_REUSED"


def test_password_history_is_trimmed(
    client: TestClient, counselor_headers, counselor_id: uuid.UUID, db
) -> None:
    passwords = [NEW_PASSWORD, OTHER_PASSWORD, "Amber-Tunnel-58", "Silver-Pillow-24"]
    current = COUNSELOR_PASSWORD
    headers = counselor_headers

    for password in passwords:
        assert (
            client.post(
                "/api/v1/auth/me/password",
                json={"current_password": current, "new_password": password},
                headers=headers,
            ).status_code
            == 204
        )
        current = password
        headers = _headers(client, COUNSELOR_EMAIL, password)

    rows = db.scalars(
        select(UserPasswordHistory).where(UserPasswordHistory.user_id == counselor_id)
    ).all()

    assert len(rows) <= settings.PASSWORD_HISTORY_COUNT


# =========================================================
# 판정 순서
# =========================================================

def test_account_state_is_not_revealed_before_password_check(
    client: TestClient, counselor_id: uuid.UUID, db
) -> None:
    """휴면 계정이라도 비밀번호가 틀리면 계정 상태를 알려주지 않는다."""

    _age_last_login(db, counselor_id, settings.DORMANT_AFTER_DAYS + 1)

    response = _login(client, COUNSELOR_EMAIL, "Wrong-Password-11")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_CREDENTIALS"


def test_user_response_exposes_account_state(
    client: TestClient, admin_headers, counselor_id: uuid.UUID
) -> None:
    """관리자 화면이 "왜 로그인이 안 되는지" 를 구분해 보여줄 수 있어야 한다."""

    users = client.get("/api/v1/auth/users", headers=admin_headers).json()["data"]
    target = next(user for user in users if user["id"] == str(counselor_id))

    for field in ("is_active", "last_login_at", "must_change_password", "locked_until", "dormant_at"):
        assert field in target

    assert "hashed_password" not in target
