# 계정 복구 script(scripts/unlock_user.py) 테스트.
#
# 관리자가 한 명뿐일 때 그 계정이 잠기거나 휴면이 되면 관리자 화면으로는 풀 수 없다.
# 서버에서 이 script 로 풀 수 있어야 한다.

import sys
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import settings
from app.core.enums import AuditAction
from app.models.audit_log import AuditLog
from app.models.base import as_utc
from app.models.user import User
from app.models.user_password_history import UserPasswordHistory
from scripts import unlock_user
from tests.conftest import ADMIN_PASSWORD

ADMIN_EMAIL = "admin@ispot.example.com"
WRONG_PASSWORD = "Wrong-Password-11"
NEW_PASSWORD = "Violet-Ferry-62"


def _login(client: TestClient, password: str = ADMIN_PASSWORD):
    return client.post(
        "/api/v1/auth/login", json={"email": ADMIN_EMAIL, "password": password}
    )


def _lock_admin(client: TestClient) -> None:
    for _ in range(settings.LOGIN_MAX_FAILURES):
        _login(client, WRONG_PASSWORD)

    assert _login(client).status_code == 401


def _logs(db, action: AuditAction):
    return db.scalars(select(AuditLog).where(AuditLog.action == action)).all()


def _reload(db, user_id: uuid.UUID) -> User:
    user = db.get(User, user_id)
    db.refresh(user)

    return user


def test_unlocks_the_only_admin(client: TestClient, admin_id: uuid.UUID, db) -> None:
    _lock_admin(client)

    result = unlock_user.recover_user(db, ADMIN_EMAIL)

    assert result.done == ["실패 잠금 해제"]
    assert _reload(db, admin_id).failed_login_count == 0
    assert _login(client).status_code == 200

    logs = _logs(db, AuditAction.ACCOUNT_UNLOCKED)

    assert len(logs) == 1
    assert logs[0].actor_id is None  # 서버에서 한 일이라 행동한 사람이 없다
    assert logs[0].entity_id == admin_id
    assert logs[0].detail == {"via": "unlock_user script"}


def test_clears_timed_lock(
    client: TestClient, admin_id: uuid.UUID, db, monkeypatch
) -> None:
    monkeypatch.setattr(settings, "LOGIN_LOCK_MINUTES", 60)

    _lock_admin(client)

    assert _reload(db, admin_id).locked_until is not None

    unlock_user.recover_user(db, ADMIN_EMAIL)

    assert _reload(db, admin_id).locked_until is None
    assert _login(client).status_code == 200


def test_reactivates_dormant_account(client: TestClient, admin_id: uuid.UUID, db) -> None:
    user = db.get(User, admin_id)
    user.dormant_at = datetime.now(timezone.utc) - timedelta(days=1)
    user.last_login_at = datetime.now(timezone.utc) - timedelta(days=365)
    db.commit()

    result = unlock_user.recover_user(db, ADMIN_EMAIL)

    assert "휴면 해제" in result.done
    assert result.notices  # 비밀번호는 그대로라는 안내

    user = _reload(db, admin_id)

    assert user.dormant_at is None
    # 휴면 해제를 활동으로 본다. 안 그러면 다음 로그인에 다시 휴면이 된다.
    assert datetime.now(timezone.utc) - as_utc(user.last_login_at) < timedelta(minutes=1)
    assert len(_logs(db, AuditAction.ACCOUNT_REACTIVATED)) == 1
    assert _login(client).status_code == 200


def test_inactive_account_is_activated_only_with_flag(
    client: TestClient, admin_id: uuid.UUID, db
) -> None:
    user = db.get(User, admin_id)
    user.is_active = False
    db.commit()

    result = unlock_user.recover_user(db, ADMIN_EMAIL)

    assert _reload(db, admin_id).is_active is False
    assert any("--activate" in notice for notice in result.notices)
    assert _logs(db, AuditAction.USER_UPDATED) == []

    result = unlock_user.recover_user(db, ADMIN_EMAIL, activate=True)

    assert "활성화" in result.done
    assert _reload(db, admin_id).is_active is True
    assert _logs(db, AuditAction.USER_UPDATED)[0].detail == {
        "via": "unlock_user script",
        "changed_fields": ["is_active"],
    }
    assert _login(client).status_code == 200


def test_reset_password_issues_temporary_password(
    client: TestClient, admin_id: uuid.UUID, db
) -> None:
    _lock_admin(client)

    result = unlock_user.recover_user(db, ADMIN_EMAIL, reset_password=True)

    assert result.temporary_password

    user = _reload(db, admin_id)

    assert user.must_change_password is True
    assert user.failed_login_count == 0
    assert len(_logs(db, AuditAction.PASSWORD_RESET)) == 1

    # 이전 비밀번호는 이력에 남는다(관리자 화면의 재발급과 같은 규칙).
    assert len(
        db.scalars(
            select(UserPasswordHistory).where(UserPasswordHistory.user_id == admin_id)
        ).all()
    ) == 1

    login = _login(client, result.temporary_password)

    assert login.status_code == 200

    headers = {"Authorization": f"Bearer {login.json()['data']['access_token']}"}
    reused = client.post(
        "/api/v1/auth/me/password",
        json={"current_password": result.temporary_password, "new_password": ADMIN_PASSWORD},
        headers=headers,
    )

    assert reused.json()["error"]["code"] == "PASSWORD_REUSED"


def test_unknown_email_is_rejected(db) -> None:
    with pytest.raises(unlock_user.RecoveryError):
        unlock_user.recover_user(db, "nobody@ispot.example.com")


def test_anonymized_account_is_not_recovered(admin_id: uuid.UUID, db) -> None:
    user = db.get(User, admin_id)
    user.anonymized_at = datetime.now(timezone.utc)
    user.failed_login_count = settings.LOGIN_MAX_FAILURES
    db.commit()

    with pytest.raises(unlock_user.RecoveryError):
        unlock_user.recover_user(db, ADMIN_EMAIL)

    assert _reload(db, admin_id).failed_login_count == settings.LOGIN_MAX_FAILURES
    assert _logs(db, AuditAction.ACCOUNT_UNLOCKED) == []


def _run(monkeypatch, *args: str) -> int:
    monkeypatch.setattr(sys, "argv", ["unlock_user", *args])

    return unlock_user.main()


def test_main_prints_temporary_password_once(
    client: TestClient, admin_id: uuid.UUID, monkeypatch, capsys
) -> None:
    _lock_admin(client)

    code = _run(monkeypatch, "--email", ADMIN_EMAIL, "--reset-password")

    assert code == 0

    output = capsys.readouterr().out
    temporary = output.split("임시 비밀번호: ")[1].split()[0]

    assert output.count(temporary) == 1
    assert "복구 완료: admin@ispot.example.com (role=ADMIN)" in output
    assert "PASSWORD_CHANGE_REQUIRED" in output  # 바꾸기 전에는 다른 요청이 막힌다는 안내
    assert _login(client, temporary).status_code == 200


def test_main_returns_1_for_unknown_email(monkeypatch, capsys) -> None:
    code = _run(monkeypatch, "--email", "nobody@ispot.example.com")

    assert code == 1
    assert "계정을 찾을 수 없습니다" in capsys.readouterr().err
