# 웹 푸시 보내기(RFC 8291 본문 암호화 aes128gcm + RFC 8292 VAPID, 2026-11-19, API_CONTRACT 27절).
#
# pywebpush 는 aiohttp · requests · py-vapid · http-ece 를 함께 끌고 와서, 이미 쓰는 cryptography 와 표준 라이브러리(urllib)로
# 직접 만든다. 하는 일은 셋뿐이다.
#  1. VAPID 서명(ES256 JWT) — 푸시 서비스(애플 · 구글 · 모질라)가 '이 서버가 보낸 것' 을 확인한다.
#  2. 본문 암호화 — 폰이 구독할 때 준 공개키(p256dh) · 비밀(auth)로 암호화한다. 푸시 서비스는 내용을 못 본다.
#  3. POST — 201 · 200 이면 보냄, 404 · 410 이면 그 구독은 없어진 것(호출한 쪽이 지운다).
#
# 키: VAPID_PRIVATE_KEY = P-256 개인키 32바이트를 base64url(패딩 없음)로. scripts/make_vapid_key 가 만든다. 공개키는 개인키에서 계산한다.
import base64
import json
import os
import struct
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlsplit

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

#: 한 레코드 크기(RFC 8188). 본문이 짧아(알림 문구 몇 줄) 레코드 하나로 끝난다.
RECORD_SIZE = 4096
#: 암호화 전 본문 상한. 푸시 서비스 대부분이 4KB 를 받으므로 여유를 둔다.
MAX_PAYLOAD_BYTES = 3000
#: 보낸 뒤 폰이 꺼져 있으면 푸시 서비스가 이만큼 들고 있다가 버린다(초). 30분 전 알림이 늦게 오면 쓸모가 없어 짧게.
DEFAULT_TTL_SECONDS = 15 * 60
#: 한 기기에 보내는 시간 상한. 시험 알림(POST /push/test)은 요청 스레드에서 보내므로 짧게 둔다.
SEND_TIMEOUT_SECONDS = 5


class WebPushError(Exception):
    pass


def b64url_decode(value: str) -> bytes:
    value = value.strip()
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _public_bytes(key: ec.EllipticCurvePublicKey) -> bytes:
    return key.public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)


def load_vapid_private_key(value: str) -> ec.EllipticCurvePrivateKey:
    raw = b64url_decode(value)

    if len(raw) != 32:
        raise WebPushError("VAPID_PRIVATE_KEY 는 32바이트 base64url 이어야 합니다")

    return ec.derive_private_key(int.from_bytes(raw, "big"), ec.SECP256R1())


def vapid_public_key(private_key: ec.EllipticCurvePrivateKey) -> str:
    """브라우저 pushManager.subscribe 의 applicationServerKey 로 주는 값(65바이트 공개키, base64url)."""
    return b64url_encode(_public_bytes(private_key.public_key()))


def new_vapid_private_key() -> str:
    key = ec.generate_private_key(ec.SECP256R1())
    return b64url_encode(key.private_numbers().private_value.to_bytes(32, "big"))


def vapid_authorization(endpoint: str, private_key: ec.EllipticCurvePrivateKey, subject: str, *, now: Optional[float] = None) -> str:
    """Authorization 헤더 값(vapid t=JWT, k=공개키). aud 는 푸시 서비스 주소의 scheme://host."""
    parts = urlsplit(endpoint)
    header = {"typ": "JWT", "alg": "ES256"}
    claims = {"aud": f"{parts.scheme}://{parts.netloc}", "exp": int((now or time.time()) + 12 * 3600), "sub": subject}
    signing_input = (
        b64url_encode(json.dumps(header, separators=(",", ":")).encode())
        + "."
        + b64url_encode(json.dumps(claims, separators=(",", ":")).encode())
    )
    r, s = decode_dss_signature(private_key.sign(signing_input.encode("ascii"), ec.ECDSA(hashes.SHA256())))
    token = signing_input + "." + b64url_encode(r.to_bytes(32, "big") + s.to_bytes(32, "big"))

    return f"vapid t={token}, k={vapid_public_key(private_key)}"


def _hkdf(salt: bytes, ikm: bytes, info: bytes, length: int) -> bytes:
    return HKDF(algorithm=hashes.SHA256(), length=length, salt=salt, info=info).derive(ikm)


