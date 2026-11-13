# 고령자 건강상담(API_CONTRACT 27절, 2026-11-13) — 대상 종류 · 기본정보 · 건강측정 · 추이 · 요약과 다음 상담 확인사항.
# 데이터는 모두 가상이다. 기본(SENIOR_BRIEF_PROVIDER=rule)은 LLM 없이 규칙으로 묶고, modeling 경로는 가짜 모듈로 본다.

import sys
import types
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.adapters.module_loader import ensure_repo_root_on_path

ensure_repo_root_on_path()

from ai.modeling.senior import senior_brief_llm as brief_llm  # noqa: E402
from app.core.config import settings  # noqa: E402
from app.core.enums import AuditAction  # noqa: E402
from app.models.audit_log import AuditLog  # noqa: E402
from app.services import senior_service  # noqa: E402
from tests.conftest import create_case, create_session  # noqa: E402
from tests.test_case_context import _approve_with_assessment  # noqa: E402


def _senior(client: TestClient, headers) -> dict:
    return create_case(client, headers, subject_type="SENIOR", child_alias="어르신_001", child_birth_year=1944)


def _measure(client: TestClient, headers, case_id: str, **values) -> dict:
    body = {"measured_at": "2026-11-01T09:00:00+09:00", **values}
    response = client.post(f"/api/v1/cases/{case_id}/health-measurements", json=body, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()["data"]


@pytest.fixture(autouse=True)
def _fresh_limits():
    senior_service.reset_limits()
    yield
    senior_service.reset_limits()


# ---------------------------------------------------------------- 대상 종류


def test_case_subject_type_defaults_to_child_and_filters_list(client: TestClient, counselor_headers) -> None:
    child = create_case(client, counselor_headers)
    senior = _senior(client, counselor_headers)

    assert child["subject_type"] == "CHILD" and senior["subject_type"] == "SENIOR"

    listed = client.get("/api/v1/cases?subject_type=SENIOR", headers=counselor_headers).json()["data"]["items"]
    assert [item["id"] for item in listed] == [senior["id"]]
    both = client.get("/api/v1/cases", headers=counselor_headers).json()["data"]["items"]
    assert {item["id"] for item in both} == {child["id"], senior["id"]}


def test_subject_type_cannot_change_after_create(client: TestClient, counselor_headers) -> None:
    case = create_case(client, counselor_headers)

    response = client.patch(f"/api/v1/cases/{case['id']}", json={"subject_type": "SENIOR"}, headers=counselor_headers)

    # 수정 요청에 없는 칸이라 무시되거나 거절된다. 어느 쪽이든 값은 그대로다.
    assert response.status_code in (200, 422)
    again = client.get(f"/api/v1/cases/{case['id']}", headers=counselor_headers).json()["data"]
    assert again["subject_type"] == "CHILD"


@pytest.mark.parametrize(
    "method,path",
    [
        ("get", "senior-profile"),
        ("patch", "senior-profile"),
        ("get", "health-measurements"),
        ("get", "health-trend"),
        ("post", "senior-brief"),
    ],
)
def test_child_case_gets_409(client: TestClient, counselor_headers, method: str, path: str) -> None:
    case = create_case(client, counselor_headers)
    kwargs = {"json": {}} if method == "patch" else {}

    response = getattr(client, method)(f"/api/v1/cases/{case['id']}/{path}", headers=counselor_headers, **kwargs)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "INVALID_CASE_STATE"


def test_other_counselor_gets_403(client: TestClient, counselor_headers, other_counselor_headers) -> None:
    case = _senior(client, counselor_headers)

    for path in ("senior-profile", "health-measurements", "health-trend"):
        assert client.get(f"/api/v1/cases/{case['id']}/{path}", headers=other_counselor_headers).status_code == 403
    response = client.post(
        f"/api/v1/cases/{case['id']}/health-measurements",
        json={"measured_at": "2026-11-01T09:00:00+09:00", "pulse": 70},
        headers=other_counselor_headers,
    )
    assert response.status_code == 403


def test_admin_can_read(client: TestClient, counselor_headers, admin_headers) -> None:
    case = _senior(client, counselor_headers)
    _measure(client, counselor_headers, case["id"], pulse=72)

    assert len(client.get(f"/api/v1/cases/{case['id']}/health-measurements", headers=admin_headers).json()["data"]) == 1


# ---------------------------------------------------------------- 기본정보


def test_profile_empty_then_partial_update(client: TestClient, counselor_headers, db) -> None:
    case = _senior(client, counselor_headers)
    url = f"/api/v1/cases/{case['id']}/senior-profile"

    empty = client.get(url, headers=counselor_headers).json()["data"]
    assert empty["living_arrangement"] is None and empty["updated_at"] is None

    first = client.patch(
        url, json={"living_arrangement": "ALONE", "care_grade": "GRADE_4", "health_notes": "  무릎 통증  "}, headers=counselor_headers
    )
    assert first.status_code == 200, first.text
    assert first.json()["data"]["health_notes"] == "무릎 통증"

    second = client.patch(url, json={"care_notes": "주 2회 경로당"}, headers=counselor_headers).json()["data"]
    assert second["living_arrangement"] == "ALONE" and second["care_grade"] == "GRADE_4" and second["care_notes"] == "주 2회 경로당"

    cleared = client.patch(url, json={"health_notes": None}, headers=counselor_headers).json()["data"]
    assert cleared["health_notes"] is None

    logs = db.scalars(select(AuditLog).where(AuditLog.action == AuditAction.SENIOR_PROFILE_UPDATED)).all()
    assert len(logs) == 3
    # 값은 남기지 않고 칸 이름만
    assert all(set(log.detail) == {"changed_fields"} for log in logs)
    assert "무릎" not in str([log.detail for log in logs])


def test_profile_rejects_unknown_grade(client: TestClient, counselor_headers) -> None:
    case = _senior(client, counselor_headers)

    response = client.patch(f"/api/v1/cases/{case['id']}/senior-profile", json={"care_grade": "GRADE_9"}, headers=counselor_headers)

    assert response.status_code == 422


# ---------------------------------------------------------------- 측정


@pytest.mark.parametrize(
    "body",
    [
        {},  # 값 없음
        {"systolic": 130},  # 혈압 짝 없음
        {"systolic": 80, "diastolic": 90},  # 이완기가 더 큼
        {"blood_glucose": 110},  # 잰 때 없음
        {"pulse": 500},  # 잴 수 없는 값
        {"weight_kg": 5},
    ],
)
def test_measurement_validation(client: TestClient, counselor_headers, body: dict) -> None:
    case = _senior(client, counselor_headers)

    response = client.post(
        f"/api/v1/cases/{case['id']}/health-measurements",
        json={"measured_at": "2026-11-01T09:00:00+09:00", **body},
        headers=counselor_headers,
    )

    assert response.status_code == 422


def test_measurement_needs_timezone(client: TestClient, counselor_headers) -> None:
    case = _senior(client, counselor_headers)

    response = client.post(
        f"/api/v1/cases/{case['id']}/health-measurements",
        json={"measured_at": "2026-11-01T09:00:00", "pulse": 70},
        headers=counselor_headers,
    )

    assert response.status_code == 422


def test_measurement_crud_and_audit(client: TestClient, counselor_headers, db) -> None:
    case = _senior(client, counselor_headers)
    created = _measure(client, counselor_headers, case["id"], systolic=132, diastolic=84, note="아침 약 드시기 전")
    url = f"/api/v1/cases/{case['id']}/health-measurements/{created['id']}"

    patched = client.patch(url, json={"pulse": 76}, headers=counselor_headers)
    assert patched.status_code == 200, patched.text
    assert patched.json()["data"]["pulse"] == 76 and patched.json()["data"]["systolic"] == 132

    # 바꾼 뒤 값도 같은 규칙: 혈압 한쪽만 지우면 400
    broken = client.patch(url, json={"diastolic": None}, headers=counselor_headers)
    assert broken.status_code == 400 and "혈압" in broken.json()["error"]["message"]
    # 측정 시각은 비울 수 없다
    assert client.patch(url, json={"measured_at": None}, headers=counselor_headers).status_code == 400

    assert client.delete(url, headers=counselor_headers).status_code == 204
    assert client.get(f"/api/v1/cases/{case['id']}/health-measurements", headers=counselor_headers).json()["data"] == []
    assert client.delete(url, headers=counselor_headers).status_code == 404

    actions = [
        log.action
        for log in db.scalars(select(AuditLog).where(AuditLog.case_id == uuid.UUID(case["id"])).order_by(AuditLog.created_at))
    ]
    assert AuditAction.HEALTH_MEASUREMENT_CREATED in actions
    assert AuditAction.HEALTH_MEASUREMENT_UPDATED in actions
    assert AuditAction.HEALTH_MEASUREMENT_DELETED in actions
    details = str([log.detail for log in db.scalars(select(AuditLog).where(AuditLog.case_id == uuid.UUID(case["id"])))])
    assert "132" not in details and "아침" not in details


def test_measurement_session_must_belong_to_case(client: TestClient, counselor_headers) -> None:
    case = _senior(client, counselor_headers)
    other = _senior(client, counselor_headers)
    own_session = create_session(client, counselor_headers, case["id"])
    other_session = create_session(client, counselor_headers, other["id"])

    ok = _measure(client, counselor_headers, case["id"], pulse=70, session_id=own_session["id"])
    assert ok["session_id"] == own_session["id"]

    response = client.post(
        f"/api/v1/cases/{case['id']}/health-measurements",
        json={"measured_at": "2026-11-01T09:00:00+09:00", "pulse": 70, "session_id": other_session["id"]},
        headers=counselor_headers,
    )
    assert response.status_code == 404 and response.json()["error"]["code"] == "SESSION_NOT_FOUND"


def test_measurement_of_other_case_is_404(client: TestClient, counselor_headers) -> None:
    case = _senior(client, counselor_headers)
    other = _senior(client, counselor_headers)
    row = _measure(client, counselor_headers, other["id"], pulse=70)

    response = client.patch(
        f"/api/v1/cases/{case['id']}/health-measurements/{row['id']}", json={"pulse": 71}, headers=counselor_headers
    )

    assert response.status_code == 404


# ---------------------------------------------------------------- 추이


def test_trend_splits_glucose_by_timing_and_reports_change(client: TestClient, counselor_headers) -> None:
    case = _senior(client, counselor_headers)
    cid = case["id"]
    _measure(client, counselor_headers, cid, measured_at="2026-10-01T09:00:00+09:00", systolic=120, diastolic=80, blood_glucose=100, glucose_timing="FASTING")
    _measure(client, counselor_headers, cid, measured_at="2026-10-15T09:00:00+09:00", blood_glucose=180, glucose_timing="POST_MEAL")
    _measure(client, counselor_headers, cid, measured_at="2026-11-01T09:00:00+09:00", systolic=138, diastolic=86, blood_glucose=112, glucose_timing="FASTING", weight_kg=55.5)

    data = client.get(f"/api/v1/cases/{cid}/health-trend", headers=counselor_headers).json()["data"]

    assert data["measurement_count"] == 3
    by_metric = {metric["metric"]: metric for metric in data["metrics"]}
    assert list(by_metric) == ["systolic", "diastolic", "blood_glucose_fasting", "blood_glucose_post_meal", "weight_kg"]
    assert by_metric["systolic"]["change"] == 18 and by_metric["systolic"]["count"] == 2
    assert by_metric["blood_glucose_fasting"]["change"] == 12  # 식후 값과 섞지 않는다
    assert by_metric["blood_glucose_post_meal"]["previous"] is None and by_metric["blood_glucose_post_meal"]["change"] is None
    assert [point["value"] for point in by_metric["systolic"]["points"]] == [120, 138]
    # 정상 · 위험 같은 기준 칸은 없다
    assert not {"status", "level", "normal", "risk"} & set(by_metric["systolic"])


# ---------------------------------------------------------------- 요약 · 다음 상담 확인사항 (규칙)


def test_brief_rule_without_data(client: TestClient, counselor_headers, db) -> None:
    case = _senior(client, counselor_headers)

    response = client.post(f"/api/v1/cases/{case['id']}/senior-brief", headers=counselor_headers)

    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["source"] == "RULE" and data["model"] is None
    assert "건강측정 기록이 아직 없습니다" in data["summary"]
    assert [item["text"] for item in data["check_items"]] == ["아직 건강측정 기록이 없어요. 이번 상담 때 혈압 등을 재서 남겨 보세요."]
    log = db.scalar(select(AuditLog).where(AuditLog.action == AuditAction.SENIOR_BRIEF_GENERATED))
    assert log.detail["source"] == "RULE" and log.detail["item_count"] == 1


def test_brief_rule_uses_measurements_profile_and_approved_session(client: TestClient, counselor_headers) -> None:
    case = _senior(client, counselor_headers)
    cid = case["id"]
    client.patch(f"/api/v1/cases/{cid}/senior-profile", json={"living_arrangement": "ALONE", "care_grade": "GRADE_3"}, headers=counselor_headers)
    first = _measure(client, counselor_headers, cid, measured_at="2026-11-01T09:00:00+09:00", systolic=120, diastolic=78)
    second = _measure(client, counselor_headers, cid, measured_at="2026-11-10T09:00:00+09:00", systolic=141, diastolic=80)
    session = create_session(client, counselor_headers, cid)
    _approve_with_assessment(client, counselor_headers, session["id"])

    data = client.post(f"/api/v1/cases/{cid}/senior-brief", headers=counselor_headers).json()["data"]

    assert "혼자 사심 · 장기요양 3등급" in data["summary"]
    assert "건강측정 2번" in data["summary"]
    texts = [item["text"] for item in data["check_items"]]
    rise = next(item for item in data["check_items"] if item["text"].startswith("수축기 혈압"))
    assert "21mmHg 올랐어요" in rise["text"]
    assert {basis["measurement_id"] for basis in rise["basis"]} == {first["id"], second["id"]}
    assert all(basis["kind"] == "MEASUREMENT" and basis["metric"] == "systolic" for basis in rise["basis"])
    # 진단 · 판정 말은 없다
    assert not any(brief_llm.is_forbidden(text) for text in texts + [data["summary"]])


# ---------------------------------------------------------------- 규칙 · 검사 함수(모듈)


def _metric(name: str, values: list, label: str = "수축기 혈압", unit: str = "mmHg") -> dict:
    return {
        "metric": name,
        "label": label,
        "unit": unit,
        "points": [{"id": f"id{i}", "date": f"2026-11-{i + 1:02d}", "value": value} for i, value in enumerate(values)],
    }


def test_rule_three_in_a_row_when_change_is_small() -> None:
    data = {"today": "2026-11-05", "metrics": [_metric("systolic", [120, 125, 130])], "sessions": []}

    items = brief_llm.rule_based_brief(data)["check_items"]

    assert len(items) == 1 and "최근 3번 이어서 올랐어요(120 → 125 → 130mmHg)" in items[0]["text"]
    assert [basis["measurement_id"] for basis in items[0]["basis"]] == ["id0", "id1", "id2"]


def test_rule_stale_measurement() -> None:
    data = {"today": "2026-12-15", "metrics": [_metric("pulse", [70], "맥박", "회/분")], "sessions": []}

    texts = [item["text"] for item in brief_llm.rule_based_brief(data)["check_items"]]

    assert texts == ["마지막 측정이 44일 전(2026-11-01)이에요. 이번 상담 때 다시 재 보세요."]


def test_rule_session_key_points() -> None:
    data = {
        "today": "2026-11-05",
        "metrics": [_metric("pulse", [70], "맥박", "회/분")],
        "sessions": [{"number": 2, "date": "2026-11-04", "overview": "식사를 거르는 날이 늘었다고 함", "key_points": ["밤에 잠을 잘 못 잠", ""]}],
    }

    items = brief_llm.rule_based_brief(data)["check_items"]

    assert items == [
        {
            "text": "지난 상담(2회차)에서 나온 이야기 — 밤에 잠을 잘 못 잠 그 뒤 어떻게 지내시는지 이어서 여쭤 보세요.",
            "basis": [{"kind": "SESSION", "session_number": 2}],
        }
    ]


@pytest.mark.parametrize(
    "text",
    [
        "고혈압으로 보입니다.",
        "우울증이 의심됩니다.",
        "치매 증상으로 판단돼요.",
        "혈압약을 늘리는 것이 좋겠습니다.",
        "정상 범위를 벗어났어요.",
        "병원 진료가 필요합니다.",
        "치료가 필요해 보입니다.",
    ],
)
def test_forbidden_sentences(text: str) -> None:
    assert brief_llm.is_forbidden(text)


@pytest.mark.parametrize(
    "text",
    [
        "수축기 혈압이 지난번보다 18 올랐어요. 잴 때 상황을 여쭤 보세요.",
        "요즘 잠은 어떻게 주무시는지 여쭤 보세요.",
        "병원에 다녀오셨는지 확인해 보세요.",
        "약은 제때 드시고 계신지 여쭤 보세요.",
    ],
)
def test_allowed_sentences(text: str) -> None:
    assert not brief_llm.is_forbidden(text)


def test_clean_output_drops_forbidden_unknown_refs_and_falls_back_summary() -> None:
    refs = {"P": {"kind": "PROFILE"}, "M1": {"kind": "MEASUREMENT", "metric": "systolic", "measurement_id": "a"}}
    raw = {
        "summary": "고혈압이 의심됩니다.",
        "check_items": [
            {"text": "혈압이 올랐어요. 잴 때 상황을 여쭤 보세요.", "refs": ["M1", "M1", "M9"]},
            {"text": "혈압약을 늘리세요.", "refs": ["M1"]},
            {"text": "근거 없는 문장", "refs": ["S7"]},
            {"text": "Check the blood pressure.", "refs": ["M1"]},
        ],
    }

    cleaned = brief_llm.clean_output(raw, refs, "규칙 요약")

    assert cleaned == {
        "summary": "규칙 요약",
        "check_items": [{"text": "혈압이 올랐어요. 잴 때 상황을 여쭤 보세요.", "basis": [refs["M1"]]}],
    }


def test_clean_output_without_items_raises() -> None:
    with pytest.raises(brief_llm.SeniorBriefOutputError):
        brief_llm.clean_output({"summary": "요약", "check_items": [{"text": "진단이 필요합니다", "refs": ["P"]}]}, {"P": {"kind": "PROFILE"}}, "x")


def test_format_input_refs() -> None:
    data = {
        "today": "2026-11-05",
        "profile": {"living_arrangement": "ALONE", "care_grade": None, "health_notes": "무릎", "care_notes": None},
        "metrics": [_metric("systolic", [120, 130])],
        "sessions": [{"number": 1, "date": "2026-11-01", "overview": "안부", "key_points": ["식사"]}],
    }

    text, refs = brief_llm.format_input(data)

    assert "M1 2026-11-01 120 / M2 2026-11-02 130" in text and "S1 (2026-11-01) 안부" in text and "혼자 사심" in text
    assert refs["M2"] == {"kind": "MEASUREMENT", "metric": "systolic", "measurement_id": "id1"}
    assert refs["S1"] == {"kind": "SESSION", "session_number": 1}


# ---------------------------------------------------------------- modeling 경로(가짜 모듈)


@pytest.fixture
def modeling(monkeypatch):
    state = {"raise": None, "calls": []}
    module = types.ModuleType("ai.modeling.senior.senior_brief_llm")

    def generate_senior_brief(data, known_identifiers=None, deadline=None):
        state["calls"].append({"data": data, "known": known_identifiers})
        if state["raise"] is not None:
            raise state["raise"]
        ids = [point["id"] for metric in data["metrics"] for point in metric["points"]]
        return {
            "summary": "AI 요약",
            "check_items": [
                {"text": "혈압 잴 때 상황을 여쭤 보세요.", "basis": [{"kind": "MEASUREMENT", "metric": "systolic", "measurement_id": i} for i in ids]},
                # 입력에 없는 측정 id 근거는 서버가 버린다
                {"text": "다른 근거", "basis": [{"kind": "MEASUREMENT", "metric": "systolic", "measurement_id": str(uuid.uuid4())}]},
            ],
            "model": "fake-model",
        }

    module.generate_senior_brief = generate_senior_brief
    module.rule_based_brief = brief_llm.rule_based_brief
    monkeypatch.setitem(sys.modules, "ai.modeling.senior.senior_brief_llm", module)
    monkeypatch.setattr(settings, "SENIOR_BRIEF_PROVIDER", "modeling")
    return state


def test_modeling_provider(client: TestClient, counselor_headers, modeling) -> None:
    case = _senior(client, counselor_headers)
    row = _measure(client, counselor_headers, case["id"], systolic=130, diastolic=80)

    data = client.post(f"/api/v1/cases/{case['id']}/senior-brief", headers=counselor_headers).json()["data"]

    assert data["source"] == "AI" and data["model"] == "fake-model" and data["summary"] == "AI 요약"
    assert data["check_items"][0]["basis"][0]["measurement_id"] == row["id"]
    assert data["check_items"][1]["basis"] == []
    assert modeling["calls"][0]["known"] == ["어르신_001"]


class SeniorBriefOutputError(ValueError):
    pass


class PrivacyGatewayBlocked(Exception):
    pass


@pytest.mark.parametrize(
    "error,status,code",
    [
        (SeniorBriefOutputError("원문 섞인 문구"), 502, "AI_INVALID_OUTPUT"),
        (PrivacyGatewayBlocked("김말순"), 422, "AI_PRIVACY_BLOCKED"),
        (RuntimeError("boom"), 502, "AI_FAILED"),
        (TimeoutError(), 504, "AI_TIMEOUT"),
    ],
)
def test_modeling_errors_map_to_codes(client: TestClient, counselor_headers, modeling, error, status, code) -> None:
    case = _senior(client, counselor_headers)
    modeling["raise"] = error

    response = client.post(f"/api/v1/cases/{case['id']}/senior-brief", headers=counselor_headers)

    assert response.status_code == status and response.json()["error"]["code"] == code
    assert "김말순" not in response.text and "원문" not in response.text


def test_production_blocks_modeling_without_flag() -> None:
    from app.core.config import Settings

    def check(**overrides):
        values = {**settings.model_dump(), "SENIOR_BRIEF_PROVIDER": "modeling", **overrides}
        return Settings.model_construct(**values)._block_senior_brief_ai_in_production()

    check(ENV="test")
    check(ENV="production", SENIOR_BRIEF_ALLOW_IN_PRODUCTION=True)
    with pytest.raises(ValueError, match="SENIOR_BRIEF_PROVIDER"):
        check(ENV="production")
