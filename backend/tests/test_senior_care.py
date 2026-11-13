# 고령자 건강상담(API_CONTRACT 27절, 2026-11-13) — 대상 종류 · 기본정보 · 건강측정 · 추이 · 요약과 다음 상담 확인사항.
# 데이터는 모두 가상이다. 기본(SENIOR_AI_PROVIDER=rule)은 LLM 없이 규칙으로 묶고, modeling 경로는 가짜 모듈로 본다.

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
    monkeypatch.setattr(settings, "SENIOR_AI_PROVIDER", "modeling")
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
        values = {**settings.model_dump(), "SENIOR_AI_PROVIDER": "modeling", **overrides}
        return Settings.model_construct(**values)._block_senior_ai_in_production()

    check(ENV="test")
    check(ENV="production", SENIOR_AI_ALLOW_IN_PRODUCTION=True)
    with pytest.raises(ValueError, match="SENIOR_AI_PROVIDER"):
        check(ENV="production")


# ================================================================ 개선안(11/13) — 그 밖 결과 · 확인사항 표 · 회차 통합 요약 · 이력

from ai.modeling.senior import senior_session_llm as session_llm  # noqa: E402
from app.adapters.senior_ai_adapter import set_senior_ai_adapter_override  # noqa: E402
from app.services import key_scan_service  # noqa: E402
from tests.test_analysis import analyzed_session, transcribed_session  # noqa: E402

CIST = {"kind": "COGNITIVE_SCREENING", "name": "CIST", "value": 24, "max_value": 30}


@pytest.fixture(autouse=True)
def _no_senior_override():
    set_senior_ai_adapter_override(None)
    yield
    set_senior_ai_adapter_override(None)


# ---------------------------------------------------------------- 그 밖 결과(치매 조기검사 등)


def test_extra_results_only_is_enough_and_trend_groups_by_name(client: TestClient, counselor_headers) -> None:
    case = _senior(client, counselor_headers)
    cid = case["id"]
    first = _measure(client, counselor_headers, cid, measured_at="2026-10-01T09:00:00+09:00", extra_results=[CIST])
    second = _measure(
        client, counselor_headers, cid, measured_at="2026-11-01T09:00:00+09:00",
        pulse=70, extra_results=[{**CIST, "value": 21}, {"kind": "OTHER", "name": "악력", "value": 18.5, "unit": "kg"}],
    )

    assert first["extra_results"] == [{**CIST, "value": 24.0, "max_value": 30.0, "unit": None}]
    trend = {item["metric"]: item for item in client.get(f"/api/v1/cases/{cid}/health-trend", headers=counselor_headers).json()["data"]["metrics"]}
    assert list(trend) == ["pulse", "COGNITIVE_SCREENING:CIST", "OTHER:악력"]
    cist = trend["COGNITIVE_SCREENING:CIST"]
    assert cist["kind"] == "COGNITIVE_SCREENING" and cist["max_value"] == 30 and cist["unit"] == "/30"
    assert cist["change"] == -3 and [p["measurement_id"] for p in cist["points"]] == [first["id"], second["id"]]
    assert trend["OTHER:악력"]["unit"] == "kg" and trend["pulse"]["kind"] is None

    brief = client.post(f"/api/v1/cases/{cid}/senior-brief", headers=counselor_headers).json()["data"]
    item = next(i for i in brief["check_items"] if i["text"].startswith("CIST"))
    assert "3점 낮아졌어요(21/30)" in item["text"] and not brief_llm.is_forbidden(item["text"])
    # 그 밖(OTHER) 결과는 규칙으로 올리지 않는다
    assert not any(i["text"].startswith("악력") for i in brief["check_items"])


@pytest.mark.parametrize(
    "extra",
    [
        [CIST, CIST],  # 같은 종류 · 이름 두 번
        [{**CIST, "value": 31}],  # 만점보다 큼
        [{**CIST, "name": "a:b"}],
        [{**CIST, "name": "  "}],
        [{**CIST, "kind": "DIAGNOSIS"}],
    ],
)
def test_extra_results_validation(client: TestClient, counselor_headers, extra) -> None:
    case = _senior(client, counselor_headers)

    response = client.post(
        f"/api/v1/cases/{case['id']}/health-measurements",
        json={"measured_at": "2026-11-01T09:00:00+09:00", "extra_results": extra},
        headers=counselor_headers,
    )

    assert response.status_code == 422