def encrypt(payload: bytes, p256dh: str, auth: str, *, salt: Optional[bytes] = None, local_key: Optional[ec.EllipticCurvePrivateKey] = None) -> bytes:
    """RFC 8291 aes128gcm 본문(머리 86바이트 + 암호문). salt · local_key 는 시험에서만 넘긴다."""
    if len(payload) > MAX_PAYLOAD_BYTES:
        raise WebPushError("알림 본문이 너무 깁니다")

    ua_public_bytes = b64url_decode(p256dh)
    auth_secret = b64url_decode(auth)

    if len(ua_public_bytes) != 65 or len(auth_secret) != 16:
        raise WebPushError("구독 키 길이가 맞지 않습니다")

    ua_public = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), ua_public_bytes)
    local_key = local_key or ec.generate_private_key(ec.SECP256R1())
    as_public_bytes = _public_bytes(local_key.public_key())
    salt = salt or os.urandom(16)

    shared = local_key.exchange(ec.ECDH(), ua_public)
    ikm = _hkdf(auth_secret, shared, b"WebPush: info\x00" + ua_public_bytes + as_public_bytes, 32)
    cek = _hkdf(salt, ikm, b"Content-Encoding: aes128gcm\x00", 16)
    nonce = _hkdf(salt, ikm, b"Content-Encoding: nonce\x00", 12)
    # 마지막(유일한) 레코드 표시 0x02.
    ciphertext = AESGCM(cek).encrypt(nonce, payload + b"\x02", None)

    return salt + struct.pack("!IB", RECORD_SIZE, len(as_public_bytes)) + as_public_bytes + ciphertext


# 브라우저 푸시 서비스 호스트(민규 #186). 다른 주소를 받으면 서버가 아무 곳에나 요청을 보내게 된다.
PUSH_HOSTS = ("fcm.googleapis.com", "updates.push.services.mozilla.com")
PUSH_HOST_SUFFIXES = (".push.apple.com", ".notify.windows.com")


def is_push_endpoint(endpoint: str) -> bool:
    """https 이고 호스트가 알려진 푸시 서비스이며 사용자 · 포트를 따로 적지 않은 주소만 받는다."""
    try:
        parts = urlsplit(endpoint)
        host = (parts.hostname or "").lower()
        port = parts.port
    except ValueError:
        return False

    if parts.scheme != "https" or parts.username or parts.password or port not in (None, 443):
        return False

    return host in PUSH_HOSTS or any(host.endswith(suffix) and len(host) > len(suffix) for suffix in PUSH_HOST_SUFFIXES)


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """이동(3xx)을 따라가지 않는다 — 따라가면 Authorization 머리글과 함께 다른 주소로 다시 요청한다(민규 #186)."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        return None


_opener = urllib.request.build_opener(_NoRedirect)


@dataclass
class SendResult:
    status: int

    @property
    def ok(self) -> bool:
        return 200 <= self.status < 300

    @property
    def gone(self) -> bool:
        """구독이 없어졌다(앱 지움 · 알림 끔 · 만료). 지워야 한다."""
        return self.status in (404, 410)

    @property
    def auth_rejected(self) -> bool:
        """푸시 서비스가 서버 키(VAPID)를 거절했다 — 구독 문제가 아니라 서버 설정 문제다."""
        return self.status in (401, 403)


def send(
    endpoint: str,
    p256dh: str,
    auth: str,
    message: dict,
    *,
    private_key: ec.EllipticCurvePrivateKey,
    subject: str,
    ttl: int = DEFAULT_TTL_SECONDS,
    urgency: str = "high",
) -> SendResult:
    """한 구독에 보낸다. 연결 오류는 status 0. 응답 본문은 읽지 않는다(로그에도 남기지 않는다)."""
    if not is_push_endpoint(endpoint):
        raise WebPushError("알려진 푸시 서비스 주소가 아닙니다")

    body = encrypt(json.dumps(message, ensure_ascii=False).encode("utf-8"), p256dh, auth)
    req = urllib.request.Request(
        endpoint,
        data=body,
        method="POST",
        headers={
            "Authorization": vapid_authorization(endpoint, private_key, subject),
            "Content-Encoding": "aes128gcm",
            "Content-Type": "application/octet-stream",
            "TTL": str(ttl),
            "Urgency": urgency,
        },
    )

    try:
        with _opener.open(req, timeout=SEND_TIMEOUT_SECONDS) as res:  # noqa: S310 — 푸시 서비스 호스트만(위에서 확인), 이동 안 따라감
            return SendResult(res.status)
    except urllib.error.HTTPError as error:
        return SendResult(error.code)
    except (urllib.error.URLError, TimeoutError, OSError):
        return SendResult(0)
