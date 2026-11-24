# 상담사 앱(폰) 알림 — 웹 푸시(/push, API_CONTRACT 27절, 2026-11-19). 실제 푸시 서비스로는 보내지 않는다(webpush.send 를 바꿔 끼움).
import json
import os
import struct
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import settings
from app.core.enums import ScheduleKind
from app.models.push import PushDelivery, PushSubscription
from app.models.schedule import ScheduleEvent
from app.models.user import User
from app.services import push_service, signup_service, webpush

KST = push_service.LOCAL_TZ


def _keys():
    ua = ec.generate_private_key(ec.SECP256R1())
    pub = ua.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
    auth = os.urandom(16)
    return ua, webpush.b64url_encode(pub), auth, webpush.b64url_encode(auth)


def _sub_body(endpoint: str = "https://fcm.googleapis.com/fcm/send/abc", **prefs):
    _, p256dh, _, auth = _keys()
    return {"endpoint": endpoint, "keys": {"p256dh": p256dh, "auth": auth}, **prefs}


@pytest.fixture(autouse=True)
def _reset_limits():
    signup_service.reset_limits()
    yield
    signup_service.reset_limits()


@pytest.fixture
def push_on(monkeypatch):
    monkeypatch.setattr(settings, "VAPID_PRIVATE_KEY", webpush.new_vapid_private_key())
    monkeypatch.setattr(settings, "VAPID_SUBJECT", "mailto:ops@ispot.example.com")


class _Calls(list):
    status: dict


@pytest.fixture
def sent(monkeypatch) -> "_Calls":
    calls = _Calls()
    status = {"value": 201}

    def fake_send(endpoint, p256dh, auth, message, **kwargs):
        calls.append({"endpoint": endpoint, "message": message})
        return webpush.SendResult(status["value"])

    monkeypatch.setattr(webpush, "send", fake_send)
    calls.status = status
    return calls


# ---------------------------------------------------------------- 암호화 · 서명


def _decrypt(body: bytes, ua: ec.EllipticCurvePrivateKey, auth: bytes) -> bytes:
    salt, (rs, idlen) = body[:16], struct.unpack("!IB", body[16:21])
    as_pub = body[21 : 21 + idlen]
    ua_pub = ua.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
    shared = ua.exchange(ec.ECDH(), ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), as_pub))

    def hk(s, ikm, info, n):
        return HKDF(algorithm=hashes.SHA256(), length=n, salt=s, info=info).derive(ikm)

    ikm = hk(auth, shared, b"WebPush: info\x00" + ua_pub + as_pub, 32)
    plain = AESGCM(hk(salt, ikm, b"Content-Encoding: aes128gcm\x00", 16)).decrypt(
        hk(salt, ikm, b"Content-Encoding: nonce\x00", 12), body[21 + idlen :], None
    )
    assert rs == webpush.RECORD_SIZE and plain.endswith(b"\x02")
    return plain[:-1]


def test_encrypt_round_trip() -> None:
    ua, p256dh, auth, auth_b64 = _keys()
    body = webpush.encrypt("3시 상담 일정이 있어요".encode(), p256dh, auth_b64)

    assert _decrypt(body, ua, auth).decode() == "3시 상담 일정이 있어요"
    # 매번 다른 salt · 임시 키라 같은 글도 다르게 나온다.
    assert webpush.encrypt(b"x", p256dh, auth_b64) != webpush.encrypt(b"x", p256dh, auth_b64)


def test_encrypt_rejects_bad_keys_and_long_payload() -> None:
    _, p256dh, _, auth = _keys()

    with pytest.raises(webpush.WebPushError):
        webpush.encrypt(b"x", p256dh[:40], auth)
    with pytest.raises(webpush.WebPushError):
        webpush.encrypt(b"x" * (webpush.MAX_PAYLOAD_BYTES + 1), p256dh, auth)


