# 회원가입 — 이메일 인증번호 → 대기 신청 → 관리자 승인(2026-11-02, API_CONTRACT 3절 '회원가입').
#
# 시각은 signup_service._now 를, 인증번호는 signup_service._new_code 를 바꿔 끼워 본다(5분 · 60초 · 24시간을 기다리지 않고,
# 우연히 같은 번호가 나와 흔들리지 않게). 메일은 fake 발송기의 outbox 로 받는다. 메일은 전용 스레드에서 나가므로 outbox ·
# 감사 기록을 읽기 전에 signup_service.wait_for_mail 로 기다린다. 동시 요청은 test_signup_races.py 에 있다.

import itertools
import logging
import re
import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Dict, Iterator, List

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.adapters import mail_adapter
from app.adapters.mail_adapter import MailMessage, MailSendError, SesMailSender
from app.core.config import settings
from app.core.enums import AuditAction, SignupRequestStatus, UserRole
from app.models.audit_log import AuditLog
from app.models.signup import SignupEmailCode, SignupRequest
from app.models.user import User
from app.services import signup_service

BASE = "/api/v1/auth/signup-requests"
SEND = f"{BASE}/send-code"
VERIFY = f"{BASE}/verify-code"
LOGIN = "/api/v1/auth/login"

EMAIL = "newbie@ispot.example.org"
NAME = "새상담사"
PASSWORD = "Maple-River-58"
WRONG_CODE = "999999"


class Clock:
    def __init__(self) -> None:
        self.now = datetime.now(timezone.utc)

    def __call__(self) -> datetime:
        return self.now

    def advance(self, **kwargs) -> None:
        self.now += timedelta(**kwargs)


@pytest.fixture(autouse=True)
def _signup_state(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    signup_service.reset_limits()
    mail_adapter.clear_fake_outbox()
    mail_adapter.set_mail_sender_override(None)

    codes = (f"{100000 + index:06d}" for index in itertools.count(1))
    monkeypatch.setattr(signup_service, "_new_code", lambda: next(codes))
    # 메일 일 하나가 일꾼을 붙잡는 시간(운영 2초)을 시험에서는 없앤다. 그 시간은 test_signup_hardening.py 가 본다.
    monkeypatch.setattr(signup_service, "MAIL_JOB_SECONDS", 0.0)

    yield

    signup_service.reset_limits()
    mail_adapter.clear_fake_outbox()
    mail_adapter.set_mail_sender_override(None)


@pytest.fixture
def enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "SIGNUP_ENABLED", True)


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch) -> Clock:
    fake = Clock()
    monkeypatch.setattr(signup_service, "_now", fake)

    return fake


def _send(client: TestClient, email: str = EMAIL):
    return client.post(SEND, json={"email": email})


def _verify(client: TestClient, code: str, email: str = EMAIL):
    return client.post(VERIFY, json={"email": email, "code": code})


def _submit(client: TestClient, token: str, name: str = NAME, password: str = PASSWORD, **extra):
    return client.post(BASE, json={"verification_token": token, "name": name, "password": password, **extra})


def _mails(to: str = EMAIL) -> List[MailMessage]:
    assert signup_service.wait_for_mail()

    return [mail for mail in mail_adapter.fake_outbox() if mail.to == to]


def _last_code(to: str = EMAIL) -> str:
    mails = _mails(to)

    assert mails, "메일이 없습니다"

    found = re.search(r"인증번호: (\d{6})", mails[-1].body)

    assert found

    return found.group(1)


def _token(client: TestClient, email: str = EMAIL) -> str:
    assert _send(client, email).status_code == 202
    response = _verify(client, _last_code(email), email)

    assert response.status_code == 200, response.text

    return response.json()["data"]["verification_token"]


def _pending(client: TestClient, email: str = EMAIL, name: str = NAME) -> None:
    assert _submit(client, _token(client, email), name=name).status_code == 201


def _audits(db, action: AuditAction) -> List[AuditLog]:
    assert signup_service.wait_for_mail()
    db.expire_all()

    return list(db.scalars(select(AuditLog).where(AuditLog.action == action).order_by(AuditLog.created_at)))


def _request_row(db, email: str = EMAIL) -> SignupRequest:
    db.expire_all()

    return db.scalars(select(SignupRequest).where(SignupRequest.email == email)).one()


def _code_row(db, email: str = EMAIL) -> SignupEmailCode:
    db.expire_all()

    return db.scalars(select(SignupEmailCode).where(SignupEmailCode.email == email)).one()


def _error(response) -> Dict:
    return response.json()["error"]


