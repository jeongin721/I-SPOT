# 회원가입 — Codex 1차 검수(11/03, 1437867) 지적을 고친 것이 지켜지는지 본다(API_CONTRACT 3절 '회원가입').
#
# M1 메일 일이 새 이메일 · 있는 계정에서 같은 자리 · 같은 시간을 쓰는가, M2 비ASCII 대문자 옛 계정과 같은 이메일,
# M3 같은 토큰으로 bcrypt 를 되풀이하지 못하는가, M4 국제화 도메인을 ASCII 로 보내는가,
# L1 이메일 형식 오류가 입력을 되돌려 보내지 않는가, L2 쓸 수 없게 된 번호는 보내지 않는가,
# L3 잘못된 허용 도메인 설정, L4 다시 뽑은 번호가 앞 번호와 같을 때. (L5 는 test_signup_races.py)

import itertools
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from typing import List

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import func, select

from app.adapters import mail_adapter
from app.adapters.mail_adapter import MailMessage
from app.core.config import Settings, settings
from app.core.enums import SignupRequestStatus, UserRole
from app.models.signup import SignupRequest
from app.models.user import User
from app.services import signup_service
from tests.conftest import ADMIN_PASSWORD

BASE = "/api/v1/auth/signup-requests"
SEND = f"{BASE}/send-code"
VERIFY = f"{BASE}/verify-code"
PASSWORD = "Maple-River-58"
OWN_A = "own.a@ispot.example.org"
OWN_B = "own.b@ispot.example.org"
TARGET = "target@ispot.example.org"


@pytest.fixture(autouse=True)
def _signup_on(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "SIGNUP_ENABLED", True)
    monkeypatch.setattr(signup_service, "MAIL_JOB_SECONDS", 0.0, raising=False)
    signup_service.reset_limits()
    mail_adapter.clear_fake_outbox()
    mail_adapter.set_mail_sender_override(None)

    codes = (f"{100000 + index:06d}" for index in itertools.count(1))
    monkeypatch.setattr(signup_service, "_new_code", lambda: next(codes))

    yield

    mail_adapter.set_mail_sender_override(None)
    assert signup_service.wait_for_mail()
    signup_service.reset_limits()
    mail_adapter.clear_fake_outbox()


class _GateSender:
    """gate 가 열릴 때까지 보내기를 붙잡는다. 보낸 메일을 순서대로 남긴다."""

    name = "gate"

    def __init__(self) -> None:
        self.gate = threading.Event()
        self.sent: List[MailMessage] = []

    def send(self, message: MailMessage) -> None:
        assert self.gate.wait(10)
        self.sent.append(message)


def _send(client: TestClient, email: str):
    return client.post(SEND, json={"email": email})


def _code_for(email: str) -> str:
    assert signup_service.wait_for_mail()
    mails = [mail for mail in mail_adapter.fake_outbox() if mail.to == email]

    return re.search(r"인증번호: (\d{6})", mails[-1].body).group(1)


def _token(client: TestClient, email: str) -> str:
    assert _send(client, email).status_code == 202
    response = client.post(VERIFY, json={"email": email, "code": _code_for(email)})

    assert response.status_code == 200, response.text

    return response.json()["data"]["verification_token"]


def _admin_headers(client: TestClient) -> dict:
    response = client.post("/api/v1/auth/login", json={"email": "admin@ispot.example.com", "password": ADMIN_PASSWORD})

    return {"Authorization": f"Bearer {response.json()['data']['access_token']}"}


# =========================================================
# M1 — 메일 일이 새 이메일과 있는 계정에서 같다
# =========================================================

def _own_b_delivered(client: TestClient, monkeypatch: pytest.MonkeyPatch, target_taken: bool, db) -> bool:
    """
    일꾼 하나 · 대기 두 칸에서 자기 주소 A → 대상 → 자기 주소 B 를 보내고, B 가 나갔는지 돌려준다.

    대상이 새 이메일일 때만 대기 칸을 쓰면, 대상이 있는 계정일 때 B 가 나가 대상의 가입 여부가 드러난다(Codex M1).
    """

    if target_taken:
        db.add(User(email=TARGET, hashed_password="x", name="기존", role=UserRole.COUNSELOR))
        db.commit()

    pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="signup-mail-test")
    monkeypatch.setattr(signup_service, "_mail_pool", pool)
    monkeypatch.setattr(signup_service, "MAIL_QUEUE_LIMIT", 2)
    sender = _GateSender()
    mail_adapter.set_mail_sender_override(sender)

    try:
        for email in (OWN_A, TARGET, OWN_B):
            assert _send(client, email).status_code == 202
    finally:
        sender.gate.set()

    assert signup_service.wait_for_mail()
    pool.shutdown(wait=True)

    return OWN_B in [mail.to for mail in sender.sent]