def test_vapid_header_is_verifiable_es256() -> None:
    key = webpush.load_vapid_private_key(webpush.new_vapid_private_key())
    header = webpush.vapid_authorization("https://fcm.googleapis.com/fcm/send/abc", key, "mailto:a@ispot.example.com", now=1_000)
    token = header.split("t=")[1].split(",")[0]
    k = header.split("k=")[1]
    head, claims, sig = token.split(".")
    raw = webpush.b64url_decode(sig)

    pub = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), webpush.b64url_decode(k))
    pub.verify(
        encode_dss_signature(int.from_bytes(raw[:32], "big"), int.from_bytes(raw[32:], "big")),
        f"{head}.{claims}".encode(),
        ec.ECDSA(hashes.SHA256()),
    )
    body = json.loads(webpush.b64url_decode(claims))
    assert body == {"aud": "https://fcm.googleapis.com", "exp": 1_000 + 12 * 3600, "sub": "mailto:a@ispot.example.com"}
    assert k == webpush.vapid_public_key(key)


def test_send_refuses_http_endpoint() -> None:
    key = webpush.load_vapid_private_key(webpush.new_vapid_private_key())
    _, p256dh, _, auth = _keys()

    with pytest.raises(webpush.WebPushError):
        webpush.send("http://push.example.com/x", p256dh, auth, {}, private_key=key, subject="mailto:a@b.c")


@pytest.mark.parametrize(
    "endpoint, ok",
    [
        ("https://fcm.googleapis.com/fcm/send/abc", True),
        ("https://updates.push.services.mozilla.com/wpush/v2/abc", True),
        ("https://web.push.apple.com/abc", True),
        ("https://wns2-par02p.notify.windows.com/w/?token=abc", True),
        ("http://fcm.googleapis.com/fcm/send/abc", False),
        ("https://push.example.com/abc", False),
        ("https://169.254.169.254/latest/meta-data", False),
        ("https://fcm.googleapis.com.evil.example/abc", False),
        ("https://evilpush.apple.com/abc", False),
        ("https://push.apple.com/abc", False),
        ("https://user@fcm.googleapis.com/abc", False),
        ("https://fcm.googleapis.com:8443/abc", False),
    ],
)
def test_only_push_service_hosts(endpoint: str, ok: bool) -> None:
    assert webpush.is_push_endpoint(endpoint) is ok


def test_sender_does_not_follow_redirects() -> None:
    """푸시 서비스가 3xx 를 줘도 다른 주소로 다시 요청하지 않는다(Authorization 이 따라가지 않게, 민규 #186)."""
    import http.server
    import threading
    import urllib.error
    import urllib.request

    hits = []

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_POST(self):  # noqa: N802
            hits.append(self.path)
            self.send_response(302)
            self.send_header("Location", "/inner")
            self.end_headers()

        do_GET = do_POST  # noqa: N815

        def log_message(self, *args):  # noqa: ANN002
            pass

    server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        req = urllib.request.Request(f"http://127.0.0.1:{server.server_port}/push", data=b"x", method="POST", headers={"Authorization": "vapid t=x"})
        with pytest.raises(urllib.error.HTTPError) as caught:
            webpush._opener.open(req, timeout=5)
        assert caught.value.code == 302
    finally:
        server.shutdown()
    assert hits == ["/push"]


# ---------------------------------------------------------------- API


def test_disabled_without_keys(client: TestClient, counselor_headers, monkeypatch) -> None:
    monkeypatch.setattr(settings, "VAPID_PRIVATE_KEY", None)
    config = client.get("/api/v1/push/config", headers=counselor_headers).json()["data"]
    assert config["enabled"] is False and config["public_key"] is None

    res = client.put("/api/v1/push/subscription", json=_sub_body(), headers=counselor_headers)
    assert res.status_code == 503 and res.json()["error"]["code"] == "PUSH_DISABLED"


def test_bad_private_key_stays_disabled(client: TestClient, counselor_headers, monkeypatch) -> None:
    monkeypatch.setattr(settings, "VAPID_PRIVATE_KEY", "not-a-key")
    monkeypatch.setattr(settings, "VAPID_SUBJECT", "mailto:a@b.c")
    assert client.get("/api/v1/push/config", headers=counselor_headers).json()["data"]["enabled"] is False


def test_needs_login(client: TestClient) -> None:
    assert client.get("/api/v1/push/config").status_code == 401


