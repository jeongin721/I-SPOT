# 사례 개인 식별 정보 암호화 저장 테스트(API_CONTRACT 4절 '개인 식별 정보', specs case-personal-info-encryption).
#
# 이름 · 생년월일은 모두 가상 값이다(05_RULES: 실제 아동 개인정보를 개발/테스트 데이터로 쓰지 않는다).

import base64
import json
import logging
import uuid

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import select, text

from app.core import pii_crypto
from app.core.config import Settings, _PUBLIC_PII_KEYS, settings
from app.core.enums import AuditAction
from app.core.pii_crypto import PersonalInfoCryptoError
from app.models.audit_log import AuditLog
from app.models.case_personal_info import CasePersonalInfo
from scripts.reencrypt_personal_info import reencrypt_all
from tests.conftest import create_case

CHILD = "한가람"
GUARDIAN = "한누리"
SIBLING = "한바다"

FULL = {
    "child_name": CHILD,
    "child_birth_date": "2015-04-12",
    "target_person": {"name": GUARDIAN, "relation": "부", "birth_date": "1983-09-02"},
    "interviewee": {"name": GUARDIAN, "relation": "부"},
    "family_members": [
        {"name": GUARDIAN, "relation": "부", "age": 43, "religion": "무교", "living_together": True},
        {"name": SIBLING, "relation": "형제", "age": 14, "education": "중학교", "living_together": True},
    ],
    "health": {
        "subject_name": SIBLING,
        "items": [{"kind": "정신과 진단", "present": True, "detail": "가상 진단명"}],
    },
}

# 저장 · 로그 · 감사 기록 어디에도 나오면 안 되는 글자.
SECRETS = [CHILD, GUARDIAN, SIBLING, "가상 진단명", "2015-04-12", "1983-09-02"]

OLD_KEYS = settings.PII_ENCRYPTION_KEYS
NEW_KEY = "new2:" + base64.b64encode(b"test-only-pii-encrypt-key-000002").decode()


def _put(client: TestClient, headers, case_id: str, body: dict):
    return client.put(f"/api/v1/cases/{case_id}/personal-info", json=body, headers=headers)


def _get(client: TestClient, headers, case_id: str):
    return client.get(f"/api/v1/cases/{case_id}/personal-info", headers=headers)


def _audit(db, *actions: AuditAction):
    return db.scalars(
        select(AuditLog).where(AuditLog.action.in_(actions)).order_by(AuditLog.created_at)
    ).all()


def _assert_no_secret(blob: str) -> None:
    for secret in SECRETS:
        assert secret not in blob


# =========================================================
# 암호화 모듈
# =========================================================


def test_encrypt_round_trip_with_fresh_nonce() -> None:
    case_id = uuid.uuid4()
    first = pii_crypto.encrypt_text(CHILD, case_id=case_id, field="child_name")
    second = pii_crypto.encrypt_text(CHILD, case_id=case_id, field="child_name")

    assert first != second  # 값마다 새 nonce
    assert first.startswith("v1.test1.")
    assert CHILD not in first
    assert pii_crypto.decrypt_text(first, case_id=case_id, field="child_name") == CHILD


def test_ciphertext_is_bound_to_case_and_field() -> None:
    case_id = uuid.uuid4()
    token = pii_crypto.encrypt_text(CHILD, case_id=case_id, field="child_name")

    with pytest.raises(PersonalInfoCryptoError):
        pii_crypto.decrypt_text(token, case_id=uuid.uuid4(), field="child_name")

    with pytest.raises(PersonalInfoCryptoError):
        pii_crypto.decrypt_text(token, case_id=case_id, field="interviewee")


@pytest.mark.parametrize(
    "mangle",
    [
        lambda token: token[:-2] + ("AA" if not token.endswith("AA") else "BB"),  # 태그 · 암호문 바뀜
        lambda token: token.replace("v1.", "v2.", 1),  # 모르는 형식
        lambda token: token.replace(".test1.", ".nokey.", 1),  # 설정에 없는 키
        lambda token: ".".join(token.split(".")[:3]),  # 조각 빠짐
        lambda token: "v1.test1.!!!.@@@",  # base64 아님
        lambda token: "v1.test1.AAAA." + token.split(".")[3],  # nonce 길이 틀림
    ],
)
def test_broken_tokens_are_rejected_without_value_in_message(mangle) -> None:
    case_id = uuid.uuid4()
    token = pii_crypto.encrypt_text(CHILD, case_id=case_id, field="child_name")

    with pytest.raises(PersonalInfoCryptoError) as caught:
        pii_crypto.decrypt_text(mangle(token), case_id=case_id, field="child_name")

    assert CHILD not in str(caught.value)


