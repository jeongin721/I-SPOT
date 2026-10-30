# AI 분석에 넘기는 사례 정보(case_context, PROPOSAL_case_context_analysis.md §3 합의 2026-10-28).
#
# - 넘기는 값: 나이대 · 성별 · 보호자 유형 · 초기면접 항목 · 직전 '승인 완료' 회차의 확정 요약 4칸.
# - 넘기지 않는 값: 가명 · 사건번호 · 제목 · 메모.
# - case_context 를 받는 어댑터(키워드)에만 넘기고, 못 만들어도 분석은 계속한다.

import uuid
from typing import Any, Dict, List

import pytest
from fastapi.testclient import TestClient

from app.adapters.ai_adapter import MockAIAdapter, ModelingAIAdapter, set_ai_adapter_override
from app.adapters.module_loader import ensure_repo_root_on_path
from app.models.session import ConsultationSession
from app.services import case_context_service
from app.services.case_context_service import age_band, build_case_context
from tests.conftest import create_case, create_session
from tests.test_analysis import _get_analysis, _run_analysis, analyzed_session, confirmed_session


class CapturingAdapter:
    """case_context 를 키워드로 받는 어댑터. 받은 값을 모으고 결과는 Mock 과 같다."""

    name = "capturing"

    def __init__(self) -> None:
        self.contexts: List[Any] = []

    def analyze(self, transcript_payload: Dict[str, Any], *, case_context: Any = None):
        self.contexts.append(case_context)
        return MockAIAdapter().analyze(transcript_payload)


@pytest.mark.parametrize(
    ("birth_year", "expected"),
    [(2026, "만 0~5세"), (2020, "만 6~9세"), (2014, "만 10~13세"), (2010, "만 14~17세"), (2000, "만 18세 이상"), (2030, None), (None, None)],
)
def test_age_band(birth_year, expected) -> None:
    assert age_band(birth_year, 2026) == expected


def _case_with_intake(client: TestClient, headers) -> dict:
    return create_case(
        client,
        headers,
        child_alias="김하늘",
        child_birth_year=2014,
        child_gender="F",
        guardian_type="FATHER",
        intake_child_traits=["불안"],
        intake_family_situations=["알콜남용"],
        notes="메모에는 이름이 들어갈 수 있다",
    )


def _approve_with_assessment(client: TestClient, headers, session_id: str) -> None:
    analyzed_session(client, headers, session_id)
    patched = client.patch(
        f"/api/v1/sessions/{session_id}/summary",
        json={"assessment": {"strengths_resources": "조모에게 연락하는 방법을 앎", "safety_risks": "부의 음주 뒤 체벌"}},
        headers=headers,
    )
    assert patched.status_code == 200, patched.text
    assert client.post(f"/api/v1/sessions/{session_id}/summary/approve", headers=headers).status_code == 200


def test_build_case_context_uses_minimum_fields_and_previous_approved_session(
    client: TestClient, counselor_headers, db
) -> None:
    case = _case_with_intake(client, counselor_headers)
    first = create_session(client, counselor_headers, case["id"])
    second = create_session(client, counselor_headers, case["id"])
    _approve_with_assessment(client, counselor_headers, first["id"])

    session = db.get(ConsultationSession, uuid.UUID(second["id"]))
    context = build_case_context(db, session)

    assert context["child_age_band"] in {"만 10~13세", "만 14~17세"}  # 출생연도 2014, 올해에 따라
    assert context["child_gender"] == "F"
    assert context["guardian_type"] == "FATHER"
    assert context["intake_child_traits"] == ["불안"]
    assert context["intake_family_situations"] == ["알콜남용"]
    assert context["previous_session"] == {
        "session_label": f"{first['session_number']}회차",
        "consulted_on": None,
        "assessment": {"strengths_resources": "조모에게 연락하는 방법을 앎", "safety_risks": "부의 음주 뒤 체벌"},
    }
    dumped = repr(context)
    assert "김하늘" not in dumped and "메모" not in dumped and case["case_number"] not in dumped


def test_previous_session_is_none_without_earlier_approved_session(client: TestClient, counselor_headers, db) -> None:
    case = _case_with_intake(client, counselor_headers)
    first = create_session(client, counselor_headers, case["id"])
    second = create_session(client, counselor_headers, case["id"])
    analyzed_session(client, counselor_headers, first["id"])  # 분석만 하고 승인하지 않음

    assert build_case_context(db, db.get(ConsultationSession, uuid.UUID(second["id"])))["previous_session"] is None
    # 이 회차보다 뒤 회차는 '직전' 이 아니다.
    _approve_with_assessment(client, counselor_headers, second["id"])
    assert build_case_context(db, db.get(ConsultationSession, uuid.UUID(first["id"])))["previous_session"] is None


