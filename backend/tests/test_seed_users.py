# 초기 계정 생성 script(scripts/seed_users.py) 테스트.
#
# 사람이 직접 준 비밀번호(--password, SEED_USER_PASSWORD)도 API 와 같은 비밀번호 규칙을 거쳐야 한다.
# 안 거치면 script 로 만든 첫 관리자 계정만 규칙 밖에 남는다.

import sys
from typing import List, Tuple

import pytest

from app.core.enums import UserRole
from scripts import seed_users

STRONG_PASSWORD = "Violet-Ferry-62"
WEAK_PASSWORD = "ispot-demo-1234"


@pytest.fixture
def created(monkeypatch) -> List[Tuple[str, str, UserRole, str]]:
    """DB 에 쓰는 대신 upsert_user 호출만 기록한다."""

    calls: List[Tuple[str, str, UserRole, str]] = []

    def fake_upsert(email: str, name: str, role: UserRole, password: str) -> str:
        calls.append((email, name, role, password))
        return f"생성 완료: {email}"

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
