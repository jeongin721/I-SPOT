# 개인 식별 정보 칸 암호화(실명 · 생년월일 · 가족 정보, specs case-personal-info-encryption 2절).
#
# AES-256-GCM(cryptography AESGCM). 값마다 새 12바이트 nonce 를 쓰고, 묶음 값(AAD)에 사례 ID 와 칸 이름을 넣어
# 다른 사례 · 다른 칸으로 옮겨 붙인 암호문은 풀리지 않는다(태그 검증 실패).
#
# 저장 모양: v1.<키 이름>.<nonce base64url>.<암호문+태그 base64url>
# 키는 설정(PII_ENCRYPTION_KEYS)에서만 읽는다. 첫 키로 암호화하고, 나머지는 풀기만 한다(키 바꾸기 —
# scripts/reencrypt_personal_info.py 가 모두 첫 키로 다시 암호화한다).
#
# 이름 검색 색인은 HMAC-SHA256(PII_INDEX_KEY, 정규화한 이름). 정확히 같은 이름(공백 무시)만 찾는다.
# 이름은 경우의 수가 적어 색인 키가 새면 이름을 맞혀 볼 수 있으므로 암호화 키와 다른 키를 쓴다(설정이 검사).
#
# 값 · 키를 예외 문구 · 로그에 넣지 않는다.

import base64
import hashlib
import hmac
import os
import unicodedata
import uuid
from functools import lru_cache
from typing import Dict, Optional, Tuple

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.config import settings
from app.core.pii_keys import decode_key, parse_key_ring

FORMAT_VERSION = "v1"
NONCE_BYTES = 12


class PersonalInfoCryptoError(Exception):
    """암호문을 풀 수 없다(키 없음 · 모양 틀림 · 태그 불일치). 문구에 값이 없다."""


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


@lru_cache(maxsize=4)
def _ring(raw: str) -> Tuple[str, Dict[str, bytes]]:
    # 설정이 시작 때 형식을 이미 검사했다. 시험이 설정을 바꾸면 값이 달라 새로 읽는다.
    return parse_key_ring(raw)


@lru_cache(maxsize=4)
def _index_key(raw: str) -> bytes:
    return decode_key(raw, "PII_INDEX_KEY")


def active_key_id() -> str:
    """지금 암호화에 쓰는 키(PII_ENCRYPTION_KEYS 맨 앞)의 이름."""

    return _ring(settings.PII_ENCRYPTION_KEYS)[0]


def aad_for(case_id: uuid.UUID, field: str) -> bytes:
    """사례 · 칸에 묶는 값. 바꾸면 저장된 모든 값을 풀 수 없게 되므로 형식을 고정한다."""

    return f"ispot:case_personal_info:{case_id}:{field}:{FORMAT_VERSION}".encode("utf-8")


def encrypt_text(plaintext: str, *, case_id: uuid.UUID, field: str) -> str:
    key_id, ring = _ring(settings.PII_ENCRYPTION_KEYS)
    nonce = os.urandom(NONCE_BYTES)
    sealed = AESGCM(ring[key_id]).encrypt(nonce, plaintext.encode("utf-8"), aad_for(case_id, field))

    return ".".join((FORMAT_VERSION, key_id, _b64(nonce), _b64(sealed)))


def key_id_of(token: str) -> Optional[str]:
    """저장 값을 만든 키 이름(키 바꾸기 · 오류 기록용). 모양이 틀리면 None."""

    parts = token.split(".")

    return parts[1] if len(parts) == 4 and parts[0] == FORMAT_VERSION else None


def decrypt_text(token: str, *, case_id: uuid.UUID, field: str) -> str:
    parts = token.split(".")

    if len(parts) != 4 or parts[0] != FORMAT_VERSION:
        raise PersonalInfoCryptoError("저장 모양이 틀립니다.")

    _, key_id, nonce_text, sealed_text = parts
    _, ring = _ring(settings.PII_ENCRYPTION_KEYS)
    key = ring.get(key_id)

    if key is None:
        raise PersonalInfoCryptoError("이 값을 만든 키가 설정에 없습니다.")

    try:
        nonce = _unb64(nonce_text)
        sealed = _unb64(sealed_text)
    except (ValueError, TypeError) as error:
        raise PersonalInfoCryptoError("저장 모양이 틀립니다.") from error

    if len(nonce) != NONCE_BYTES:
        raise PersonalInfoCryptoError("저장 모양이 틀립니다.")

    try:
        plain = AESGCM(key).decrypt(nonce, sealed, aad_for(case_id, field))
    except InvalidTag as error:
        raise PersonalInfoCryptoError("암호문이 이 사례 · 칸의 것이 아니거나 바뀌었습니다.") from error

    return plain.decode("utf-8")


def normalize_name(name: str) -> str:
    """검색 색인용: 유니코드 NFC + 모든 공백 제거('김 서윤' = '김서윤')."""

    return "".join(unicodedata.normalize("NFC", name).split())


def name_index(name: str) -> Optional[str]:
    """이름 정확 검색 색인. 정규화하면 빈 글자이면 None."""

    normalized = normalize_name(name)

    if not normalized:
        return None

    digest = hmac.new(_index_key(settings.PII_INDEX_KEY), normalized.encode("utf-8"), hashlib.sha256)

    return digest.hexdigest()
