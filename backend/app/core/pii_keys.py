# 개인 식별 정보 키 읽기(설정 검사 · app/core/pii_crypto.py 가 함께 쓴다).
#
# 설정(config.py)이 이 모듈을 불러 검사하므로 여기서는 settings 를 부르지 않는다(순환 import).
# 오류 문구에 키 값을 넣지 않는다 — 서버 시작 실패는 로그에 그대로 남는다.

import base64
import binascii
import re
from typing import Dict, Tuple

KEY_BYTES = 32

# 키 이름은 저장 모양(v1.<키 이름>.…)에 그대로 들어가므로 '.' 과 ',' · ':' 을 쓰지 않는다.
_KEY_ID = re.compile(r"[A-Za-z0-9_-]{1,16}")


class PiiKeyError(ValueError):
    """키 설정 형식 오류. 문구에는 어느 설정이 왜 틀렸는지만 적는다."""


def decode_key(value: str, setting: str) -> bytes:
    """base64(표준 · URL 안전, '=' 생략 가능) 32바이트 키."""

    text = value.strip()
    padded = text + "=" * (-len(text) % 4)

    try:
        raw = base64.b64decode(padded.replace("-", "+").replace("_", "/"), validate=True)
    except (binascii.Error, ValueError) as error:
        raise PiiKeyError(f"{setting} 의 키가 base64 가 아닙니다.") from error

    if len(raw) != KEY_BYTES:
        raise PiiKeyError(f"{setting} 의 키는 {KEY_BYTES}바이트여야 합니다.")

    return raw


def parse_key_ring(value: str) -> Tuple[str, Dict[str, bytes]]:
    """PII_ENCRYPTION_KEYS → (암호화에 쓸 첫 키 이름, {키 이름: 키}). 이름이 겹치면 오류."""

    ring: Dict[str, bytes] = {}
    active = ""

    for part in value.split(","):
        part = part.strip()

        if not part:
            continue

        key_id, sep, encoded = part.partition(":")

        if not sep or not _KEY_ID.fullmatch(key_id):
            raise PiiKeyError(
                "PII_ENCRYPTION_KEYS 는 '키이름:base64키' 를 쉼표로 이은 값이어야 합니다"
                "(키 이름은 영문 · 숫자 · '-' · '_' 16자 이내)."
            )

        if key_id in ring:
            raise PiiKeyError("PII_ENCRYPTION_KEYS 에 같은 키 이름이 두 번 있습니다.")

        ring[key_id] = decode_key(encoded, "PII_ENCRYPTION_KEYS")
        active = active or key_id

    if not ring:
        raise PiiKeyError("PII_ENCRYPTION_KEYS 가 비어 있습니다.")

    return active, ring
