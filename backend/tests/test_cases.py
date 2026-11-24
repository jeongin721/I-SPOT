# Case CRUD / Validation / 없는 Case 테스트.

import uuid
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from tests.conftest import create_case


def _instant(value: str) -> datetime:
    """응답 시각을 같은 순간인지 비교할 수 있게 바꾼다.

    시간대 표시는 DB 에 따라 다르다(API_CONTRACT 1.5). SQLite 는 표시 없이(UTC),
    PostgreSQL 은 연결 시간대 기준(예: +09:00)으로 온다. 문자열 앞부분으로 비교하면
    PostgreSQL 에서 같은 순간인데도 틀린다.
    """

    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))

    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def test_create_case_assigns_requester_as_counselor(
    client: TestClient, counselor_headers, counselor_id: uuid.UUID
) -> None:
    data = create_case(client, counselor_headers, title="첫 사례")

    assert data["title"] == "첫 사례"
    assert data["counselor_id"] == str(counselor_id)
    assert data["status"] == "ACTIVE"
    assert data["case_number"].startswith("C-")


def test_create_case_generates_sequential_case_numbers(
    client: TestClient, counselor_headers
) -> None:
    first = create_case(client, counselor_headers)
    second = create_case(client, counselor_headers)

    assert first["case_number"] != second["case_number"]