def test_patch_extra_results(client: TestClient, counselor_headers) -> None:
    case = _senior(client, counselor_headers)
    row = _measure(client, counselor_headers, case["id"], pulse=70)
    url = f"/api/v1/cases/{case['id']}/health-measurements/{row['id']}"

    patched = client.patch(url, json={"extra_results": [CIST]}, headers=counselor_headers)
    assert patched.status_code == 200, patched.text
    assert patched.json()["data"]["extra_results"][0]["name"] == "CIST"

    # 값을 모두 비우면 400
    assert client.patch(url, json={"pulse": None, "extra_results": []}, headers=counselor_headers).status_code == 400


# ---------------------------------------------------------------- 다음 상담 확인사항 표


def test_next_checks_save_list_update_delete(client: TestClient, counselor_headers, db) -> None:
    case = _senior(client, counselor_headers)
    cid = case["id"]
    row = _measure(client, counselor_headers, cid, systolic=140, diastolic=85)
    visit = create_session(client, counselor_headers, cid)
    later = create_session(client, counselor_headers, cid)
    url = f"/api/v1/cases/{cid}/next-checks"

    saved = client.post(
        url,
        json={
            "source_session_id": visit["id"],
            "items": [
                {"text": " 혈압 다시 재기 ", "origin": "RULE", "basis": [{"kind": "MEASUREMENT", "metric": "systolic", "measurement_id": row["id"]}]},
                {"text": "복약을 잊는지 여쭤 보기", "origin": "AI", "edited": True, "basis": [{"kind": "SEGMENT", "segment_ids": ["seg_004"]}]},
                {"text": "따님과 통화했는지", "edited": True},
            ],
        },
        headers=counselor_headers,
    )
    assert saved.status_code == 201, saved.text
    items = saved.json()["data"]
    assert [i["text"] for i in items] == ["혈압 다시 재기", "복약을 잊는지 여쭤 보기", "따님과 통화했는지"]
    assert [i["edited"] for i in items] == [False, True, False]  # 담당자가 쓴 것은 edited 가 아니다
    assert items[0]["basis"] == [{"kind": "MEASUREMENT", "metric": "systolic", "measurement_id": row["id"], "session_number": None, "segment_ids": None}]
    assert all(i["status"] == "OPEN" and i["source_session_id"] == visit["id"] for i in items)

    first = items[0]["id"]
    edited = client.patch(f"{url}/{first}", json={"text": "혈압 두 번 재기"}, headers=counselor_headers).json()["data"]
    assert edited["edited"] is True

    # OPEN 인데 확인 방문을 적으면 400
    assert client.patch(f"{url}/{first}", json={"checked_session_id": later["id"]}, headers=counselor_headers).status_code == 400
    done = client.patch(
        f"{url}/{first}", json={"status": "DONE", "checked_session_id": later["id"], "result_note": "128/80"}, headers=counselor_headers
    ).json()["data"]
    assert done["status"] == "DONE" and done["checked_session_id"] == later["id"] and done["checked_at"] and done["result_note"] == "128/80"

    assert [i["id"] for i in client.get(f"{url}?status=OPEN", headers=counselor_headers).json()["data"]] == [items[1]["id"], items[2]["id"]]

    reopened = client.patch(f"{url}/{first}", json={"status": "OPEN"}, headers=counselor_headers).json()["data"]
    assert reopened["checked_at"] is None and reopened["checked_session_id"] is None

    assert client.delete(f"{url}/{items[2]['id']}", headers=counselor_headers).status_code == 204
    assert len(client.get(url, headers=counselor_headers).json()["data"]) == 2

    details = str([log.detail for log in db.scalars(select(AuditLog).where(AuditLog.case_id == uuid.UUID(cid)))])
    assert "혈압" not in details and "따님" not in details and "128" not in details
    saved_log = db.scalar(select(AuditLog).where(AuditLog.action == AuditAction.NEXT_CHECKS_SAVED))
    assert saved_log.detail == {"count": 3, "by_origin": {"RULE": 1, "AI": 1, "COUNSELOR": 1}, "edited": 1}


