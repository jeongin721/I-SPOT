# 사례의 초기면접(서식 4 ②) 아동 특성 · 가정상황 칸 테스트.
#
# 서식 항목만 받고(그 밖은 422), 겹친 항목은 하나로 합치며, 수정은 목록을 통째로 바꾼다.
# 감사 기록에는 바뀐 칸 이름만 남기고 고른 항목은 남기지 않는다.
# 상담사 웹의 항목 목록(counselor-web/src/data/screens/intakeItems.ts)과 같은지도 본다.

import re
import uuid
from pathlib import Path

import pytest
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


# 글자 항목 안에서 받는 이스케이프. 서식 항목에는 이스케이프가 없어 따옴표 · 역슬래시만 둔다.
_TS_ESCAPABLE = ("\\", '"', "'")


def _ts_string(source: str, start: int, name: str) -> tuple[str, int]:
    """source[start] 의 따옴표로 시작하는 글자 항목을 읽어 (글자, 닫는 따옴표 다음 위치) 를 돌려준다."""

    quote = source[start]
    chars: list[str] = []
    i = start + 1

    while i < len(source):
        ch = source[i]

        if ch == quote:
            return "".join(chars), i + 1

        assert ch not in "\r\n", f"{name}: 글자 항목 안에서 줄이 바뀝니다."

        if ch == "\\":
            escaped = source[i + 1 : i + 2]
            assert escaped in _TS_ESCAPABLE, f"{name}: 따옴표 · 역슬래시 말고 다른 이스케이프가 있습니다."
            chars.append(escaped)
            i += 2
            continue

        chars.append(ch)
        i += 1

    raise AssertionError(f"{name}: 닫히지 않은 글자 항목이 있습니다.")


def _ts_string_array(source: str, name: str) -> list[str]:
    """
    TS 소스에서 `export const <name> = [ ... ];` 배열의 글자 항목을 순서대로 읽는다.

    큰 · 작은따옴표, `=` 와 `[` 사이 줄바꿈, 끝 쉼표, // · /* */ 주석을 읽는다.
    배열 안에 글자 · 쉼표 · 공백 · 주석 말고 다른 것(펼침 · 이름 · 숫자 · 템플릿 글자 · 빈 칸 · 쉼표 빠짐)이 있으면
    실패한다. 그런 목록은 실제 값을 이 시험이 알 수 없어 서버 목록과 같은지 판단할 수 없다.
    """

    heads = list(re.finditer(rf"\bexport\s+const\s+{re.escape(name)}\s*=\s*\[", source))
    assert len(heads) == 1, f"{name} 선언을 하나 찾아야 하는데 {len(heads)}개입니다."

    items: list[str] = []
    expect_item = True  # 배열 맨 앞이거나 쉼표 바로 뒤
    i = heads[0].end()

    while i < len(source):
        ch = source[i]

        if ch.isspace():
            i += 1
        elif source.startswith("//", i):
            end = source.find("\n", i)
            i = len(source) if end < 0 else end + 1
        elif source.startswith("/*", i):
            end = source.find("*/", i + 2)
            assert end >= 0, f"{name}: 닫히지 않은 주석이 있습니다."
            i = end + 2
        elif ch in "\"'":
            assert expect_item, f"{name}: 항목 사이에 쉼표가 없습니다."
            text_item, i = _ts_string(source, i, name)
            items.append(text_item)
            expect_item = False
        elif ch == ",":
            assert not expect_item, f"{name}: 빈 항목(맨 앞 쉼표 또는 쉼표 두 개)이 있습니다."
            expect_item = True
            i += 1
        elif ch == "]":
            # 끝 쉼표(expect_item 이 참)는 JS 에서 항목을 늘리지 않는다.
            return items
        else:
            raise AssertionError(f"{name}: 글자 항목이 아닌 것({ch!r})이 있습니다.")

    raise AssertionError(f"{name}: 배열이 닫히지 않았습니다.")


def _web_list(name: str) -> list[str]:
    return _ts_string_array(WEB_ITEMS.read_text(encoding="utf-8"), name)


def test_intake_items_match_counselor_web() -> None:
    assert _web_list("INTAKE_CHILD_ITEMS") == list(INTAKE_CHILD_TRAITS)
    assert _web_list("INTAKE_HOME_ITEMS") == list(INTAKE_FAMILY_SITUATIONS)


