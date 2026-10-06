# 비밀번호 규칙(app/core/password_policy.py)과 비밀번호 변경 창구 테스트.
#
# 규칙은 "새로 정하는 비밀번호" 에만 적용한다. 로그인 요청은 검사하지 않는다.
# (이미 있는 계정이 전부 잠기는 것을 막기 위해서다.)

import unicodedata
import uuid
from typing import Dict

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import select

from app.core.config import Settings, settings
from app.core.enums import AuditAction
from app.core.password_policy import check_password, generate_password
from app.models.audit_log import AuditLog
from tests.conftest import COUNSELOR_PASSWORD

COUNSELOR_EMAIL = "counselor.a@ispot.example.com"
NEW_PASSWORD = "Violet-Ferry-62"

# 8자 이상 + 글자 · 숫자 · 특수문자를 모두 갖춘 값들
OK_MIN = "Ab3-xyzQ"
OK_3_CLASSES = "Manzoburitakoy7!"
OK_PASSPHRASE = "manzoburitakoyhanabira"
KO_24 = "가나다라마바사아자차카타파하거너더러머버서어저처"

# 한글 23자(69바이트) + 숫자 · 특수문자 3자 = 72바이트. bcrypt 가 받는 최대 길이다.
KO_72 = "가나다라마바사아자차카타파하거너더러머버서어저" + "7!?"

SEQUENCE_REASON = "연속된 문자"
BANNED_WORD_REASON = "쉽게 짐작할 수 있는 단어"


def _has_reason(password: str, keyword: str) -> bool:
    return any(keyword in reason for reason in check_password(password))


# =========================================================
# 규칙 단위
# =========================================================

def test_minimum_length() -> None:
    assert check_password("Ab3-xyz") != []  # 7자
    assert check_password(OK_MIN) == []  # 8자 (팀 결정 기준)


def test_all_three_classes_required() -> None:
    """팀 결정은 영문 · 숫자 · 특수문자를 모두 포함하는 것이다."""

    assert check_password("manzoburitakoy7") != []  # 글자 + 숫자 = 2종
    assert check_password("Abcdefgh1") != []  # 대소문자를 나눠 세면 통과하던 값
    assert check_password(OK_3_CLASSES) == []  # 특수문자까지 = 3종


def test_long_password_is_not_exempt_from_classes_by_default(monkeypatch) -> None:
    """팀 결정(8자 이상, 영문 · 숫자 · 특수문자 모두)에 긴 비밀번호 면제는 없다."""

    assert Settings(_env_file=None).PASSWORD_PASSPHRASE_LENGTH == 0

    monkeypatch.setattr(settings, "PASSWORD_PASSPHRASE_LENGTH", 0)

    assert check_password(OK_PASSPHRASE) != []  # 22자, 글자만
    assert check_password(KO_24) != []  # 한글 24자, 글자만
    assert not any("섞지 않아도" in reason for reason in check_password(OK_PASSPHRASE))


def test_passphrase_exemption_applies_only_when_configured(monkeypatch) -> None:
    monkeypatch.setattr(settings, "PASSWORD_PASSPHRASE_LENGTH", 20)

    assert check_password(OK_PASSPHRASE) == []
    assert any("20자 이상이면" in reason for reason in check_password("manzoburitakoy7"))


@pytest.mark.parametrize("value", [0, 12, 20, 72])
def test_passphrase_length_setting_accepts_off_or_12_to_72(value: int) -> None:
    configured = Settings(_env_file=None, PASSWORD_PASSPHRASE_LENGTH=value)

    assert configured.PASSWORD_PASSPHRASE_LENGTH == value


@pytest.mark.parametrize("value", [-1, 1, 8, 11, 73])
def test_passphrase_length_setting_rejects_other_values(value: int) -> None:
    with pytest.raises(ValidationError, match="PASSWORD_PASSPHRASE_LENGTH"):
        Settings(_env_file=None, PASSWORD_PASSPHRASE_LENGTH=value)


