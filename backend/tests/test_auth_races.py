# 로그인 · 비밀번호 변경의 "5번 틀리면" 제한이 동시 요청에서도 지켜지는지 본다.
#
# 비밀번호 대조(bcrypt)는 요청마다 약 0.3초 걸린다. 횟수를 대조한 뒤에 세면, 그 사이 함께 들어온
# 요청이 모두 "아직 기준 전" 을 보고 대조까지 가서 기준보다 훨씬 많이 맞혀 볼 수 있다.
# 그래서 대조하기 전에 시도를 먼저 세어(예약) 두는지 확인한다.
#
# 동시 요청은 요청마다 TestClient 를 따로 만들어 스레드로 보낸다. 각자 이벤트 루프와 스레드 풀을
# 가지므로 실제 서버처럼 대조가 겹친다(conftest 의 client 는 요청을 하나씩 처리한다).

import threading
import uuid
from datetime import datetime, timedelta, timezone
from typing import Callable, Dict, List, Optional

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.enums import AuditAction
from app.main import app
from app.models.audit_log import AuditLog
from app.models.base import as_utc
from app.models.user import User
from app.services import audit_service, user_service
from tests.conftest import COUNSELOR_PASSWORD

COUNSELOR_EMAIL = "counselor.a@ispot.example.com"
LOGIN = "/api/v1/auth/login"
ME_PASSWORD = "/api/v1/auth/me/password"
NEW_PASSWORD = "Violet-Ferry-62"

# 기준(LOGIN_MAX_FAILURES=5)보다 넉넉히 많게. 많을수록 느려진다(잠긴 뒤 요청도 가짜 해시와 대조한다).
BURST = 12


def _burst(send: Callable[[TestClient, dict], int], bodies: List[dict]) -> List[Optional[int]]:
    """bodies 를 한꺼번에 보내고 응답 상태 코드를 같은 순서로 돌려준다."""

    statuses: List[Optional[int]] = [None] * len(bodies)
    start = threading.Barrier(len(bodies))

    def one(index: int) -> None:
        start.wait()
        statuses[index] = send(TestClient(app), bodies[index])

    threads = [threading.Thread(target=one, args=(index,)) for index in range(len(bodies))]

    for thread in threads:
        thread.start()

    for thread in threads:
        thread.join()

    return statuses


def _count(db, *conditions) -> int:
    return db.scalar(select(func.count()).select_from(AuditLog).where(*conditions)) or 0


# =========================================================
# 로그인
# =========================================================

def test_login_attempt_is_counted_before_password_check(
    client: TestClient, counselor_id: uuid.UUID, monkeypatch: pytest.MonkeyPatch
) -> None:
    """진짜 해시와 대조하는 순간에는 이번 시도가 이미 실패 횟수에 들어가 있어야 한다."""

    seen: List[int] = []
    original = user_service.verify_password

    def spy(password: str, hashed: str) -> bool:
        if hashed != user_service._dummy_password_hash():
            with SessionLocal() as other:
                seen.append(other.get(User, counselor_id).failed_login_count)

        return original(password, hashed)

    monkeypatch.setattr(user_service, "verify_password", spy)

    client.post(LOGIN, json={"email": COUNSELOR_EMAIL, "password": "Wrong-Guess-01x"})
    client.post(LOGIN, json={"email": COUNSELOR_EMAIL, "password": COUNSELOR_PASSWORD})

    assert seen == [1, 2]

    # 맞는 비밀번호로 들어오면 횟수는 처음부터 다시 센다.
    with SessionLocal() as other:
        assert other.get(User, counselor_id).failed_login_count == 0