def test_create_case_rejects_duplicate_case_number(
    client: TestClient, counselor_headers
) -> None:
    create_case(client, counselor_headers, case_number="C-FIXED-0001")

    response = client.post(
        "/api/v1/cases",
        json={
            "title": "중복 번호",
            "child_alias": "아동_002",
            "case_number": "C-FIXED-0001",
        },
        headers=counselor_headers,
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "DUPLICATE_RESOURCE"


def test_create_case_rejects_empty_title_and_alias(
    client: TestClient, counselor_headers
) -> None:
    """빈 글로 보낸 제목 · 별칭은 여전히 422 다(빼거나 null 일 때만 서버가 채운다 — 2026-11-24)."""

    for payload in ({"title": ""}, {"child_alias": ""}, {"title": "", "child_alias": ""}):
        response = client.post("/api/v1/cases", json=payload, headers=counselor_headers)

        assert response.status_code == 422, payload

        body = response.json()

        assert body["error"]["code"] == "VALIDATION_ERROR"
        assert body["error"]["details"]["fields"]


# =========================================================
# 제목 · 별칭을 빼고 보내면 서버가 사례번호로 채운다(2026-11-24)
#   상담사 앱(폰)의 '새 사례 등록' 창에는 이름 · 생년월일 · 성별 칸만 있다.
# =========================================================

def test_create_case_fills_title_and_alias_from_case_number_when_omitted(
    client: TestClient, counselor_headers
) -> None:
    response = client.post("/api/v1/cases", json={"child_gender": "여"}, headers=counselor_headers)

    assert response.status_code == 201, response.text

    data = response.json()["data"]
    case_number = data["case_number"]
    serial = case_number.rsplit("-", 1)[-1]

    assert case_number.startswith("C-") and serial.isdigit()
    assert data["title"] == f"{case_number} 사례"
    assert data["child_alias"] == f"아동_{serial}"

    # 저장된 값이다 — 다시 읽어도 같다.
    detail = client.get(f"/api/v1/cases/{data['id']}", headers=counselor_headers).json()["data"]

    assert (detail["title"], detail["child_alias"]) == (data["title"], data["child_alias"])


def test_create_case_treats_null_title_and_alias_as_omitted(
    client: TestClient, counselor_headers
) -> None:
    response = client.post(
        "/api/v1/cases", json={"title": None, "child_alias": None}, headers=counselor_headers
    )

    assert response.status_code == 201, response.text

    data = response.json()["data"]

    assert data["title"] == f"{data['case_number']} 사례"
    assert data["child_alias"] == f"아동_{data['case_number'].rsplit('-', 1)[-1]}"


def test_create_case_fills_only_the_missing_one(client: TestClient, counselor_headers) -> None:
    only_title = client.post(
        "/api/v1/cases", json={"title": "직접 쓴 제목"}, headers=counselor_headers
    ).json()["data"]

    assert only_title["title"] == "직접 쓴 제목"
    assert only_title["child_alias"] == f"아동_{only_title['case_number'].rsplit('-', 1)[-1]}"

    only_alias = client.post(
        "/api/v1/cases", json={"child_alias": "직접 쓴 별칭"}, headers=counselor_headers
    ).json()["data"]

    assert only_alias["child_alias"] == "직접 쓴 별칭"
    assert only_alias["title"] == f"{only_alias['case_number']} 사례"


def test_create_case_fills_from_a_given_case_number(client: TestClient, counselor_headers) -> None:
    """사례번호를 직접 준 경우에도 그 번호로 채운다. '-' 가 없는 번호는 번호 전체를 별칭에 쓴다."""

    dashed = client.post(
        "/api/v1/cases", json={"case_number": "C-FIXED-0007"}, headers=counselor_headers
    ).json()["data"]

    assert (dashed["title"], dashed["child_alias"]) == ("C-FIXED-0007 사례", "아동_0007")

    plain = client.post(
        "/api/v1/cases", json={"case_number": "사건123"}, headers=counselor_headers
    ).json()["data"]

    assert (plain["title"], plain["child_alias"]) == ("사건123 사례", "아동_사건123")


def test_create_case_never_builds_alias_from_the_real_name(
    client: TestClient, counselor_headers
) -> None:
    """별칭은 암호화하지 않는 칸이다. 실명을 같이 보내도 실명(성 포함)에서 별칭 · 제목을 만들지 않는다."""

    response = client.post(
        "/api/v1/cases",
        json={"personal_info": {"child_name": "남궁하늘", "child_birth_date": "2015-03-02"}},
        headers=counselor_headers,
    )

    assert response.status_code == 201, response.text

    data = response.json()["data"]

    for value in (data["title"], data["child_alias"]):
        assert "남궁" not in value and "하늘" not in value

    assert data["child_alias"] == f"아동_{data['case_number'].rsplit('-', 1)[-1]}"


def test_create_case_refills_title_and_alias_when_the_number_is_retried(
    client: TestClient, counselor_headers, monkeypatch
) -> None:
    """번호가 겹쳐 다시 만들 때 제목 · 별칭도 새 번호로 다시 채운다(옛 번호의 값이 남지 않는다)."""

    from app.services import case_service

    taken = create_case(client, counselor_headers)["case_number"]
    numbers = iter([taken, "C-RETRY-0042"])

    monkeypatch.setattr(case_service, "_generate_case_number", lambda db: next(numbers))

    response = client.post("/api/v1/cases", json={}, headers=counselor_headers)

    assert response.status_code == 201, response.text

    data = response.json()["data"]

    assert (data["case_number"], data["title"], data["child_alias"]) == (
        "C-RETRY-0042",
        "C-RETRY-0042 사례",
        "아동_0042",
    )


def test_create_case_rejects_invalid_birth_year(
    client: TestClient, counselor_headers
) -> None:
    response = client.post(
        "/api/v1/cases",
        json={"title": "잘못된 연도", "child_alias": "아동_003", "child_birth_year": 1500},
        headers=counselor_headers,
    )

    assert response.status_code == 422


# =========================================================
# 보호자 유형
# =========================================================

def test_create_case_with_guardian_type(
    client: TestClient, counselor_headers
) -> None:
    response = client.post(
        "/api/v1/cases",
        json={
            "title": "보호자 지정",
            "child_alias": "아동_보호자",
            "guardian_type": "GRANDPARENTS",
        },
        headers=counselor_headers,
    )

    assert response.status_code == 201

    data = response.json()["data"]

    assert data["guardian_type"] == "GRANDPARENTS"
    assert data["guardian_note"] is None


def test_guardian_type_is_optional(client: TestClient, counselor_headers) -> None:
    """기존 사례와 호환되어야 하므로 보호자는 필수가 아니다."""

    data = create_case(client, counselor_headers, title="보호자 미지정")

    assert data["guardian_type"] is None


def test_other_guardian_uses_note(client: TestClient, counselor_headers) -> None:
    """목록에 없는 관계는 OTHER + guardian_note 로 기록한다."""

    response = client.post(
        "/api/v1/cases",
        json={
            "title": "기타 보호자",
            "child_alias": "아동_기타",
            "guardian_type": "OTHER",
            "guardian_note": "외조모",
        },
        headers=counselor_headers,
    )

    assert response.status_code == 201

    data = response.json()["data"]

    assert data["guardian_type"] == "OTHER"
    assert data["guardian_note"] == "외조모"


def test_note_without_other_is_rejected(
    client: TestClient, counselor_headers
) -> None:
    """
    목록 값을 골라놓고 자유 입력까지 하면 어느 쪽이 맞는지 알 수 없다.
    통계를 내려면 guardian_type 이 단일 기준이어야 한다.
    """

    response = client.post(
        "/api/v1/cases",
        json={
            "title": "잘못된 조합",
            "child_alias": "아동_오류",
            "guardian_type": "MOTHER",
            "guardian_note": "친모",
        },
        headers=counselor_headers,
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_unknown_guardian_type_is_rejected(
    client: TestClient, counselor_headers
) -> None:
    """목록에 없는 값은 거부한다. 오타로 통계가 갈라지는 것을 막는다."""

    response = client.post(
        "/api/v1/cases",
        json={
            "title": "없는 유형",
            "child_alias": "아동_오타",
            "guardian_type": "친척",
        },
        headers=counselor_headers,
    )

    assert response.status_code == 422


def test_update_guardian_type(
    client: TestClient, counselor_headers, case: dict
) -> None:
    response = client.patch(
        f"/api/v1/cases/{case['id']}",
        json={"guardian_type": "FOSTER"},
        headers=counselor_headers,
    )

    assert response.status_code == 200
    assert response.json()["data"]["guardian_type"] == "FOSTER"


def test_guardian_appears_in_list_and_detail(
    client: TestClient, counselor_headers
) -> None:
    """화면이 목록에서도 보호자를 표시하므로 두 응답 모두에 있어야 한다."""

    created = client.post(
        "/api/v1/cases",
        json={
            "title": "목록 표시 확인",
            "child_alias": "아동_목록",
            "guardian_type": "FACILITY",
        },
        headers=counselor_headers,
    ).json()["data"]

    listed = client.get("/api/v1/cases", headers=counselor_headers).json()["data"]

    assert listed["items"][0]["guardian_type"] == "FACILITY"

    detail = client.get(
        f"/api/v1/cases/{created['id']}", headers=counselor_headers
    ).json()["data"]

    assert detail["guardian_type"] == "FACILITY"


def test_list_cases_returns_paged_envelope(
    client: TestClient, counselor_headers
) -> None:
    for index in range(3):
        create_case(client, counselor_headers, title=f"사례 {index}")

    response = client.get(
        "/api/v1/cases", params={"page": 1, "page_size": 2}, headers=counselor_headers
    )

    assert response.status_code == 200

    data = response.json()["data"]

    assert len(data["items"]) == 2
    assert data["meta"]["total"] == 3
    assert data["meta"]["total_pages"] == 2


def test_list_cases_includes_counselor_name(
    client: TestClient, counselor_headers
) -> None:
    """Frontend 가 담당자를 이름으로 표시하므로 목록에서 함께 내려준다."""

    create_case(client, counselor_headers, title="담당자 표시 확인")

    response = client.get("/api/v1/cases", headers=counselor_headers)

    assert response.status_code == 200

    item = response.json()["data"]["items"][0]

    # UUID 만으로는 화면에 이름을 띄울 수 없다.
    assert item["counselor_id"]
    assert item["counselor_name"] == "상담사A"


def test_create_and_update_responses_include_counselor_name(
    client: TestClient, counselor_headers
) -> None:
    """
    생성/수정 응답에도 담당자 이름이 있어야 한다.

    목록에만 채우면 화면이 사례를 만든 직후 담당자를 표시하지 못하고
    목록을 다시 불러와야 한다.
    """

    created = create_case(client, counselor_headers, title="생성 응답 확인")

    assert created["counselor_name"] == "상담사A"

    response = client.patch(
        f"/api/v1/cases/{created['id']}",
        json={"title": "수정 응답 확인"},
        headers=counselor_headers,
    )

    assert response.status_code == 200
    assert response.json()["data"]["counselor_name"] == "상담사A"


def test_case_detail_includes_counselor_name(
    client: TestClient, counselor_headers, case: dict
) -> None:
    """상세 응답도 목록과 같은 필드로 읽을 수 있어야 한다."""

    response = client.get(f"/api/v1/cases/{case['id']}", headers=counselor_headers)

    assert response.status_code == 200

    data = response.json()["data"]

    assert data["counselor_name"] == "상담사A"
    # 기존 counselor 객체도 그대로 유지된다.
    assert data["counselor"]["name"] == "상담사A"


def test_list_cases_search_by_alias(client: TestClient, counselor_headers) -> None:
    create_case(client, counselor_headers, child_alias="아동_특이케이스")
    create_case(client, counselor_headers, child_alias="아동_기본")

    response = client.get(
        "/api/v1/cases", params={"search": "특이케이스"}, headers=counselor_headers
    )

    assert response.status_code == 200

    items = response.json()["data"]["items"]

    assert len(items) == 1
    assert items[0]["child_alias"] == "아동_특이케이스"


def test_case_list_includes_last_session_at(
    client: TestClient, counselor_headers, case: dict
) -> None:
    """
    Case List 화면(03_UI_UX.md S02)의 "최근 상담일".
    Frontend 가 Case 별로 Session 을 다시 조회하지 않아도 되어야 한다.
    """

    listed = client.get("/api/v1/cases", headers=counselor_headers).json()["data"]

    # Session 이 없으면 null
    assert listed["items"][0]["last_session_at"] is None

    client.post(
        f"/api/v1/cases/{case['id']}/sessions",
        json={"title": "1회기", "consulted_at": "2026-08-20T10:00:00Z"},
        headers=counselor_headers,
    )
    client.post(
        f"/api/v1/cases/{case['id']}/sessions",
        json={"title": "2회기", "consulted_at": "2026-09-01T14:30:00Z"},
        headers=counselor_headers,
    )

    listed = client.get("/api/v1/cases", headers=counselor_headers).json()["data"]

    # 가장 최근 상담 일시가 반영된다.
    assert _instant(listed["items"][0]["last_session_at"]) == _instant("2026-09-01T14:30:00Z")


def test_case_detail_includes_last_session_at(
    client: TestClient, counselor_headers, case: dict
) -> None:
    client.post(
        f"/api/v1/cases/{case['id']}/sessions",
        json={"title": "1회기", "consulted_at": "2026-08-20T10:00:00Z"},
        headers=counselor_headers,
    )

    detail = client.get(
        f"/api/v1/cases/{case['id']}", headers=counselor_headers
    ).json()["data"]

    assert _instant(detail["last_session_at"]) == _instant("2026-08-20T10:00:00Z")


def test_last_session_at_falls_back_to_created_at(
    client: TestClient, counselor_headers, case: dict
) -> None:
    """consulted_at 을 기록하지 않은 Session 도 최근 상담일에 반영된다."""

    client.post(
        f"/api/v1/cases/{case['id']}/sessions",
        json={"title": "일시 미기록 회기"},
        headers=counselor_headers,
    )

    listed = client.get("/api/v1/cases", headers=counselor_headers).json()["data"]

    assert listed["items"][0]["last_session_at"] is not None


def test_get_case_detail_includes_counselor_and_session_count(
    client: TestClient, counselor_headers, case: dict
) -> None:
    client.post(
        f"/api/v1/cases/{case['id']}/sessions",
        json={"title": "1회기"},
        headers=counselor_headers,
    )

    response = client.get(f"/api/v1/cases/{case['id']}", headers=counselor_headers)

    assert response.status_code == 200

    data = response.json()["data"]

    assert data["session_count"] == 1
    assert data["counselor"]["email"] == "counselor.a@ispot.example.com"


def test_get_missing_case_returns_case_not_found(
    client: TestClient, counselor_headers
) -> None:
    response = client.get(f"/api/v1/cases/{uuid.uuid4()}", headers=counselor_headers)

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "CASE_NOT_FOUND"


def test_malformed_case_id_returns_validation_error(
    client: TestClient, counselor_headers
) -> None:
    response = client.get("/api/v1/cases/not-a-uuid", headers=counselor_headers)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_update_case_changes_fields(
    client: TestClient, counselor_headers, case: dict
) -> None:
    response = client.patch(
        f"/api/v1/cases/{case['id']}",
        json={"title": "수정된 제목", "status": "CLOSED"},
        headers=counselor_headers,
    )

    assert response.status_code == 200

    data = response.json()["data"]

    assert data["title"] == "수정된 제목"
    assert data["status"] == "CLOSED"


def test_counselor_cannot_delete_case(
    client: TestClient, counselor_headers, case: dict
) -> None:
    response = client.delete(f"/api/v1/cases/{case['id']}", headers=counselor_headers)

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


def test_admin_can_delete_case(
    client: TestClient, counselor_headers, admin_headers, case: dict
) -> None:
    response = client.delete(f"/api/v1/cases/{case['id']}", headers=admin_headers)

    assert response.status_code == 204

    follow_up = client.get(f"/api/v1/cases/{case['id']}", headers=admin_headers)

    assert follow_up.status_code == 404


def test_counselor_cannot_assign_case_to_another_counselor(
    client: TestClient, counselor_headers, other_counselor_id: uuid.UUID
) -> None:
    response = client.post(
        "/api/v1/cases",
        json={
            "title": "타인 배정 시도",
            "child_alias": "아동_004",
            "counselor_id": str(other_counselor_id),
        },
        headers=counselor_headers,
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


def test_admin_can_assign_case_to_counselor(
    client: TestClient, admin_headers, counselor_id: uuid.UUID
) -> None:
    response = client.post(
        "/api/v1/cases",
        json={
            "title": "관리자 배정",
            "child_alias": "아동_005",
            "counselor_id": str(counselor_id),
        },
        headers=admin_headers,
    )

    assert response.status_code == 201
    assert response.json()["data"]["counselor_id"] == str(counselor_id)


def test_admin_assign_to_unknown_user_returns_user_not_found(
    client: TestClient, admin_headers
) -> None:
    response = client.post(
        "/api/v1/cases",
        json={
            "title": "없는 사용자",
            "child_alias": "아동_006",
            "counselor_id": str(uuid.uuid4()),
        },
        headers=admin_headers,
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "USER_NOT_FOUND"


def test_admin_cannot_assign_case_to_inactive_counselor(
    client: TestClient, admin_headers, admin_id: uuid.UUID, counselor_id: uuid.UUID
) -> None:
    """정지된 계정은 담당자로 지정할 수 없다 — 400 VALIDATION_ERROR(details 없음, API_CONTRACT 4절)."""

    deactivated = client.patch(
        f"/api/v1/auth/users/{counselor_id}",
        json={"is_active": False},
        headers=admin_headers,
    )

    assert deactivated.status_code == 200

    created = client.post(
        "/api/v1/cases",
        json={
            "title": "정지 계정 배정",
            "child_alias": "아동_007",
            "counselor_id": str(counselor_id),
        },
        headers=admin_headers,
    )

    assert created.status_code == 400
    assert created.json()["error"]["code"] == "VALIDATION_ERROR"
    assert "details" not in created.json()["error"]

    case = create_case(client, admin_headers)

    updated = client.patch(
        f"/api/v1/cases/{case['id']}",
        json={"counselor_id": str(counselor_id)},
        headers=admin_headers,
    )

    assert updated.status_code == 400
    assert updated.json()["error"]["code"] == "VALIDATION_ERROR"

    after = client.get(f"/api/v1/cases/{case['id']}", headers=admin_headers)

    assert after.json()["data"]["counselor_id"] == str(admin_id)


def test_update_case_rejects_null_counselor_id(
    client: TestClient, admin_headers, admin_id: uuid.UUID, counselor_id: uuid.UUID
) -> None:
    """counselor_id: null 을 조용히 무시하면 담당자가 비워진 줄 안다. 422 로 거부한다."""

    case = create_case(client, admin_headers, counselor_id=str(counselor_id))

    response = client.patch(
        f"/api/v1/cases/{case['id']}",
        json={"counselor_id": None, "title": "같이 보낸 제목"},
        headers=admin_headers,
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"

    # 거절되면 같이 보낸 필드도 바뀌지 않는다.
    after = client.get(f"/api/v1/cases/{case['id']}", headers=admin_headers).json()["data"]

    assert after["counselor_id"] == str(counselor_id)
    assert after["title"] == case["title"]


def test_update_case_null_counselor_id_is_rejected_for_counselor_too(
    client: TestClient, counselor_headers
) -> None:
    case = create_case(client, counselor_headers)

    response = client.patch(
        f"/api/v1/cases/{case['id']}",
        json={"counselor_id": None},
        headers=counselor_headers,
    )

    assert response.status_code == 422


def test_update_case_without_counselor_id_keeps_counselor(
    client: TestClient, admin_headers, counselor_id: uuid.UUID
) -> None:
    case = create_case(client, admin_headers, counselor_id=str(counselor_id))

    response = client.patch(
        f"/api/v1/cases/{case['id']}", json={"title": "제목만"}, headers=admin_headers
    )

    assert response.status_code == 200
    assert response.json()["data"]["counselor_id"] == str(counselor_id)
