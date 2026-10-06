# 초기 계정 생성 script(scripts/seed_users.py) 테스트.
#
# 사람이 직접 준 비밀번호(--password, SEED_USER_PASSWORD)도 API 와 같은 비밀번호 규칙을 거쳐야 한다.
# 안 거치면 script 로 만든 첫 관리자 계정만 규칙 밖에 남는다.

import sys
from typing import List, Tuple

import pytest
from sqlalchemy import select

from app.core.enums import AuditAction, UserRole
from app.core.security import verify_password
from app.models.audit_log import AuditLog
from app.models.user import User
from scripts import seed_users

STRONG_PASSWORD = "Violet-Ferry-62"
WEAK_PASSWORD = "ispot-demo-1234"


@pytest.fixture
def created(monkeypatch) -> List[Tuple[str, str, UserRole, str]]:
    """DB 에 쓰는 대신 upsert_user 호출만 기록한다."""

    calls: List[Tuple[str, str, UserRole, str]] = []

    def fake_upsert(email: str, name: str, role: UserRole, password: str) -> Tuple[str, bool]:
        calls.append((email, name, role, password))
        return f"생성 완료: {email}", True

    monkeypatch.setattr(seed_users, "upsert_user", fake_upsert)
    monkeypatch.delenv("SEED_USER_PASSWORD", raising=False)

    return calls


def _run(monkeypatch, *args: str) -> int:
    monkeypatch.setattr(sys, "argv", ["seed_users", *args])

    return seed_users.main()


def test_weak_password_argument_is_rejected(monkeypatch, capsys, created) -> None:
    code = _run(
        monkeypatch,
        "--email", "admin@example.com", "--name", "관리자", "--role", "ADMIN",
        "--password", WEAK_PASSWORD,
    )

    assert code == 1
    assert created == []  # 계정을 만들지 않는다

    output = capsys.readouterr()

    assert "쉽게 짐작할 수 있는 단어" in output.err  # 사유를 보여준다
    assert WEAK_PASSWORD not in output.out + output.err  # 원문은 출력하지 않는다


def test_weak_password_from_environment_is_rejected(monkeypatch, capsys, created) -> None:
    monkeypatch.setenv("SEED_USER_PASSWORD", WEAK_PASSWORD)

    code = _run(monkeypatch, "--demo")

    assert code == 1
    assert created == []


def test_password_containing_demo_account_email_id_is_rejected(
    monkeypatch, capsys, created
) -> None:
    """--demo 는 계정 여러 개에 같은 비밀번호를 쓴다. 어느 계정 기준으로든 걸리면 거부한다."""

    code = _run(monkeypatch, "--demo", "--password", "Counselor-77x!")

    assert code == 1
    assert created == []


def test_compliant_password_argument_creates_account(monkeypatch, created) -> None:
    code = _run(
        monkeypatch,
        "--email", "admin@example.com", "--name", "관리자", "--role", "ADMIN",
        "--password", STRONG_PASSWORD,
    )

    assert code == 0
    assert created == [("admin@example.com", "관리자", UserRole.ADMIN, STRONG_PASSWORD)]


def test_compliant_password_from_environment_creates_demo_accounts(
    monkeypatch, created
) -> None:
    monkeypatch.setenv("SEED_USER_PASSWORD", STRONG_PASSWORD)

    code = _run(monkeypatch, "--demo")

    assert code == 0
    assert [call[0] for call in created] == [email for email, _, _ in seed_users.DEMO_ACCOUNTS]


def test_generated_password_is_used_without_extra_check(monkeypatch, created) -> None:
    code = _run(monkeypatch, "--email", "admin@example.com", "--name", "관리자")

    assert code == 0
    assert len(created) == 1


def test_seeded_user_is_recorded_without_actor(db) -> None:
    """서버에서 직접 만든 계정도 감사 로그(USER_CREATED)에 남는다. 행동한 사람은 없다."""

    seed_users.upsert_user("seed.admin@example.com", "관리자", UserRole.ADMIN, STRONG_PASSWORD)

    user = db.scalar(select(User).where(User.email == "seed.admin@example.com"))
    log = db.scalar(select(AuditLog).where(AuditLog.action == AuditAction.USER_CREATED))

    assert log is not None
    assert log.actor_id is None
    assert log.entity_id == user.id
    assert log.detail == {"role": "ADMIN", "via": "seed_users script"}

    # 이미 있는 계정이면 만들지 않으므로 기록도 늘지 않는다.
    seed_users.upsert_user("seed.admin@example.com", "관리자", UserRole.ADMIN, STRONG_PASSWORD)

    assert len(db.scalars(select(AuditLog)).all()) == 1


# =========================================================
# 이미 있는 계정으로 다시 돌릴 때
# =========================================================
#
# 이미 있는 계정은 비밀번호를 바꾸지 않는다. 그런데 새로 만든 비밀번호를 출력하면 사람은 그 값으로
# 로그인하다 틀리고, 5번 틀리면 계정이 잠긴다. 계정을 새로 만들 때만 비밀번호를 알려 준다.