# =========================================================
# 켜기 · 끄기 · 설정 조회
# =========================================================

def test_disabled_by_default(client: TestClient, admin_headers) -> None:
    assert settings.SIGNUP_ENABLED is False

    for response in (_send(client), _verify(client, "123456"), _submit(client, "x" * 20)):
        assert response.status_code == 503
        assert _error(response)["code"] == "SIGNUP_DISABLED"

    settings_response = client.get(f"{BASE}/settings")

    assert settings_response.status_code == 200
    assert settings_response.json() == {"data": {"enabled": False, "allowed_email_domains": []}}

    # 끈 뒤에도 남은 신청을 처리할 수 있게 관리자 창구는 동작한다.
    assert client.get(BASE, headers=admin_headers).status_code == 200
    assert signup_service.wait_for_mail()
    assert mail_adapter.fake_outbox() == []


def test_settings_reports_enabled_and_domains(client: TestClient, enabled, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "SIGNUP_ALLOWED_EMAIL_DOMAINS", ["ispot.example.org"])

    assert client.get(f"{BASE}/settings").json()["data"] == {
        "enabled": True,
        "allowed_email_domains": ["ispot.example.org"],
    }


def test_old_register_path_does_not_exist(client: TestClient, enabled) -> None:
    response = client.post("/api/v1/auth/register", json={"email": EMAIL, "password": PASSWORD, "name": NAME})

    assert response.status_code == 404


# =========================================================
# 처음부터 끝까지
# =========================================================

def test_full_flow_creates_account_only_on_approval(client: TestClient, enabled, admin_headers, db) -> None:
    sent = _send(client)

    assert sent.status_code == 202
    assert sent.json() == {"data": {"resend_after_seconds": 60, "expires_in_seconds": 300}}

    mails = _mails()

    assert len(mails) == 1
    assert mails[0].subject == "[I-SPOT] 회원가입 인증번호"

    code = _last_code()
    row = _code_row(db)

    assert re.fullmatch(r"[0-9a-f]{64}", row.code_hash)
    assert code not in row.code_hash

    verified = _verify(client, code)

    assert verified.status_code == 200
    body = verified.json()["data"]
    assert body["expires_in_seconds"] == 1800
    assert len(body["verification_token"]) >= 40
    assert _code_row(db).code_hash is None

    created = _submit(client, body["verification_token"])

    assert created.status_code == 201
    assert created.json() == {"data": {"status": "PENDING"}}

    # 대기 중에는 계정이 없다. 없는 계정과 같은 응답이다.
    assert db.scalar(select(User).where(User.email == EMAIL)) is None
    login = client.post(LOGIN, json={"email": EMAIL, "password": PASSWORD})
    assert login.status_code == 401
    assert _error(login)["code"] == "INVALID_CREDENTIALS"

    listed = client.get(BASE, headers=admin_headers).json()["data"]

    assert listed["meta"]["total"] == 1
    item = listed["items"][0]
    assert item["email"] == EMAIL
    assert item["name"] == NAME
    assert item["status"] == "PENDING"
    assert item["expires_at"] is not None
    assert item["user_id"] is None
    assert "hashed_password" not in item

    approved = client.post(f"{BASE}/{item['id']}/approve", json={"role": "COUNSELOR"}, headers=admin_headers)

    assert approved.status_code == 200, approved.text
    approved_item = approved.json()["data"]
    assert approved_item["status"] == "APPROVED"
    assert approved_item["role"] == "COUNSELOR"
    assert approved_item["decided_by_name"] == "관리자"
    assert approved_item["expires_at"] is None

    user = db.scalars(select(User).where(User.email == EMAIL)).one()
    assert str(user.id) == approved_item["user_id"]
    assert user.role == UserRole.COUNSELOR
    assert user.name == NAME
    assert user.must_change_password is False
    assert _request_row(db).hashed_password is None

    # 신청 때 정한 비밀번호로 바로 로그인한다.
    assert client.post(LOGIN, json={"email": EMAIL, "password": PASSWORD}).status_code == 200

    assert [log.detail for log in _audits(db, AuditAction.SIGNUP_CODE_SENT)] == [{"mail": "QUEUED"}]
    assert [log.status for log in _audits(db, AuditAction.SIGNUP_CODE_VERIFIED)] == ["SUCCESS"]
    assert len(_audits(db, AuditAction.SIGNUP_REQUESTED)) == 1

    approvals = _audits(db, AuditAction.SIGNUP_APPROVED)
    assert len(approvals) == 1
    assert approvals[0].actor_id is not None
    assert approvals[0].detail == {"role": "COUNSELOR", "user_id": str(user.id)}

    created_logs = [log for log in _audits(db, AuditAction.USER_CREATED) if log.entity_id == user.id]
    assert [log.detail for log in created_logs] == [{"role": "COUNSELOR", "via": "signup_request"}]


