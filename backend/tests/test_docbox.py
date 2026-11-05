# 문서함(GET /docbox · POST /docbox/folders · POST /docbox/files · PATCH /docbox/files/{id} · GET …/download, API_CONTRACT 23절).
# 데이터는 모두 가상이다.
import io
import zipfile

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.enums import AuditAction
from app.models.audit_log import AuditLog

URL = "/api/v1/docbox"


def _docx(text: str) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(
            "word/document.xml",
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>'
            f"<w:p><w:r><w:t>{text}</w:t></w:r></w:p></w:body></w:document>",
        )
    return buffer.getvalue()


PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32


def _upload(client: TestClient, headers, files, folder_id=None):
    data = {"folder_id": folder_id} if folder_id else None
    return client.post(f"{URL}/files", files=[("files", f) for f in files], data=data, headers=headers)


def test_folders_upload_preview_move_and_download(client: TestClient, counselor_headers, other_counselor_headers, db) -> None:
    folder = client.post(f"{URL}/folders", json={"name": "  기관   서식 "}, headers=counselor_headers)
    assert folder.status_code == 201, folder.text
    folder_id = folder.json()["data"]["id"]
    assert folder.json()["data"]["name"] == "기관 서식"
    assert client.post(f"{URL}/folders", json={"name": "기관 서식"}, headers=counselor_headers).status_code == 409

    response = _upload(
        client,
        counselor_headers,
        [
            ("점검표 안내.txt", "점검표 안내\n1. 작성 시점".encode(), "text/plain"),
            ("요약.docx", _docx("아동복지법 제17조 요약"), "application/octet-stream"),
            ("사진.png", PNG, "image/png"),
            ("표.xlsx", b"PK\x03\x04 not really", "application/octet-stream"),
        ],
        folder_id,
    )
    assert response.status_code == 201, response.text
    files = {f["name"]: f for f in response.json()["data"]["files"]}
    assert files["점검표 안내.txt"]["preview_kind"] == "text" and files["점검표 안내.txt"]["preview_text"].startswith("점검표 안내")
    assert files["요약.docx"]["preview_kind"] == "text" and "제17조" in files["요약.docx"]["preview_text"]
    assert files["사진.png"]["preview_kind"] == "image" and files["사진.png"]["content_type"] == "image/png"
    assert files["표.xlsx"]["preview_kind"] == "other" and files["표.xlsx"]["content_type"] == "application/octet-stream"

    # 공용 보관함 — 다른 상담원도 본다.
    listed = client.get(URL, headers=other_counselor_headers).json()["data"]
    assert [f["name"] for f in listed["folders"]] == ["기관 서식"] and listed["folders"][0]["count"] == 4
    assert len(listed["files"]) == 4 and all(f["folder_id"] == folder_id for f in listed["files"])

    moved = client.patch(f"{URL}/files/{files['사진.png']['id']}", json={"folder_id": None}, headers=other_counselor_headers)
    assert moved.status_code == 200 and moved.json()["data"]["folder_id"] is None
    assert client.get(URL, headers=counselor_headers).json()["data"]["folders"][0]["count"] == 3

    download = client.get(f"{URL}/files/{files['점검표 안내.txt']['id']}/download", headers=counselor_headers)
    assert download.status_code == 200 and download.content == "점검표 안내\n1. 작성 시점".encode()
    assert download.headers["content-disposition"].startswith("attachment;")
    assert download.headers["x-content-type-options"] == "nosniff"
    assert download.headers["content-type"].startswith("application/octet-stream")

    # 감사 기록에는 파일 이름을 남기지 않는다.
    logs = db.scalars(select(AuditLog).where(AuditLog.action == AuditAction.DOCBOX_FILE_UPLOADED)).all()
    assert logs and "점검표" not in str(logs[0].detail) and logs[0].detail["count"] == 4


def test_upload_rules(client: TestClient, counselor_headers) -> None:
    bad = _upload(client, counselor_headers, [("실행.exe", b"MZ", "application/octet-stream")])
    assert bad.status_code == 422 and ".exe" in bad.json()["error"]["message"]
    assert _upload(client, counselor_headers, [("빈.txt", b"", "text/plain")]).status_code == 422
    big = _upload(client, counselor_headers, [("큰.pdf", b"%PDF" + b"0" * (10 * 1024 * 1024), "application/pdf")])
    assert big.status_code == 422
    many = _upload(client, counselor_headers, [(f"{i}.txt", b"x", "text/plain") for i in range(11)])
    assert many.status_code == 422
    # 하나라도 어긋나면 아무것도 남기지 않는다.
    mixed = _upload(client, counselor_headers, [("좋음.txt", b"ok", "text/plain"), ("나쁨.exe", b"MZ", "application/octet-stream")])
    assert mixed.status_code == 422
    assert client.get(URL, headers=counselor_headers).json()["data"]["files"] == []
    # 경로가 섞인 이름은 이름만 남긴다. 깨진 pdf 는 미리보기 없이 올라간다.
    ok = _upload(client, counselor_headers, [("../../etc/안내.txt", b"hi", "text/plain"), ("깨짐.pdf", b"%PDF-1.4 broken", "application/pdf")])
    assert ok.status_code == 201, ok.text
    names = {f["name"]: f["preview_kind"] for f in ok.json()["data"]["files"]}
    assert names == {"안내.txt": "text", "깨짐.pdf": "other"}


def test_unknown_folder_and_file_are_404(client: TestClient, counselor_headers) -> None:
    missing = "00000000-0000-0000-0000-000000000000"

    assert _upload(client, counselor_headers, [("a.txt", b"x", "text/plain")], missing).status_code == 404
    assert client.patch(f"{URL}/files/{missing}", json={"folder_id": None}, headers=counselor_headers).status_code == 404
    assert client.get(f"{URL}/files/{missing}/download", headers=counselor_headers).status_code == 404


def test_login_is_required(client: TestClient) -> None:
    assert client.get(URL).status_code == 401
    assert client.post(f"{URL}/files", files=[("files", ("a.txt", b"x", "text/plain"))]).status_code == 401