def test_old_key_still_decrypts_while_listed(monkeypatch: pytest.MonkeyPatch) -> None:
    case_id = uuid.uuid4()
    old_token = pii_crypto.encrypt_text(CHILD, case_id=case_id, field="child_name")

    monkeypatch.setattr(settings, "PII_ENCRYPTION_KEYS", f"{NEW_KEY},{OLD_KEYS}")

    assert pii_crypto.active_key_id() == "new2"
    assert pii_crypto.encrypt_text(CHILD, case_id=case_id, field="child_name").startswith("v1.new2.")
    assert pii_crypto.decrypt_text(old_token, case_id=case_id, field="child_name") == CHILD

    monkeypatch.setattr(settings, "PII_ENCRYPTION_KEYS", NEW_KEY)

    with pytest.raises(PersonalInfoCryptoError):
        pii_crypto.decrypt_text(old_token, case_id=case_id, field="child_name")


def test_name_index_ignores_spaces_and_depends_on_index_key(monkeypatch: pytest.MonkeyPatch) -> None:
    index = pii_crypto.name_index("한가람")

    assert index == pii_crypto.name_index(" 한 가람 ")
    assert index != pii_crypto.name_index("가람")
    assert pii_crypto.name_index("   ") is None
    assert "한가람" not in index

    monkeypatch.setattr(
        settings, "PII_INDEX_KEY", base64.b64encode(b"test-only-pii-index-key-00000002").decode()
    )

    assert pii_crypto.name_index("한가람") != index


# =========================================================
# 설정 — 운영에서 공개 키 · 틀린 키로 뜨지 않음
# =========================================================


def _settings(**overrides) -> Settings:
    return Settings(_env_file=None, **overrides)


def test_production_rejects_public_development_keys() -> None:
    with pytest.raises(ValidationError, match="PII_ENCRYPTION_KEYS"):
        _settings(ENV="production", PII_ENCRYPTION_KEYS="dev1:" + _PUBLIC_PII_KEYS[0])

    with pytest.raises(ValidationError, match="PII_INDEX_KEY"):
        _settings(ENV="production", PII_INDEX_KEY=_PUBLIC_PII_KEYS[1])