def test_email_case_and_spaces_are_normalized(client: TestClient, enabled, db) -> None:
    # EmailStr 은 앞뒤 공백을 떼고 도메인만 소문자로 바꾼다. 아이디 부분은 서버가 소문자로 맞춘다.
    assert _send(client, "  NewBie@ISPOT.Example.ORG ").status_code == 202

    assert _code_row(db).email == EMAIL
    assert len(_mails(EMAIL)) == 1
    assert _verify(client, _last_code(EMAIL), "NEWBIE@ispot.example.org").status_code == 200


# =========================================================
# 계정 열거 — 있는 계정 · 대기 신청도 같은 응답
# =========================================================

def test_existing_account_gets_same_response_without_mail(client: TestClient, enabled, counselor_id, db) -> None:
    existing = "counselor.a@ispot.example.com"

    new = _send(client)
    known = _send(client, existing)

    assert known.status_code == new.status_code == 202
    assert known.json() == new.json()
    assert _mails(existing) == []
    assert len(_mails(EMAIL)) == 1

    assert sorted(log.detail["mail"] for log in _audits(db, AuditAction.SIGNUP_CODE_SENT)) == ["QUEUED", "SKIPPED"]

    # 60초 제한도 똑같이 걸린다.
    again_new = _send(client)
    again_known = _send(client, existing)

    assert again_new.status_code == again_known.status_code == 429
    assert _error(again_new) == _error(again_known)

    # 번호는 아무에게도 가지 않았지만 틀린 번호 응답도 같다.
    wrong_new = _verify(client, WRONG_CODE)
    wrong_known = _verify(client, WRONG_CODE, existing)

    assert wrong_new.status_code == wrong_known.status_code == 422
    assert _error(wrong_new) == _error(wrong_known)


def test_pending_email_gets_same_response_without_mail(client: TestClient, enabled, clock, db) -> None:
    _pending(client)
    mail_adapter.clear_fake_outbox()
    clock.advance(seconds=61)

    response = _send(client)

    assert response.status_code == 202
    assert response.json() == {"data": {"resend_after_seconds": 60, "expires_in_seconds": 300}}
    assert _mails() == []
    assert _audits(db, AuditAction.SIGNUP_CODE_SENT)[-1].detail == {"mail": "SKIPPED"}


# =========================================================
# 다시 보내기 · 하루 횟수 · IP
# =========================================================

def test_resend_waits_60_seconds_and_replaces_code(client: TestClient, enabled, clock, db) -> None:
    assert _send(client).status_code == 202
    first = _last_code()

    clock.advance(seconds=30)
    blocked = _send(client)

    assert blocked.status_code == 429
    assert _error(blocked)["code"] == "RATE_LIMITED"
    assert _error(blocked)["details"] == {"retry_after_seconds": 30}

    clock.advance(seconds=31)
    assert _send(client).status_code == 202
    second = _last_code()
    assert second != first

    # 앞 번호는 지금 번호와 다르므로 틀린 번호다. 틀린 횟수는 새 번호에서 0 부터 센다.
    stale = _verify(client, first)
    assert stale.status_code == 422
    assert _error(stale)["code"] == "VERIFICATION_CODE_MISMATCH"
    assert _error(stale)["details"] == {"remaining_attempts": 4}

    assert _verify(client, second).status_code == 200


def test_daily_limit_is_5_per_24_hours(client: TestClient, enabled, clock, db) -> None:
    for _ in range(5):
        assert _send(client).status_code == 202
        clock.advance(seconds=61)

    blocked = _send(client)

    assert blocked.status_code == 429
    expected = int(timedelta(hours=24).total_seconds()) - 5 * 61
    assert _error(blocked)["details"]["retry_after_seconds"] == expected

    clock.advance(seconds=expected)
    assert _send(client).status_code == 202
    assert _code_row(db).send_count == 1


def test_ip_limit_for_send_and_verify(client: TestClient, enabled) -> None:
    for index in range(signup_service.SEND_IP_LIMIT):
        assert _send(client, f"user{index}@ispot.example.org").status_code == 202

    blocked = _send(client, "one-more@ispot.example.org")
    assert blocked.status_code == 429
    assert 3500 < _error(blocked)["details"]["retry_after_seconds"] <= 3600

    for _ in range(signup_service.VERIFY_IP_LIMIT):
        assert _verify(client, WRONG_CODE, "nobody@ispot.example.org").status_code == 422

    assert _verify(client, WRONG_CODE, "nobody@ispot.example.org").status_code == 429


