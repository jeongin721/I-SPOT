# 서식 4 의 '준비 중' 칸(2026-11-05) — ① 조치결과 2 · 위험도(우선) · 사례연계 경위, ② 가족유형 · 초기면접 글 칸 6.
#
# 만들 때 저장 · 목록 · 상세에 같은 이름으로 오고, 수정은 보낸 칸만 바꾸며 null · 빈 글은 비운다.
# 목록에 없는 값 · 2000자 넘는 글은 422, 감사 기록에는 바뀐 칸 이름만 남는다(글은 남기지 않는다).
# AI 분석 입력(case_context)에는 넘기지 않는다. 상담사 웹의 고르기 목록(api/types.ts)이 서버 열거형과 같은지도 본다.
# 데이터는 모두 가상이다.

import re
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.enums import AuditAction, ChildActionResult, FamilyType, RiskLevel, TargetActionResult
from app.models.audit_log import AuditLog
from app.models.session import ConsultationSession
from app.schemas.case import CASE_FORM_FIELDS, CASE_FORM_TEXT_FIELDS, CASE_FORM_TEXT_MAX
from app.services.case_context_service import build_case_context
from tests.conftest import create_case, create_session

REPO_DIR = Path(__file__).resolve().parents[2]
WEB_TYPES = REPO_DIR / "counselor-web" / "src" / "api" / "types.ts"

FILLED = {
    "child_action_result": "FOSTER",
    "target_action_result": "OBSERVATION",
    "counselor_risk_level": "MEDIUM",
    "linked_background": "학교 담임교사 신고 뒤 경찰 동행 연계(가상)",
    "intake_family_type": "MOTHER_STEPFATHER",
    "intake_guardian_relation": "어머니와는 가깝고 계부와는 대화가 적음(가상)",
    "intake_problem": "늦은 귀가 · 결석이 잦음, 보호자는 훈육이라고 말함(가상)",
    "intake_attitude": "면담에 협조적(가상)",
    "intake_environment": "방 두 칸, 정리가 안 됨(가상)",
    "intake_opinion": "2주 뒤 가정 방문 예정(가상)",
}


def _patch(client: TestClient, headers, case_id: str, payload: dict):
    return client.patch(f"/api/v1/cases/{case_id}", json=payload, headers=headers)


def test_fields_list_matches_filled_example() -> None:
    assert set(CASE_FORM_FIELDS) == set(FILLED)


def test_new_case_without_fields_has_nulls(client: TestClient, counselor_headers) -> None:
    case = create_case(client, counselor_headers)

    assert {key: case[key] for key in FILLED} == {key: None for key in FILLED}


def test_fields_are_saved_on_create_and_read_back(client: TestClient, counselor_headers) -> None:
    case = create_case(client, counselor_headers, **FILLED)

    detail = client.get(f"/api/v1/cases/{case['id']}", headers=counselor_headers).json()["data"]
    listed = client.get("/api/v1/cases", headers=counselor_headers).json()["data"]["items"][0]

    assert {key: case[key] for key in FILLED} == FILLED
    assert {key: detail[key] for key in FILLED} == FILLED
    assert {key: listed[key] for key in FILLED} == FILLED


def test_patch_changes_and_clears_only_sent_fields(client: TestClient, counselor_headers) -> None:
    case = create_case(client, counselor_headers, **FILLED)

    response = _patch(
        client,
        counselor_headers,
        case["id"],
        {"counselor_risk_level": "HIGH", "child_action_result": None, "intake_opinion": "  ", "intake_attitude": "  바뀐 태도  "},
    )

    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["counselor_risk_level"] == "HIGH"
    assert data["child_action_result"] is None
    assert data["intake_opinion"] is None  # 빈 글은 비운다
    assert data["intake_attitude"] == "바뀐 태도"  # 앞뒤 빈칸을 지운다
    untouched = {key: value for key, value in FILLED.items() if key not in {"counselor_risk_level", "child_action_result", "intake_opinion", "intake_attitude"}}
    assert {key: data[key] for key in untouched} == untouched


def test_blank_text_on_create_is_null(client: TestClient, counselor_headers) -> None:
    case = create_case(client, counselor_headers, linked_background=" \n ")

    assert case["linked_background"] is None


@pytest.mark.parametrize(
    "field, value",
    [
        ("child_action_result", "원가정보호"),  # 화면 글자가 아니라 코드만
        ("child_action_result", "OBSERVATION"),  # 다른 칸의 값
        ("target_action_result", "HOME"),
        ("counselor_risk_level", "상"),
        ("counselor_risk_level", 3),
        ("intake_family_type", "일반가정"),
        ("linked_background", "가" * (CASE_FORM_TEXT_MAX + 1)),
        ("intake_opinion", ["목록"]),
    ],
)
def test_bad_values_are_rejected(client: TestClient, counselor_headers, field, value) -> None:
    created = client.post(
        "/api/v1/cases",
        json={"title": "t", "child_alias": "a", field: value},
        headers=counselor_headers,
    )
    case = create_case(client, counselor_headers)
    patched = _patch(client, counselor_headers, case["id"], {field: value})

    assert created.status_code == 422, created.text
    assert patched.status_code == 422, patched.text