def test_subscribe_update_and_move_between_accounts(
    client: TestClient, counselor_headers, other_counselor_headers, push_on, db, counselor_id, other_counselor_id
) -> None:
    config = client.get("/api/v1/push/config", headers=counselor_headers).json()["data"]
    assert config["enabled"] is True and len(webpush.b64url_decode(config["public_key"])) == 65
    assert config["before_session_minutes"] == settings.PUSH_BEFORE_SESSION_MINUTES

    body = _sub_body(before_session=True, upload_failed=False)
    res = client.put("/api/v1/push/subscription", json=body, headers=counselor_headers)
    assert res.status_code == 200 and res.json()["data"] == {"before_session": True, "upload_failed": False}

    body["before_session"] = False
    client.put("/api/v1/push/subscription", json=body, headers=counselor_headers)
    rows = db.scalars(select(PushSubscription)).all()
    assert len(rows) == 1 and rows[0].before_session is False and rows[0].user_id == counselor_id

    # 같은 폰에서 다른 계정으로 켜면 그 계정으로 옮긴다.
    client.put("/api/v1/push/subscription", json=body, headers=other_counselor_headers)
    db.expire_all()
    rows = db.scalars(select(PushSubscription)).all()
    assert len(rows) == 1 and rows[0].user_id == other_counselor_id


def test_rejects_http_endpoint(client: TestClient, counselor_headers, push_on) -> None:
    res = client.put("/api/v1/push/subscription", json=_sub_body("http://push.example.com/x"), headers=counselor_headers)
    assert res.status_code == 422


def test_rejects_non_push_service_endpoint(client: TestClient, counselor_headers, push_on) -> None:
    res = client.put("/api/v1/push/subscription", json=_sub_body("https://internal.example.com/hook"), headers=counselor_headers)
    assert res.status_code == 422


def test_unsubscribe_only_own(client: TestClient, counselor_headers, other_counselor_headers, push_on, db) -> None:
    body = _sub_body()
    client.put("/api/v1/push/subscription", json=body, headers=counselor_headers)

    client.post("/api/v1/push/unsubscribe", json={"endpoint": body["endpoint"]}, headers=other_counselor_headers)
    assert db.scalar(select(PushSubscription)) is not None

    assert client.post("/api/v1/push/unsubscribe", json={"endpoint": body["endpoint"]}, headers=counselor_headers).status_code == 200
    db.expire_all()
    assert db.scalar(select(PushSubscription)) is None


def test_per_user_device_limit(client: TestClient, counselor_headers, push_on, db) -> None:
    for i in range(12):
        client.put("/api/v1/push/subscription", json=_sub_body(f"https://fcm.googleapis.com/fcm/send/{i}"), headers=counselor_headers)

    rows = db.scalars(select(PushSubscription)).all()
    assert len(rows) == 10
    assert "https://fcm.googleapis.com/fcm/send/11" in {row.endpoint for row in rows}


def test_test_push_and_gone_subscription_removed(client: TestClient, counselor_headers, push_on, sent, db) -> None:
    client.put("/api/v1/push/subscription", json=_sub_body("https://fcm.googleapis.com/fcm/send/a"), headers=counselor_headers)
    client.put("/api/v1/push/subscription", json=_sub_body("https://fcm.googleapis.com/fcm/send/b"), headers=counselor_headers)

    res = client.post("/api/v1/push/test", headers=counselor_headers).json()["data"]
    assert res == {"sent": 2, "failed": 0}
    assert sent[0]["message"]["body"] == "알림이 켜졌어요."

    sent.status["value"] = 410
    assert client.post("/api/v1/push/test", headers=counselor_headers).json()["data"] == {"sent": 0, "failed": 2}
    db.expire_all()
    assert db.scalars(select(PushSubscription)).all() == []


def test_repeated_failures_remove_subscription(client: TestClient, counselor_headers, push_on, sent, db) -> None:
    client.put("/api/v1/push/subscription", json=_sub_body(), headers=counselor_headers)
    sent.status["value"] = 500

    for _ in range(push_service.MAX_FAILS - 1):
        client.post("/api/v1/push/test", headers=counselor_headers)
    db.expire_all()
    assert db.scalar(select(PushSubscription)).fail_count == push_service.MAX_FAILS - 1

    client.post("/api/v1/push/test", headers=counselor_headers)
    db.expire_all()
    assert db.scalar(select(PushSubscription)) is None


def test_key_rejection_is_not_counted_as_failure(client: TestClient, counselor_headers, push_on, sent, db) -> None:
    client.put("/api/v1/push/subscription", json=_sub_body(), headers=counselor_headers)

    for status in (401, 403):
        sent.status["value"] = status
        assert client.post("/api/v1/push/test", headers=counselor_headers).json()["data"] == {"sent": 0, "failed": 1}
    db.expire_all()
    assert db.scalar(select(PushSubscription)).fail_count == 0