def test_allowed_domains(client: TestClient, enabled, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "SIGNUP_ALLOWED_EMAIL_DOMAINS", ["ispot.example.org"])

    outside = _send(client, "someone@gmail.example.com")

    assert outside.status_code == 422
    assert _error(outside)["code"] == "SIGNUP_EMAIL_DOMAIN_NOT_ALLOWED"
    assert signup_service.wait_for_mail()
    assert mail_adapter.fake_outbox() == []

    # 하위 도메인은 따로 적어야 한다.
    assert _send(client, "someone@sub.ispot.example.org").status_code == 422
    assert _send(client, "Someone@ISPOT.example.org").status_code == 202


# =========================================================
# 인증번호 확인
# =========================================================

def test_wrong_codes_count_down_then_code_dies(client: TestClient, enabled, db) -> None:
    assert _send(client).status_code == 202
    code = _last_code()

    remaining = []

    for _ in range(5):
        response = _verify(client, WRONG_CODE)
        assert response.status_code == 422
        assert _error(response)["code"] == "VERIFICATION_CODE_MISMATCH"
        remaining.append(_error(response)["details"]["remaining_attempts"])

    assert remaining == [4, 3, 2, 1, 0]
    assert "새 인증번호" in _error(response)["message"]

    dead = _verify(client, code)
    assert dead.status_code == 422
    assert _error(dead)["code"] == "VERIFICATION_CODE_EXPIRED"

    failures = _audits(db, AuditAction.SIGNUP_CODE_VERIFIED)
    assert [log.detail["failed_attempts"] for log in failures] == [1, 2, 3, 4, 5]
    assert {log.error_code for log in failures} == {"VERIFICATION_CODE_MISMATCH"}


def test_code_expires_after_5_minutes(client: TestClient, enabled, clock) -> None:
    assert _send(client).status_code == 202
    code = _last_code()

    clock.advance(minutes=5, seconds=1)
    response = _verify(client, code)

    assert response.status_code == 422
    assert _error(response)["code"] == "VERIFICATION_CODE_EXPIRED"


def test_code_works_only_once(client: TestClient, enabled) -> None:
    assert _send(client).status_code == 202
    code = _last_code()

    assert _verify(client, code).status_code == 200

    again = _verify(client, code)
    assert again.status_code == 422
    assert _error(again)["code"] == "VERIFICATION_CODE_EXPIRED"


def test_never_requested_email_is_expired(client: TestClient, enabled) -> None:
    response = _verify(client, "123456", "nobody@ispot.example.org")

    assert response.status_code == 422
    assert _error(response)["code"] == "VERIFICATION_CODE_EXPIRED"


@pytest.mark.parametrize("code", ["12345", "1234567", "12a456", "１２３４５６", " 123456", ""])
def test_code_must_be_6_ascii_digits(client: TestClient, enabled, code: str) -> None:
    response = _verify(client, code)

    assert response.status_code == 422
    assert _error(response)["code"] == "VALIDATION_ERROR"


def test_validation_error_does_not_echo_input(client: TestClient, enabled) -> None:
    marker = "secret-marker-xyz"
    response = client.post(VERIFY, json={"email": EMAIL, "code": marker})

    assert response.status_code == 422
    assert marker not in response.text


# =========================================================
# 대기 신청
# =========================================================

def test_weak_password_keeps_token(client: TestClient, enabled) -> None:
    token = _token(client)

    weak = _submit(client, token, password="abc")
    assert weak.status_code == 422
    assert _error(weak)["code"] == "WEAK_PASSWORD"

    # 이메일 아이디(newbie)가 든 비밀번호도 지금 규칙대로 막는다.
    with_id = _submit(client, token, password="Newbie-River-58")
    assert with_id.status_code == 422
    assert _error(with_id)["code"] == "WEAK_PASSWORD"

    assert _submit(client, token).status_code == 201


def test_token_is_single_use(client: TestClient, enabled) -> None:
    token = _token(client)

    assert _submit(client, token).status_code == 201

    again = _submit(client, token, name="다른이름")
    assert again.status_code == 422
    assert _error(again)["code"] == "SIGNUP_TOKEN_INVALID"


def test_token_expires_after_30_minutes(client: TestClient, enabled, clock) -> None:
    token = _token(client)

    clock.advance(minutes=30, seconds=1)
    response = _submit(client, token)

    assert response.status_code == 422
    assert _error(response)["code"] == "SIGNUP_TOKEN_INVALID"


