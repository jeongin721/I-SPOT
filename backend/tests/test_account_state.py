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

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.enums import AuditAction, UserRole
from app.core.errors import APIError
from app.core.security import hash_password
from app.models.audit_log import AuditLog
from app.models.user import User
from app.models.user_password_history import UserPasswordHistory
from app.services import user_service
from tests.conftest import ADMIN_PASSWORD, COUNSELOR_PASSWORD

COUNSELOR_EMAIL = "counselor.a@ispot.example.com"
ADMIN_EMAIL = "admin@ispot.example.com"
NEW_PASSWORD = "Violet-Ferry-62"
OTHER_PASSWORD = "Copper-Meadow-31"
WRONG_PASSWORD = "Wrong-Password-11"


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

def _lock(client: TestClient, email: str = COUNSELOR_EMAIL) -> None:
    for _ in range(settings.LOGIN_MAX_FAILURES):
        assert _login(client, email, WRONG_PASSWORD).status_code == 401


def _last_login_failure(db) -> AuditLog:
    return db.scalar(
        select(AuditLog)
        .where(AuditLog.action == AuditAction.LOGIN, AuditLog.status == "FAILURE")
        .order_by(AuditLog.created_at.desc())
    )


def _lock_logs(db, user_id: uuid.UUID):
    return db.scalars(
        select(AuditLog).where(
            AuditLog.action == AuditAction.ACCOUNT_LOCKED, AuditLog.entity_id == user_id
        )
    ).all()


def test_account_locks_after_five_failures(
    client: TestClient, counselor_id: uuid.UUID
) -> None:
    _lock(client)

    # 맞는 비밀번호로도 들어가지 못한다. 잠김은 알려주지 않는다(아래 테스트).
    locked = _login(client, COUNSELOR_EMAIL, COUNSELOR_PASSWORD)

    assert locked.status_code == 401
    assert locked.json()["error"]["code"] == "INVALID_CREDENTIALS"


def test_locked_account_does_not_reveal_correct_password(
    client: TestClient, counselor_id: uuid.UUID
) -> None:
    """잠긴 뒤에 맞는 비밀번호와 틀린 비밀번호의 응답이 같아야 계속 맞혀 볼 수 없다."""

    _lock(client)

    right = _login(client, COUNSELOR_EMAIL, COUNSELOR_PASSWORD)
    wrong = _login(client, COUNSELOR_EMAIL, WRONG_PASSWORD)
    unknown = _login(client, "nobody@ispot.example.com", COUNSELOR_PASSWORD)

    assert right.status_code == wrong.status_code == unknown.status_code == 401
    assert right.json() == wrong.json() == unknown.json()


def test_invalid_credentials_message_guides_locked_users(
    client: TestClient, counselor_id: uuid.UUID
) -> None:
    """잠긴 사람도 안내를 받아야 한다. 잠김 여부와 상관없이 같은 문구다."""

    message = _login(client, COUNSELOR_EMAIL, WRONG_PASSWORD).json()["error"]["message"]

    assert "관리자에게 문의" in message


def test_locked_login_attempt_is_recorded_as_account_locked(
    client: TestClient, counselor_id: uuid.UUID, db
) -> None:
    """응답은 같아도 관리자는 감사 로그로 구분할 수 있어야 한다."""

    _lock(client)
    _login(client, COUNSELOR_EMAIL, COUNSELOR_PASSWORD)

    log = _last_login_failure(db)

    assert log.actor_id == counselor_id
    assert log.error_code == "ACCOUNT_LOCKED"


def test_locked_account_attempts_do_not_count_as_failures(
    client: TestClient, counselor_id: uuid.UUID, db
) -> None:
    _lock(client)
    _login(client, COUNSELOR_EMAIL, WRONG_PASSWORD)
    _login(client, COUNSELOR_EMAIL, WRONG_PASSWORD)

    user = db.get(User, counselor_id)
    db.refresh(user)

    assert user.failed_login_count == settings.LOGIN_MAX_FAILURES
    assert len(_lock_logs(db, counselor_id)) == 1  # 잠금은 한 번만 남는다


def test_unknown_and_locked_accounts_still_run_bcrypt(
    client: TestClient, counselor_id: uuid.UUID, monkeypatch
) -> None:
    """bcrypt 비교를 건너뛰면 응답 시간으로 "없다 / 잠겼다" 가 드러난다."""

    compared = []
    original = user_service.verify_password

    def spy(password: str, hashed: str) -> bool:
        compared.append(hashed)
        return original(password, hashed)

    monkeypatch.setattr(user_service, "verify_password", spy)

    _login(client, "nobody@ispot.example.com", COUNSELOR_PASSWORD)

    assert compared == [user_service._dummy_password_hash()]

    _lock(client)
    compared.clear()
    _login(client, COUNSELOR_EMAIL, COUNSELOR_PASSWORD)

    # 잠긴 계정은 진짜 해시가 아니라 가짜 해시와 비교한다.
    assert compared == [user_service._dummy_password_hash()]


