# 사내 공지사항(API_CONTRACT 28절, 2026-11-20): 읽기는 로그인한 누구나, 쓰고 고치고 지우기는 관리자만.
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.enums import AuditAction
from app.models.audit_log import AuditLog

URL = "/api/v1/notices"


def test_admin_writes_and_everyone_reads(client: TestClient, admin_headers, counselor_headers) -> None:
    first = client.post(URL, json={"title": " 시스템 점검 ", "body": "22:00~24:00 점검", "team": "정보보안팀"}, headers=admin_headers)
    assert first.status_code == 201, first.text
    second = client.post(URL, json={"title": "개인정보 교육", "body": "꼭 참석", "important": True}, headers=admin_headers).json()["data"]
    data = first.json()["data"]
    assert (data["title"], data["team"], data["important"]) == ("시스템 점검", "정보보안팀", False)
    assert second["team"] is None and second["author_name"]

    listed = client.get(URL, headers=counselor_headers)
    assert listed.status_code == 200, listed.text
    assert [row["id"] for row in listed.json()["data"]] == [second["id"], data["id"]]
    assert [row["id"] for row in client.get(URL, params={"limit": 1}, headers=counselor_headers).json()["data"]] == [second["id"]]

    patched = client.patch(f"{URL}/{data['id']}", json={"important": True, "team": None}, headers=admin_headers)
    assert patched.status_code == 200, patched.text
    assert (patched.json()["data"]["important"], patched.json()["data"]["team"]) == (True, None)

    assert client.delete(f"{URL}/{data['id']}", headers=admin_headers).status_code == 204
    assert [row["id"] for row in client.get(URL, headers=counselor_headers).json()["data"]] == [second["id"]]
    assert client.delete(f"{URL}/{data['id']}", headers=admin_headers).status_code == 404


def test_counselor_cannot_write(client: TestClient, admin_headers, counselor_headers) -> None:
    assert client.get(URL).status_code == 401
    assert client.post(URL, json={"title": "t", "body": "b"}, headers=counselor_headers).status_code == 403
    notice = client.post(URL, json={"title": "t", "body": "b"}, headers=admin_headers).json()["data"]
    assert client.patch(f"{URL}/{notice['id']}", json={"title": "x"}, headers=counselor_headers).status_code == 403
    assert client.delete(f"{URL}/{notice['id']}", headers=counselor_headers).status_code == 403


def test_validation(client: TestClient, admin_headers) -> None:
    for body in ({"title": "", "body": "b"}, {"title": "  ", "body": "b"}, {"title": "t"}, {"title": "t" * 121, "body": "b"}):
        assert client.post(URL, json=body, headers=admin_headers).status_code == 422, body
    notice = client.post(URL, json={"title": "t", "body": "b"}, headers=admin_headers).json()["data"]
    assert client.patch(f"{URL}/{notice['id']}", json={"title": None}, headers=admin_headers).status_code == 422


def test_audit_has_no_text(client: TestClient, admin_headers, db) -> None:
    notice = client.post(URL, json={"title": "비밀 제목", "body": "비밀 본문"}, headers=admin_headers).json()["data"]
    client.patch(f"{URL}/{notice['id']}", json={"body": "새 본문"}, headers=admin_headers)
    client.delete(f"{URL}/{notice['id']}", headers=admin_headers)
    rows = list(db.scalars(select(AuditLog).where(AuditLog.entity_type == "Notice").order_by(AuditLog.created_at)))
    assert [row.action for row in rows] == [AuditAction.NOTICE_CREATED, AuditAction.NOTICE_UPDATED, AuditAction.NOTICE_DELETED]
    assert "비밀" not in str([row.detail for row in rows]) and "새 본문" not in str([row.detail for row in rows])