def test_unknown_token_is_invalid(client: TestClient, enabled) -> None:
    response = _submit(client, "not-a-real-token-0123456789")

    assert response.status_code == 422
    assert _error(response)["code"] == "SIGNUP_TOKEN_INVALID"


def test_token_survives_new_code(client: TestClient, enabled, clock) -> None:
    token = _token(client)

    clock.advance(seconds=61)
    assert _send(client).status_code == 202

    assert _submit(client, token).status_code == 201


@pytest.mark.parametrize("name", ["", "   ", "가" * 101])
def test_name_is_required_and_bounded(client: TestClient, enabled, name: str) -> None:
    response = _submit(client, _token(client), name=name)

    assert response.status_code == 422
    assert _error(response)["code"] == "VALIDATION_ERROR"


def test_name_is_stripped(client: TestClient, enabled, db) -> None:
    assert _submit(client, _token(client), name="  새상담사  ").status_code == 201
    assert _request_row(db).name == "새상담사"


def test_applicant_cannot_choose_role(client: TestClient, enabled, admin_headers, db) -> None:
    assert _submit(client, _token(client), role="ADMIN").status_code == 201

    request_id = _request_row(db).id
    approved = client.post(f"{BASE}/{request_id}/approve", json={"role": "COUNSELOR"}, headers=admin_headers)

    assert approved.status_code == 200
    assert db.scalars(select(User).where(User.email == EMAIL)).one().role == UserRole.COUNSELOR


def test_account_created_after_verify_is_conflict(client: TestClient, enabled, admin_headers) -> None:
    token = _token(client)

    made = client.post(
        "/api/v1/auth/users",
        json={"email": EMAIL, "password": PASSWORD, "name": NAME, "role": "COUNSELOR"},
        headers=admin_headers,
    )
    assert made.status_code == 201

    response = _submit(client, token)
    assert response.status_code == 409
    assert _error(response)["code"] == "DUPLICATE_RESOURCE"


# =========================================================
# 관리자
# =========================================================

def test_admin_endpoints_need_admin(client: TestClient, enabled, counselor_headers, db) -> None:
    _pending(client)
    request_id = _request_row(db).id

    for headers, expected in ((counselor_headers, 403), ({}, 401)):
        assert client.get(BASE, headers=headers).status_code == expected
        assert client.post(f"{BASE}/{request_id}/approve", json={"role": "ADMIN"}, headers=headers).status_code == expected
        assert client.post(f"{BASE}/{request_id}/reject", headers=headers).status_code == expected

    assert _request_row(db).status == SignupRequestStatus.PENDING


def test_approve_requires_role(client: TestClient, enabled, admin_headers, db) -> None:
    _pending(client)

    response = client.post(f"{BASE}/{_request_row(db).id}/approve", json={}, headers=admin_headers)

    assert response.status_code == 422
    assert _request_row(db).status == SignupRequestStatus.PENDING


def test_approve_as_admin_role(client: TestClient, enabled, admin_headers, db) -> None:
    _pending(client)

    response = client.post(f"{BASE}/{_request_row(db).id}/approve", json={"role": "ADMIN"}, headers=admin_headers)

    assert response.status_code == 200
    assert db.scalars(select(User).where(User.email == EMAIL)).one().role == UserRole.ADMIN


def test_decided_request_cannot_be_decided_again(client: TestClient, enabled, admin_headers, db) -> None:
    _pending(client)
    request_id = _request_row(db).id

    rejected = client.post(f"{BASE}/{request_id}/reject", headers=admin_headers)

    assert rejected.status_code == 200
    assert rejected.json()["data"]["status"] == "REJECTED"
    row = _request_row(db)
    assert row.hashed_password is None
    assert row.decided_by_id is not None

    for path, body in ((f"{BASE}/{request_id}/approve", {"role": "COUNSELOR"}), (f"{BASE}/{request_id}/reject", None)):
        response = client.post(path, json=body, headers=admin_headers)
        assert response.status_code == 409
        assert _error(response)["code"] == "SIGNUP_ALREADY_DECIDED"

    assert db.scalar(select(User).where(User.email == EMAIL)) is None
    assert client.post(LOGIN, json={"email": EMAIL, "password": PASSWORD}).status_code == 401
    assert len(_audits(db, AuditAction.SIGNUP_REJECTED)) == 1


def test_approve_unknown_is_404(client: TestClient, enabled, admin_headers) -> None:
    response = client.post(
        f"{BASE}/00000000-0000-0000-0000-000000000000/approve", json={"role": "COUNSELOR"}, headers=admin_headers
    )

    assert response.status_code == 404
    assert _error(response)["code"] == "NOT_FOUND"