def test_next_checks_rejects_other_case_basis_and_child_case(client: TestClient, counselor_headers) -> None:
    case = _senior(client, counselor_headers)
    other = _senior(client, counselor_headers)
    foreign = _measure(client, counselor_headers, other["id"], pulse=70)

    response = client.post(
        f"/api/v1/cases/{case['id']}/next-checks",
        json={"items": [{"text": "x", "basis": [{"kind": "MEASUREMENT", "measurement_id": foreign["id"]}]}]},
        headers=counselor_headers,
    )
    assert response.status_code == 400

    child = create_case(client, counselor_headers)
    assert client.post(
        f"/api/v1/cases/{child['id']}/next-checks", json={"items": [{"text": "x"}]}, headers=counselor_headers
    ).status_code == 409
    assert client.post(f"/api/v1/cases/{case['id']}/next-checks", json={"items": []}, headers=counselor_headers).status_code == 422


# ---------------------------------------------------------------- 회차 통합 요약(분석)


def test_senior_session_analysis_uses_visit_measurements_and_skips_child_steps(
    client: TestClient, counselor_headers, monkeypatch
) -> None:
    calls = []
    monkeypatch.setattr(settings, "AI_PROVIDER", "modeling")  # 아동이면 핵심 발화 스캔이 돌 설정
    monkeypatch.setattr(key_scan_service, "_load_scanner", lambda: (lambda contract: calls.append(contract) or {}))
    monkeypatch.setattr(settings, "FOLLOWUP_PROVIDER", "mock")
    case = _senior(client, counselor_headers)
    session = create_session(client, counselor_headers, case["id"])
    row = _measure(client, counselor_headers, case["id"], systolic=142, diastolic=88, pulse=76, session_id=session["id"])

    stt = transcribed_session(client, counselor_headers, session["id"])
    assert stt["transcript"]["key_scan"]["status"] == "SKIPPED" and calls == []

    envelope = analyzed_session(client, counselor_headers, session["id"])
    analysis = envelope["analysis"]
    assert analysis["status"] == "COMPLETED" and analysis["provider"] == "senior-rule"
    result = analysis["result"]
    assert result["abuse_signals"] == [] and result["risk_utterances"] == [] and result["topic_tags"] is None
    senior = result["senior"]
    assert senior["source"] == "RULE" and senior["visit_measurement_ids"] == [row["id"]] * 3
    assert result["summary"]["key_points"][0] == "이번 측정: 혈압 142/88mmHg, 맥박 76회/분."
    assert senior["key_point_basis"][0][0] == {"kind": "MEASUREMENT", "metric": "systolic", "measurement_id": row["id"]}
    assert senior["key_point_basis"][1] == [{"kind": "SEGMENT", "segment_ids": ["seg_002"]}]
    assert "이번 측정: 혈압 142/88mmHg" in result["summary"]["overview"]
    assert any("규칙으로 옮긴" in w for w in result["warnings"])
    # 아동용 체크리스트는 만들지 않는다(켜 둬도)
    checklist = client.get(f"/api/v1/sessions/{session['id']}/followup-checklist", headers=counselor_headers).json()["data"]
    assert checklist.get("checklist") is None or checklist["checklist"] is None
    assert client.post(f"/api/v1/sessions/{session['id']}/followup-checklist", headers=counselor_headers).status_code == 409


def test_child_session_result_has_no_senior(client: TestClient, counselor_headers, session: dict) -> None:
    envelope = analyzed_session(client, counselor_headers, session["id"])

    assert envelope["analysis"]["provider"] == "mock" and envelope["analysis"]["result"]["senior"] is None


@pytest.fixture
def senior_modeling(monkeypatch):
    state = {"raise": None, "calls": []}
    module = types.ModuleType("ai.modeling.senior.senior_session_llm")

    def summarize_senior_session(data, known_identifiers=None, deadline=None):
        state["calls"].append({"data": data, "known": known_identifiers, "deadline": deadline})
        if state["raise"] is not None:
            raise state["raise"]
        return {
            "overview": "AI 통합 요약",
            "key_points": [{"text": "약 먹는 걸 깜빡한다고 말씀하심", "basis": [{"kind": "SEGMENT", "segment_ids": ["seg_006"]}]}],
            "check_points": [{"text": "복약 여부 여쭤 보기", "basis": [{"kind": "SEGMENT", "segment_ids": ["seg_006"]}]}],
            "safety_mentions": [{"kind": "URGENT_HEALTH", "text": "가슴이 답답해", "segment_ids": ["seg_004"]}],
            "model": "fake-senior",
        }

    module.summarize_senior_session = summarize_senior_session
    module.rule_based_session_summary = session_llm.rule_based_session_summary
    monkeypatch.setitem(sys.modules, "ai.modeling.senior.senior_session_llm", module)
    monkeypatch.setattr(settings, "SENIOR_AI_PROVIDER", "modeling")
    return state


