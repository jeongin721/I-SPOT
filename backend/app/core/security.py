# 비밀번호 해싱 및 JWT 발급/검증.

import unicodedata
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import bcrypt
import jwt

from app.core.config import settings
from app.core.errors import unauthorized

# bcrypt 는 72 byte 를 초과하는 입력을 처리하지 않는다.
_BCRYPT_MAX_BYTES = 72


def _normalize(password: str) -> bytes:
    """
    저장·검증에 쓸 byte 값.

    한글은 표기 방식이 두 가지(NFC/NFD)라 눈에 같아 보여도 byte 가 다르다.
    한쪽으로 저장하고 다른 쪽으로 입력하면 로그인이 안 되므로 NFC 로 맞춘다.
    ASCII 는 NFC 로 바뀌지 않아 기존 해시에 영향이 없다.
    """

    normalized = unicodedata.normalize("NFC", password)

    return normalized.encode("utf-8")[:_BCRYPT_MAX_BYTES]


def hash_password(password: str) -> str:
    return bcrypt.hashpw(_normalize(password), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(_normalize(password), hashed_password.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def create_access_token(
    subject: str,
    role: str,
    expires_minutes: Optional[int] = None,
) -> str:
    expire_minutes = expires_minutes or settings.ACCESS_TOKEN_EXPIRE_MINUTES
    now = datetime.now(timezone.utc)

    payload: Dict[str, Any] = {
        "sub": subject,
        "role": role,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=expire_minutes)).timestamp()),
    }

    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> Dict[str, Any]:
    try:
        return jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
    except jwt.ExpiredSignatureError as error:
        raise unauthorized("토큰이 만료되었습니다. 다시 로그인해 주세요.") from error
    except jwt.PyJWTError as error:
        raise unauthorized("유효하지 않은 토큰입니다.") from error


def token_expires_in_seconds() -> int:
    return settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