def test_approve_when_email_now_taken_keeps_pending(client: TestClient, enabled, admin_headers, db) -> None:
    _pending(client)
    request_id = _request_row(db).id

    # 대소문자만 다른 옛 계정(유일 제약에 걸리지 않음)도 같은 이메일로 본다.
    db.add(User(email="NewBie@ispot.example.org", hashed_password="x", name="옛계정", role=UserRole.COUNSELOR))
    db.commit()

    response = client.post(f"{BASE}/{request_id}/approve", json={"role": "COUNSELOR"}, headers=admin_headers)

    assert response.status_code == 409
    assert _error(response)["code"] == "DUPLICATE_RESOURCE"
    row = _request_row(db)
    assert row.status == SignupRequestStatus.PENDING
    assert row.hashed_password is not None
    assert _audits(db, AuditAction.SIGNUP_APPROVED) == []


def test_rejected_person_can_apply_again(client: TestClient, enabled, admin_headers, clock, db) -> None:
    _pending(client)
    first_id = _request_row(db).id
    assert client.post(f"{BASE}/{first_id}/reject", headers=admin_headers).status_code == 200

    clock.advance(seconds=61)
    _pending(client)

    db.expire_all()
    statuses = sorted(row.status.value for row in db.scalars(select(SignupRequest)))
    assert statuses == ["PENDING", "REJECTED"]


def test_list_filter_order_and_pages(client: TestClient, enabled, admin_headers, db) -> None:
    for index in range(3):
        _pending(client, f"user{index}@ispot.example.org", name=f"신청자{index}")

    first = db.scalars(select(SignupRequest).where(SignupRequest.email == "user0@ispot.example.org")).one()
    assert client.post(f"{BASE}/{first.id}/reject", headers=admin_headers).status_code == 200

    pending = client.get(BASE, params={"page_size": 1}, headers=admin_headers).json()["data"]
    assert pending["meta"]["total"] == 2
    assert pending["meta"]["total_pages"] == 2
    assert [item["email"] for item in pending["items"]] == ["user1@ispot.example.org"]

    second_page = client.get(BASE, params={"page_size": 1, "page": 2}, headers=admin_headers).json()["data"]
    assert [item["email"] for item in second_page["items"]] == ["user2@ispot.example.org"]

    rejected = client.get(BASE, params={"status": "REJECTED"}, headers=admin_headers).json()["data"]
    assert [item["email"] for item in rejected["items"]] == ["user0@ispot.example.org"]
    assert rejected["items"][0]["decided_by_name"] == "관리자"

    assert client.get(BASE, params={"status": "WHATEVER"}, headers=admin_headers).status_code == 422


# =========================================================
# 보관 기한
# =========================================================

def test_purge_removes_expired_rows_but_keeps_audit(client: TestClient, enabled, admin_headers, clock, db) -> None:
    _pending(client, "pending@ispot.example.org")
    _pending(client, "decided@ispot.example.org")
    decided = db.scalars(select(SignupRequest).where(SignupRequest.email == "decided@ispot.example.org")).one()
    assert client.post(f"{BASE}/{decided.id}/reject", headers=admin_headers).status_code == 200

    audit_count = len(db.scalars(select(AuditLog)).all())

    # 24시간 뒤: 인증번호 행만 지워진다.
    clock.advance(hours=24, seconds=1)
    assert client.get(BASE, headers=admin_headers).status_code == 200
    db.expire_all()
    assert db.scalars(select(SignupEmailCode)).all() == []
    assert len(db.scalars(select(SignupRequest)).all()) == 2

    # 15일 뒤: PENDING 이 지워진다.
    clock.advance(days=14)
    assert client.get(BASE, headers=admin_headers).json()["data"]["meta"]["total"] == 0
    db.expire_all()
    assert [row.email for row in db.scalars(select(SignupRequest))] == ["decided@ispot.example.org"]

    # 처리 30일 뒤: 처리된 신청도 지워진다(decided_at 은 진짜 시각이라 오늘부터 31일).
    clock.now = datetime.now(timezone.utc) + timedelta(days=31)
    assert client.get(BASE, params={"status": "REJECTED"}, headers=admin_headers).json()["data"]["items"] == []
    db.expire_all()
    assert db.scalars(select(SignupRequest)).all() == []

    # 감사 기록은 지우지 않는다(목록 조회는 감사 기록을 더하지 않는다).
    assert len(db.scalars(select(AuditLog)).all()) == audit_count


# =========================================================
# 비밀 · 기록
# =========================================================

