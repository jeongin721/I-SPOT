# 사례 개인 식별 정보 암호화 저장 테스트(API_CONTRACT 4절 '개인 식별 정보', specs case-personal-info-encryption).
#
# 이름 · 생년월일은 모두 가상 값이다(05_RULES: 실제 아동 개인정보를 개발/테스트 데이터로 쓰지 않는다).

import base64
import json
import logging
import re
import shutil
import subprocess
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import event, select, text

import scripts.reencrypt_personal_info as reencrypt_script
from app.core import pii_crypto
from app.core.config import REPO_ROOT, Settings, _PUBLIC_PII_KEYS, settings
from app.core.database import SessionLocal, engine
from app.core.enums import AuditAction
from app.core.errors import APIError
from app.core.pii_crypto import PersonalInfoCryptoError
from app.models.audit_log import AuditLog
from app.models.case import Case
from app.models.case_personal_info import ENCRYPTED_FIELDS, CasePersonalInfo
from app.models.user import User
from app.schemas.case import CaseCreateRequest, CaseListItemResponse
from app.schemas.case_personal_info import PersonalInfoRequest, PersonalInfoResponse
from app.services import personal_info_service
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


# =========================================================
# Codex #127 교차검증 지적 재현(R1 ~ R5)
# =========================================================


def _two_sessions(counselor_id, case_id: str):
    first, second = SessionLocal(), SessionLocal()
    users = (first.get(User, counselor_id), second.get(User, counselor_id))
    cases = (first.get(Case, uuid.UUID(case_id)), second.get(Case, uuid.UUID(case_id)))
    return (first, second), users, cases


def test_overlapping_puts_keep_the_last_body_whole(
    client: TestClient, counselor_headers, counselor_id, case: dict
) -> None:
    """R2: 두 저장이 같은 옛 값을 읽고 겹쳐도 나중 커밋의 본문이 통째로 남는다(칸별로 섞이지 않음)."""

    _put(client, counselor_headers, case["id"], {"child_name": CHILD, "interviewee": {"name": GUARDIAN}})
    (first, second), (user1, user2), (case1, case2) = _two_sessions(counselor_id, case["id"])

    try:
        personal_info_service.apply_personal_info(
            first, case1, user1, PersonalInfoRequest(child_name="한가온", interviewee={"name": GUARDIAN})
        )
        personal_info_service.apply_personal_info(
            second, case2, user2, PersonalInfoRequest(child_name=CHILD, interviewee={"name": SIBLING})
        )
        first.commit()
        second.commit()
    finally:
        first.close()
        second.close()

    data = _get(client, counselor_headers, case["id"]).json()["data"]

    assert (data["child_name"], data["interviewee"]["name"]) == (CHILD, SIBLING)


def _overlap(counselor_id, case_id: str, first_body: dict, last_body: dict) -> None:
    """두 요청이 같은 값을 읽은 뒤 first_body 가 먼저, last_body 가 나중에 커밋한다."""

    (first, second), (user1, user2), (case1, case2) = _two_sessions(counselor_id, case_id)

    try:
        personal_info_service.apply_personal_info(first, case1, user1, PersonalInfoRequest(**first_body))
        personal_info_service.apply_personal_info(second, case2, user2, PersonalInfoRequest(**last_body))
        first.commit()
        second.commit()
    finally:
        first.close()
        second.close()


@pytest.mark.parametrize("field", ENCRYPTED_FIELDS)
def test_overlapping_puts_clear_fields_the_last_body_left_empty(
    client: TestClient, counselor_headers, counselor_id, case: dict, field: str
) -> None:
    """재검증 R2: 비어 있던 칸을 앞 요청이 채워도 그 칸을 뺀 나중 요청이 커밋되면 비어 있다(UPDATE 에 NULL 도 실린다)."""

    base = {"child_name": CHILD} if field != "child_name" else {"interviewee": {"name": GUARDIAN}}
    _put(client, counselor_headers, case["id"], base)

    _overlap(counselor_id, case["id"], {**base, field: FULL[field]}, base)

    data = _get(client, counselor_headers, case["id"]).json()["data"]

    assert data[field] in (None, [])


def test_overlapping_puts_keep_name_index_of_the_last_body(
    client: TestClient, counselor_headers, counselor_id, case: dict, db
) -> None:
    """재검증 R2: 앞 요청이 이름을 바꿔도 나중 요청(읽은 이름 그대로)이 커밋되면 검색 색인도 그 이름이다."""

    _put(client, counselor_headers, case["id"], {"child_name": CHILD})

    _overlap(
        counselor_id,
        case["id"],
        {"child_name": "한가온"},
        {"child_name": CHILD, "interviewee": {"name": GUARDIAN}},
    )

    db.expire_all()
    row = db.get(CasePersonalInfo, uuid.UUID(case["id"]))

    assert row.child_name_index == pii_crypto.name_index(CHILD)

    def search(term: str):
        response = client.get("/api/v1/cases", params={"search": term}, headers=counselor_headers)
        return [item["id"] for item in response.json()["data"]["items"]]

    assert search(CHILD) == [case["id"]]
    assert search("한가온") == []