def test_test_push_is_rate_limited(client: TestClient, counselor_headers, push_on, sent) -> None:
    client.put("/api/v1/push/subscription", json=_sub_body(), headers=counselor_headers)

    for _ in range(push_service.TEST_HOURLY_LIMIT):
        assert client.post("/api/v1/push/test", headers=counselor_headers).status_code == 200
    assert client.post("/api/v1/push/test", headers=counselor_headers).status_code == 429


# ---------------------------------------------------------------- 상담 30분 전


def _event(db, owner_id: uuid.UUID, start: datetime, *, kind=ScheduleKind.CONSULT, with_time=True) -> ScheduleEvent:
    local = start.astimezone(KST)
    event = ScheduleEvent(
        owner_id=owner_id,
        kind=kind,
        title="김가상 아동 상담",
        event_date=local.date(),
        event_time=local.strftime("%H:%M") if with_time else None,
        deadline_done={},
    )
    db.add(event)
    db.commit()
    return event


NOW = datetime(2026, 11, 19, 5, 0, tzinfo=timezone.utc)  # 한국 14:00


def test_before_session_sends_once_with_generic_text(
    client: TestClient, counselor_headers, other_counselor_headers, push_on, sent, db, counselor_id, other_counselor_id
) -> None:
    client.put("/api/v1/push/subscription", json=_sub_body("https://fcm.googleapis.com/fcm/send/me"), headers=counselor_headers)
    client.put("/api/v1/push/subscription", json=_sub_body("https://fcm.googleapis.com/fcm/send/other"), headers=other_counselor_headers)

    soon = _event(db, counselor_id, NOW + timedelta(minutes=20))
    _event(db, counselor_id, NOW + timedelta(minutes=40))  # 아직
    _event(db, counselor_id, NOW - timedelta(minutes=5))  # 지남
    _event(db, counselor_id, NOW + timedelta(minutes=10), kind=ScheduleKind.OTHER)  # 개인 · 기관 일정
    _event(db, counselor_id, NOW + timedelta(minutes=10), with_time=False)  # 시간 없음

    assert push_service.run_before_session(db, NOW) == 1
    assert [call["endpoint"] for call in sent] == ["https://fcm.googleapis.com/fcm/send/me"]
    message = sent[0]["message"]
    assert message["body"] == "14:20 상담 일정이 있어요." and message["tag"] == f"before-session-{soon.id}"
    # 잠금 화면에 보이므로 제목(아이 이름)은 넣지 않는다.
    assert "김가상" not in json.dumps(message, ensure_ascii=False)

    # 1분 뒤 다시 돌아도 또 보내지 않는다.
    assert push_service.run_before_session(db, NOW + timedelta(minutes=1)) == 0
    assert len(sent) == 1
    assert db.scalar(select(PushDelivery)).sent == 1

    # 시간을 바꾸면 새 시간에 다시 알린다.
    soon.event_time = (NOW + timedelta(minutes=25)).astimezone(KST).strftime("%H:%M")
    db.commit()
    assert push_service.run_before_session(db, NOW + timedelta(minutes=1)) == 1


def test_before_session_respects_device_setting_and_inactive_user(
    client: TestClient, counselor_headers, push_on, sent, db, counselor_id
) -> None:
    client.put("/api/v1/push/subscription", json=_sub_body(before_session=False), headers=counselor_headers)
    _event(db, counselor_id, NOW + timedelta(minutes=10))

    assert push_service.run_before_session(db, NOW) == 0 and sent == []
    # 켜진 기기가 없으면 보낸 기록도 남기지 않는다(나중에 켜면 그때 알린다).
    assert db.scalar(select(PushDelivery)) is None

    # 정지된 계정에는 보내지 않는다.
    client.put("/api/v1/push/subscription", json=_sub_body(before_session=True), headers=counselor_headers)
    db.get(User, counselor_id).is_active = False
    db.commit()
    assert push_service.run_before_session(db, NOW) == 0 and sent == []