def test_senior_session_modeling(client: TestClient, counselor_headers, senior_modeling) -> None:
    case = _senior(client, counselor_headers)
    session = create_session(client, counselor_headers, case["id"])

    analysis = analyzed_session(client, counselor_headers, session["id"])["analysis"]

    assert analysis["provider"] == "senior-modeling" and analysis["model"] == "fake-senior"
    result = analysis["result"]
    assert result["summary"] == {"overview": "AI 통합 요약", "key_points": ["약 먹는 걸 깜빡한다고 말씀하심"], "assessment": result["summary"]["assessment"]}
    assert result["senior"]["source"] == "AI"
    assert result["senior"]["next_check_drafts"] == [{"text": "복약 여부 여쭤 보기", "basis": [{"kind": "SEGMENT", "segment_ids": ["seg_006"]}]}]
    assert result["senior"]["safety_mentions"][0]["kind"] == "URGENT_HEALTH"
    assert any("급한 건강 문제" in w for w in result["warnings"])
    assert senior_modeling["calls"][0]["known"] == ["어르신_001"]
    assert senior_modeling["calls"][0]["deadline"] is not None


@pytest.mark.parametrize(
    "error,code",
    [
        (type("SeniorSessionOutputError", (ValueError,), {})("x"), "AI_INVALID_OUTPUT"),
        (type("PrivacyGatewayBlocked", (Exception,), {})("김말순"), "AI_PRIVACY_BLOCKED"),
        (RuntimeError("boom"), "AI_FAILED"),
    ],
)
def test_senior_session_modeling_errors(client: TestClient, counselor_headers, senior_modeling, error, code) -> None:
    senior_modeling["raise"] = error
    case = _senior(client, counselor_headers)
    session = create_session(client, counselor_headers, case["id"])

    envelope = analyzed_session(client, counselor_headers, session["id"])

    assert envelope["session_status"] == "AI_FAILED"
    assert envelope["analysis"]["error"]["code"] == code
    assert "김말순" not in str(envelope)


def test_session_module_rules_and_cleaning() -> None:
    segments = [
        {"segment_id": "s1", "speaker": "COUNSELOR", "text": "요즘 어떠세요?"},
        {"segment_id": "s2", "speaker": "CHILD", "text": "요즘 약 먹는 걸 자꾸 깜빡해."},
        {"segment_id": "s3", "speaker": "OTHER", "text": "가끔은 그냥 죽고 싶다는 생각도 들어."},
        {"segment_id": "s4", "speaker": "CHILD", "text": "어제는 가슴이 답답하고 숨이 차더라고."},
        {"segment_id": "s5", "speaker": "COUNSELOR", "text": "죽고 싶다는 생각이 드실 때가 있나요?"},  # 담당자 말은 안 본다
    ]

    safety = session_llm.find_safety_mentions(segments)
    assert [(s["kind"], s["segment_ids"]) for s in safety] == [("SELF_HARM", ["s3"]), ("URGENT_HEALTH", ["s4"])]

    refs = {"V1": {"kind": "MEASUREMENT", "metric": "systolic", "measurement_id": "m1"}, "S2": {"kind": "SESSION", "session_number": 2}}
    raw = {
        "overview": "치매가 의심됩니다.",
        "key_points": [
            {"text": "약 먹는 걸 자꾸 깜빡한다고 말씀하심", "refs": ["s2", "s2", "s9"]},
            {"text": "혈압이 140으로 지난번보다 올랐어요", "refs": ["V1", "S2"]},
            {"text": "고혈압입니다", "refs": ["V1"]},
            {"text": "근거 없음", "refs": []},
        ],
        "check_points": [{"text": "복약 여부 여쭤 보기", "refs": ["s2"]}],
        "safety_mentions": [{"kind": "SELF_HARM", "text": "죽고 싶다", "refs": ["s3", "s99"]}, {"kind": "OTHER", "text": "x", "refs": ["s3"]}],
    }
    cleaned = session_llm.clean_output(raw, refs, ["s1", "s2", "s3", "s4"], "규칙 개요")
    assert cleaned["overview"] == "규칙 개요"
    assert cleaned["key_points"] == [
        {"text": "약 먹는 걸 자꾸 깜빡한다고 말씀하심", "basis": [{"kind": "SEGMENT", "segment_ids": ["s2"]}]},
        {"text": "혈압이 140으로 지난번보다 올랐어요", "basis": [refs["V1"], refs["S2"]]},
    ]
    assert cleaned["safety_mentions"] == [{"kind": "SELF_HARM", "text": "죽고 싶다", "segment_ids": ["s3"]}]
    assert session_llm._merge_safety(safety, cleaned["safety_mentions"]) == safety

    with pytest.raises(session_llm.SeniorSessionOutputError):
        session_llm.clean_output({"overview": "x", "key_points": [{"text": "진단 필요", "refs": ["s2"]}]}, refs, ["s2"], "f")