def test_analysis_passes_case_context_to_adapter_that_accepts_it(client: TestClient, counselor_headers) -> None:
    case = _case_with_intake(client, counselor_headers)
    first = create_session(client, counselor_headers, case["id"])
    second = create_session(client, counselor_headers, case["id"])
    _approve_with_assessment(client, counselor_headers, first["id"])

    adapter = CapturingAdapter()
    set_ai_adapter_override(adapter)
    try:
        confirmed_session(client, counselor_headers, second["id"])
        assert _run_analysis(client, counselor_headers, second["id"]).status_code == 202
    finally:
        set_ai_adapter_override(None)

    assert _get_analysis(client, counselor_headers, second["id"]).json()["data"]["analysis"]["status"] == "COMPLETED"
    assert adapter.contexts[-1]["intake_family_situations"] == ["알콜남용"]
    assert adapter.contexts[-1]["previous_session"]["session_label"] == f"{first['session_number']}회차"


def test_case_context_failure_does_not_stop_analysis(
    client: TestClient, counselor_headers, session: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken(*args, **kwargs):
        raise RuntimeError("사례 정보 실패")

    monkeypatch.setattr(case_context_service, "build_case_context", broken)
    adapter = CapturingAdapter()
    set_ai_adapter_override(adapter)
    try:
        confirmed_session(client, counselor_headers, session["id"])
        assert _run_analysis(client, counselor_headers, session["id"]).status_code == 202
    finally:
        set_ai_adapter_override(None)

    assert _get_analysis(client, counselor_headers, session["id"]).json()["data"]["analysis"]["status"] == "COMPLETED"
    assert adapter.contexts == [None]


def _modeling_with(monkeypatch: pytest.MonkeyPatch, pipeline) -> ModelingAIAdapter:
    ensure_repo_root_on_path()
    from ai.schemas.analysis import Transcript

    adapter = ModelingAIAdapter()
    monkeypatch.setattr(adapter, "_load_pipeline", lambda: (Transcript, pipeline))
    return adapter


TRANSCRIPT = {
    "schema_version": "1.0",
    "segments": [
        {"segment_id": "seg_001", "speaker": "CHILD", "start_ms": 0, "end_ms": 1000, "text": "무서웠어요.", "confidence": 0.9}
    ],
}
CONTEXT = {"child_age_band": "만 10~13세", "intake_family_situations": ["알콜남용"]}


def test_modeling_adapter_passes_case_context_when_module_accepts(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: List[Dict[str, Any]] = []

    def pipeline(stt_result, deadline=None, case_context=None):
        seen.append({"case_context": case_context})
        return {"schema_version": "1.0"}, [], "test-model"

    _modeling_with(monkeypatch, pipeline).analyze(TRANSCRIPT, case_context=CONTEXT)

    assert seen == [{"case_context": CONTEXT}]


def test_modeling_adapter_skips_case_context_for_old_module(monkeypatch: pytest.MonkeyPatch) -> None:
    def pipeline(stt_result, deadline=None):  # case_context 를 모르는 예전 판
        return {"schema_version": "1.0"}, [], "test-model"

    bundle = _modeling_with(monkeypatch, pipeline).analyze(TRANSCRIPT, case_context=CONTEXT)

    assert bundle.model == "test-model"


@pytest.mark.parametrize(
    ("consulted_at", "expected"),
    [
        ("2026-10-20T23:30:00+00:00", "2026-10-21"),  # 한국 10/21 08:30 — UTC 날짜(10/20)로 나가면 안 된다
        ("2026-10-21T05:00:00+00:00", "2026-10-21"),
    ],
)
def test_previous_session_date_is_korean_date(
    client: TestClient, counselor_headers, db, consulted_at: str, expected: str
) -> None:
    case = _case_with_intake(client, counselor_headers)
    first = create_session(client, counselor_headers, case["id"])
    second = create_session(client, counselor_headers, case["id"])
    assert (
        client.patch(f"/api/v1/sessions/{first['id']}", json={"consulted_at": consulted_at}, headers=counselor_headers).status_code
        == 200
    )
    _approve_with_assessment(client, counselor_headers, first["id"])

    session = db.get(ConsultationSession, uuid.UUID(second["id"]))

    assert build_case_context(db, session)["previous_session"]["consulted_on"] == expected
