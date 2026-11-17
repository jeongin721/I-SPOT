# 고령자 봉인 칸 — 확인사항 글 · 영역 기록 글 암호화와 키 바꾸기(민규 72fc991 리뷰 11/17). 데이터는 모두 가상이다.
#  1) next_checks 의 text · result_note, care_domain_notes 의 text · change_note 가 DB 에 평문으로 남지 않는다.
#  2) reencrypt_personal_info 가 고령자 봉인 칸(건강 정보 · 측정값 · 확인사항 · 영역 기록)도 새 키로 옮겨, 옛 키를 빼도 풀린다.

import base64

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core.config import settings
from app.services import senior_service
from scripts.reencrypt_personal_info import SEALED_MODELS, reencrypt_all
from tests.conftest import create_case, create_session

OLD_KEYS = settings.PII_ENCRYPTION_KEYS
NEW_KEY = "new2:" + base64.b64encode(b"test-only-pii-encrypt-key-000002").decode()

CHECK_TEXT = "가상확인글 아드님 연락 여쭙기"
RESULT_NOTE = "가상결과메모 통화하셨다고 함"
DOMAIN_TEXT = "가상영역글 매일 아침 산책"
HEALTH_NOTE = "가상건강메모 무릎 불편"
SECRETS = [CHECK_TEXT, RESULT_NOTE, DOMAIN_TEXT, HEALTH_NOTE]


@pytest.fixture(autouse=True)
def _clean():
    senior_service.reset_limits()
    yield
    senior_service.reset_limits()


def _fill(client: TestClient, headers) -> dict:
    case = create_case(client, headers, subject_type="SENIOR", child_alias="어르신_009", child_birth_year=1940)
    cid = case["id"]
    r = client.patch(f"/api/v1/cases/{cid}/senior-profile", json={"health_notes": HEALTH_NOTE}, headers=headers)
    assert r.status_code == 200, r.text
    r = client.post(f"/api/v1/cases/{cid}/health-measurements", json={"measured_at": "2026-11-10T10:00:00+09:00", "systolic": 131, "diastolic": 82}, headers=headers)
    assert r.status_code == 201, r.text
    r = client.post(f"/api/v1/cases/{cid}/next-checks", json={"items": [{"text": CHECK_TEXT}]}, headers=headers)
    assert r.status_code == 201, r.text
    check_id = r.json()["data"][0]["id"]
    r = client.patch(f"/api/v1/cases/{cid}/next-checks/{check_id}", json={"status": "DONE", "result_note": RESULT_NOTE}, headers=headers)
    assert r.status_code == 200, r.text
    session = create_session(client, headers, cid)
    r = client.put(f"/api/v1/sessions/{session['id']}/care-domains", json={"items": [{"domain": "OUTING", "change": "NEW", "text": DOMAIN_TEXT}]}, headers=headers)
    assert r.status_code == 200, r.text
    return {"case": cid, "session": session["id"]}


def _read_back(client: TestClient, headers, ids: dict) -> None:
    checks = client.get(f"/api/v1/cases/{ids['case']}/next-checks", headers=headers).json()["data"]
    assert checks[0]["text"] == CHECK_TEXT and checks[0]["result_note"] == RESULT_NOTE
    domains = client.get(f"/api/v1/sessions/{ids['session']}/care-domains", headers=headers).json()["data"]["domains"]
    assert [d["saved"]["text"] for d in domains if d["saved"]] == [DOMAIN_TEXT]
    profile = client.get(f"/api/v1/cases/{ids['case']}/senior-profile", headers=headers).json()["data"]
    assert profile["health_notes"] == HEALTH_NOTE


def test_check_and_domain_text_are_not_stored_plain(client: TestClient, counselor_headers, db) -> None:
    ids = _fill(client, counselor_headers)
    _read_back(client, counselor_headers, ids)
    for table in ("next_checks", "care_domain_notes", "senior_profiles", "health_measurements"):
        rows = db.execute(text(f"SELECT * FROM {table}")).mappings().all()
        dump = " ".join(str(v) for row in rows for v in row.values())
        for secret in SECRETS:
            assert secret not in dump, (table, secret)
        assert all(row["sealed_values"] for row in rows), table


def test_reencrypt_moves_senior_sealed_values_to_new_key(
    client: TestClient, counselor_headers, db, monkeypatch: pytest.MonkeyPatch
) -> None:
    ids = _fill(client, counselor_headers)
    monkeypatch.setattr(settings, "PII_ENCRYPTION_KEYS", f"{NEW_KEY},{OLD_KEYS}")

    dry = reencrypt_all(db, dry_run=True)
    assert dry.sealed_rows == dry.sealed_changed == 4  # 프로필 · 측정 · 확인사항 · 영역 기록 한 줄씩

    result = reencrypt_all(db)
    assert (result.sealed_changed, result.sealed_failed, result.sealed_busy) == (4, [], [])
    db.expire_all()
    for model in SEALED_MODELS:
        for (token,) in db.execute(text(f"SELECT sealed_values FROM {model.__tablename__}")):
            assert token.startswith("v1.new2."), model.__tablename__

    # 옛 키를 빼도 풀린다. 다시 돌리면 바꿀 것이 없다.
    monkeypatch.setattr(settings, "PII_ENCRYPTION_KEYS", NEW_KEY)
    _read_back(client, counselor_headers, ids)
    assert reencrypt_all(db).sealed_changed == 0


def test_reencrypt_reports_sealed_rows_it_cannot_read(
    client: TestClient, counselor_headers, db, monkeypatch: pytest.MonkeyPatch
) -> None:
    _fill(client, counselor_headers)
    monkeypatch.setattr(settings, "PII_ENCRYPTION_KEYS", NEW_KEY)  # 옛 키를 먼저 뺀 실수

    result = reencrypt_all(db)
    assert len(result.sealed_failed) == 4 and result.sealed_changed == 0
    assert all(":" in label for label in result.sealed_failed)  # 표 이름:줄 ID 만(값 없음)