def test_login_checked_with_old_password_gets_no_token_that_outlives_a_password_change(
    client: TestClient,
    counselor_headers: Dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    로그인이 옛 비밀번호를 대조한 직후 본인이 다른 기기에서 비밀번호를 바꾸면(그 계정의 Token 을 모두
    끊는다), 그 로그인이 받은 Token 도 바꾼 뒤에는 쓸 수 없어야 한다. 대조 뒤 계정을 다시 읽을 때
    Token 버전까지 새로 읽으면, 옛 비밀번호로 확인된 로그인이 바꾼 뒤의 버전으로 Token 을 받아 남는다.
    """

    original = user_service.verify_password
    change: List[int] = []

    def check_then_change(password: str, hashed: str) -> bool:
        matched = original(password, hashed)

        # 로그인의 대조가 끝난 직후 한 번만 본인이 비밀번호를 바꾼다. 바꾸는 요청 안의 대조는 그대로 지나간다.
        if matched and not change:
            change.append(0)
            change[0] = TestClient(app).post(
                ME_PASSWORD,
                json={"current_password": COUNSELOR_PASSWORD, "new_password": NEW_PASSWORD},
                headers=counselor_headers,
            ).status_code

        return matched

    monkeypatch.setattr(user_service, "verify_password", check_then_change)

    login = client.post(LOGIN, json={"email": COUNSELOR_EMAIL, "password": COUNSELOR_PASSWORD})

    monkeypatch.undo()

    assert change == [204]

    # 로그인은 바꾸기 전 비밀번호로 확인됐으므로 200 이지만, 받은 Token 은 바꾼 뒤에 쓸 수 없다.
    assert login.status_code == 200

    stale = {"Authorization": f"Bearer {login.json()['data']['access_token']}"}

    assert client.get("/api/v1/auth/me", headers=stale).status_code == 401
    assert client.get("/api/v1/cases", headers=stale).status_code == 401

    # 옛 비밀번호로는 더 들어오지 못하고, 새 비밀번호로는 들어온다.
    assert client.post(
        LOGIN, json={"email": COUNSELOR_EMAIL, "password": COUNSELOR_PASSWORD}
    ).status_code == 401
    assert client.post(
        LOGIN, json={"email": COUNSELOR_EMAIL, "password": NEW_PASSWORD}
    ).status_code == 200


def test_concurrent_wrong_logins_check_password_only_up_to_the_limit(
    counselor_id: uuid.UUID, db
) -> None:
    wrong = [
        {"email": COUNSELOR_EMAIL, "password": f"Wrong-Guess-{index:02d}x"}
        for index in range(BURST)
    ]

    statuses = _burst(lambda c, body: c.post(LOGIN, json=body).status_code, wrong)

    assert statuses == [401] * BURST

    login_failures = (AuditLog.action == AuditAction.LOGIN, AuditLog.status == "FAILURE")

    # 진짜 해시와 대조한 것은 기준 횟수까지만이다. 나머지는 잠긴 계정과 같게 거절된다.
    assert _count(db, *login_failures, AuditLog.error_code == "INVALID_CREDENTIALS") == (
        settings.LOGIN_MAX_FAILURES
    )
    assert _count(db, *login_failures, AuditLog.error_code == "ACCOUNT_LOCKED") == (
        BURST - settings.LOGIN_MAX_FAILURES
    )
    assert _count(db, AuditLog.action == AuditAction.ACCOUNT_LOCKED) == 1

    user = db.get(User, counselor_id)
    db.refresh(user)

    assert user.failed_login_count == settings.LOGIN_MAX_FAILURES

    # 잠겼으므로 맞는 비밀번호로도 들어오지 못한다.
    correct = TestClient(app).post(
        LOGIN, json={"email": COUNSELOR_EMAIL, "password": COUNSELOR_PASSWORD}
    )

    assert correct.status_code == 401


def test_concurrent_wrong_logins_right_after_timed_lock_expires_lock_again_at_the_limit(
    counselor_id: uuid.UUID, db, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    시간 잠금(LOGIN_LOCK_MINUTES > 0)이 막 풀린 순간에 몰려 든 요청도 기준 횟수까지만 대조하고 다시 잠근다.

    요청마다 처음 읽은 "지난 잠금" 을 보고 실패 횟수를 0 으로 되돌리면, 앞 요청이 예약한 횟수를 지워
    기준보다 많이 대조하고 다시 잠기지도 않는다. 잠금은 처음 읽은 잠금 시각이 그대로일 때 한 번만 풀어야 한다.
    """

    monkeypatch.setattr(settings, "LOGIN_LOCK_MINUTES", 15)

    user = db.get(User, counselor_id)
    user.failed_login_count = settings.LOGIN_MAX_FAILURES
    user.locked_until = datetime.now(timezone.utc) - timedelta(seconds=1)
    db.commit()

    wrong = [
        {"email": COUNSELOR_EMAIL, "password": f"Wrong-Guess-{index:02d}x"}
        for index in range(BURST)
    ]

    statuses = _burst(lambda c, body: c.post(LOGIN, json=body).status_code, wrong)

    assert statuses == [401] * BURST

    login_failures = (AuditLog.action == AuditAction.LOGIN, AuditLog.status == "FAILURE")

    assert _count(db, *login_failures, AuditLog.error_code == "INVALID_CREDENTIALS") == (
        settings.LOGIN_MAX_FAILURES
    )
    assert _count(db, *login_failures, AuditLog.error_code == "ACCOUNT_LOCKED") == (
        BURST - settings.LOGIN_MAX_FAILURES
    )
    assert _count(db, AuditLog.action == AuditAction.ACCOUNT_LOCKED) == 1

    db.refresh(user)

    assert user.failed_login_count == settings.LOGIN_MAX_FAILURES
    assert as_utc(user.locked_until) > datetime.now(timezone.utc)


# =========================================================
# 비밀번호 변경 창구
# =========================================================

def _password_failures(db) -> int:
    return _count(
        db,
        AuditLog.action == AuditAction.PASSWORD_CHANGED,
        AuditLog.status == "FAILURE",
        AuditLog.error_code == "INVALID_CURRENT_PASSWORD",
    )


def test_concurrent_wrong_current_passwords_check_only_up_to_the_limit(
    client: TestClient, counselor_headers: Dict[str, str], db
) -> None:
    wrong = [
        {"current_password": f"Wrong-Current-{index:02d}x", "new_password": NEW_PASSWORD}
        for index in range(BURST)
    ]

    statuses = _burst(
        lambda c, body: c.post(ME_PASSWORD, json=body, headers=counselor_headers).status_code,
        wrong,
    )

    assert set(statuses) <= {400, 401}
    assert statuses.count(401) >= BURST - settings.LOGIN_MAX_FAILURES

    # 현재 비밀번호를 실제로 대조한 것은 기준 횟수를 넘지 않는다.
    assert _password_failures(db) <= settings.LOGIN_MAX_FAILURES

    # Token 은 한 번만 끊는다.
    assert _count(db, AuditLog.action == AuditAction.LOGOUT_ALL) == 1
    assert client.get("/api/v1/auth/me", headers=counselor_headers).status_code == 401


def test_password_change_is_not_checked_once_the_limit_is_reached(
    client: TestClient,
    counselor_headers: Dict[str, str],
    counselor_id: uuid.UUID,
    db,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    함께 들어온 다른 요청들이 이미 기준만큼 틀렸으면(감사 로그에 남음), 맞는 비밀번호라도
    대조하지 않고 Token 을 끊는다. 대조하면 기준을 넘어 맞혀 보는 것이 된다.
    """

    for _ in range(settings.LOGIN_MAX_FAILURES):
        audit_service.record(
            db,
            action=AuditAction.PASSWORD_CHANGED,
            entity_type="User",
            entity_id=counselor_id,
            actor_id=counselor_id,
            status="FAILURE",
            error_code="INVALID_CURRENT_PASSWORD",
        )

    db.commit()

    checked: List[str] = []
    original = user_service.verify_password

    def spy(password: str, hashed: str) -> bool:
        checked.append(password)
        return original(password, hashed)

    monkeypatch.setattr(user_service, "verify_password", spy)

    response = client.post(
        ME_PASSWORD,
        json={"current_password": COUNSELOR_PASSWORD, "new_password": NEW_PASSWORD},
        headers=counselor_headers,
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"
    assert COUNSELOR_PASSWORD not in checked
    assert client.get("/api/v1/auth/me", headers=counselor_headers).status_code == 401

    monkeypatch.undo()

    # 비밀번호는 바뀌지 않았다.
    assert client.post(
        LOGIN, json={"email": COUNSELOR_EMAIL, "password": COUNSELOR_PASSWORD}
    ).status_code == 200


def test_password_change_does_not_finish_after_token_was_cut_while_checking(
    client: TestClient,
    counselor_headers: Dict[str, str],
    counselor_id: uuid.UUID,
    db,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    현재 비밀번호를 대조하는 사이 다른 요청이 Token 을 끊었으면(예: 함께 보낸 다른 추측이
    5번째로 틀림) 맞는 비밀번호여도 바꾸지 않는다. 이미 끊긴 Token 으로 계정을 가져가지 못하게 한다.
    """

    original = user_service.verify_password

    def cut_then_check(password: str, hashed: str) -> bool:
        with SessionLocal() as other:
            other.get(User, counselor_id).token_version += 1
            other.commit()

        return original(password, hashed)

    monkeypatch.setattr(user_service, "verify_password", cut_then_check)

    response = client.post(
        ME_PASSWORD,
        json={"current_password": COUNSELOR_PASSWORD, "new_password": NEW_PASSWORD},
        headers=counselor_headers,
    )

    monkeypatch.undo()

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"

    assert client.post(
        LOGIN, json={"email": COUNSELOR_EMAIL, "password": NEW_PASSWORD}
    ).status_code == 401
    assert client.post(
        LOGIN, json={"email": COUNSELOR_EMAIL, "password": COUNSELOR_PASSWORD}
    ).status_code == 200

    # 성공으로 남지 않는다.
    assert _count(
        db,
        AuditLog.action == AuditAction.PASSWORD_CHANGED,
        AuditLog.status == "SUCCESS",
    ) == 0


def test_successful_password_change_leaves_one_success_record(
    client: TestClient, counselor_headers: Dict[str, str], db
) -> None:
    """대조 전에 남긴 시도 기록은 성공하면 성공 기록 하나로 바뀐다(실패로 남지 않는다)."""

    response = client.post(
        ME_PASSWORD,
        json={"current_password": COUNSELOR_PASSWORD, "new_password": NEW_PASSWORD},
        headers=counselor_headers,
    )

    assert response.status_code == 204

    records = db.scalars(
        select(AuditLog).where(AuditLog.action == AuditAction.PASSWORD_CHANGED)
    ).all()

    assert [(record.status, record.error_code) for record in records] == [("SUCCESS", None)]


def test_reused_password_is_not_left_as_a_failure(
    client: TestClient, counselor_headers: Dict[str, str], db
) -> None:
    """현재 비밀번호가 맞았는데 이전 비밀번호라 거절된 것은 틀린 횟수에 넣지 않는다."""

    changed = client.post(
        ME_PASSWORD,
        json={"current_password": COUNSELOR_PASSWORD, "new_password": NEW_PASSWORD},
        headers=counselor_headers,
    )

    assert changed.status_code == 204

    login = client.post(LOGIN, json={"email": COUNSELOR_EMAIL, "password": NEW_PASSWORD})
    fresh = {"Authorization": f"Bearer {login.json()['data']['access_token']}"}

    reused = client.post(
        ME_PASSWORD,
        json={"current_password": NEW_PASSWORD, "new_password": COUNSELOR_PASSWORD},
        headers=fresh,
    )

    assert reused.status_code == 422
    assert reused.json()["error"]["code"] == "PASSWORD_REUSED"
    assert _count(
        db, AuditLog.action == AuditAction.PASSWORD_CHANGED, AuditLog.status == "FAILURE"
    ) == 0