ANOTHER_STRONG_PASSWORD = "Amber-Canyon-35"


def _stored_password_matches(db, email: str, password: str) -> bool:
    db.expire_all()
    user = db.scalar(select(User).where(User.email == email))

    return verify_password(password, user.hashed_password)


def _generated(monkeypatch, *values: str) -> None:
    pending = iter(values)

    monkeypatch.setattr(seed_users, "generate_password", lambda: next(pending))


def test_rerunning_demo_keeps_existing_passwords_and_prints_none(
    db, monkeypatch, capsys
) -> None:
    monkeypatch.delenv("SEED_USER_PASSWORD", raising=False)
    _generated(monkeypatch, "Gen-First-Pass-11", "Gen-Second-Pass-22")

    assert _run(monkeypatch, "--demo") == 0
    assert "생성된 공용 데모 비밀번호: Gen-First-Pass-11" in capsys.readouterr().out

    assert _run(monkeypatch, "--demo") == 0

    second = capsys.readouterr().out

    assert "Gen-Second-Pass-22" not in second  # 쓸 수 없는 새 값을 알려 주지 않는다
    assert "생성된" not in second
    assert "이미 있는 계정의 비밀번호는 바뀌지 않았습니다." in second
    assert "unlock_user" in second  # 모를 때 푸는 방법을 알려 준다
    assert "먼저 새 비밀번호로 바꿔야" in second  # 임시 비밀번호로는 seed_demo_data 가 403 이다

    for email, _, _ in seed_users.DEMO_ACCOUNTS:
        assert _stored_password_matches(db, email, "Gen-First-Pass-11")


def test_given_password_is_not_applied_to_existing_demo_accounts(
    db, monkeypatch, capsys
) -> None:
    """SEED_USER_PASSWORD 를 바꿔 다시 돌려도 이미 있는 계정의 비밀번호는 그대로다. 그렇다고 알려 준다."""

    monkeypatch.setenv("SEED_USER_PASSWORD", STRONG_PASSWORD)

    assert _run(monkeypatch, "--demo") == 0

    capsys.readouterr()
    monkeypatch.setenv("SEED_USER_PASSWORD", ANOTHER_STRONG_PASSWORD)

    assert _run(monkeypatch, "--demo") == 0

    output = capsys.readouterr().out

    assert "이미 있는 계정의 비밀번호는 바뀌지 않았습니다." in output
    assert ANOTHER_STRONG_PASSWORD not in output

    for email, _, _ in seed_users.DEMO_ACCOUNTS:
        assert _stored_password_matches(db, email, STRONG_PASSWORD)
        assert not _stored_password_matches(db, email, ANOTHER_STRONG_PASSWORD)


def test_partial_demo_run_names_accounts_that_got_the_password(
    db, monkeypatch, capsys
) -> None:
    """일부만 새로 만들면 출력한 비밀번호가 어느 계정의 것인지 이메일로 밝힌다."""

    admin_email, admin_name, admin_role = seed_users.DEMO_ACCOUNTS[0]
    counselor_email = seed_users.DEMO_ACCOUNTS[1][0]

    seed_users.upsert_user(admin_email, admin_name, admin_role, STRONG_PASSWORD)
    monkeypatch.delenv("SEED_USER_PASSWORD", raising=False)
    _generated(monkeypatch, "Gen-Only-New-33")

    assert _run(monkeypatch, "--demo") == 0

    lines = capsys.readouterr().out.splitlines()
    applied = [line for line in lines if "적용" in line]

    assert "생성된 공용 데모 비밀번호: Gen-Only-New-33" in lines
    assert len(applied) == 1
    assert counselor_email in applied[0]
    assert admin_email not in applied[0]
    assert "이미 있는 계정의 비밀번호는 바뀌지 않았습니다." in "\n".join(lines)
    assert _stored_password_matches(db, admin_email, STRONG_PASSWORD)
    assert _stored_password_matches(db, counselor_email, "Gen-Only-New-33")


def test_rerunning_single_account_does_not_print_password(db, monkeypatch, capsys) -> None:
    monkeypatch.delenv("SEED_USER_PASSWORD", raising=False)
    _generated(monkeypatch, "Gen-Single-One-44", "Gen-Single-Two-55")
    args = ("--email", "seed.one@example.com", "--name", "상담사")

    assert _run(monkeypatch, *args) == 0
    assert "생성된 비밀번호: Gen-Single-One-44" in capsys.readouterr().out

    assert _run(monkeypatch, *args) == 0

    second = capsys.readouterr().out

    assert "Gen-Single-Two-55" not in second
    assert "생성된" not in second
    assert "이미 있는 계정의 비밀번호는 바뀌지 않았습니다." in second
    assert _stored_password_matches(db, "seed.one@example.com", "Gen-Single-One-44")
