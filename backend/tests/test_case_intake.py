# 사례의 초기면접(서식 4 ②) 아동 특성 · 가정상황 칸 테스트.
#
# 서식 항목만 받고(그 밖은 422), 겹친 항목은 하나로 합치며, 수정은 목록을 통째로 바꾼다.
# 감사 기록에는 바뀐 칸 이름만 남기고 고른 항목은 남기지 않는다.
# 상담사 웹의 항목 목록(counselor-web/src/data/screens/intakeItems.ts)과 같은지도 본다.

import re
import uuid
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, text

from app.core.enums import AuditAction
from app.core.intake import INTAKE_CHILD_TRAITS, INTAKE_FAMILY_SITUATIONS
from app.models.audit_log import AuditLog
from app.models.case import Case
from tests.conftest import create_case
from tests.test_migrations import _alembic

REPO_DIR = Path(__file__).resolve().parents[2]
WEB_ITEMS = REPO_DIR / "counselor-web" / "src" / "data" / "screens" / "intakeItems.ts"

# 초기면접 칸을 추가하기 바로 전 revision
BEFORE_INTAKE = "a3538c45b811"


def _patch(client: TestClient, headers, case_id: str, payload: dict):
    return client.patch(f"/api/v1/cases/{case_id}", json=payload, headers=headers)


def test_new_case_has_empty_intake_lists(client: TestClient, counselor_headers) -> None:
    data = create_case(client, counselor_headers)

    assert data["intake_child_traits"] == []
    assert data["intake_family_situations"] == []


def test_create_case_stores_intake_items_in_order_without_duplicates(
    client: TestClient, counselor_headers
) -> None:
    data = create_case(
        client,
        counselor_headers,
        intake_child_traits=["우울", "불안", "우울"],
        intake_family_situations=["스트레스", "도박 · 게임중독"],
    )

    assert data["intake_child_traits"] == ["우울", "불안"]
    assert data["intake_family_situations"] == ["스트레스", "도박 · 게임중독"]

    detail = client.get(f"/api/v1/cases/{data['id']}", headers=counselor_headers)
    assert detail.status_code == 200
    assert detail.json()["data"]["intake_child_traits"] == ["우울", "불안"]

    listed = client.get("/api/v1/cases", headers=counselor_headers).json()["data"]["items"]
    assert listed[0]["intake_family_situations"] == ["스트레스", "도박 · 게임중독"]


def test_create_case_rejects_items_outside_form(
    client: TestClient, counselor_headers
) -> None:
    cases = [
        {"intake_child_traits": ["불안", "없는 항목"]},
        # 아동 특성 항목을 가정상황에 보내도 거부한다.
        {"intake_family_situations": ["거짓말"]},
        {"intake_child_traits": ["불안 "]},
        {"intake_child_traits": "불안"},
        {"intake_child_traits": [1]},
    ]

    for extra in cases:
        response = client.post(
            "/api/v1/cases",
            json={"title": "사례", "child_alias": "아동_001", **extra},
            headers=counselor_headers,
        )

        assert response.status_code == 422, extra
        body = response.json()
        assert body["error"]["code"] == "VALIDATION_ERROR"
        # 보낸 글자를 문구에 되풀이하지 않는다.
        assert "없는 항목" not in body["error"]["message"]

    listed = client.get("/api/v1/cases", headers=counselor_headers).json()["data"]
    assert listed["items"] == []


def test_create_case_rejects_too_many_items(client: TestClient, counselor_headers) -> None:
    response = client.post(
        "/api/v1/cases",
        json={"title": "사례", "child_alias": "아동_001", "intake_child_traits": ["불안"] * 101},
        headers=counselor_headers,
    )

    assert response.status_code == 422


def test_update_replaces_intake_lists_and_keeps_them_when_not_sent(
    client: TestClient, counselor_headers
) -> None:
    case = create_case(
        client,
        counselor_headers,
        intake_child_traits=["불안"],
        intake_family_situations=["스트레스"],
    )

    response = _patch(client, counselor_headers, case["id"], {"intake_child_traits": ["틱", "틱", "우울"]})
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["intake_child_traits"] == ["틱", "우울"]
    assert data["intake_family_situations"] == ["스트레스"]

    # 다른 칸만 고치면 초기면접 칸은 그대로다.
    data = _patch(client, counselor_headers, case["id"], {"notes": "메모"}).json()["data"]
    assert data["intake_child_traits"] == ["틱", "우울"]

    # 빈 목록이면 모두 지운다.
    data = _patch(client, counselor_headers, case["id"], {"intake_family_situations": []}).json()["data"]
    assert data["intake_family_situations"] == []


