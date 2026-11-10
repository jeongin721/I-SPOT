# 상담사 메모(GET/POST/PATCH/DELETE /memos, API_CONTRACT 25절, 2026-11-10). 데이터는 모두 가상이다.

import logging
import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core import pii_crypto
from app.core.enums import AuditAction
from app.models.audit_log import AuditLog
from app.models.counselor_memo import CounselorMemo
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

    # 다른 메모 행으로 옮겨 붙인 암호문은 풀리지 않는다 → 500 MEMO_UNAVAILABLE.
    rows[second["id"]].text_enc = token
    db.commit()
    response = client.get(f"{URL}/{second['id']}", headers=counselor_headers)
    assert response.status_code == 500 and response.json()["error"]["code"] == "MEMO_UNAVAILABLE"


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
