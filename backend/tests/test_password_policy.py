# 비밀번호 규칙(app/core/password_policy.py)과 비밀번호 변경 창구 테스트.
#
# 규칙은 "새로 정하는 비밀번호" 에만 적용한다. 로그인 요청은 검사하지 않는다.
# (이미 있는 계정이 전부 잠기는 것을 막기 위해서다.)

import uuid
from typing import Dict

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import settings
from app.core.enums import AuditAction
from app.core.password_policy import check_password, generate_password
from app.models.audit_log import AuditLog
from tests.conftest import COUNSELOR_PASSWORD

COUNSELOR_EMAIL = "counselor.a@ispot.example.com"
NEW_PASSWORD = "Violet-Ferry-62"

# 12자 이상 + 3종 이상을 만족하는 값들
OK_12 = "Ab3-xyzPmQvt"
OK_3_CLASSES = "Manzoburitakoy7"
OK_PASSPHRASE = "manzoburitakoyhanabira"
KO_24 = "가나다라마바사아자차카타파하거너더러머버서어저처"


# =========================================================
# 규칙 단위
# =========================================================

def test_minimum_length() -> None:
    assert check_password("Ab3-xyzPmQv") != []  # 11자
    assert check_password(OK_12) == []  # 12자


def test_three_classes_required() -> None:
    assert check_password("manzoburitakoy7") != []  # 소문자 + 숫자 = 2종
    assert check_password(OK_3_CLASSES) == []  # 대문자 추가 = 3종


def test_long_passphrase_is_exempt_from_classes() -> None:
    assert len(OK_PASSPHRASE) >= settings.PASSWORD_PASSPHRASE_LENGTH
    assert check_password(OK_PASSPHRASE) == []


def test_korean_passphrase_and_byte_limit() -> None:
    assert len(KO_24) == 24
    assert len(KO_24.encode("utf-8")) == 72

    assert check_password(KO_24) == []
    assert check_password(KO_24 + "커") != []  # 75바이트 — bcrypt 가 잘라내는 구간


def test_hangul_counts_as_a_character_class() -> None:
    """한글도 한 종류로 센다. 안 세면 한글 비밀번호는 20자 미만에서 모두 거부된다."""

    assert check_password("가나다라마바사아자차1!") == []  # 한글 + 숫자 + 특수 = 3종


def test_hangul_only_password_still_needs_classes() -> None:
    assert check_password("가나다라마바사아자차카타") != []  # 한글만 = 1종


def test_korean_name_is_blocked() -> None:
    assert check_password("최민규-Pwqmxz82!") == []
    assert check_password("최민규-Pwqmxz82!", name="최민규") != []


def test_mixed_case_repetition_is_blocked() -> None:
    assert check_password("Vx-AAaa-Poqm9!") != []


def test_generate_password_follows_min_length_setting(monkeypatch) -> None:
    monkeypatch.setattr(settings, "PASSWORD_MIN_LENGTH", 20)

    password = generate_password()

    assert len(password) >= 20
    assert check_password(password) == []


def test_email_id_is_blocked() -> None:
    assert check_password("Counselor-77x!") == []
    assert check_password("Counselor-77x!", email=COUNSELOR_EMAIL) != []


def test_name_is_blocked() -> None:
    assert check_password("Mingyu-Choe-88!", name="Mingyu Choe") != []


def test_service_name_is_blocked() -> None:
    assert check_password("Ispot-Backend-7!") != []


def test_common_password_is_blocked() -> None:
    assert check_password("Password-77x!") != []
    assert check_password("MyQwerty-88x!") != []


def test_repeated_characters_are_blocked() -> None:
    assert check_password("Vaaaa-Poqm9!") != []


def test_sequential_characters_are_blocked() -> None:
    assert check_password("Vx-1234-Poqm!") != []  # 숫자 연속
    assert check_password("Vx-asdf-Poqm9!") != []  # 키보드 연속
    assert check_password("Vx-hijk-Poqm9!") != []  # 알파벳 연속


def test_reason_is_returned_for_each_violation() -> None:
    reasons = check_password("abc")

    assert len(reasons) >= 1
    assert all(isinstance(reason, str) and reason for reason in reasons)


def test_min_classes_setting_is_honored(monkeypatch) -> None:
    monkeypatch.setattr(settings, "PASSWORD_MIN_CLASSES", 4)

    assert check_password(OK_3_CLASSES) != []
    assert check_password(OK_3_CLASSES + "!") == []


def test_generated_password_always_passes_policy() -> None:
    for _ in range(20):
        password = generate_password()

        assert len(password) >= settings.PASSWORD_MIN_LENGTH
        assert check_password(password) == []


# =========================================================
# 계정 생성 (관리자)
# =========================================================

def _create_user_payload(password: str, email: str = "new@ispot.example.com") -> Dict[str, str]:
    return {"email": email, "password": password, "name": "신규", "role": "COUNSELOR"}


def test_create_user_rejects_weak_password(client: TestClient, admin_headers) -> None:
    response = client.post(
        "/api/v1/auth/users",
        json=_create_user_payload("manzoburitakoy7"),
        headers=admin_headers,
    )

    assert response.status_code == 422

    error = response.json()["error"]

    assert error["code"] == "WEAK_PASSWORD"
    assert error["details"]["reasons"]
    assert "manzoburitakoy7" not in response.text  # 원문이 응답에 없다