def test_update_rejects_null_and_items_outside_form(
    client: TestClient, counselor_headers
) -> None:
    case = create_case(client, counselor_headers, intake_child_traits=["불안"])

    for payload in (
        {"intake_child_traits": None},
        {"intake_family_situations": None},
        {"intake_child_traits": ["없는 항목"]},
    ):
        response = _patch(client, counselor_headers, case["id"], payload)
        assert response.status_code == 422, payload
        assert response.json()["error"]["code"] == "VALIDATION_ERROR"

    detail = client.get(f"/api/v1/cases/{case['id']}", headers=counselor_headers).json()["data"]
    assert detail["intake_child_traits"] == ["불안"]


def test_other_counselor_cannot_change_intake(
    client: TestClient, counselor_headers, other_counselor_headers
) -> None:
    case = create_case(client, counselor_headers, intake_child_traits=["불안"])

    response = _patch(client, other_counselor_headers, case["id"], {"intake_child_traits": []})

    assert response.status_code == 403


def test_audit_log_records_field_names_not_items(
    client: TestClient, counselor_headers, db
) -> None:
    case = create_case(client, counselor_headers, intake_child_traits=["불안"])

    _patch(client, counselor_headers, case["id"], {"intake_family_situations": ["배우자폭력"]})

    logs = db.scalars(
        select(AuditLog).where(
            AuditLog.entity_id == uuid.UUID(case["id"]),
            AuditLog.action.in_([AuditAction.CASE_CREATED, AuditAction.CASE_UPDATED]),
        )
    ).all()

    assert {log.action for log in logs} == {AuditAction.CASE_CREATED, AuditAction.CASE_UPDATED}

    updated = next(log for log in logs if log.action == AuditAction.CASE_UPDATED)
    assert updated.detail == {"changed_fields": ["intake_family_situations"]}

    for log in logs:
        assert "불안" not in str(log.detail)
        assert "배우자폭력" not in str(log.detail)


def test_case_saved_before_intake_columns_reads_as_empty_lists(
    client: TestClient, counselor_headers, db
) -> None:
    case = create_case(client, counselor_headers)

    row = db.get(Case, uuid.UUID(case["id"]))
    row.intake_child_traits = None
    row.intake_family_situations = None
    db.commit()

    detail = client.get(f"/api/v1/cases/{case['id']}", headers=counselor_headers).json()["data"]

    assert detail["intake_child_traits"] == []
    assert detail["intake_family_situations"] == []


def _web_list(name: str) -> list[str]:
    source = WEB_ITEMS.read_text(encoding="utf-8")
    match = re.search(rf"export const {name} = \[(.*?)\];", source, re.S)

    assert match, f"{WEB_ITEMS} 에서 {name} 을 찾지 못했습니다."

    return re.findall(r'"([^"]*)"', match.group(1))


def test_intake_items_match_counselor_web() -> None:
    assert _web_list("INTAKE_CHILD_ITEMS") == list(INTAKE_CHILD_TRAITS)
    assert _web_list("INTAKE_HOME_ITEMS") == list(INTAKE_FAMILY_SITUATIONS)


def test_migration_keeps_existing_cases_and_can_be_reverted(tmp_path) -> None:
    database_url = f"sqlite+pysqlite:///{(tmp_path / 'migration.db').as_posix()}"

    _alembic(database_url, "upgrade", BEFORE_INTAKE)

    engine = create_engine(database_url)

    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO users "
                    "(id, email, hashed_password, name, role, is_active, created_at, updated_at) "
                    "VALUES ('0123456789abcdef0123456789abcdef', 'old@example.com', 'x', '기존 계정', "
                    "'COUNSELOR', 1, '2025-01-01 00:00:00', '2025-01-01 00:00:00')"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO cases "
                    "(id, case_number, title, child_alias, status, counselor_id, created_at, updated_at) "
                    "VALUES ('fedcba9876543210fedcba9876543210', 'C-OLD-0001', '기존 사례', '아동', "
                    "'ACTIVE', '0123456789abcdef0123456789abcdef', '2025-01-01 00:00:00', '2025-01-01 00:00:00')"
                )
            )

        _alembic(database_url, "upgrade", "head")

        with engine.connect() as connection:
            row = connection.execute(
                text("SELECT case_number, intake_child_traits, intake_family_situations FROM cases")
            ).one()

        assert tuple(row) == ("C-OLD-0001", None, None)

        _alembic(database_url, "downgrade", BEFORE_INTAKE)

        with engine.connect() as connection:
            columns = {item[1] for item in connection.execute(text("PRAGMA table_info(cases)"))}
            count = connection.scalar(text("SELECT COUNT(*) FROM cases"))

        assert "intake_child_traits" not in columns
        assert "intake_family_situations" not in columns
        assert count == 1
    finally:
        engine.dispose()