def test_korean_byte_limit() -> None:
    assert len(KO_72.encode("utf-8")) == 72

    assert check_password(KO_72) == []
    assert check_password(KO_72 + "커") != []  # 75바이트 — bcrypt 가 잘라내는 구간


def test_hangul_counts_as_a_letter() -> None:
    """한글도 글자로 센다. 안 세면 한글 + 숫자 + 특수문자 비밀번호가 모두 거부된다."""

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


def test_hangul_notation_does_not_change_the_result() -> None:
    """같은 한글도 표기(NFC/NFD)가 다르면 byte 가 달라진다. 규칙은 같게 봐야 한다."""

    nfc = "가나다라마바사아자차1!"
    nfd = unicodedata.normalize("NFD", nfc)

    assert nfc.encode("utf-8") != nfd.encode("utf-8")
    assert check_password(nfc) == check_password(nfd) == []


def test_leading_or_trailing_space_is_blocked() -> None:
    assert check_password(" Rainy-Harbor-73") != []
    assert check_password("Rainy-Harbor-73 ") != []


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


@pytest.mark.parametrize(
    "password",
    [
        "P@ssw0rd!",  # @→a, 0→o
        "Passw0rd!",  # 0→o
        "4dm1n-Tiger-9",  # 4→a, 1→i
        "$ecret-Tiger-9",  # $→s
        "H3ll0-Tiger-9",  # 3→e, 0→o
        "R007-Tiger-9!",  # 0→o, 7→t
        "Mas7er-Tiger-9!",  # 7→t
    ],
)
def test_common_password_with_symbol_substitution_is_blocked(password: str) -> None:
    """흔한 기호 치환(@→a, 0→o 같은 것)을 되돌려서도 금지 단어를 찾는다."""

    assert _has_reason(password, BANNED_WORD_REASON)


def test_symbol_substitution_does_not_block_ordinary_password() -> None:
    assert check_password(NEW_PASSWORD) == []
    assert check_password("Rainy-Harbor-73") == []


def test_repeated_characters_are_blocked() -> None:
    assert check_password("Vaaaa-Poqm9!") != []


def test_sequential_characters_are_blocked() -> None:
    assert check_password("Vx-1234-Poqm!") != []  # 숫자 연속
    assert check_password("Vx-asdf-Poqm9!") != []  # 키보드 연속
    assert check_password("Vx-hijk-Poqm9!") != []  # 알파벳 연속


@pytest.mark.parametrize(
    "password",
    [
        "1q2w3e4r!",  # 숫자 · 영문 교차
        "q1w2e3r4!",  # 영문 · 숫자 교차
        "Vx-r4e3w2-Poqm!",  # 교차 배열을 거꾸로
        "ㅂㅈㄷㄱ12!@",  # 한글 자판 상태로 친 qwer
        "ㅁㄴㅇㄹ-Poqm9!",  # 한글 자판 상태로 친 asdf
        "ㅋㅌㅊㅍ-Poqm9!",  # 한글 자판 상태로 친 zxcv
    ],
)
def test_keyboard_patterns_are_blocked(password: str) -> None:
    assert _has_reason(password, SEQUENCE_REASON)


def test_reason_is_returned_for_each_violation() -> None:
    reasons = check_password("abc")

    assert len(reasons) >= 1
    assert all(isinstance(reason, str) and reason for reason in reasons)


def test_min_classes_setting_is_honored(monkeypatch) -> None:
    monkeypatch.setattr(settings, "PASSWORD_MIN_CLASSES", 2)

    assert check_password("manzoburitakoy7") == []  # 2종만 요구하면 통과한다


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


def test_create_user_short_password_is_weak_password(
    client: TestClient, admin_headers
) -> None:
    """8자 미만도 규칙 위반이다. 다른 위반과 같이 WEAK_PASSWORD 와 한국어 사유로 알린다."""

    response = client.post(
        "/api/v1/auth/users",
        json=_create_user_payload("Ab3-xyz"),
        headers=admin_headers,
    )

    assert response.status_code == 422

    error = response.json()["error"]

    assert error["code"] == "WEAK_PASSWORD"
    assert f"{settings.PASSWORD_MIN_LENGTH}자 이상이어야 합니다." in error["details"]["reasons"]


