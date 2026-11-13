# 상담사 메모(GET/POST/PATCH/DELETE /memos, API_CONTRACT 25절, 2026-11-10). 데이터는 모두 가상이다.

import base64
import logging
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core import pii_crypto
from app.core.config import settings
from app.core.enums import AuditAction
from app.models.audit_log import AuditLog
from app.models.counselor_memo import CounselorMemo
import scripts.reencrypt_personal_info as reencrypt_script
from scripts.reencrypt_personal_info import reencrypt_all
from tests.conftest import create_case

URL = "/api/v1/memos"
SECRET = "현관 앞에서 만남. 서윤이 할머니 연락처 다시 확인"


def _create(client: TestClient, headers, **body) -> dict:
    response = client.post(URL, json={"text": SECRET, **body}, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()["data"]


def test_create_list_get_update_delete(client: TestClient, counselor_headers, case: dict) -> None:
    created = _create(client, counselor_headers, case_id=case["id"])
    assert created["text"] == SECRET and created["case_id"] == case["id"] and created["child_alias"] == case["child_alias"]

    plain = _create(client, counselor_headers)
    assert plain["case_id"] is None and plain["child_alias"] is None

    listed = client.get(URL, headers=counselor_headers).json()["data"]
    assert [row["id"] for row in listed["items"]] == [plain["id"], created["id"]]
    assert listed["meta"]["total"] == 2

    by_case = client.get(URL, params={"case_id": case["id"]}, headers=counselor_headers).json()["data"]
    assert [row["id"] for row in by_case["items"]] == [created["id"]]

    one = client.get(f"{URL}/{created['id']}", headers=counselor_headers)
    assert one.status_code == 200 and one.json()["data"]["text"] == SECRET

    patched = client.patch(f"{URL}/{created['id']}", json={"text": "  고친 메모  ", "case_id": None}, headers=counselor_headers)
    assert patched.status_code == 200, patched.text
    assert patched.json()["data"]["text"] == "고친 메모" and patched.json()["data"]["case_id"] is None

    deleted = client.delete(f"{URL}/{created['id']}", headers=counselor_headers)
    assert deleted.status_code == 204
    assert client.get(f"{URL}/{created['id']}", headers=counselor_headers).status_code == 404


def test_pagination(client: TestClient, counselor_headers) -> None:
    ids = [_create(client, counselor_headers, text=f"메모 {n}")["id"] for n in range(5)]

    first = client.get(URL, params={"page": 1, "page_size": 2}, headers=counselor_headers).json()["data"]
    third = client.get(URL, params={"page": 3, "page_size": 2}, headers=counselor_headers).json()["data"]

    assert first["meta"] == {"total": 5, "page": 1, "page_size": 2, "total_pages": 3}
    assert [row["id"] for row in first["items"]] == ids[::-1][:2]
    assert [row["id"] for row in third["items"]] == ids[:1]
    assert client.get(URL, params={"page_size": 101}, headers=counselor_headers).status_code == 422


def test_only_owner_can_see_even_admin_cannot(
    client: TestClient, counselor_headers, other_counselor_headers, admin_headers, case: dict
) -> None:
    memo = _create(client, counselor_headers, case_id=case["id"])

    for headers in (other_counselor_headers, admin_headers):
        assert client.get(URL, headers=headers).json()["data"]["items"] == []
        assert client.get(f"{URL}/{memo['id']}", headers=headers).status_code == 404
        assert client.patch(f"{URL}/{memo['id']}", json={"text": "x"}, headers=headers).status_code == 404
        assert client.delete(f"{URL}/{memo['id']}", headers=headers).status_code == 404

    assert client.get(f"{URL}/{memo['id']}", headers=counselor_headers).status_code == 200


def test_case_must_be_visible(client: TestClient, counselor_headers, other_counselor_headers) -> None:
    others = create_case(client, other_counselor_headers)

    assert client.post(URL, json={"text": "a", "case_id": others["id"]}, headers=counselor_headers).status_code == 403
    assert client.post(URL, json={"text": "a", "case_id": str(uuid.uuid4())}, headers=counselor_headers).status_code == 404

    memo = _create(client, counselor_headers)
    assert client.patch(f"{URL}/{memo['id']}", json={"case_id": others["id"]}, headers=counselor_headers).status_code == 403


def test_memo_of_reassigned_case_drops_out(
    client: TestClient, counselor_headers, admin_headers, other_counselor_id, case: dict
) -> None:
    on_case = _create(client, counselor_headers, case_id=case["id"])
    free = _create(client, counselor_headers)

    moved = client.patch(f"/api/v1/cases/{case['id']}", json={"counselor_id": str(other_counselor_id)}, headers=admin_headers)
    assert moved.status_code == 200, moved.text

    listed = client.get(URL, headers=counselor_headers).json()["data"]
    assert [row["id"] for row in listed["items"]] == [free["id"]] and listed["meta"]["total"] == 1
    assert client.get(f"{URL}/{on_case['id']}", headers=counselor_headers).status_code == 404


def test_validation(client: TestClient, counselor_headers) -> None:
    for body in ({"text": ""}, {"text": "   "}, {"text": "가" * 4001}, {"text": "a\x00b"}, {}):
        assert client.post(URL, json=body, headers=counselor_headers).status_code == 422, body

    memo = _create(client, counselor_headers)
    assert client.patch(f"{URL}/{memo['id']}", json={"text": None}, headers=counselor_headers).status_code == 422
    assert client.post(URL, json={"text": "가" * 4000}, headers=counselor_headers).status_code == 201


def test_text_is_encrypted_and_bound_to_memo(client: TestClient, counselor_headers, db) -> None:
    first = _create(client, counselor_headers)
    second = _create(client, counselor_headers, text="다른 메모")

    rows = {str(row.id): row for row in db.scalars(select(CounselorMemo)).all()}
    token = rows[first["id"]].text_enc
    assert SECRET not in token and token.startswith("v1.")
    assert pii_crypto.decrypt_memo(token, memo_id=uuid.UUID(first["id"])) == SECRET

    # 다른 메모 행으로 옮겨 붙인 암호문은 풀리지 않는다 → 그 메모만 text null · unreadable, 목록은 200(민규 #170 2).
    rows[second["id"]].text_enc = token
    db.commit()
    one = client.get(f"{URL}/{second['id']}", headers=counselor_headers)
    assert one.status_code == 200 and one.json()["data"]["text"] is None and one.json()["data"]["unreadable"] is True

    listed = client.get(URL, headers=counselor_headers)
    assert listed.status_code == 200
    by_id = {row["id"]: row for row in listed.json()["data"]["items"]}
    assert by_id[first["id"]]["text"] == SECRET and by_id[first["id"]]["unreadable"] is False
    assert by_id[second["id"]]["unreadable"] is True

    # 읽을 수 없는 메모도 지울 수 있고, 새 본문으로 고치면 다시 읽힌다.
    fixed = client.patch(f"{URL}/{second['id']}", json={"text": "새로 쓴 메모"}, headers=counselor_headers)
    assert fixed.status_code == 200 and fixed.json()["data"]["text"] == "새로 쓴 메모"
    assert client.delete(f"{URL}/{second['id']}", headers=counselor_headers).status_code == 204


def test_audit_without_text_and_no_text_in_logs(client: TestClient, counselor_headers, case: dict, db, caplog) -> None:
    caplog.set_level(logging.DEBUG)
    memo = _create(client, counselor_headers, case_id=case["id"])
    client.patch(f"{URL}/{memo['id']}", json={"text": SECRET + " 추가"}, headers=counselor_headers)
    client.get(URL, headers=counselor_headers)
    client.delete(f"{URL}/{memo['id']}", headers=counselor_headers)

    logs = db.scalars(select(AuditLog).where(AuditLog.entity_type == "CounselorMemo").order_by(AuditLog.created_at)).all()
    assert [log.action for log in logs] == [AuditAction.MEMO_CREATED, AuditAction.MEMO_UPDATED, AuditAction.MEMO_DELETED]
    assert all(str(log.entity_id) == memo["id"] for log in logs)
    assert logs[1].detail == {"fields": ["text"]}
    for log in logs:
        assert SECRET not in repr(log.detail)

    assert SECRET not in caplog.text and "현관" not in caplog.text


def test_deleting_case_deletes_its_memos(client: TestClient, counselor_headers, admin_headers, case: dict, db) -> None:
    on_case = _create(client, counselor_headers, case_id=case["id"])
    free = _create(client, counselor_headers)

    assert client.delete(f"/api/v1/cases/{case['id']}", headers=admin_headers).status_code == 204

    left = {str(row.id) for row in db.scalars(select(CounselorMemo)).all()}
    assert on_case["id"] not in left and free["id"] in left


# =========================================================
# 키 바꾸기 script 가 메모도 다시 암호화(민규 #170 1)
# =========================================================

NEW_KEY = "new2:" + base64.b64encode(b"test-only-pii-encrypt-key-000002").decode()


def test_reencrypt_moves_memos_to_new_key(client: TestClient, counselor_headers, db, monkeypatch: pytest.MonkeyPatch) -> None:
    memo = _create(client, counselor_headers)
    old_keys = settings.PII_ENCRYPTION_KEYS
    monkeypatch.setattr(settings, "PII_ENCRYPTION_KEYS", f"{NEW_KEY},{old_keys}")

    dry = reencrypt_all(db, dry_run=True)
    assert (dry.memo_rows, dry.changed_memos) == (1, 1)

    result = reencrypt_all(db)
    assert result.changed_memos == 1 and result.clean
    db.expire_all()
    assert db.get(CounselorMemo, uuid.UUID(memo["id"])).text_enc.startswith("v1.new2.")

    audit = db.scalars(select(AuditLog).where(AuditLog.action == AuditAction.MEMO_UPDATED)).all()
    assert audit and audit[-1].detail["via"] == reencrypt_script.VIA and SECRET not in repr(audit[-1].detail)

    # 옛 키를 빼도 읽히고, 다시 돌리면 바꿀 것이 없다.
    monkeypatch.setattr(settings, "PII_ENCRYPTION_KEYS", NEW_KEY)
    assert client.get(f"{URL}/{memo['id']}", headers=counselor_headers).json()["data"]["text"] == SECRET
    assert reencrypt_all(db).changed_memos == 0


def test_reencrypt_exits_1_when_a_memo_cannot_be_read(
    client: TestClient, counselor_headers, db, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    memo = _create(client, counselor_headers)
    # 옛 키를 먼저 빼 버린 경우: 메모를 풀 수 없다.
    monkeypatch.setattr(settings, "PII_ENCRYPTION_KEYS", NEW_KEY)

    result = reencrypt_all(db)
    assert result.failed_memo_ids == [uuid.UUID(memo["id"])] and not result.clean

    monkeypatch.setattr(reencrypt_script, "SessionLocal", lambda: db)
    monkeypatch.setattr("sys.argv", ["reencrypt_personal_info"])
    assert reencrypt_script.main() == 1
    err = capsys.readouterr().err
    assert memo["id"] in err and SECRET not in err
