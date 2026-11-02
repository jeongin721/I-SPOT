# 회원가입 요청 수 제한 · 한 번만 쓰는 값이 동시 요청에서도 지켜지는지 본다(API_CONTRACT 3절 '회원가입').
#
# 동시 요청은 test_auth_races.py 와 같이 요청마다 TestClient 를 따로 만들어 스레드로 한꺼번에 보낸다.
# TEST_DATABASE_URL 로 PostgreSQL 에서도 돌린다(README 3절).

import re
import threading
from typing import Callable, List, Optional

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.adapters import mail_adapter
from app.core.config import settings
from app.core.enums import SignupRequestStatus
from app.main import app
from app.models.signup import SignupEmailCode, SignupRequest
from app.models.user import User
from app.services import signup_service
from tests.conftest import ADMIN_PASSWORD

BASE = "/api/v1/auth/signup-requests"
SEND = f"{BASE}/send-code"
VERIFY = f"{BASE}/verify-code"

EMAIL = "racer@ispot.example.org"
PASSWORD = "Maple-River-58"
WRONG_CODE = "999999"


@pytest.fixture(autouse=True)
def _signup_on(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "SIGNUP_ENABLED", True)
    signup_service.reset_limits()
    mail_adapter.clear_fake_outbox()
    mail_adapter.set_mail_sender_override(None)

    yield

    signup_service.reset_limits()
    mail_adapter.clear_fake_outbox()


def _burst(count: int, send: Callable[[TestClient, int], int]) -> List[Optional[int]]:
    """send 를 count 개 한꺼번에 부르고 응답 상태 코드를 같은 순서로 돌려준다."""

    statuses: List[Optional[int]] = [None] * count
    start = threading.Barrier(count)

    def one(index: int) -> None:
        start.wait()
        statuses[index] = send(TestClient(app), index)

    threads = [threading.Thread(target=one, args=(index,)) for index in range(count)]

    for thread in threads:
        thread.start()

    for thread in threads:
        thread.join()

    return statuses


def _outbox():
    assert signup_service.wait_for_mail()

    return mail_adapter.fake_outbox()


def _code(client: TestClient, email: str = EMAIL) -> str:
    assert client.post(SEND, json={"email": email}).status_code == 202
    assert signup_service.wait_for_mail()
    mails = [mail for mail in mail_adapter.fake_outbox() if mail.to == email]

    return re.search(r"인증번호: (\d{6})", mails[-1].body).group(1)


def _token(client: TestClient, email: str = EMAIL) -> str:
    response = client.post(VERIFY, json={"email": email, "code": _code(client, email)})

    assert response.status_code == 200, response.text

    return response.json()["data"]["verification_token"]


def _admin(client: TestClient) -> dict:
    response = client.post("/api/v1/auth/login", json={"email": "admin@ispot.example.com", "password": ADMIN_PASSWORD})

    assert response.status_code == 200, response.text

    return {"Authorization": f"Bearer {response.json()['data']['access_token']}"}


def test_same_email_send_burst_makes_one_code(client: TestClient, db) -> None:
    statuses = _burst(10, lambda c, _: c.post(SEND, json={"email": EMAIL}).status_code)

    assert sorted(statuses) == [202] + [429] * 9
    assert len(_outbox()) == 1

    db.expire_all()
    row = db.scalars(select(SignupEmailCode).where(SignupEmailCode.email == EMAIL)).one()
    assert row.send_count == 1


def test_resend_burst_after_interval_makes_one_code(client: TestClient, db, monkeypatch: pytest.MonkeyPatch) -> None:
    """행이 이미 있는 이메일의 다시 보내기(조건부 UPDATE)도 동시에 몰려 와 하나만 된다."""

    _code(client)
    first = signup_service._now()
    monkeypatch.setattr(signup_service, "_now", lambda: first + signup_service.RESEND_INTERVAL)
    mail_adapter.clear_fake_outbox()

    statuses = _burst(10, lambda c, _: c.post(SEND, json={"email": EMAIL}).status_code)

    assert sorted(statuses) == [202] + [429] * 9
    assert len(_outbox()) == 1

    db.expire_all()
    assert db.scalars(select(SignupEmailCode).where(SignupEmailCode.email == EMAIL)).one().send_count == 2


def test_wrong_code_burst_compares_only_five_times(client: TestClient) -> None:
    code = _code(client)

    statuses = _burst(12, lambda c, _: c.post(VERIFY, json={"email": EMAIL, "code": WRONG_CODE}).status_code)

    # 422 는 MISMATCH(5개) · EXPIRED(7개) 둘 다라 본문으로 나눈다.
    assert statuses == [422] * 12

    # 기준만큼 틀렸으니 맞는 번호도 이제 쓸 수 없다.
    late = client.post(VERIFY, json={"email": EMAIL, "code": code})
    assert late.json()["error"]["code"] == "VERIFICATION_CODE_EXPIRED"


def test_wrong_code_burst_reports_exactly_five_mismatches(client: TestClient) -> None:
    _code(client)
    codes: List[Optional[str]] = [None] * 12

    def send(c: TestClient, index: int) -> int:
        response = c.post(VERIFY, json={"email": EMAIL, "code": WRONG_CODE})
        codes[index] = response.json()["error"]["code"]

        return response.status_code

    _burst(12, send)

    assert codes.count("VERIFICATION_CODE_MISMATCH") == 5
    assert codes.count("VERIFICATION_CODE_EXPIRED") == 7


def test_right_code_burst_gives_one_token(client: TestClient) -> None:
    code = _code(client)

    statuses = _burst(6, lambda c, _: c.post(VERIFY, json={"email": EMAIL, "code": code}).status_code)

    assert sorted(statuses) == [200] + [422] * 5


def test_same_token_submit_burst_makes_one_request(client: TestClient, db) -> None:
    token = _token(client)
    body = {"verification_token": token, "name": "동시신청", "password": PASSWORD}

    statuses = _burst(3, lambda c, _: c.post(BASE, json=body).status_code)

    assert sorted(statuses) == [201, 422, 422]

    db.expire_all()
    assert db.scalar(select(func.count()).select_from(SignupRequest)) == 1


def test_approve_burst_makes_one_account(client: TestClient, admin_id, db) -> None:
    token = _token(client)
    assert client.post(BASE, json={"verification_token": token, "name": "동시승인", "password": PASSWORD}).status_code == 201

    db.expire_all()
    request_id = db.scalars(select(SignupRequest)).one().id
    headers = _admin(client)

    def decide(c: TestClient, index: int) -> int:
        if index % 2:
            return c.post(f"{BASE}/{request_id}/reject", headers=headers).status_code

        return c.post(f"{BASE}/{request_id}/approve", json={"role": "COUNSELOR"}, headers=headers).status_code

    statuses = _burst(4, decide)

    assert sorted(statuses) == [200, 409, 409, 409]

    db.expire_all()
    row = db.get(SignupRequest, request_id)
    users = db.scalar(select(func.count()).select_from(User).where(User.email == EMAIL))
    assert users == (1 if row.status == SignupRequestStatus.APPROVED else 0)
    assert row.hashed_password is None


def test_ip_burst_allows_exactly_the_limit(client: TestClient) -> None:
    count = signup_service.SEND_IP_LIMIT + 10

    statuses = _burst(count, lambda c, index: c.post(SEND, json={"email": f"ip{index}@ispot.example.org"}).status_code)

    assert statuses.count(202) == signup_service.SEND_IP_LIMIT
    assert statuses.count(429) == 10
    assert len(_outbox()) == signup_service.SEND_IP_LIMIT