@pytest.mark.parametrize("target_taken", [False, True])
def test_queue_slot_is_used_the_same_for_new_and_existing(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, db, target_taken: bool
) -> None:
    # 대기가 차 B 는 둘 다 나가지 않는다(대상이 새것이든 있는 계정이든 한 칸을 쓴다).
    assert _own_b_delivered(client, monkeypatch, target_taken, db) is False


def test_mail_job_holds_the_same_time_for_existing_email(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, counselor_id
) -> None:
    """있는 계정 이메일도 일꾼을 MAIL_JOB_SECONDS 만큼 붙잡는다(보내지는 않는다)."""

    monkeypatch.setattr(signup_service, "MAIL_JOB_SECONDS", 0.4, raising=False)

    started = time.monotonic()
    assert _send(client, "counselor.a@ispot.example.com").status_code == 202
    assert signup_service.wait_for_mail()
    taken_elapsed = time.monotonic() - started

    started = time.monotonic()
    assert _send(client, "fresh@ispot.example.org").status_code == 202
    assert signup_service.wait_for_mail()
    new_elapsed = time.monotonic() - started

    assert taken_elapsed >= 0.35
    assert new_elapsed >= 0.35
    assert abs(taken_elapsed - new_elapsed) < 0.35
    assert [mail.to for mail in mail_adapter.fake_outbox()] == ["fresh@ispot.example.org"]


# =========================================================
# M2 — 비ASCII 대문자 · 유니코드 도메인 옛 계정
# =========================================================

LEGACY_UNICODE = "NEWBIE@BÜCHER.de"
SIGNUP_PUNYCODE = "newbie@xn--bcher-kva.de"


def test_legacy_unicode_domain_account_blocks_mail_and_approval(client: TestClient, admin_id, db) -> None:
    token = _token(client, SIGNUP_PUNYCODE)
    assert client.post(BASE, json={"verification_token": token, "name": "새사람", "password": PASSWORD}).status_code == 201

    # 같은 메일함을 다른 표기(대문자 · 유니코드 도메인)로 적은 옛 계정. DB lower() 로는 같게 보이지 않는다.
    db.add(User(email=LEGACY_UNICODE, hashed_password="x", name="옛계정", role=UserRole.COUNSELOR))
    db.commit()

    request_id = db.scalars(select(SignupRequest)).one().id
    headers = _admin_headers(client)
    approved = client.post(f"{BASE}/{request_id}/approve", json={"role": "COUNSELOR"}, headers=headers)

    assert approved.status_code == 409
    assert approved.json()["error"]["code"] == "DUPLICATE_RESOURCE"

    db.expire_all()
    assert db.get(SignupRequest, request_id).status == SignupRequestStatus.PENDING
    assert db.scalar(select(func.count()).select_from(User).where(User.name == "새사람")) == 0


def test_legacy_unicode_domain_account_gets_no_mail(client: TestClient, db) -> None:
    db.add(User(email=LEGACY_UNICODE, hashed_password="x", name="옛계정", role=UserRole.COUNSELOR))
    db.commit()

    assert _send(client, SIGNUP_PUNYCODE).status_code == 202
    assert signup_service.wait_for_mail()
    assert mail_adapter.fake_outbox() == []