def test_failure_count_is_added_in_database(counselor_id: uuid.UUID, db) -> None:
    """
    동시에 틀린 요청이 들어와도 횟수가 빠지지 않아야 한다.

    예전 값(0)을 들고 있는 세션에서 실패해도, 그사이 다른 요청이 올린 값(3)에 더해야 한다.
    """

    stale = db.get(User, counselor_id)

    assert stale.failed_login_count == 0

    other = SessionLocal()

    try:
        other.get(User, counselor_id).failed_login_count = 3
        other.commit()
    finally:
        other.close()

    with pytest.raises(APIError):
        user_service.authenticate(db, COUNSELOR_EMAIL, WRONG_PASSWORD)

    db.refresh(stale)

    assert stale.failed_login_count == 4


def test_timed_lock_expires(
    client: TestClient, counselor_id: uuid.UUID, db, monkeypatch
) -> None:
    monkeypatch.setattr(settings, "LOGIN_LOCK_MINUTES", 10)

    _lock(client)

    assert _login(client, COUNSELOR_EMAIL, COUNSELOR_PASSWORD).status_code == 401

    _expire_lock(db, counselor_id)

    assert _login(client, COUNSELOR_EMAIL, COUNSELOR_PASSWORD).status_code == 200


def test_timed_lock_locks_again_after_expiry(
    client: TestClient, counselor_id: uuid.UUID, db, monkeypatch
) -> None:
    """잠금이 풀린 뒤 다시 5번 틀리면 다시 잠겨야 한다."""

    monkeypatch.setattr(settings, "LOGIN_LOCK_MINUTES", 10)

    _lock(client)
    _expire_lock(db, counselor_id)
    _lock(client)

    relocked = _login(client, COUNSELOR_EMAIL, COUNSELOR_PASSWORD)

    assert relocked.status_code == 401
    assert _last_login_failure(db).error_code == "ACCOUNT_LOCKED"
    assert len(_lock_logs(db, counselor_id)) == 2


def _expire_lock(db, user_id: uuid.UUID) -> None:
    """잠금 시간이 지난 것처럼 만든다."""

    user = db.get(User, user_id)
    db.refresh(user)

    assert user.locked_until is not None

    user.locked_until = datetime.now(timezone.utc) - timedelta(seconds=1)
    db.commit()


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


def _change_password(client: TestClient, email: str, current: str, new: str):
    headers = _headers(client, email, current)

    return client.post(
        "/api/v1/auth/me/password",
        json={"current_password": current, "new_password": new},
        headers=headers,
    )


def _history_count(db, user_id: uuid.UUID) -> int:
    return len(
        db.scalars(
            select(UserPasswordHistory).where(UserPasswordHistory.user_id == user_id)
        ).all()
    )


def test_password_before_dormancy_cannot_be_reused(
    client: TestClient, admin_headers, counselor_id: uuid.UUID, db
) -> None:
    """휴면 해제도 새 비밀번호를 발급한다. 휴면 전 비밀번호로 돌아갈 수 없어야 한다."""

    _age_last_login(db, counselor_id, settings.DORMANT_AFTER_DAYS + 1)
    _login(client, COUNSELOR_EMAIL, COUNSELOR_PASSWORD)  # 휴면 처리

    temporary = client.post(
        f"/api/v1/auth/users/{counselor_id}/reactivate", headers=admin_headers
    ).json()["data"]["temporary_password"]

    response = _change_password(client, COUNSELOR_EMAIL, temporary, COUNSELOR_PASSWORD)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "PASSWORD_REUSED"


def test_temporary_passwords_do_not_take_history_slots(
    client: TestClient, admin_headers, counselor_id: uuid.UUID, db
) -> None:
    """
    임시 비밀번호는 이력에 넣지 않는다.

    넣으면 재발급을 몇 번 하는 것만으로 진짜 이전 비밀번호가 보관 개수(3) 밖으로 밀려나
    다시 쓸 수 있게 된다.
    """

    assert _change_password(client, COUNSELOR_EMAIL, COUNSELOR_PASSWORD, NEW_PASSWORD).status_code == 204

    for _ in range(settings.PASSWORD_HISTORY_COUNT):
        temporary = client.post(
            f"/api/v1/auth/users/{counselor_id}/password-reset", headers=admin_headers
        ).json()["data"]["temporary_password"]

    # 처음 비밀번호와 첫 재발급 전 비밀번호만 남는다. 재발급 한 번에 한 줄이다.
    assert _history_count(db, counselor_id) == 2

    assert _change_password(client, COUNSELOR_EMAIL, temporary, OTHER_PASSWORD).status_code == 204

    # 임시 비밀번호에서 바꿀 때도 임시 비밀번호는 남기지 않는다.
    assert _history_count(db, counselor_id) == 2

    reused = _change_password(client, COUNSELOR_EMAIL, OTHER_PASSWORD, COUNSELOR_PASSWORD)

    assert reused.status_code == 422
    assert reused.json()["error"]["code"] == "PASSWORD_REUSED"


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