def test_before_session_crosses_midnight(client: TestClient, counselor_headers, push_on, sent, db, counselor_id) -> None:
    client.put("/api/v1/push/subscription", json=_sub_body(), headers=counselor_headers)
    late = datetime(2026, 11, 19, 14, 50, tzinfo=timezone.utc)  # 한국 23:50
    _event(db, counselor_id, late + timedelta(minutes=20))  # 한국 다음 날 00:10

    assert push_service.run_before_session(db, late) == 1


def test_before_session_does_nothing_when_disabled(db, counselor_id, sent, monkeypatch) -> None:
    monkeypatch.setattr(settings, "VAPID_PRIVATE_KEY", None)
    _event(db, counselor_id, NOW + timedelta(minutes=10))
    assert push_service.run_before_session(db, NOW) == 0


def test_cleanup_old_deliveries(db, counselor_id) -> None:
    db.add(PushDelivery(user_id=counselor_id, kind="before_session", ref_key="x", sent=1))
    db.commit()
    push_service.cleanup_deliveries(db, datetime.now(timezone.utc) + timedelta(days=push_service.DELIVERY_KEEP_DAYS + 1))
    assert db.scalar(select(PushDelivery)) is None


def test_loop_off_by_default_and_without_keys(monkeypatch) -> None:
    # 시험 · CI · 로컬에서는 실행기가 돌지 않는다(PUSH_LOOP_ENABLED 기본 끔). 켜도 키가 없으면 바로 끝난다.
    import asyncio

    assert settings.PUSH_LOOP_ENABLED is False
    called = []
    monkeypatch.setattr(push_service, "_tick", lambda: called.append(1))
    asyncio.run(asyncio.wait_for(push_service.run_push_loop(), 1))

    monkeypatch.setattr(settings, "PUSH_LOOP_ENABLED", True)
    monkeypatch.setattr(settings, "VAPID_PRIVATE_KEY", None)
    asyncio.run(asyncio.wait_for(push_service.run_push_loop(), 1))
    assert called == []


# ---------------------------------------------------------------- 아이 긴급 알림(2026-11-20)


@pytest.fixture
def child_on(monkeypatch):
    monkeypatch.setattr(settings, "CHILD_APP_ENABLED", True)


def _child_device(client: TestClient, headers, case_id: str) -> dict:
    code = client.post(f"/api/v1/cases/{case_id}/child-app/invite", headers=headers).json()["data"]["code"]
    token = client.post("/api/v1/child-app/link", json={"code": code}).json()["data"]["device_token"]
    return {"Authorization": f"Bearer {token}"}


def _press(client: TestClient, device: dict) -> None:
    res = client.post("/api/v1/child-app/alerts", headers=device)
    assert res.status_code == 200, res.text


def test_child_alert_pushes_to_case_counselor_once(
    client: TestClient, counselor_headers, other_counselor_headers, case, child_on, push_on, sent, db
) -> None:
    client.put("/api/v1/push/subscription", json=_sub_body("https://fcm.googleapis.com/fcm/send/mine"), headers=counselor_headers)
    client.put("/api/v1/push/subscription", json=_sub_body("https://fcm.googleapis.com/fcm/send/other"), headers=other_counselor_headers)
    # 상담 30분 전 · 업로드 실패를 꺼 둔 폰도 긴급 알림은 받는다(따로 끄는 칸이 없다).
    client.put(
        "/api/v1/push/subscription",
        json=_sub_body("https://fcm.googleapis.com/fcm/send/mine2", before_session=False, upload_failed=False),
        headers=counselor_headers,
    )
    device = _child_device(client, counselor_headers, case["id"])

    _press(client, device)

    assert sorted(call["endpoint"] for call in sent) == [
        "https://fcm.googleapis.com/fcm/send/mine",
        "https://fcm.googleapis.com/fcm/send/mine2",
    ]
    message = sent[0]["message"]
    assert message["title"] == push_service.CHILD_ALERT_TITLE and message["body"] == push_service.CHILD_ALERT_BODY
    assert message["url"] == f"/#/ChildDetail?case={case['id']}"
    # 잠금 화면 문구에 아이 가명 · 사례 번호가 없다.
    assert case["child_alias"] not in json.dumps(message, ensure_ascii=False)
    assert case.get("case_number", "C-") not in message["body"]

    # 확인 전에 다시 누르면 같은 알림(횟수만) — 새로 보내지 않는다.
    _press(client, device)
    assert len(sent) == 2

    # 상담사가 확인한 뒤 다시 누르면 새 알림이라 다시 보낸다.
    alert_id = client.get(f"/api/v1/cases/{case['id']}/child-app", headers=counselor_headers).json()["data"]["open_alerts"][0]["id"]
    assert client.post(f"/api/v1/cases/{case['id']}/child-app/alerts/{alert_id}/ack", headers=counselor_headers).status_code == 204
    _press(client, device)
    assert len(sent) == 4
    db.expire_all()
    assert len(db.scalars(select(PushDelivery).where(PushDelivery.kind == push_service.KIND_CHILD_ALERT)).all()) == 2


