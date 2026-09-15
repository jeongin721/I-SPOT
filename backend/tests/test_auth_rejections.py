# 인증 거부 경로 테스트.
#
# 토큰이 없는 경우 외에, 서명은 맞지만 사용자 정보가 잘못됐거나 사용할 수 없는 계정인
# 경우도 거부해야 한다(app/core/deps.py get_current_user).

import uuid
from datetime import datetime, timedelta, timezone

import jwt
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.security import create_access_token
from app.models.user import User

ME = "/api/v1/auth/me"


def _signed(payload: dict) -> dict:
    """서버 키로 서명한 토큰. 서명은 유효하므로 내용 검사만 확인할 수 있다."""

    payload = {"exp": int((datetime.now(timezone.utc) + timedelta(minutes=5)).timestamp()), **payload}
    token = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

    return {"Authorization": f"Bearer {token}"}


def _assert_unauthorized(response) -> None:
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


def test_token_without_subject_is_rejected(client: TestClient) -> None:
    _assert_unauthorized(client.get(ME, headers=_signed({"role": "ADMIN"})))


def test_token_with_malformed_user_id_is_rejected(client: TestClient) -> None:
    _assert_unauthorized(client.get(ME, headers=_signed({"sub": "not-a-uuid"})))


def test_token_for_deleted_user_is_rejected(client: TestClient) -> None:
    _assert_unauthorized(client.get(ME, headers=_signed({"sub": str(uuid.uuid4())})))


def test_token_for_inactive_user_is_forbidden(client: TestClient, counselor_id: uuid.UUID) -> None:
    token = create_access_token(subject=str(counselor_id), role="COUNSELOR")

    with SessionLocal() as db:
        db.get(User, counselor_id).is_active = False
        db.commit()

    response = client.get(ME, headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "INACTIVE_USER"


def test_expired_token_is_rejected(client: TestClient, counselor_id: uuid.UUID) -> None:
    expired = int((datetime.now(timezone.utc) - timedelta(minutes=1)).timestamp())

    _assert_unauthorized(client.get(ME, headers=_signed({"sub": str(counselor_id), "exp": expired})))


def test_token_signed_with_another_key_is_rejected(client: TestClient, counselor_id: uuid.UUID) -> None:
    forged = jwt.encode(
        {"sub": str(counselor_id), "exp": int((datetime.now(timezone.utc) + timedelta(minutes=5)).timestamp())},
        "attacker-controlled-key-0123456789abcdef",
        algorithm="HS256",
    )

    _assert_unauthorized(client.get(ME, headers={"Authorization": f"Bearer {forged}"}))


def test_role_claim_in_token_does_not_grant_admin(
    client: TestClient, counselor_id: uuid.UUID
) -> None:
    """권한은 토큰의 role 이 아니라 DB 의 사용자 역할로 판단한다."""

    headers = _signed({"sub": str(counselor_id), "role": "ADMIN"})

    response = client.get("/api/v1/auth/users", headers=headers)

    assert response.status_code == 403