def test_rule_session_summary_includes_brief_checks() -> None:
    data = {
        "today": "2026-11-13",
        "segments": [{"segment_id": "s1", "speaker": "CHILD", "text": "무릎이 아파요"}],
        "visit_measurements": [
            {"id": "m2", "metric": "systolic", "label": "수축기 혈압", "unit": "mmHg", "value": 140.0},
            {"id": "m2", "metric": "diastolic", "label": "이완기 혈압", "unit": "mmHg", "value": 85.0},
            {"id": "m2", "metric": "COGNITIVE_SCREENING:CIST", "label": "CIST", "unit": "/30", "value": 22.0},
        ],
        "metrics": [_metric("systolic", [120, 140])],
        "sessions": [],
        "profile": {},
    }

    out = session_llm.rule_based_session_summary(data)

    assert out["key_points"][0]["text"] == "이번 측정: 혈압 140/85mmHg, CIST 22/30."
    assert out["key_points"][1] == {"text": "무릎이 아파요", "basis": [{"kind": "SEGMENT", "segment_ids": ["s1"]}]}
    assert len(out["check_points"]) == 1 and "20mmHg 올랐어요" in out["check_points"][0]["text"]
    assert out["safety_mentions"] == []


# ---------------------------------------------------------------- 상담 이력 조회


def test_history_groups_by_visit(client: TestClient, counselor_headers) -> None:
    case = _senior(client, counselor_headers)
    cid = case["id"]
    first = create_session(client, counselor_headers, cid)
    second = create_session(client, counselor_headers, cid)
    client.patch(f"/api/v1/sessions/{first['id']}", json={"consulted_at": "2026-10-01T10:00:00+09:00"}, headers=counselor_headers)
    client.patch(f"/api/v1/sessions/{second['id']}", json={"consulted_at": "2026-11-01T10:00:00+09:00"}, headers=counselor_headers)
    in_visit = _measure(client, counselor_headers, cid, measured_at="2026-10-01T10:10:00+09:00", pulse=70, session_id=first["id"])
    loose = _measure(client, counselor_headers, cid, measured_at="2026-10-15T09:00:00+09:00", pulse=74)
    checks = client.post(
        f"/api/v1/cases/{cid}/next-checks",
        json={"source_session_id": first["id"], "items": [{"text": "맥박 다시 재기"}, {"text": "외출 여쭤 보기"}]},
        headers=counselor_headers,
    ).json()["data"]
    client.patch(
        f"/api/v1/cases/{cid}/next-checks/{checks[0]['id']}",
        json={"status": "DONE", "checked_session_id": second["id"]},
        headers=counselor_headers,
    )

    data = client.get(f"/api/v1/cases/{cid}/senior-history", headers=counselor_headers).json()["data"]

    kinds = [(e["kind"], e["session_number"]) for e in data["entries"]]
    assert kinds == [("VISIT", second["session_number"]), ("MEASUREMENT", None), ("VISIT", first["session_number"])]
    newest, middle, oldest = data["entries"]
    assert [c["id"] for c in newest["checks_resolved"]] == [checks[0]["id"]]
    assert middle["measurements"][0]["id"] == loose["id"]
    assert oldest["measurements"][0]["id"] == in_visit["id"] and len(oldest["checks_created"]) == 2
    assert [c["id"] for c in data["open_checks"]] == [checks[1]["id"]]