def test_child_alert_works_without_push(client: TestClient, counselor_headers, case, child_on, sent, monkeypatch) -> None:
    monkeypatch.setattr(settings, "VAPID_PRIVATE_KEY", None)
    device = _child_device(client, counselor_headers, case["id"])

    _press(client, device)

    assert sent == []
    assert client.get(f"/api/v1/cases/{case['id']}/child-app", headers=counselor_headers).json()["data"]["open_alerts"]


def test_child_alert_push_error_does_not_reach_child(
    client: TestClient, counselor_headers, case, child_on, push_on, monkeypatch
) -> None:
    client.put("/api/v1/push/subscription", json=_sub_body(), headers=counselor_headers)

    def boom(*args, **kwargs):
        raise RuntimeError("push service down")

    monkeypatch.setattr(webpush, "send", boom)
    device = _child_device(client, counselor_headers, case["id"])

    _press(client, device)

    assert client.get(f"/api/v1/cases/{case['id']}/child-app", headers=counselor_headers).json()["data"]["open_alerts"]



@pytest.mark.parametrize(("first", "tries"), [(503, 2), (0, 2), (410, 1), (201, 1)])
def test_child_alert_retries_once_on_brief_failure(
    client: TestClient, counselor_headers, case, child_on, push_on, monkeypatch, first, tries
) -> None:
    # 잠깐의 실패(5xx · 연결 실패)면 한 번 더 보낸다. 구독이 없어졌거나(410) 보냈으면 다시 보내지 않는다(민규 #190 리뷰 1).
    monkeypatch.setattr(push_service, "CHILD_ALERT_RETRY_SECONDS", 0)
    client.put("/api/v1/push/subscription", json=_sub_body(), headers=counselor_headers)
    calls = []

    def flaky(endpoint, p256dh, auth, message, **kwargs):
        calls.append(endpoint)
        return webpush.SendResult(first if len(calls) == 1 else 201)

    monkeypatch.setattr(webpush, "send", flaky)
    device = _child_device(client, counselor_headers, case["id"])

    _press(client, device)

    assert len(calls) == tries

# ---------------------------------------------------------------- 토큰을 끊으면 폰 구독도 지운다(11/20 점검)

@pytest.mark.parametrize("action", ["logout-all", "password-reset"])
def test_revoking_tokens_drops_push_subscriptions(
    client: TestClient, admin_headers, counselor_headers, other_counselor_headers, push_on, db, counselor_id, action
) -> None:
    client.put("/api/v1/push/subscription", json=_sub_body("https://fcm.googleapis.com/fcm/send/mine"), headers=counselor_headers)
    client.put("/api/v1/push/subscription", json=_sub_body("https://fcm.googleapis.com/fcm/send/other"), headers=other_counselor_headers)

    assert client.post(f"/api/v1/auth/users/{counselor_id}/{action}", headers=admin_headers).status_code in (200, 204)

    db.expire_all()
    rows = db.scalars(select(PushSubscription)).all()
    # 끊은 계정 것만 지우고 다른 계정 것은 남긴다.
    assert [row.endpoint for row in rows] == ["https://fcm.googleapis.com/fcm/send/other"]


def test_before_session_enabled_needs_loop(client: TestClient, counselor_headers, push_on, monkeypatch) -> None:
    monkeypatch.setattr(settings, "PUSH_LOOP_ENABLED", False)
    assert client.get("/api/v1/push/config", headers=counselor_headers).json()["data"]["before_session_enabled"] is False
    monkeypatch.setattr(settings, "PUSH_LOOP_ENABLED", True)
    assert client.get("/api/v1/push/config", headers=counselor_headers).json()["data"]["before_session_enabled"] is True