def test_text_at_limit_is_accepted(client: TestClient, counselor_headers) -> None:
    case = create_case(client, counselor_headers, intake_opinion="가" * CASE_FORM_TEXT_MAX)

    assert len(case["intake_opinion"]) == CASE_FORM_TEXT_MAX


def test_audit_keeps_only_changed_field_names(client: TestClient, counselor_headers, db) -> None:
    case = create_case(client, counselor_headers)

    _patch(client, counselor_headers, case["id"], {"linked_background": "비밀 경위 글(가상)", "counselor_risk_level": "LOW"})

    updated = db.scalars(
        select(AuditLog).where(
            AuditLog.entity_id == uuid.UUID(case["id"]),
            AuditLog.action == AuditAction.CASE_UPDATED,
        )
    ).one()

    assert sorted(updated.detail["changed_fields"]) == ["counselor_risk_level", "linked_background"]
    assert set(updated.detail) == {"changed_fields"}
    assert "비밀 경위 글" not in str(updated.detail)


def test_other_counselor_cannot_read_or_change(client: TestClient, counselor_headers, other_counselor_headers) -> None:
    case = create_case(client, counselor_headers, **FILLED)

    assert client.get(f"/api/v1/cases/{case['id']}", headers=other_counselor_headers).status_code == 403
    assert _patch(client, other_counselor_headers, case["id"], {"intake_opinion": "남의 사례"}).status_code == 403
    # 거부된 수정은 아무 칸도 바꾸지 않는다.
    after = client.get(f"/api/v1/cases/{case['id']}", headers=counselor_headers).json()["data"]
    assert after["intake_opinion"] == FILLED["intake_opinion"]


def test_admin_can_change_fields_of_any_case(client: TestClient, counselor_headers, admin_headers) -> None:
    case = create_case(client, counselor_headers, **FILLED)

    response = _patch(client, admin_headers, case["id"], {"counselor_risk_level": "LOW", "intake_family_type": None})

    assert response.status_code == 200, response.text
    assert response.json()["data"]["counselor_risk_level"] == "LOW"
    assert response.json()["data"]["intake_family_type"] is None


def test_validation_error_does_not_echo_text(client: TestClient, counselor_headers) -> None:
    # 글 칸에는 개인정보가 섞일 수 있다 — 422 응답이 보낸 글을 되돌려 주지 않는다(main.py 는 칸 이름 · 사유만 보낸다).
    marker = "가상표지글"
    too_long = marker + "가" * CASE_FORM_TEXT_MAX
    case = create_case(client, counselor_headers)

    created = client.post(
        "/api/v1/cases", json={"title": "t", "child_alias": "a", "linked_background": too_long}, headers=counselor_headers
    )
    patched = _patch(client, counselor_headers, case["id"], {"intake_opinion": too_long, "child_action_result": marker})

    assert created.status_code == 422 and patched.status_code == 422
    assert marker not in created.text
    assert marker not in patched.text


def test_fields_are_not_passed_to_ai_case_context(client: TestClient, counselor_headers, db) -> None:
    case = create_case(client, counselor_headers, **FILLED)
    session = create_session(client, counselor_headers, case["id"])

    context = build_case_context(db, db.get(ConsultationSession, uuid.UUID(session["id"])))

    assert not set(CASE_FORM_FIELDS) & set(context)
    text = str(context)
    for field in CASE_FORM_TEXT_FIELDS:
        assert FILLED[field] not in text
    for field in ("child_action_result", "target_action_result", "counselor_risk_level", "intake_family_type"):
        assert FILLED[field] not in text


def _web_label_keys(name: str) -> set:
    source = WEB_TYPES.read_text(encoding="utf-8")
    matched = re.search(rf"export const {name}\b[^=]*=\s*\{{(.*?)\}};", source, re.S)
    assert matched, f"{name} 를 {WEB_TYPES} 에서 찾지 못했습니다."
    return set(re.findall(r"^\s*([A-Z_]+):", matched.group(1), re.M))


@pytest.mark.parametrize(
    "name, enum",
    [
        ("CHILD_ACTION_LABELS", ChildActionResult),
        ("TARGET_ACTION_LABELS", TargetActionResult),
        ("RISK_LEVEL_LABELS", RiskLevel),
        ("FAMILY_TYPE_LABELS", FamilyType),
    ],
)
def test_web_choice_labels_match_server_enums(name, enum) -> None:
    assert _web_label_keys(name) == {member.value for member in enum}