def test_create_user_empty_password_stays_validation_error(
    client: TestClient, admin_headers
) -> None:
    """빈 값은 규칙을 볼 것도 없이 입력 형식 오류다."""

    response = client.post(
        "/api/v1/auth/users",
        json=_create_user_payload(""),
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
    """
    현재 비밀번호가 틀린 것은 로그인 만료가 아니다.

    Frontend 는 401 을 로그인 만료로 보고 로그인 화면으로 보낸다(client.ts isUnauthorized).
    입력만 틀렸는데 쫓겨나지 않도록 400 으로 알린다.
    """

    response = client.post(
        "/api/v1/auth/me/password",
        json={"current_password": "Wrong-Current-11", "new_password": NEW_PASSWORD},
        headers=counselor_headers,
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_CURRENT_PASSWORD"

    # 로그인은 그대로 유지된다.
    assert client.get("/api/v1/auth/me", headers=counselor_headers).status_code == 200


def test_change_password_short_new_password_is_weak_password(
    client: TestClient, counselor_headers
) -> None:
    response = client.post(
        "/api/v1/auth/me/password",
        json={"current_password": COUNSELOR_PASSWORD, "new_password": "Ab3-xyz"},
        headers=counselor_headers,
    )

    assert response.status_code == 422

    error = response.json()["error"]

    assert error["code"] == "WEAK_PASSWORD"
    assert f"{settings.PASSWORD_MIN_LENGTH}자 이상이어야 합니다." in error["details"]["reasons"]


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


# =========================================================
# 비밀번호 변경 — 현재 비밀번호를 맞혀 보는 것 막기
# =========================================================
#
# 현재 비밀번호를 받는 이유는 토큰만 훔친 사람이 비밀번호를 바꿔 계정을 가져가는 것을 막기
# 위해서다(API_CONTRACT 3절). 이 창구로 현재 비밀번호를 끝없이 맞혀 볼 수 있으면 그 목적이 깨진다.

ME_PASSWORD = "/api/v1/auth/me/password"
WRONG_CURRENT = "Wrong-Current-11"


def _password_failures(db) -> list:
    return db.scalars(
        select(AuditLog).where(
            AuditLog.action == AuditAction.PASSWORD_CHANGED,
            AuditLog.status == "FAILURE",
        )
    ).all()


def test_change_password_failure_is_audited(
    client: TestClient, counselor_headers, counselor_id: uuid.UUID, db
) -> None:
    response = client.post(
        ME_PASSWORD,
        json={"current_password": WRONG_CURRENT, "new_password": NEW_PASSWORD},
        headers=counselor_headers,
    )

    assert response.status_code == 400

    failures = _password_failures(db)

    assert len(failures) == 1
    assert failures[0].actor_id == counselor_id
    assert failures[0].entity_id == counselor_id
    assert failures[0].error_code == "INVALID_CURRENT_PASSWORD"
    assert WRONG_CURRENT not in str(failures[0].detail)
    assert NEW_PASSWORD not in str(failures[0].detail)


@pytest.mark.parametrize("current", [WRONG_CURRENT, COUNSELOR_PASSWORD])
def test_change_password_answers_rule_errors_before_checking_current_password(
    client: TestClient, counselor_headers, current: str, db
) -> None:
    """
    새 비밀번호 규칙 위반 · 같은 비밀번호는 현재 비밀번호가 맞든 틀리든 같은 422 다.

    현재 비밀번호를 먼저 확인하면 "맞으면 422, 틀리면 400" 이 되어, 비밀번호를 바꾸지 않고도
    정답인지 알아내는 수단이 된다. 이렇게 걸러진 요청은 현재 비밀번호를 확인하지 않았으므로
    실패 횟수에도 넣지 않는다.
    """

    weak = client.post(
        ME_PASSWORD,
        json={"current_password": current, "new_password": "abc"},
        headers=counselor_headers,
    )

    assert weak.status_code == 422
    assert weak.json()["error"]["code"] == "WEAK_PASSWORD"

    same = client.post(
        ME_PASSWORD,
        json={"current_password": current, "new_password": current},
        headers=counselor_headers,
    )

    assert same.status_code == 422
    assert same.json()["error"]["code"] == "SAME_PASSWORD"

    assert _password_failures(db) == []


def test_repeated_wrong_current_password_ends_the_session(
    client: TestClient,
    counselor_headers,
    counselor_id: uuid.UUID,
    db,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    현재 비밀번호를 정해진 횟수(LOGIN_MAX_FAILURES)만큼 틀리면 그 계정의 토큰을 모두 끊는다.

    계정은 잠그지 않는다. 다시 로그인하면 되고, 로그인 쪽은 이미 실패 잠금이 있다.
    그래서 토큰 하나로 맞혀 볼 수 있는 횟수가 정해진 횟수로 묶인다.
    """

    monkeypatch.setattr(settings, "LOGIN_MAX_FAILURES", 3)
    wrong = {"current_password": WRONG_CURRENT, "new_password": NEW_PASSWORD}

    for _ in range(2):
        response = client.post(ME_PASSWORD, json=wrong, headers=counselor_headers)

        assert response.status_code == 400
        assert response.json()["error"]["code"] == "INVALID_CURRENT_PASSWORD"

    last = client.post(ME_PASSWORD, json=wrong, headers=counselor_headers)

    assert last.status_code == 401
    assert last.json()["error"]["code"] == "UNAUTHORIZED"

    # 토큰은 끊겼다. 끊긴 뒤에는 현재 비밀번호를 확인하지 않는다.
    assert client.get("/api/v1/auth/me", headers=counselor_headers).status_code == 401
    assert client.post(ME_PASSWORD, json=wrong, headers=counselor_headers).status_code == 401

    revoked = db.scalars(select(AuditLog).where(AuditLog.action == AuditAction.LOGOUT_ALL)).all()

    assert len(revoked) == 1
    assert revoked[0].actor_id == counselor_id
    assert revoked[0].entity_id == counselor_id

    # 계정은 잠기지 않는다. 다시 로그인하면 횟수가 처음부터 다시 센다.
    login = client.post(
        "/api/v1/auth/login",
        json={"email": COUNSELOR_EMAIL, "password": COUNSELOR_PASSWORD},
    )

    assert login.status_code == 200

    fresh = {"Authorization": f"Bearer {login.json()['data']['access_token']}"}

    assert client.post(ME_PASSWORD, json=wrong, headers=fresh).status_code == 400
    assert len(_password_failures(db)) == 4


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
        json={"current_password": COUNSELOR_PASSWORD, "new_password": KO_72},
        headers=counselor_headers,
    )

    assert first.status_code == 204

    # 비밀번호를 바꾸면 이전 Token 이 무효가 되므로 다시 로그인한다.
    relogin = client.post(
        "/api/v1/auth/login",
        json={"email": COUNSELOR_EMAIL, "password": KO_72},
    )

    assert relogin.status_code == 200

    headers = {"Authorization": f"Bearer {relogin.json()['data']['access_token']}"}

    second = client.post(
        "/api/v1/auth/me/password",
        json={"current_password": KO_72, "new_password": KO_72},
        headers=headers,
    )

    assert second.status_code == 422
    assert second.json()["error"]["code"] == "SAME_PASSWORD"


def test_korean_password_works_across_notations(
    client: TestClient, counselor_headers
) -> None:
    """NFC 로 바꾼 한글 비밀번호를 NFD 로 입력해도 로그인돼야 한다."""

    changed = client.post(
        "/api/v1/auth/me/password",
        json={"current_password": COUNSELOR_PASSWORD, "new_password": KO_72},
        headers=counselor_headers,
    )

    assert changed.status_code == 204

    login = client.post(
        "/api/v1/auth/login",
        json={
            "email": COUNSELOR_EMAIL,
            "password": unicodedata.normalize("NFD", KO_72),
        },
    )

    assert login.status_code == 200