def test_overlapping_puts_keep_birth_year_of_the_last_body(
    client: TestClient, counselor_headers, counselor_id, case: dict, db
) -> None:
    """재검증 R2: 앞 요청이 생년월일의 해를 바꿔도 나중 요청(읽은 날짜 그대로)이 커밋되면 출생연도도 그 해다."""

    _put(client, counselor_headers, case["id"], {"child_birth_date": "2016-01-05"})

    _overlap(
        counselor_id,
        case["id"],
        {"child_birth_date": "2017-01-05"},
        {"child_birth_date": "2016-01-05", "interviewee": {"name": GUARDIAN}},
    )

    db.expire_all()

    assert db.get(Case, uuid.UUID(case["id"])).child_birth_year == 2016
    assert _get(client, counselor_headers, case["id"]).json()["data"]["child_birth_date"] == "2016-01-05"


def test_save_locks_the_row_it_reads(client: TestClient, counselor_headers, counselor_id, case: dict) -> None:
    """재검증 N1: 저장은 읽는 행을 잠근다(PostgreSQL FOR UPDATE) — 같은 사례의 저장이 차례로 돌아 감사의 바뀐 칸이 실제와 맞는다."""

    _put(client, counselor_headers, case["id"], {"child_name": CHILD})
    statements: list = []

    def capture(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    session = SessionLocal()
    event.listen(engine, "before_cursor_execute", capture)

    try:
        personal_info_service.apply_personal_info(
            session,
            session.get(Case, uuid.UUID(case["id"])),
            session.get(User, counselor_id),
            PersonalInfoRequest(child_name=SIBLING),
        )
    finally:
        event.remove(engine, "before_cursor_execute", capture)
        session.rollback()
        session.close()

    reads = [s for s in statements if s.lstrip().upper().startswith("SELECT") and "case_personal_infos" in s]

    assert reads
    if engine.dialect.name == "postgresql":
        assert any("FOR UPDATE" in s.upper() for s in reads)


def test_overlapping_first_saves_answer_409_not_500(
    client: TestClient, counselor_headers, counselor_id, case: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    """R2: 행이 없는 사례에 처음 저장이 겹치면 늦은 쪽은 409 DUPLICATE_RESOURCE, 먼저 저장한 값은 그대로."""

    (first, second), (user1, user2), (case1, case2) = _two_sessions(counselor_id, case["id"])
    original = pii_crypto.encrypt_text
    state = {"done": False}

    def encrypt_after_other_save(plaintext, *, case_id, field):
        # 늦은 요청이 '행 없음' 을 읽은 뒤 · 넣기 전에 먼저 요청이 저장을 마친다.
        if not state["done"]:
            state["done"] = True
            personal_info_service.apply_personal_info(first, case1, user1, PersonalInfoRequest(child_name=CHILD))
            first.commit()
        return original(plaintext, case_id=case_id, field=field)

    monkeypatch.setattr(pii_crypto, "encrypt_text", encrypt_after_other_save)

    try:
        with pytest.raises(APIError) as caught:
            personal_info_service.apply_personal_info(second, case2, user2, PersonalInfoRequest(child_name=SIBLING))
    finally:
        first.close()
        second.close()

    assert caught.value.status_code == 409
    assert caught.value.code.value == "DUPLICATE_RESOURCE"
    monkeypatch.setattr(pii_crypto, "encrypt_text", original)
    assert _get(client, counselor_headers, case["id"]).json()["data"]["child_name"] == CHILD


def test_reencrypt_does_not_overwrite_a_save_made_meanwhile(
    client: TestClient, counselor_headers, case: dict, db, monkeypatch: pytest.MonkeyPatch
) -> None:
    """R1: script 가 행을 읽은 뒤 API 저장이 끼면, script 는 옛 값으로 덮지 않고 다시 읽는다."""

    _put(client, counselor_headers, case["id"], {"child_name": CHILD})
    monkeypatch.setattr(settings, "PII_ENCRYPTION_KEYS", f"{NEW_KEY},{OLD_KEYS}")
    original = reencrypt_script._decrypt_row
    state = {"done": False}

    def decrypt_then_api_saves(row):
        plain = original(row)
        if not state["done"]:
            state["done"] = True
            assert _put(client, counselor_headers, case["id"], {"child_name": SIBLING}).status_code == 200
        return plain

    monkeypatch.setattr(reencrypt_script, "_decrypt_row", decrypt_then_api_saves)

    result = reencrypt_all(db)

    assert result.busy_case_ids == [] and result.failed_case_ids == []
    assert _get(client, counselor_headers, case["id"]).json()["data"]["child_name"] == SIBLING

    db.expire_all()
    row = db.get(CasePersonalInfo, uuid.UUID(case["id"]))

    assert row.child_name_enc.startswith("v1.new2.")
    assert row.child_name_index == pii_crypto.name_index(SIBLING)


def test_same_birth_date_restores_birth_year(client: TestClient, counselor_headers, case: dict, db) -> None:
    """R3: 출생연도만 따로 고쳐도 같은 생년월일을 다시 저장하면 그 해로 돌아온다."""

    _put(client, counselor_headers, case["id"], {"child_birth_date": "2016-01-05"})
    client.patch(f"/api/v1/cases/{case['id']}", json={"child_birth_year": 2020}, headers=counselor_headers)
    _put(client, counselor_headers, case["id"], {"child_birth_date": "2016-01-05"})

    detail = client.get(f"/api/v1/cases/{case['id']}", headers=counselor_headers).json()["data"]
    last = _audit(db, AuditAction.CASE_PERSONAL_INFO_UPDATED)[-1]

    assert detail["child_birth_year"] == 2016
    assert last.detail == {"changed_fields": ["child_birth_year"]}


def test_schemas_do_not_print_values() -> None:
    """R4: 요청 · 응답 · 중첩 스키마를 repr · str 로 찍어도 값이 나오지 않는다. 검증 오류 문구에도 입력값이 없다."""

    request = PersonalInfoRequest.model_validate(FULL)
    texts = [
        repr(request),
        str(request),
        repr(request.family_members[0]),
        repr(request.health),
        repr(PersonalInfoResponse(child_name=CHILD, family_members=FULL["family_members"])),
        repr(CaseCreateRequest(title="t", child_alias="a", personal_info=FULL)),
        repr(CaseListItemResponse.model_construct(child_name=CHILD)),
    ]

    with pytest.raises(ValidationError) as caught:
        PersonalInfoRequest.model_validate({**FULL, "child_birth_date": "2999-01-01"})

    child_error = str(caught.value)
    texts.append(child_error)

    # 재검증 R4: 부모 요청(새 사례 등록)의 중첩 검증 오류 문구에도 입력값이 없다.
    with pytest.raises(ValidationError) as parent:
        CaseCreateRequest.model_validate({"title": "t", "child_alias": "a", "personal_info": {**FULL, "child_name": CHILD * 30}})

    parent_text = str(parent.value)
    texts.append(parent_text)
    assert "child_name" in parent_text

    for item in texts:
        _assert_no_secret(item)
    assert "2999" not in child_error


_BASH = shutil.which("bash")


@pytest.mark.skipif(_BASH is None, reason="bash 가 있어야 돌릴 수 있다")
@pytest.mark.parametrize(
    ("env", "stops"),
    [
        ("ENV=production\n", True),
        ("ENV=production\nPII_ENCRYPTION_KEYS=   \nPII_INDEX_KEY=   \n", True),
        ("ENV=production\nPII_ENCRYPTION_KEYS=k1:abc\nPII_INDEX_KEY=\n", True),
        ("ENV=production\nPII_ENCRYPTION_KEYS=k1:abc\nPII_INDEX_KEY=xyz\n", False),
        ("ENV=local\n", False),
    ],
)
def test_deploy_stops_before_switching_when_keys_are_missing(tmp_path: Path, env: str, stops: bool) -> None:
    """R5: 배포 스크립트의 키 검사(공백뿐인 값도 없는 것으로 봄). 스크립트의 그 덩어리만 떼어 돌린다."""

    script = (REPO_ROOT / "deploy" / "web-deploy.sh").read_text(encoding="utf-8")
    block = re.search(r"^# 개인 식별 정보 키\(2026-10-30\).*?^fi$", script, re.S | re.M)

    assert block is not None

    env_file = tmp_path / "backend.env"
    env_file.write_bytes(env.encode("utf-8"))
    runner = tmp_path / "guard.sh"
    runner.write_bytes(f'ENV_FILE="{env_file.as_posix()}"\n{block.group(0)}\necho PASSED\n'.encode("utf-8"))

    result = subprocess.run([_BASH, str(runner)], capture_output=True, text=True, encoding="utf-8")

    assert (result.returncode == 1) is stops
    assert ("PASSED" in result.stdout) is not stops
    assert "abc" not in result.stdout + result.stderr