def test_web_items_reader_sees_single_quoted_addition() -> None:
    """작은따옴표로 더한 항목도 읽어야 서버 목록과 어긋난 것을 잡는다(Codex PR #56 낮음)."""

    source = WEB_ITEMS.read_text(encoding="utf-8")
    head = "export const INTAKE_CHILD_ITEMS = ["
    assert source.count(head) == 1

    changed = source.replace(head, head + "\n  '작은따옴표로 더한 항목',", 1)
    items = _ts_string_array(changed, "INTAKE_CHILD_ITEMS")

    assert items == ["작은따옴표로 더한 항목", *INTAKE_CHILD_TRAITS]
    assert items != list(INTAKE_CHILD_TRAITS)


@pytest.mark.parametrize("newline", ["\n", "\r\n"], ids=["lf", "crlf"])
def test_web_items_reader_survives_line_break_after_equals(newline: str) -> None:
    """`= [` 사이에 줄이 바뀌어도(같은 JS 값) 같은 목록으로 읽는다. CRLF 파일도 같다."""

    source = WEB_ITEMS.read_text(encoding="utf-8").replace("\r\n", "\n")
    head = "export const INTAKE_HOME_ITEMS = ["
    assert source.count(head) == 1

    changed = source.replace(head, "export const INTAKE_HOME_ITEMS =\n  [", 1).replace("\n", newline)

    assert _ts_string_array(changed, "INTAKE_HOME_ITEMS") == list(INTAKE_FAMILY_SITUATIONS)


def test_ts_array_reader_reads_quotes_comments_and_trailing_comma() -> None:
    source = """
const OTHER = ["무시"];
export const SAMPLE_ITEMS =
  [
  "가", // 줄 끝 주석
  '나',
  /* 블록 주석 */ "다 · 라",
  "큰따옴표 안 ' 작은따옴표",
  '작은따옴표 안 " 큰따옴표',
];
"""

    assert _ts_string_array(source, "SAMPLE_ITEMS") == [
        "가",
        "나",
        "다 · 라",
        "큰따옴표 안 ' 작은따옴표",
        '작은따옴표 안 " 큰따옴표',
    ]


@pytest.mark.parametrize(
    "body",
    [
        '[...OTHER, "가"]',  # 펼침
        '["가", OTHER_ITEM]',  # 이름
        '["가", 1]',  # 숫자
        '["가", `나`]',  # 템플릿 글자
        '["가",, "나"]',  # 빈 칸
        '[, "가"]',  # 맨 앞 쉼표
        '["가" "나"]',  # 쉼표 빠짐
        '["가", "나"',  # 배열이 닫히지 않음
        '["가", "나]',  # 글자가 닫히지 않음
        '["가\n나"]',  # 글자 안 줄바꿈
        r'["\x41"]',  # 따옴표 · 역슬래시 말고 다른 이스케이프
        '["가" /* 닫히지 않은 주석 ]',
    ],
    ids=[
        "spread",
        "identifier",
        "number",
        "template",
        "hole",
        "leading-comma",
        "missing-comma",
        "unclosed-array",
        "unclosed-string",
        "newline-in-string",
        "other-escape",
        "unclosed-comment",
    ],
)
def test_ts_array_reader_rejects_anything_but_strings(body: str) -> None:
    """글자 · 쉼표 · 공백 · 주석 말고 다른 것이 있으면 서버 목록과 비교할 수 없으므로 실패한다."""

    with pytest.raises(AssertionError):
        _ts_string_array(f"export const SAMPLE_ITEMS = {body};\n", "SAMPLE_ITEMS")


@pytest.mark.parametrize(
    "source",
    [
        'export const OTHER_ITEMS = ["가"];\n',  # 없음
        'export const SAMPLE_ITEMS = ["가"];\nexport const SAMPLE_ITEMS = ["나"];\n',  # 두 번
    ],
    ids=["missing", "twice"],
)
def test_ts_array_reader_needs_exactly_one_declaration(source: str) -> None:
    with pytest.raises(AssertionError):
        _ts_string_array(source, "SAMPLE_ITEMS")


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