def test_local_accepts_public_development_keys() -> None:
    local = _settings(
        ENV="local",
        PII_ENCRYPTION_KEYS="dev1:" + _PUBLIC_PII_KEYS[0],
        PII_INDEX_KEY=_PUBLIC_PII_KEYS[1],
    )

    assert local.PII_ENCRYPTION_KEYS.startswith("dev1:")


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"PII_ENCRYPTION_KEYS": "k1:" + base64.b64encode(b"short").decode()}, "32바이트"),
        ({"PII_ENCRYPTION_KEYS": "k1:not*base64*at*all"}, "base64"),
        ({"PII_ENCRYPTION_KEYS": base64.b64encode(b"x" * 32).decode()}, "키이름"),
        ({"PII_ENCRYPTION_KEYS": "k.1:" + base64.b64encode(b"x" * 32).decode()}, "키이름"),
        (
            {"PII_ENCRYPTION_KEYS": "k1:{0},k1:{0}".format(base64.b64encode(b"x" * 32).decode())},
            "두 번",
        ),
        ({"PII_ENCRYPTION_KEYS": " , "}, "비어"),
        ({"PII_INDEX_KEY": base64.b64encode(b"short").decode()}, "PII_INDEX_KEY"),
    ],
)
def test_malformed_keys_stop_startup_in_every_environment(overrides: dict, message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        _settings(ENV="local", **overrides)


def test_index_key_must_differ_from_encryption_keys() -> None:
    same = base64.b64encode(b"y" * 32).decode()

    with pytest.raises(ValidationError, match="다른 값"):
        _settings(ENV="local", PII_ENCRYPTION_KEYS=f"k1:{same}", PII_INDEX_KEY=same)


def test_key_errors_do_not_print_key_values() -> None:
    value = base64.b64encode(b"z" * 31).decode()

    with pytest.raises(ValidationError) as caught:
        _settings(ENV="production", PII_ENCRYPTION_KEYS=f"k1:{value}")

    assert value not in str(caught.value)


# =========================================================
# 창구 — 저장 · 조회 · 권한 · 열람 기록
# =========================================================


def test_put_then_get_returns_decrypted_values(
    client: TestClient, counselor_headers, case: dict
) -> None:
    before = _get(client, counselor_headers, case["id"])

    assert before.status_code == 200
    assert before.json()["data"]["registered"] is False
    assert before.json()["data"]["family_members"] == []

    saved = _put(client, counselor_headers, case["id"], FULL)

    assert saved.status_code == 200, saved.text
    assert saved.json()["data"]["child_name"] == CHILD
    assert saved.json()["data"]["registered"] is True

    data = _get(client, counselor_headers, case["id"]).json()["data"]

    assert data["child_name"] == CHILD
    assert data["child_birth_date"] == "2015-04-12"
    assert data["target_person"] == {"name": GUARDIAN, "relation": "부", "birth_date": "1983-09-02"}
    assert [member["name"] for member in data["family_members"]] == [GUARDIAN, SIBLING]
    assert data["family_members"][1]["education"] == "중학교"
    assert data["health"]["items"][0] == {"kind": "정신과 진단", "present": True, "detail": "가상 진단명"}
    assert data["updated_at"] is not None


def test_database_holds_only_ciphertext(client: TestClient, counselor_headers, case: dict, db) -> None:
    _put(client, counselor_headers, case["id"], FULL)

    rows = db.execute(text("SELECT * FROM case_personal_infos")).mappings().all()

    assert len(rows) == 1
    _assert_no_secret(json.dumps({key: str(value) for key, value in rows[0].items()}, ensure_ascii=False))

    for field in ("child_name", "child_birth_date", "target_person", "interviewee", "family_members", "health"):
        assert rows[0][f"{field}_enc"].startswith("v1.test1.")


def test_other_counselor_is_forbidden_and_admin_can_read(
    client: TestClient, counselor_headers, other_counselor_headers, admin_headers, case: dict
) -> None:
    _put(client, counselor_headers, case["id"], FULL)

    assert _get(client, other_counselor_headers, case["id"]).status_code == 403
    assert _put(client, other_counselor_headers, case["id"], {"child_name": "다른이름"}).status_code == 403
    assert _get(client, admin_headers, case["id"]).json()["data"]["child_name"] == CHILD
    assert _get(client, counselor_headers, str(uuid.uuid4())).status_code == 404


def test_requires_login(client: TestClient, case: dict) -> None:
    assert client.get(f"/api/v1/cases/{case['id']}/personal-info").status_code == 401


def test_views_and_updates_are_audited_without_values(
    client: TestClient, counselor_headers, counselor_id, case: dict, db
) -> None:
    _put(client, counselor_headers, case["id"], FULL)
    _put(client, counselor_headers, case["id"], FULL)  # 바뀐 것 없음 → 기록 없음
    _put(client, counselor_headers, case["id"], {**FULL, "interviewee": None})
    _get(client, counselor_headers, case["id"])

    updates = _audit(db, AuditAction.CASE_PERSONAL_INFO_UPDATED)
    views = _audit(db, AuditAction.CASE_PERSONAL_INFO_VIEWED)

    assert [log.detail["changed_fields"] for log in updates] == [
        ["child_name", "child_birth_date", "target_person", "interviewee", "family_members", "health"],
        ["interviewee"],
    ]
    assert len(views) == 1
    assert views[0].actor_id == counselor_id
    assert str(views[0].case_id) == case["id"]
    assert views[0].detail == {
        "fields": ["child_name", "child_birth_date", "target_person", "family_members", "health"]
    }

    every_detail = json.dumps([log.detail for log in db.scalars(select(AuditLog))], ensure_ascii=False)
    _assert_no_secret(every_detail)


def test_birth_date_sets_case_birth_year(client: TestClient, counselor_headers, case: dict) -> None:
    _put(client, counselor_headers, case["id"], {"child_birth_date": "2016-01-05"})

    detail = client.get(f"/api/v1/cases/{case['id']}", headers=counselor_headers).json()["data"]

    assert detail["child_birth_year"] == 2016
    # 일반 사례 응답에는 실명 칸이 없다.
    assert "child_name" not in detail
    assert "personal_info" not in detail


def test_put_replaces_everything(client: TestClient, counselor_headers, case: dict) -> None:
    _put(client, counselor_headers, case["id"], FULL)
    cleared = _put(client, counselor_headers, case["id"], {})

    assert cleared.json()["data"]["registered"] is False
    assert _get(client, counselor_headers, case["id"]).json()["data"]["child_name"] is None


@pytest.mark.parametrize(
    "body",
    [
        {"child_name": CHILD, "child_birth_date": "2999-01-01"},
        {"child_name": CHILD * 30},
        {"child_name": "  "},
        {"child_name": CHILD, "family_members": [{"name": SIBLING}] * 31},
        {"child_name": CHILD, "health": {"items": [{"kind": "질병"}, {"kind": "질병"}]}},
        {"child_name": CHILD, "health": {"items": [{"kind": "감기"}]}},
        {"child_name": CHILD + "\u0000"},
    ],
)
def test_invalid_values_are_422_without_echoing_input(
    client: TestClient, counselor_headers, case: dict, body: dict
) -> None:
    response = _put(client, counselor_headers, case["id"], body)

    assert response.status_code == 422
    assert CHILD not in response.text
    assert SIBLING not in response.text


# =========================================================
# 새 사례 등록 · 목록 · 검색 · 삭제
# =========================================================


def test_create_case_with_personal_info(client: TestClient, counselor_headers) -> None:
    created = create_case(client, counselor_headers, personal_info=FULL)

    assert "child_name" not in created
    assert "personal_info" not in created
    assert _get(client, counselor_headers, created["id"]).json()["data"]["child_name"] == CHILD


def test_create_case_with_invalid_personal_info_creates_nothing(
    client: TestClient, counselor_headers, db
) -> None:
    response = client.post(
        "/api/v1/cases",
        json={"title": "사례", "child_alias": "아동_X", "personal_info": {"child_birth_date": "2999-01-01"}},
        headers=counselor_headers,
    )

    assert response.status_code == 422
    assert client.get("/api/v1/cases", headers=counselor_headers).json()["data"]["meta"]["total"] == 0


def test_list_names_only_when_asked_and_audited_once(
    client: TestClient, counselor_headers, counselor_id, db
) -> None:
    named = create_case(client, counselor_headers, personal_info={"child_name": CHILD})
    unnamed = create_case(client, counselor_headers)

    plain = client.get("/api/v1/cases", headers=counselor_headers).json()["data"]["items"]

    assert all(item["child_name"] is None for item in plain)
    assert _audit(db, AuditAction.CASE_LIST_PERSONAL_INFO_VIEWED) == []

    items = client.get(
        "/api/v1/cases", params={"with_child_name": "true"}, headers=counselor_headers
    ).json()["data"]["items"]
    names = {item["id"]: item["child_name"] for item in items}

    assert names == {named["id"]: CHILD, unnamed["id"]: None}

    logs = _audit(db, AuditAction.CASE_LIST_PERSONAL_INFO_VIEWED)

    assert len(logs) == 1
    assert logs[0].actor_id == counselor_id
    assert logs[0].detail == {"case_ids": [named["id"]], "count": 1}


def test_list_names_never_cross_counselors(
    client: TestClient, counselor_headers, other_counselor_headers
) -> None:
    create_case(client, counselor_headers, personal_info={"child_name": CHILD})
    create_case(client, other_counselor_headers, personal_info={"child_name": SIBLING})

    items = client.get(
        "/api/v1/cases", params={"with_child_name": "true"}, headers=other_counselor_headers
    ).json()["data"]["items"]

    assert [item["child_name"] for item in items] == [SIBLING]


def test_search_matches_exact_name_only(
    client: TestClient, counselor_headers, other_counselor_headers
) -> None:
    mine = create_case(client, counselor_headers, personal_info={"child_name": CHILD})
    create_case(client, counselor_headers, personal_info={"child_name": SIBLING})

    def search(headers, term: str):
        response = client.get("/api/v1/cases", params={"search": term}, headers=headers)
        return [item["id"] for item in response.json()["data"]["items"]]

    assert search(counselor_headers, CHILD) == [mine["id"]]
    assert search(counselor_headers, " 한 가람 ") == [mine["id"]]
    assert search(counselor_headers, "가람") == []  # 부분 검색은 안 됨
    assert search(other_counselor_headers, CHILD) == []  # 남의 사례는 이름으로도 안 나옴


def test_deleting_case_removes_personal_info(
    client: TestClient, counselor_headers, admin_headers, case: dict, db
) -> None:
    _put(client, counselor_headers, case["id"], FULL)

    assert client.delete(f"/api/v1/cases/{case['id']}", headers=admin_headers).status_code == 204
    assert db.scalars(select(CasePersonalInfo)).all() == []


# =========================================================
# 풀 수 없는 값 · 로그
# =========================================================


def _corrupt(db, case_id: str) -> None:
    row = db.get(CasePersonalInfo, uuid.UUID(case_id))
    token = row.child_name_enc
    row.child_name_enc = token[:-2] + ("AA" if not token.endswith("AA") else "BB")
    db.commit()


def test_unreadable_value_is_500_without_value(
    client: TestClient, counselor_headers, case: dict, db, caplog
) -> None:
    _put(client, counselor_headers, case["id"], FULL)
    _corrupt(db, case["id"])

    with caplog.at_level(logging.ERROR):
        response = _get(client, counselor_headers, case["id"])

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "PERSONAL_INFO_UNAVAILABLE"
    _assert_no_secret(response.text)
    assert f"case_id={case['id']}" in caplog.text
    _assert_no_secret(caplog.text)

    # 목록은 그 줄만 이름 없이 둔다.
    items = client.get(
        "/api/v1/cases", params={"with_child_name": "true"}, headers=counselor_headers
    ).json()["data"]["items"]

    assert items[0]["child_name"] is None

    # 다시 저장하면 고쳐진다.
    assert _put(client, counselor_headers, case["id"], FULL).status_code == 200
    assert _get(client, counselor_headers, case["id"]).json()["data"]["child_name"] == CHILD


def test_values_never_reach_logs(client: TestClient, counselor_headers, caplog) -> None:
    with caplog.at_level(logging.DEBUG):
        created = create_case(client, counselor_headers, personal_info=FULL)
        _get(client, counselor_headers, created["id"])
        _put(client, counselor_headers, created["id"], {**FULL, "child_name": "한가온"})
        client.get("/api/v1/cases", params={"with_child_name": "true", "search": CHILD}, headers=counselor_headers)
        _put(client, counselor_headers, created["id"], {"child_birth_date": "2999-01-01"})

    _assert_no_secret(caplog.text)
    assert "한가온" not in caplog.text


# =========================================================
# 키 바꾸기 script
# =========================================================


def test_reencrypt_moves_old_values_to_new_key(
    client: TestClient, counselor_headers, case: dict, db, monkeypatch: pytest.MonkeyPatch
) -> None:
    _put(client, counselor_headers, case["id"], FULL)
    monkeypatch.setattr(settings, "PII_ENCRYPTION_KEYS", f"{NEW_KEY},{OLD_KEYS}")

    dry = reencrypt_all(db, dry_run=True)

    assert (dry.rows, dry.changed_rows, dry.changed_fields) == (1, 1, 6)
    assert db.get(CasePersonalInfo, uuid.UUID(case["id"])).child_name_enc.startswith("v1.test1.")

    result = reencrypt_all(db)

    assert (result.changed_rows, result.changed_fields, result.failed_case_ids) == (1, 6, [])
    db.expire_all()
    assert db.get(CasePersonalInfo, uuid.UUID(case["id"])).child_name_enc.startswith("v1.new2.")

    # 옛 키를 빼도 풀린다.
    monkeypatch.setattr(settings, "PII_ENCRYPTION_KEYS", NEW_KEY)
    assert _get(client, counselor_headers, case["id"]).json()["data"]["child_name"] == CHILD
    assert reencrypt_all(db).changed_rows == 0


def test_reencrypt_reports_rows_it_cannot_read(
    client: TestClient, counselor_headers, case: dict, db, monkeypatch: pytest.MonkeyPatch
) -> None:
    _put(client, counselor_headers, case["id"], FULL)
    monkeypatch.setattr(settings, "PII_ENCRYPTION_KEYS", NEW_KEY)

    result = reencrypt_all(db)

    assert result.failed_case_ids == [uuid.UUID(case["id"])]
    assert result.changed_rows == 0


def test_reindex_after_index_key_change(
    client: TestClient, counselor_headers, case: dict, db, monkeypatch: pytest.MonkeyPatch
) -> None:
    _put(client, counselor_headers, case["id"], {"child_name": CHILD})
    monkeypatch.setattr(
        settings, "PII_INDEX_KEY", base64.b64encode(b"test-only-pii-index-key-00000002").decode()
    )

    def found() -> bool:
        items = client.get("/api/v1/cases", params={"search": CHILD}, headers=counselor_headers).json()
        return bool(items["data"]["items"])

    assert not found()
    assert reencrypt_all(db, reindex=True).reindexed_rows == 1
    assert found()
