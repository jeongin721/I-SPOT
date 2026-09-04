# 인증 / 계정 관리 테스트.
# 자유 회원가입이 없고, 계정 생성이 관리자 전용임을 확인한다.

import uuid

from fastapi.testclient import TestClient

from tests.conftest import ADMIN_PASSWORD, COUNSELOR_PASSWORD


def test_login_success(client: TestClient, counselor_id: uuid.UUID) -> None:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "counselor.a@ispot.example.com", "password": COUNSELOR_PASSWORD},
    )

    assert response.status_code == 200

    data = response.json()["data"]

    assert data["token_type"] == "bearer"
    assert data["access_token"]
    assert data["user"]["role"] == "COUNSELOR"
    # 비밀번호 관련 정보는 응답에 포함되지 않아야 한다.
    assert "hashed_password" not in data["user"]


def test_login_wrong_password_returns_error_contract(
    client: TestClient, counselor_id: uuid.UUID
) -> None:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "counselor.a@ispot.example.com", "password": "wrong-password"},
    )

    assert response.status_code == 401

    body = response.json()

    assert "data" not in body
    assert body["error"]["code"] == "INVALID_CREDENTIALS"
    assert body["error"]["message"]


def test_login_unknown_email_does_not_reveal_existence(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "nobody@ispot.example.com", "password": "whatever-1234"},
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_CREDENTIALS"


def test_login_invalid_email_format_is_validation_error(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "not-an-email", "password": "whatever-1234"},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_me_requires_token(client: TestClient) -> None:
    response = client.get("/api/v1/auth/me")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


def test_me_rejects_invalid_token(client: TestClient) -> None:
    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer not-a-real-token"},
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


def test_me_returns_current_user(client: TestClient, counselor_headers) -> None:
    response = client.get("/api/v1/auth/me", headers=counselor_headers)

    assert response.status_code == 200
    assert response.json()["data"]["email"] == "counselor.a@ispot.example.com"


def test_no_public_signup_endpoint(client: TestClient) -> None:
    """자유 회원가입 경로가 존재하지 않아야 한다."""

    response = client.post(
        "/api/v1/auth/register",
        json={"email": "new@ispot.example.com", "password": "password-1234", "name": "신규"},
    )

    assert response.status_code == 404


def test_counselor_cannot_create_user(client: TestClient, counselor_headers) -> None:
    response = client.post(
        "/api/v1/auth/users",
        json={
            "email": "new@ispot.example.com",
            "password": "password-1234",
            "name": "신규",
            "role": "COUNSELOR",
        },
        headers=counselor_headers,
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


def test_admin_can_create_user_and_new_user_can_login(
    client: TestClient, admin_headers
) -> None:
    response = client.post(
        "/api/v1/auth/users",
        json={
            "email": "counselor.c@ispot.example.com",
            "password": "password-1234",
            "name": "상담사C",
            "role": "COUNSELOR",
        },
        headers=admin_headers,
    )

    assert response.status_code == 201
    assert response.json()["data"]["email"] == "counselor.c@ispot.example.com"

    login = client.post(
        "/api/v1/auth/login",
        json={"email": "counselor.c@ispot.example.com", "password": "password-1234"},
    )

    assert login.status_code == 200


def test_admin_cannot_create_duplicate_email(client: TestClient, admin_headers) -> None:
    payload = {
        "email": "dup@ispot.example.com",
        "password": "password-1234",
        "name": "중복",
        "role": "COUNSELOR",
    }

    assert client.post("/api/v1/auth/users", json=payload, headers=admin_headers).status_code == 201

    second = client.post("/api/v1/auth/users", json=payload, headers=admin_headers)

    assert second.status_code == 409
    assert second.json()["error"]["code"] == "DUPLICATE_RESOURCE"


def test_short_password_is_rejected(client: TestClient, admin_headers) -> None:
    response = client.post(
        "/api/v1/auth/users",
        json={
            "email": "weak@ispot.example.com",
            "password": "123",
            "name": "약한비밀번호",
            "role": "COUNSELOR",
        },
        headers=admin_headers,
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_admin_login_returns_admin_role(client: TestClient, admin_id: uuid.UUID) -> None:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@ispot.example.com", "password": ADMIN_PASSWORD},
    )

    assert response.status_code == 200
    assert response.json()["data"]["user"]["role"] == "ADMIN"