class _LeakySender:
    """SES 처럼 받는 주소가 든 문구로 실패한다."""

    name = "leaky"

    def send(self, message: MailMessage) -> None:
        raise RuntimeError(f"Email address is not verified. The following identities failed: {message.to}")


def test_mail_failure_is_audited_without_address(client: TestClient, enabled, db, caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG)
    mail_adapter.set_mail_sender_override(_LeakySender())

    response = _send(client)

    assert response.status_code == 202

    logs = _audits(db, AuditAction.SIGNUP_CODE_SENT)
    assert [(log.status, log.error_code) for log in logs] == [("SUCCESS", None), ("FAILURE", "MAIL_SEND_FAILED")]
    assert logs[1].detail == {"provider": "leaky", "cause": "RuntimeError"}
    assert EMAIL not in caplog.text
    assert EMAIL not in str([log.detail for log in logs])


class _BlockingSender:
    """release 될 때까지 보내기를 붙잡는다(느린 SES 흉내)."""

    name = "blocking"

    def __init__(self) -> None:
        self.release = threading.Event()
        self.sent: List[MailMessage] = []

    def send(self, message: MailMessage) -> None:
        assert self.release.wait(10)
        self.sent.append(message)


def test_send_does_not_wait_for_mail(client: TestClient, enabled) -> None:
    """
    메일은 요청과 떨어진 전용 스레드에서 나간다. BackgroundTasks 처럼 요청 처리가 발송을 기다리면 같은 연결의 다음 요청이
    발송 시간만큼 늦어져 '메일을 보냈는지'(= 새 이메일인지)가 드러난다(스펙 보완 사항 R1).
    """

    sender = _BlockingSender()
    mail_adapter.set_mail_sender_override(sender)

    try:
        started = time.monotonic()
        response = _send(client)
        elapsed = time.monotonic() - started

        assert response.status_code == 202
        assert elapsed < 2
        # 아직 보내는 중이다.
        assert signup_service.wait_for_mail(timeout=0.2) is False
        assert sender.sent == []
    finally:
        sender.release.set()

    assert signup_service.wait_for_mail()
    assert [mail.to for mail in sender.sent] == [EMAIL]