def test_admin_create_user_blocks_non_ascii_case_variant(client: TestClient, admin_headers, db) -> None:
    db.add(User(email="Écho@ispot.example.org", hashed_password="x", name="옛계정", role=UserRole.COUNSELOR))
    db.commit()

    response = client.post(
        "/api/v1/auth/users",
        json={"email": "écho@ispot.example.org", "password": PASSWORD, "name": "새계정", "role": "COUNSELOR"},
        headers=admin_headers,
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "DUPLICATE_RESOURCE"


# =========================================================
# M3 — 같은 토큰으로 bcrypt 를 되풀이하지 못한다
# =========================================================

@pytest.fixture
def hash_calls(monkeypatch: pytest.MonkeyPatch) -> List[int]:
    calls: List[int] = []
    real = signup_service.hash_password

    def counting(password: str) -> str:
        calls.append(1)

        return real(password)

    monkeypatch.setattr(signup_service, "hash_password", counting)

    return calls


def test_second_token_for_pending_email_is_spent_without_bcrypt(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, hash_calls: List[int]
) -> None:
    email = "twice@ispot.example.org"
    first = _token(client, email)
    assert client.post(BASE, json={"verification_token": first, "name": "두번", "password": PASSWORD}).status_code == 201
    hash_calls.clear()

    # 60초 뒤 새 번호로 두 번째 토큰을 받는다(대기 신청이 있는 이메일이라 메일은 안 간다 — 번호는 해시에서 못 읽으니 직접 맞춘다).
    later = signup_service._now() + signup_service.RESEND_INTERVAL
    monkeypatch.setattr(signup_service, "_now", lambda: later)
    monkeypatch.setattr(signup_service, "_new_code", lambda: "424242")
    assert _send(client, email).status_code == 202
    second = client.post(VERIFY, json={"email": email, "code": "424242"}).json()["data"]["verification_token"]

    body = {"verification_token": second, "name": "두번", "password": PASSWORD}
    duplicate = client.post(BASE, json=body)
    replay = client.post(BASE, json=body)

    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "DUPLICATE_RESOURCE"
    assert replay.status_code == 422
    assert replay.json()["error"]["code"] == "SIGNUP_TOKEN_INVALID"
    assert hash_calls == []


def test_account_made_after_verify_spends_token_without_bcrypt(
    client: TestClient, admin_headers, hash_calls: List[int]
) -> None:
    email = "late@ispot.example.org"
    token = _token(client, email)
    made = client.post(
        "/api/v1/auth/users",
        json={"email": email, "password": PASSWORD, "name": "관리자가만듦", "role": "COUNSELOR"},
        headers=admin_headers,
    )
    assert made.status_code == 201
    hash_calls.clear()

    body = {"verification_token": token, "name": "늦음", "password": PASSWORD}
    assert client.post(BASE, json=body).status_code == 409
    assert client.post(BASE, json=body).status_code == 422
    assert hash_calls == []


def test_weak_password_still_keeps_token_and_skips_bcrypt(client: TestClient, hash_calls: List[int]) -> None:
    token = _token(client, "weak@ispot.example.org")

    weak = client.post(BASE, json={"verification_token": token, "name": "약함", "password": "abc"})
    assert weak.status_code == 422
    assert weak.json()["error"]["code"] == "WEAK_PASSWORD"
    assert hash_calls == []

    assert client.post(BASE, json={"verification_token": token, "name": "약함", "password": PASSWORD}).status_code == 201
    assert len(hash_calls) == 1


# =========================================================
# M4 · L1 — 이메일은 ASCII 로 보내고, 형식 오류는 입력을 되돌려 보내지 않는다
# =========================================================

@pytest.mark.parametrize("given", ["idn@xn--bcher-kva.de", "IDN@Bücher.DE"])
def test_international_domain_is_sent_as_ascii(client: TestClient, given: str) -> None:
    assert _send(client, given).status_code == 202
    assert signup_service.wait_for_mail()

    assert [mail.to for mail in mail_adapter.fake_outbox()] == ["idn@xn--bcher-kva.de"]


@pytest.mark.parametrize("path", [SEND, VERIFY])
@pytest.mark.parametrize(
    "email",
    ["tést@ispot.example.org", "a@[IPv6:probe@example.org]", "probe", "probe@@example.org", "Probe <probe@example.org>"],
)
def test_bad_email_is_a_fixed_validation_error(client: TestClient, path: str, email: str) -> None:
    response = client.post(path, json={"email": email, "code": "123456"})

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "VALIDATION_ERROR"
    assert [item["field"] for item in error["details"]["fields"]] == ["email"]
    assert "probe" not in response.text
    assert "tést" not in response.text
    assert signup_service.wait_for_mail()
    assert mail_adapter.fake_outbox() == []


def test_allowed_domains_compare_ascii_form(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "SIGNUP_ALLOWED_EMAIL_DOMAINS", ["xn--bcher-kva.de"])

    assert _send(client, "a@bücher.de").status_code == 202
    assert _send(client, "a@ispot.example.org").status_code == 422


# =========================================================
# L2 — 쓸 수 없게 된 번호는 대기열에서 보내지 않는다
# =========================================================

def test_queued_mail_for_expired_code_is_not_sent(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    sender = _GateSender()
    mail_adapter.set_mail_sender_override(sender)
    pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="signup-mail-test")
    monkeypatch.setattr(signup_service, "_mail_pool", pool)

    try:
        assert _send(client, OWN_A).status_code == 202  # 일꾼을 붙잡는다
        assert _send(client, TARGET).status_code == 202  # 대기

        later = signup_service._now() + signup_service.CODE_TTL + timedelta(seconds=1)
        monkeypatch.setattr(signup_service, "_now", lambda: later)
    finally:
        sender.gate.set()

    assert signup_service.wait_for_mail()
    pool.shutdown(wait=True)

    assert [mail.to for mail in sender.sent] == [OWN_A]


def test_queued_mail_for_replaced_code_is_not_sent(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    sender = _GateSender()
    mail_adapter.set_mail_sender_override(sender)
    pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="signup-mail-test")
    monkeypatch.setattr(signup_service, "_mail_pool", pool)

    try:
        assert _send(client, OWN_A).status_code == 202  # 일꾼을 붙잡는다
        assert _send(client, TARGET).status_code == 202  # 첫 번호 — 대기

        later = signup_service._now() + signup_service.RESEND_INTERVAL
        monkeypatch.setattr(signup_service, "_now", lambda: later)
        assert _send(client, TARGET).status_code == 202  # 새 번호 — 첫 번호는 이제 틀린 번호
    finally:
        sender.gate.set()

    assert signup_service.wait_for_mail()
    pool.shutdown(wait=True)

    target_mails = [mail for mail in sender.sent if mail.to == TARGET]
    assert len(target_mails) == 1
    assert "100003" in target_mails[0].body


# =========================================================
# L3 — 잘못된 허용 도메인 설정은 서버가 뜨지 않는다
# =========================================================

@pytest.mark.parametrize("raw", ["@@", " , ", "not a domain", "localhost", "a@b.org", "ispot.example.org,@"])
def test_bad_allowed_domains_setting_is_rejected(monkeypatch: pytest.MonkeyPatch, raw: str) -> None:
    monkeypatch.setenv("SIGNUP_ALLOWED_EMAIL_DOMAINS", raw)

    with pytest.raises(ValidationError, match="SIGNUP_ALLOWED_EMAIL_DOMAINS"):
        Settings(_env_file=None)


@pytest.mark.parametrize("raw, expected", [("", []), ("Agency.Example.KR, @ispot.example.org", ["agency.example.kr", "ispot.example.org"])])
def test_allowed_domains_setting_accepts_empty_and_domains(monkeypatch: pytest.MonkeyPatch, raw: str, expected) -> None:
    monkeypatch.setenv("SIGNUP_ALLOWED_EMAIL_DOMAINS", raw)

    assert Settings(_env_file=None).SIGNUP_ALLOWED_EMAIL_DOMAINS == expected


# =========================================================
# L4 — 다시 뽑은 번호가 지금 번호와 같으면 다시 뽑는다
# =========================================================

def test_resend_never_reuses_the_live_code(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    draws = iter(["111111", "111111", "222222"])
    monkeypatch.setattr(signup_service, "_new_code", lambda: next(draws))
    email = "same@ispot.example.org"

    assert _send(client, email).status_code == 202
    first = _code_for(email)

    later = signup_service._now() + signup_service.RESEND_INTERVAL
    monkeypatch.setattr(signup_service, "_now", lambda: later)
    assert _send(client, email).status_code == 202
    second = _code_for(email)

    assert (first, second) == ("111111", "222222")
    stale = client.post(VERIFY, json={"email": email, "code": first})
    assert stale.status_code == 422
    assert stale.json()["error"]["code"] == "VERIFICATION_CODE_MISMATCH"