def _locked_second_admin(db) -> uuid.UUID:
    """로그인 실패로 잠긴 두 번째 관리자."""

    admin = User(
        email="admin.b@ispot.example.com",
        name="관리자B",
        role=UserRole.ADMIN,
        hashed_password=hash_password(ADMIN_PASSWORD),
        is_active=True,
        failed_login_count=settings.LOGIN_MAX_FAILURES,
    )
    db.add(admin)
    db.commit()

    return admin.id


def test_active_admin_count_excludes_locked_admins(admin_id: uuid.UUID, db) -> None:
    _locked_second_admin(db)

    assert user_service.active_admin_count(db) == 1


def test_last_usable_admin_is_protected_when_other_admin_is_locked(
    client: TestClient, admin_headers, admin_id: uuid.UUID, db
) -> None:
    """다른 관리자가 잠겨 있으면 나머지 한 명이 마지막 관리자다. 끄면 아무도 풀 수 없다."""

    _locked_second_admin(db)

    deactivate = client.patch(
        f"/api/v1/auth/users/{admin_id}", json={"is_active": False}, headers=admin_headers
    )

    assert deactivate.status_code == 409

    demote = client.patch(
        f"/api/v1/auth/users/{admin_id}", json={"role": "COUNSELOR"}, headers=admin_headers
    )

    assert demote.status_code == 409


def test_locked_admin_can_be_deactivated(
    client: TestClient, admin_headers, admin_id: uuid.UUID, db
) -> None:
    """잠긴 관리자를 끄는 것은 쓸 수 있는 관리자 수를 줄이지 않는다."""

    locked_id = _locked_second_admin(db)

    response = client.patch(
        f"/api/v1/auth/users/{locked_id}", json={"is_active": False}, headers=admin_headers
    )

    assert response.status_code == 200


def test_admin_is_not_made_dormant_when_other_admin_is_locked(
    client: TestClient, admin_id: uuid.UUID, db
) -> None:
    """잠긴 관리자는 휴면을 풀어 줄 수 없다. 남은 관리자를 휴면으로 만들면 아무도 못 들어온다."""

    _locked_second_admin(db)
    _age_last_login(db, admin_id, settings.DORMANT_AFTER_DAYS + 10)

    assert _login(client, ADMIN_EMAIL, ADMIN_PASSWORD).status_code == 200


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

    for field in (
        "is_active",
        "last_login_at",
        "must_change_password",
        "is_locked",
        "locked_until",
        "dormant_at",
    ):
        assert field in target

    assert "hashed_password" not in target


def _account(client: TestClient, admin_headers, user_id: uuid.UUID) -> dict:
    users = client.get("/api/v1/auth/users", headers=admin_headers).json()["data"]

    return next(user for user in users if user["id"] == str(user_id))


def test_user_response_shows_lock_with_default_settings(
    client: TestClient, admin_headers, counselor_id: uuid.UUID
) -> None:
    """기본 설정(LOGIN_LOCK_MINUTES=0)에서는 locked_until 이 비어 있어 is_locked 로만 보인다."""

    assert _account(client, admin_headers, counselor_id)["is_locked"] is False

    _lock(client)

    locked = _account(client, admin_headers, counselor_id)

    assert locked["is_locked"] is True
    assert locked["locked_until"] is None

    client.post(f"/api/v1/auth/users/{counselor_id}/unlock", headers=admin_headers)

    assert _account(client, admin_headers, counselor_id)["is_locked"] is False


def test_user_response_shows_expired_timed_lock_as_unlocked(
    client: TestClient, admin_headers, counselor_id: uuid.UUID, db, monkeypatch
) -> None:
    monkeypatch.setattr(settings, "LOGIN_LOCK_MINUTES", 10)

    _lock(client)

    assert _account(client, admin_headers, counselor_id)["is_locked"] is True

    _expire_lock(db, counselor_id)

    assert _account(client, admin_headers, counselor_id)["is_locked"] is False


def test_is_locked_at_uses_one_rule() -> None:
    """계정 응답과 로그인 판정이 같은 규칙을 쓴다(User.is_locked_at)."""

    now = datetime.now(timezone.utc)
    user = User(failed_login_count=settings.LOGIN_MAX_FAILURES - 1, locked_until=None)

    assert user.is_locked_at(now) is False
    assert user_service._is_locked(user, now) is False

    user.failed_login_count = settings.LOGIN_MAX_FAILURES

    assert user.is_locked_at(now) is True
    assert user_service._is_locked(user, now) is True

    # 시간 잠금은 시각으로 본다. SQLite 처럼 시간대 없이 읽힌 값도 UTC 로 본다.
    user.locked_until = (now + timedelta(minutes=1)).replace(tzinfo=None)

    assert user.is_locked_at(now) is True
    assert user.is_locked_at(now + timedelta(minutes=2)) is False
