# 저장할 수 없는 문자 거절 테스트 (app/schemas/common.py 의 RequestModel · StorableQueryText).
#
# PostgreSQL 은 NUL(U+0000) 과 짝 없는 서로게이트(U+D800~U+DFFF)를 저장하지 못한다.
# 저장 단계까지 가면 500 이 되고 오류 로그에 원문이 실릴 수 있어, 요청의 글자 칸 전체에서 422 로 거절한다.
# 기본 SQLite 는 NUL 을 그대로 저장하므로, 422 와 함께 뒤이은 조회로 저장되지 않았는지 본다.
# 데이터는 모두 가상이다.

import json
from typing import Any, Callable, Dict, List

import pytest
from fastapi.testclient import TestClient

from app.core.enums import UserRole
from app.core.security import hash_password
from app.models.user import User
from tests.conftest import COUNSELOR_PASSWORD, create_case, create_session
from tests.test_analysis import analyzed_session
from tests.test_stt_transcript import transcribed_session

COUNSELOR_EMAIL = "counselor.a@ispot.example.com"

# JSON 본문에 그대로 넣는 이스케이프 글자다(r"" 라 파이썬 문자열에는 역슬래시가 그대로 있다).
# 서로게이트는 httpx 의 json= 으로 보내면 클라이언트에서 인코딩 오류가 나므로 원문 JSON 으로 보낸다.
BAD_ESCAPES = {
    "nul": r"\u0000",
    "surrogate": r"\ud800",
}
BAD_PARAMS = pytest.mark.parametrize(
    "escape", list(BAD_ESCAPES.values()), ids=list(BAD_ESCAPES.keys())
)

# 응답에 받은 값이 그대로 나가는지 보는 표식.
MARK = "숨김표식"
_SLOT = "@@BAD@@"


def _poison(value: str) -> str:
    """값 뒤에 표식과 나쁜 글자 자리를 붙인다. 자리는 _send 가 이스케이프로 바꾼다."""

    return f"{value}{MARK}{_SLOT}끝"


def _send(
    client: TestClient,
    method: str,
    url: str,
    payload: Any,
    escape: str,
    headers: Dict[str, str],
):
    body = json.dumps(payload, ensure_ascii=False).replace(_SLOT, escape)

    return client.request(
        method,
        url,
        content=body.encode("utf-8"),
        headers={**headers, "Content-Type": "application/json"},
    )


def _assert_rejected(response, field: str) -> None:
    assert response.status_code == 422, response.text

    error = response.json()["error"]

    assert error["code"] == "VALIDATION_ERROR"
    assert field in [item["field"] for item in error["details"]["fields"]]
    # 오류 응답에 받은 원문을 돌려주지 않는다.
    assert MARK not in response.text


def _items(response) -> List[dict]:
    assert response.status_code == 200, response.text

    return response.json()["data"]["items"]


# =========================================================
# 계정
# =========================================================

@BAD_PARAMS
@pytest.mark.parametrize("field", ["name", "password"])
def test_user_create_rejects_unstorable_text(
    client: TestClient, admin_headers, field: str, escape: str
) -> None:
    payload = {
        "email": "nul.check@ispot.example.com",
        "password": "Willow-Creek-31",
        "name": "가상상담사",
        "role": "COUNSELOR",
    }
    payload[field] = _poison(payload[field])

    _assert_rejected(_send(client, "POST", "/api/v1/auth/users", payload, escape, admin_headers), field)

    users = client.get("/api/v1/auth/users", headers=admin_headers).json()["data"]

    assert "nul.check@ispot.example.com" not in [user["email"] for user in users]


@BAD_PARAMS
def test_user_update_rejects_unstorable_text(
    client: TestClient, admin_headers, counselor_id, escape: str
) -> None:
    response = _send(
        client,
        "PATCH",
        f"/api/v1/auth/users/{counselor_id}",
        {"name": _poison("상담사A")},
        escape,
        admin_headers,
    )

    _assert_rejected(response, "name")

    users = client.get("/api/v1/auth/users", headers=admin_headers).json()["data"]

    assert [user["name"] for user in users if user["id"] == str(counselor_id)] == ["상담사A"]