def test_full_mail_queue_drops_with_log_only(
    client: TestClient, enabled, db, counselor_id, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """
    대기가 차면 메일 일을 넣지 않고 서버 로그 경고만 남긴다. 새 이메일 · 있는 계정이 요청 처리에서 같은 일만 하게
    감사 기록은 쓰지 않는다(Codex #139 M1 — 처음엔 새 이메일만 MailQueueFull 감사 기록을 썼다).
    """

    caplog.set_level(logging.WARNING)
    monkeypatch.setattr(signup_service, "MAIL_QUEUE_LIMIT", 0)

    assert _send(client).status_code == 202
    assert _send(client, "counselor.a@ispot.example.com").status_code == 202
    assert _mails() == []

    assert [log.status for log in _audits(db, AuditAction.SIGNUP_CODE_SENT)] == ["SUCCESS", "SUCCESS"]
    assert caplog.text.count("회원가입 메일 대기가 가득 차") == 2


def test_secrets_never_reach_logs_audit_or_errors(
    client: TestClient, enabled, admin_headers, db, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    bodies: List[str] = []

    def keep(response):
        bodies.append(response.text)

        return response

    keep(_send(client))
    code = _last_code()
    keep(_send(client))  # 60초 전 → 429
    keep(_verify(client, WRONG_CODE))
    verified = _verify(client, code)
    token = verified.json()["data"]["verification_token"]
    keep(_submit(client, token, password="abc"))
    keep(_submit(client, token))
    keep(_submit(client, token))  # 이미 씀
    keep(client.get(BASE, headers=admin_headers))

    request_id = _request_row(db).id
    keep(client.post(f"{BASE}/{request_id}/approve", json={"role": "COUNSELOR"}, headers=admin_headers))

    db.expire_all()
    details = str([(log.detail, log.error_code) for log in db.scalars(select(AuditLog))])
    secrets_ = [code, token, PASSWORD]

    for secret in secrets_:
        assert secret not in caplog.text
        assert secret not in details
        assert all(secret not in body for body in bodies)

    # 이메일 · 이름은 관리자 목록 응답에만 나간다. 로그 · 감사 기록에는 없다.
    for value in (EMAIL, NAME):
        assert value not in caplog.text
        assert value not in details


# =========================================================
# 발송기
# =========================================================

class _FakeSesClient:
    def __init__(self, error: Exception = None) -> None:
        self.calls: List[dict] = []
        self.error = error

    def send_email(self, **kwargs) -> dict:
        self.calls.append(kwargs)

        if self.error is not None:
            raise self.error

        return {"MessageId": "x"}


class _ClientError(Exception):
    """botocore ClientError 와 같은 모양(response 사전)."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.response = {"Error": {"Code": code, "Message": message}}


def test_ses_sender_builds_simple_utf8_message(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "SES_FROM_ADDRESS", "I-SPOT <noreply@ispot.example.org>")
    client = _FakeSesClient()

    SesMailSender(client=client).send(MailMessage(to=EMAIL, subject="제목", body="본문 123456"))

    assert client.calls == [
        {
            "FromEmailAddress": "I-SPOT <noreply@ispot.example.org>",
            "Destination": {"ToAddresses": [EMAIL]},
            "Content": {
                "Simple": {
                    "Subject": {"Data": "제목", "Charset": "UTF-8"},
                    "Body": {"Text": {"Data": "본문 123456", "Charset": "UTF-8"}},
                }
            },
        }
    ]


def test_ses_failure_keeps_only_error_code() -> None:
    client = _FakeSesClient(_ClientError("MessageRejected", f"Email address is not verified: {EMAIL}"))

    with pytest.raises(MailSendError) as caught:
        SesMailSender(client=client).send(MailMessage(to=EMAIL, subject="s", body="b"))

    assert caught.value.cause == "MessageRejected"
    assert EMAIL not in str(caught.value)
    assert caught.value.__cause__ is None
    assert caught.value.__suppress_context__ is True


def test_ses_client_uses_region_and_timeouts(monkeypatch: pytest.MonkeyPatch) -> None:
    boto3 = pytest.importorskip("boto3")
    seen: Dict = {}

    def fake_client(service: str, **kwargs):
        seen["service"] = service
        seen.update(kwargs)

        return _FakeSesClient()

    monkeypatch.setattr(boto3, "client", fake_client)
    monkeypatch.setattr(settings, "SES_REGION", "ap-northeast-2")
    monkeypatch.setattr(settings, "SES_FROM_ADDRESS", "noreply@ispot.example.org")

    SesMailSender().send(MailMessage(to=EMAIL, subject="s", body="b"))

    assert seen["service"] == "sesv2"
    assert seen["region_name"] == "ap-northeast-2"
    assert seen["config"].connect_timeout == 5
    assert seen["config"].read_timeout == 10
    # 접근 키를 코드에서 넘기지 않는다(EC2 역할).
    assert "aws_access_key_id" not in seen
    assert "aws_secret_access_key" not in seen


def test_ses_client_quiets_botocore_debug_logs(monkeypatch: pytest.MonkeyPatch) -> None:
    """LOG_LEVEL=DEBUG 여도 botocore 가 요청 내용(받는 주소 · 인증번호)을 찍지 않게 WARNING 으로 올린다(보완 사항 R2)."""

    boto3 = pytest.importorskip("boto3")
    monkeypatch.setattr(boto3, "client", lambda service, **kwargs: _FakeSesClient())
    monkeypatch.setattr(settings, "SES_FROM_ADDRESS", "noreply@ispot.example.org")

    root = logging.getLogger()
    loggers = [logging.getLogger(name) for name in ("botocore", "boto3")]
    saved = [root.level] + [item.level for item in loggers]

    try:
        root.setLevel(logging.DEBUG)

        for item in loggers:
            item.setLevel(logging.NOTSET)

        SesMailSender().send(MailMessage(to=EMAIL, subject="s", body="b"))

        assert all(item.getEffectiveLevel() >= logging.WARNING for item in loggers)
    finally:
        root.setLevel(saved[0])

        for item, level in zip(loggers, saved[1:], strict=True):
            item.setLevel(level)


def test_provider_switch(monkeypatch: pytest.MonkeyPatch) -> None:
    assert mail_adapter.get_mail_sender().name == "fake"

    monkeypatch.setattr(settings, "MAIL_PROVIDER", "console")
    assert mail_adapter.get_mail_sender().name == "console"

    monkeypatch.setattr(settings, "MAIL_PROVIDER", "ses")
    assert mail_adapter.get_mail_sender().name == "ses"


def test_console_sender_prints_to_stdout(capsys: pytest.CaptureFixture) -> None:
    mail_adapter.ConsoleMailSender().send(MailMessage(to=EMAIL, subject="제목", body="인증번호: 123456"))

    assert "123456" in capsys.readouterr().out


def test_fake_sender_does_not_log(client: TestClient, enabled, caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG)

    assert _send(client).status_code == 202
    assert len(_mails()) == 1
    assert EMAIL not in caplog.text
    assert _last_code() not in caplog.text