def test_create_user_rejects_password_containing_email_id(
    client: TestClient, admin_headers
) -> None:
    response = client.post(
        "/api/v1/auth/users",
        json=_create_user_payload("Sunflower-9!", email="sunflower@ispot.example.com"),
        headers=admin_headers,
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "WEAK_PASSWORD"


def test_create_user_short_password_stays_validation_error(
    client: TestClient, admin_headers
) -> None:
    """8자 미만은 기존 계약대로 VALIDATION_ERROR 로 남긴다."""

    response = client.post(
        "/api/v1/auth/users",
        json=_create_user_payload("123"),
        headers=admin_headers,
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_create_user_accepts_compliant_password(client: TestClient, admin_headers) -> None:
    response = client.post(
        "/api/v1/auth/users",
        json=_create_user_payload(NEW_PASSWORD),
        headers=admin_headers,
    )

    assert response.status_code == 201

    login = client.post(
        "/api/v1/auth/login",
        json={"email": "new@ispot.example.com", "password": NEW_PASSWORD},
    )

    assert login.status_code == 200


# =========================================================
# 비밀번호 변경 (본인)
# =========================================================

def test_change_password_requires_login(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/me/password",
        json={"current_password": COUNSELOR_PASSWORD, "new_password": NEW_PASSWORD},
    )

    assert response.status_code == 401


def test_change_password_rejects_wrong_current_password(
    client: TestClient, counselor_headers
) -> None:
    response = client.post(
        "/api/v1/auth/me/password",
        json={"current_password": "Wrong-Current-11", "new_password": NEW_PASSWORD},
        headers=counselor_headers,
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_CREDENTIALS"


def test_change_password_rejects_weak_new_password(
    client: TestClient, counselor_headers
) -> None:
    response = client.post(
        "/api/v1/auth/me/password",
        json={"current_password": COUNSELOR_PASSWORD, "new_password": "manzoburitakoy7"},
        headers=counselor_headers,
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "WEAK_PASSWORD"


def test_change_password_rejects_same_password(
    client: TestClient, counselor_headers
) -> None:
    response = client.post(
        "/api/v1/auth/me/password",
        json={"current_password": COUNSELOR_PASSWORD, "new_password": COUNSELOR_PASSWORD},
        headers=counselor_headers,
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "SAME_PASSWORD"


def test_change_password_rejects_password_containing_own_email(
    client: TestClient, counselor_headers
) -> None:
    response = client.post(
        "/api/v1/auth/me/password",
        json={"current_password": COUNSELOR_PASSWORD, "new_password": "Counselor-77x!"},
        headers=counselor_headers,
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "WEAK_PASSWORD"


def test_change_password_succeeds_and_old_password_stops_working(
    client: TestClient, counselor_headers
) -> None:
    response = client.post(
        "/api/v1/auth/me/password",
        json={"current_password": COUNSELOR_PASSWORD, "new_password": NEW_PASSWORD},
        headers=counselor_headers,
    )

    assert response.status_code == 204
    assert response.text == ""

    new_login = client.post(
        "/api/v1/auth/login",
        json={"email": COUNSELOR_EMAIL, "password": NEW_PASSWORD},
    )

    assert new_login.status_code == 200

    old_login = client.post(
        "/api/v1/auth/login",
        json={"email": COUNSELOR_EMAIL, "password": COUNSELOR_PASSWORD},
    )

    assert old_login.status_code == 401


def test_change_password_writes_audit_log_without_password(
    client: TestClient, counselor_headers, counselor_id: uuid.UUID, db
) -> None:
    client.post(
        "/api/v1/auth/me/password",
        json={"current_password": COUNSELOR_PASSWORD, "new_password": NEW_PASSWORD},
        headers=counselor_headers,
    )

    log = db.scalar(
        select(AuditLog).where(AuditLog.action == AuditAction.PASSWORD_CHANGED)
    )

    assert log is not None
    assert log.actor_id == counselor_id
    assert log.entity_type == "User"
    assert NEW_PASSWORD not in str(log.detail)
    assert COUNSELOR_PASSWORD not in str(log.detail)


def test_login_does_not_apply_password_policy(client: TestClient, counselor_id) -> None:
    """규칙은 새로 정할 때만 적용한다. 기존 계정 로그인은 막지 않는다."""

    response = client.post(
        "/api/v1/auth/login",
        json={"email": COUNSELOR_EMAIL, "password": COUNSELOR_PASSWORD},
    )

    assert response.status_code == 200


def test_change_password_detects_same_korean_password(
    client: TestClient, counselor_headers
) -> None:
    """한글 비밀번호는 문자열 비교 함수가 str 로 받지 못한다. bytes 로 비교하는지 확인한다."""

    first = client.post(
        "/api/v1/auth/me/password",
        json={"current_password": COUNSELOR_PASSWORD, "new_password": KO_24},
        headers=counselor_headers,
    )

    assert first.status_code == 204

    second = client.post(
        "/api/v1/auth/me/password",
        json={"current_password": KO_24, "new_password": KO_24},
        headers=counselor_headers,
    )

    assert second.status_code == 422
    assert second.json()["error"]["code"] == "SAME_PASSWORD"