@BAD_PARAMS
def test_new_password_rejects_unstorable_text(
    client: TestClient, counselor_headers, escape: str
) -> None:
    payload = {"current_password": COUNSELOR_PASSWORD, "new_password": _poison("Maple-Stone-82")}

    _assert_rejected(
        _send(client, "POST", "/api/v1/auth/me/password", payload, escape, counselor_headers),
        "new_password",
    )

    # 바뀌지 않았다. 원래 비밀번호로 로그인된다.
    login = client.post(
        "/api/v1/auth/login", json={"email": COUNSELOR_EMAIL, "password": COUNSELOR_PASSWORD}
    )

    assert login.status_code == 200


def test_login_password_with_nul_is_checked_as_usual(client: TestClient, counselor_id) -> None:
    """로그인 비밀번호는 검사하지 않는다. 틀린 비밀번호와 같은 401 이다(password_policy.py 머리말)."""

    response = client.post(
        "/api/v1/auth/login",
        json={"email": COUNSELOR_EMAIL, "password": COUNSELOR_PASSWORD + "\x00"},
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_CREDENTIALS"


def test_existing_password_with_nul_still_logs_in_and_changes(client: TestClient, db) -> None:
    """
    예전 규칙은 NUL 을 특수문자로 세어 이런 비밀번호를 만들 수 있었다.
    로그인 · 현재 비밀번호 칸까지 막으면 그런 계정이 잠긴다.
    """

    old_password = "Amber-Field-64\x00가상"
    db.add(
        User(
            email="nul.legacy@ispot.example.com",
            name="가상예전계정",
            role=UserRole.COUNSELOR,
            hashed_password=hash_password(old_password),
            is_active=True,
        )
    )
    db.commit()

    login = client.post(
        "/api/v1/auth/login",
        json={"email": "nul.legacy@ispot.example.com", "password": old_password},
    )

    assert login.status_code == 200, login.text

    headers = {"Authorization": f"Bearer {login.json()['data']['access_token']}"}
    changed = client.post(
        "/api/v1/auth/me/password",
        json={"current_password": old_password, "new_password": "Cedar-Brook-29"},
        headers=headers,
    )

    assert changed.status_code == 204, changed.text
    assert client.post(
        "/api/v1/auth/login",
        json={"email": "nul.legacy@ispot.example.com", "password": "Cedar-Brook-29"},
    ).status_code == 200


# =========================================================
# 사례
# =========================================================

_CASE_PAYLOAD = {
    "title": "가상 사례",
    "child_alias": "아동_가상",
    "child_gender": "남",
    "notes": "가상 메모",
    "case_number": "C-2099-0001",
    "guardian_type": "OTHER",
    "guardian_note": "가상 보호자",
}


@BAD_PARAMS
@pytest.mark.parametrize(
    "field", ["title", "child_alias", "child_gender", "notes", "case_number", "guardian_note"]
)
def test_case_create_rejects_unstorable_text(
    client: TestClient, counselor_headers, field: str, escape: str
) -> None:
    payload = {**_CASE_PAYLOAD, field: _poison(_CASE_PAYLOAD[field])}

    _assert_rejected(_send(client, "POST", "/api/v1/cases", payload, escape, counselor_headers), field)

    assert _items(client.get("/api/v1/cases", headers=counselor_headers)) == []


@BAD_PARAMS
@pytest.mark.parametrize("field", ["title", "child_alias", "child_gender", "notes", "guardian_note"])
def test_case_update_rejects_unstorable_text(
    client: TestClient, counselor_headers, field: str, escape: str
) -> None:
    created = create_case(client, counselor_headers, **_CASE_PAYLOAD)
    url = f"/api/v1/cases/{created['id']}"
    payload = {field: _poison(_CASE_PAYLOAD[field])}

    if field == "guardian_note":
        payload["guardian_type"] = "OTHER"

    _assert_rejected(_send(client, "PATCH", url, payload, escape, counselor_headers), field)

    stored = client.get(url, headers=counselor_headers).json()["data"]

    assert stored[field] == _CASE_PAYLOAD[field]


def test_case_search_rejects_nul(client: TestClient, counselor_headers, case: dict) -> None:
    """
    검색어는 저장되지 않지만 SQL 파라미터로 쓰인다. PostgreSQL 은 NUL 이 든 파라미터도 거절한다.
    짝 없는 서로게이트는 쿼리 문자열로 들어올 수 없다(잘못된 UTF-8 은 U+FFFD 로 바뀐다).
    """

    response = client.get(
        "/api/v1/cases", params={"search": f"{MARK}\x00끝"}, headers=counselor_headers
    )

    _assert_rejected(response, "query.search")


# =========================================================
# 회차
# =========================================================

_SESSION_PAYLOAD = {"title": "1회기 가상", "location": "가상 상담실", "memo": "가상 메모"}


@BAD_PARAMS
@pytest.mark.parametrize("field", ["title", "location", "memo"])
def test_session_create_rejects_unstorable_text(
    client: TestClient, counselor_headers, case: dict, field: str, escape: str
) -> None:
    url = f"/api/v1/cases/{case['id']}/sessions"
    payload = {**_SESSION_PAYLOAD, field: _poison(_SESSION_PAYLOAD[field])}

    _assert_rejected(_send(client, "POST", url, payload, escape, counselor_headers), field)

    assert _items(client.get(url, headers=counselor_headers)) == []


@BAD_PARAMS
@pytest.mark.parametrize("field", ["title", "location", "memo"])
def test_session_update_rejects_unstorable_text(
    client: TestClient, counselor_headers, case: dict, field: str, escape: str
) -> None:
    created = client.post(
        f"/api/v1/cases/{case['id']}/sessions", json=_SESSION_PAYLOAD, headers=counselor_headers
    ).json()["data"]
    url = f"/api/v1/sessions/{created['id']}"

    _assert_rejected(
        _send(client, "PATCH", url, {field: _poison("가상")}, escape, counselor_headers), field
    )

    stored = client.get(url, headers=counselor_headers).json()["data"]

    assert stored[field] == _SESSION_PAYLOAD[field]


# =========================================================
# 원문 수정 (중첩 모델 · 글자 목록)
# =========================================================

_TRANSCRIPT_BODIES: Dict[str, Callable[[str], dict]] = {
    "segments.0.text": lambda seg: {"segments": [{"segment_id": seg, "text": _poison("가상 수정")}]},
    "segments.0.segment_id": lambda seg: {"segments": [{"segment_id": _poison(seg), "text": "가상"}]},
    "removed_segment_ids": lambda seg: {"removed_segment_ids": [_poison(seg)]},
}


@BAD_PARAMS
@pytest.mark.parametrize("field", list(_TRANSCRIPT_BODIES))
def test_transcript_update_rejects_unstorable_text(
    client: TestClient, counselor_headers, session: dict, field: str, escape: str
) -> None:
    before = transcribed_session(client, counselor_headers, session["id"])["transcript"]
    url = f"/api/v1/sessions/{session['id']}/transcript"
    payload = _TRANSCRIPT_BODIES[field](before["segments"][0]["segment_id"])

    _assert_rejected(_send(client, "PATCH", url, payload, escape, counselor_headers), field)

    after = client.get(url, headers=counselor_headers).json()["data"]["transcript"]

    assert after["version"] == before["version"]
    assert after["segments"] == before["segments"]


# =========================================================
# 요약 검수 (글자 목록 key_points 포함)
# =========================================================

_SUMMARY_BODIES: Dict[str, dict] = {
    "overview": {"overview": _poison("가상 요약")},
    "counselor_note": {"counselor_note": _poison("가상 메모")},
    "key_points": {"key_points": ["가상 요점", _poison("가상 요점")]},
}


@BAD_PARAMS
@pytest.mark.parametrize("field", list(_SUMMARY_BODIES))
def test_summary_update_rejects_unstorable_text(
    client: TestClient, counselor_headers, session: dict, field: str, escape: str
) -> None:
    analyzed_session(client, counselor_headers, session["id"])
    url = f"/api/v1/sessions/{session['id']}/summary"
    before = client.get(url, headers=counselor_headers).json()["data"]["summary"]

    _assert_rejected(
        _send(client, "PATCH", url, _SUMMARY_BODIES[field], escape, counselor_headers), field
    )

    after = client.get(url, headers=counselor_headers)

    assert after.status_code == 200
    after_summary = after.json()["data"]["summary"]

    for key in ("overview", "key_points", "counselor_note", "is_edited"):
        assert after_summary[key] == before[key]


# =========================================================
# 상담 기록 문서
# =========================================================

_DOCUMENT_PAYLOAD = {"title": "가상 기록", "content": "가상 본문", "doc_type": "CONSULTATION_RECORD"}


@BAD_PARAMS
@pytest.mark.parametrize("field", ["title", "content", "doc_type"])
def test_document_create_rejects_unstorable_text(
    client: TestClient, counselor_headers, session: dict, field: str, escape: str
) -> None:
    url = f"/api/v1/sessions/{session['id']}/documents"
    payload = {**_DOCUMENT_PAYLOAD, field: _poison(_DOCUMENT_PAYLOAD[field])}

    _assert_rejected(_send(client, "POST", url, payload, escape, counselor_headers), field)

    assert client.get(url, headers=counselor_headers).json()["data"] == []


@BAD_PARAMS
@pytest.mark.parametrize("field", ["title", "content"])
def test_document_update_rejects_unstorable_text(
    client: TestClient, counselor_headers, session: dict, field: str, escape: str
) -> None:
    url = f"/api/v1/sessions/{session['id']}/documents"
    created = client.post(url, json=_DOCUMENT_PAYLOAD, headers=counselor_headers).json()["data"]

    _assert_rejected(
        _send(client, "PATCH", f"{url}/{created['id']}", {field: _poison("가상")}, escape, counselor_headers),
        field,
    )

    listed = client.get(url, headers=counselor_headers).json()["data"]

    assert [item[field] for item in listed] == [_DOCUMENT_PAYLOAD[field]]


# =========================================================
# 정상 글자는 그대로 통과
# =========================================================

def test_korean_emoji_and_line_breaks_pass(client: TestClient, counselor_headers) -> None:
    # 짝이 맞는 서로게이트 이스케이프(😀)는 이모지 한 글자로 풀리므로 받아야 한다.
    body = (
        '{"title": "가상 사례 \\ud83d\\ude00", "child_alias": "아동_가상 🙂",'
        ' "notes": "첫 줄\\n둘째 줄\\r\\n\\t탭 · 가나다"}'
    )
    response = client.post(
        "/api/v1/cases",
        content=body.encode("utf-8"),
        headers={**counselor_headers, "Content-Type": "application/json"},
    )

    assert response.status_code == 201, response.text

    stored = client.get(f"/api/v1/cases/{response.json()['data']['id']}", headers=counselor_headers)
    data = stored.json()["data"]

    assert data["title"] == "가상 사례 😀"
    assert data["child_alias"] == "아동_가상 🙂"
    assert data["notes"] == "첫 줄\n둘째 줄\r\n\t탭 · 가나다"

    session = create_session(client, counselor_headers, data["id"])
    found = client.get(
        "/api/v1/cases", params={"search": "가상 사례 😀"}, headers=counselor_headers
    )

    assert [item["id"] for item in _items(found)] == [data["id"]]
    assert session["case_id"] == data["id"]


def test_summary_key_points_with_emoji_pass(
    client: TestClient, counselor_headers, session: dict
) -> None:
    analyzed_session(client, counselor_headers, session["id"])

    response = client.patch(
        f"/api/v1/sessions/{session['id']}/summary",
        json={"key_points": ["가상 요점 🙂", "줄\n바꿈"], "counselor_note": "가상 메모 ✅"},
        headers=counselor_headers,
    )

    assert response.status_code == 200, response.text
    assert response.json()["data"]["key_points"] == ["가상 요점 🙂", "줄\n바꿈"]
    assert response.json()["data"]["counselor_note"] == "가상 메모 ✅"
