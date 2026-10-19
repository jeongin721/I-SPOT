# 상담 기록 문서 생성·수정·승인 테스트 (app/services/document_service.py).

from fastapi.testclient import TestClient

from tests.conftest import create_case, create_session


def _documents_url(session_id: str) -> str:
    return f"/api/v1/sessions/{session_id}/documents"


def _create_document(client: TestClient, headers, session_id: str, **overrides) -> dict:
    payload = {"title": "상담 기록", "content": "합성 기록 본문"}
    payload.update(overrides)

    response = client.post(_documents_url(session_id), json=payload, headers=headers)

    assert response.status_code == 201, response.text

    return response.json()["data"]


def test_create_and_list_documents(client: TestClient, counselor_headers, session: dict) -> None:
    created = _create_document(client, counselor_headers, session["id"])

    assert created["status"] == "DRAFT"
    assert created["doc_type"] == "CONSULTATION_RECORD"

    listed = client.get(_documents_url(session["id"]), headers=counselor_headers).json()["data"]

    assert [item["id"] for item in listed] == [created["id"]]


def test_update_document_changes_only_given_fields(
    client: TestClient, counselor_headers, session: dict
) -> None:
    created = _create_document(client, counselor_headers, session["id"])

    response = client.patch(
        f"{_documents_url(session['id'])}/{created['id']}",
        json={"title": "수정한 제목"},
        headers=counselor_headers,
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["title"] == "수정한 제목"
    assert data["content"] == created["content"]


def test_update_document_requires_a_field(client: TestClient, counselor_headers, session: dict) -> None:
    created = _create_document(client, counselor_headers, session["id"])

    response = client.patch(
        f"{_documents_url(session['id'])}/{created['id']}", json={}, headers=counselor_headers
    )

    assert response.status_code == 422


def test_approved_document_cannot_be_updated_or_approved_again(
    client: TestClient, counselor_headers, counselor_id, session: dict
) -> None:
    created = _create_document(client, counselor_headers, session["id"])
    document_url = f"{_documents_url(session['id'])}/{created['id']}"

    approved = client.post(f"{document_url}/approve", headers=counselor_headers)

    assert approved.status_code == 200
    assert approved.json()["data"]["status"] == "APPROVED"
    assert approved.json()["data"]["approved_by_id"] == str(counselor_id)

    update = client.patch(document_url, json={"content": "승인 후 수정 시도"}, headers=counselor_headers)
    assert update.status_code == 409
    assert update.json()["error"]["code"] == "ALREADY_APPROVED"

    again = client.post(f"{document_url}/approve", headers=counselor_headers)
    assert again.status_code == 409
    assert again.json()["error"]["code"] == "ALREADY_APPROVED"


def test_reopen_approved_document_keeps_content_and_allows_reapproval(
    client: TestClient, counselor_headers, counselor_id, session: dict
) -> None:
    created = _create_document(client, counselor_headers, session["id"], content="처음 쓴 기록")
    document_url = f"{_documents_url(session['id'])}/{created['id']}"
    client.post(f"{document_url}/approve", headers=counselor_headers)

    reopened = client.post(f"{document_url}/reopen", headers=counselor_headers)

    assert reopened.status_code == 200
    data = reopened.json()["data"]
    assert data["status"] == "DRAFT"
    assert data["approved_at"] is None
    assert data["approved_by_id"] is None
    # 처음 쓴 내용은 그대로 남아 이어서 고칠 수 있다.
    assert data["title"] == created["title"]
    assert data["content"] == "처음 쓴 기록"

    edited = client.patch(document_url, json={"content": "처음 쓴 기록 + 고친 부분"}, headers=counselor_headers)
    assert edited.status_code == 200
    assert edited.json()["data"]["content"] == "처음 쓴 기록 + 고친 부분"

    approved = client.post(f"{document_url}/approve", headers=counselor_headers)
    assert approved.status_code == 200
    assert approved.json()["data"]["status"] == "APPROVED"
    assert approved.json()["data"]["approved_by_id"] == str(counselor_id)

    # 문서 승인 · 풀기는 회기 상태를 바꾸지 않는다.
    detail = client.get(f"/api/v1/sessions/{session['id']}", headers=counselor_headers).json()["data"]
    assert detail["status"] == session["status"]


def test_reopen_draft_document_returns_not_approved(
    client: TestClient, counselor_headers, session: dict
) -> None:
    created = _create_document(client, counselor_headers, session["id"])

    response = client.post(
        f"{_documents_url(session['id'])}/{created['id']}/reopen", headers=counselor_headers
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "NOT_APPROVED"


def test_reopen_document_of_another_session_is_not_found(
    client: TestClient, counselor_headers, session: dict
) -> None:
    created = _create_document(client, counselor_headers, session["id"])
    client.post(f"{_documents_url(session['id'])}/{created['id']}/approve", headers=counselor_headers)
    other_session = create_session(client, counselor_headers, session["case_id"])

    response = client.post(
        f"{_documents_url(other_session['id'])}/{created['id']}/reopen", headers=counselor_headers
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "DOCUMENT_NOT_FOUND"


def test_document_of_another_session_is_not_found(
    client: TestClient, counselor_headers, session: dict
) -> None:
    created = _create_document(client, counselor_headers, session["id"])
    other_session = create_session(client, counselor_headers, session["case_id"])

    response = client.patch(
        f"{_documents_url(other_session['id'])}/{created['id']}",
        json={"title": "다른 회기 경로로 수정"},
        headers=counselor_headers,
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "DOCUMENT_NOT_FOUND"


def test_other_counselor_cannot_touch_documents(
    client: TestClient, counselor_headers, other_counselor_headers, session: dict
) -> None:
    created = _create_document(client, counselor_headers, session["id"])
    document_url = f"{_documents_url(session['id'])}/{created['id']}"

    assert client.get(_documents_url(session["id"]), headers=other_counselor_headers).status_code == 403
    assert client.patch(document_url, json={"title": "x"}, headers=other_counselor_headers).status_code == 403
    assert client.post(f"{document_url}/approve", headers=other_counselor_headers).status_code == 403

    client.post(f"{document_url}/approve", headers=counselor_headers)
    assert client.post(f"{document_url}/reopen", headers=other_counselor_headers).status_code == 403


def test_documents_are_removed_with_their_session(
    client: TestClient, counselor_headers, admin_headers
) -> None:
    case = create_case(client, counselor_headers)
    session = create_session(client, counselor_headers, case["id"])
    _create_document(client, counselor_headers, session["id"])

    assert client.delete(f"/api/v1/sessions/{session['id']}", headers=counselor_headers).status_code == 204
    assert client.get(_documents_url(session["id"]), headers=admin_headers).status_code == 404
