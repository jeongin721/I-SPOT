# 외부 AI 로 보내기 전 이름 가리기에 사례의 등록 실명을 넣는 연결 테스트(specs case-personal-info-encryption 7절, 2026-11-02).
#
# 서버가 case_personal_infos(#127)의 이름을 메모리에서만 풀어 known_identifiers 로 넘긴다(personal_info_service.known_identifiers).
#   - 분석: analysis_service → ModelingAIAdapter → ai/ analyze_audio_session_as_contract → analyze_audio_session
#   - 다음 상담 체크리스트: followup_checklist_service → rag.session.analyze_reviewed_transcript
#   - 종결 요약: closure_review_service → ai/ closure_summary_llm.generate_closure_summary(사례 별칭과 함께)
# 법령 질의는 사례와 묶이지 않아 넘길 이름이 없다(specs 비목표).
#
# 분석 · 종결 요약은 실제 가리기(privacy_gateway)를 거친 글을 외부 LLM 자리(가짜)가 받게 해 등록 이름이 남지 않는지 본다.
# NER 은 가짜라 이름을 하나도 찾지 못한다(tests/test_modeling_gateway_residual.py 의 gateway) — 가려졌다면 등록 이름 대조 덕이다.
# 로그 · 감사 detail · DB 에 이름이 남지 않는지도 본다. 이름은 모두 가상이다.

import importlib
import json
import logging
import sys
import types
import uuid
from typing import Any, Dict, List

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.exc import OperationalError

from app.adapters.ai_adapter import ModelingAIAdapter, set_ai_adapter_override
from app.adapters.followup_checklist_adapter import FollowupChecklistInput, set_followup_checklist_adapter_override
from app.core.config import settings
from app.core.enums import AuditAction
from app.models.analysis import AIAnalysis
from app.models.audit_log import AuditLog
from app.models.followup_checklist import SessionFollowupChecklist
from app.services import closure_review_service, personal_info_service
from tests.conftest import create_session
from tests.test_analysis import _get_analysis, _run_analysis, analyzed_session, confirmed_session
from tests.test_case_personal_info import CHILD, FULL, GUARDIAN, SECRETS, SIBLING, _corrupt, _put
from tests.test_followup_checklist import _FakeRag, _module, _set_analysis_result, _url
from tests.test_modeling_ai_adapter import (  # noqa: F401 — modeling 은 고정 장치
    CONTRACT_ADAPTER,
    PACKAGE,
    TRANSCRIPT,
    _capture_pipeline_kwargs,
    modeling,
)
from tests.test_modeling_gateway_residual import gateway  # noqa: F401 — 고정 장치

GIVEN = ["가람", "누리", "바다"]
# FULL(아동 한가람 · 사례관리대상자 · 면접대상자 · 가족 한누리 · 가족 · 건강정도 한바다)에서 만들어지는 목록. 긴 것부터.
EXPECTED = [CHILD, GUARDIAN, SIBLING, *GIVEN]
NAMES = [CHILD, GUARDIAN, SIBLING, *GIVEN]
ALIAS = "아동_001"  # tests.conftest.create_case 의 별칭


def _assert_no_names(blob: str) -> None:
    for secret in [*SECRETS, *GIVEN]:
        assert secret not in blob, secret


def _views(db) -> int:
    return db.scalar(
        select(func.count()).select_from(AuditLog).where(AuditLog.action == AuditAction.CASE_PERSONAL_INFO_VIEWED)
    )


def _stored(db, *models) -> str:
    """감사 detail 과 주어진 표의 행을 글자로 덤프한다(이름이 남았는지 보려고)."""

    db.expire_all()
    rows: List[Any] = [log.detail for log in db.scalars(select(AuditLog))]

    for model in models:
        for row in db.scalars(select(model)):
            rows.append({column.name: getattr(row, column.name) for column in model.__table__.columns})

    return json.dumps(rows, ensure_ascii=False, default=str)


# =========================================================
# 이름 목록(personal_info_service.known_identifiers)
# =========================================================


def test_names_are_full_and_given_names_longest_first(client: TestClient, counselor_headers, case: dict, db) -> None:
    assert _put(client, counselor_headers, case["id"], FULL).status_code == 200

    names = personal_info_service.known_identifiers(db, uuid.UUID(case["id"]))

    # 같은 이름이 여러 칸에 있어도 한 번만. 생년월일 · 관계 · 건강 세부는 넣지 않는다.
    assert names == EXPECTED
    assert not {"2015-04-12", "1983-09-02", "부", "형제", "가상 진단명"} & set(names)


def test_unregistered_case_gives_only_extra(case: dict, db) -> None:
    case_id = uuid.UUID(case["id"])

    assert personal_info_service.known_identifiers(db, case_id) == []
    assert personal_info_service.known_identifiers(db, case_id, extra=[f" {ALIAS} ", None, " "]) == [ALIAS]


def test_extra_joins_the_longest_first_order(client: TestClient, counselor_headers, case: dict, db) -> None:
    _put(client, counselor_headers, case["id"], FULL)

    # 별칭이 이름 조각이어도(가람) 긴 이름(한가람)이 앞에 와야 '한' 이 남지 않는다. 같은 길이는 넣은 순서대로.
    names = personal_info_service.known_identifiers(db, uuid.UUID(case["id"]), extra=["가람", "아동A"])

    assert names == [CHILD, GUARDIAN, SIBLING, "아동A", "가람", "누리", "바다"]


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("한가람", ["한가람", "가람"]),
        ("한 가람", ["한 가람", "한가람", "가람"]),
        ("이수", ["이수"]),  # 성 뺀 이름이 한 글자면 넣지 않는다
        ("김", []),
        ("남궁민수", ["남궁민수", "궁민수", "민수"]),
        ("선우진", ["선우진", "우진"]),  # 성이 '선' 인지 '선우' 인지 모른다 — 두 글자 이상만
        ("엄마", []),  # 이름 칸에 적은 관계말은 원문의 같은 낱말을 다 가리므로 뺀다
        ("어머니", []),
        ("Kim Ara", ["Kim Ara"]),
    ],
)
def test_name_variants(name: str, expected: List[str]) -> None:
    assert personal_info_service._variants(name) == expected


def test_unreadable_field_is_skipped_with_warning_without_values(
    client: TestClient, counselor_headers, case: dict, db, caplog
) -> None:
    _put(client, counselor_headers, case["id"], FULL)
    _corrupt(db, case["id"])  # 아동 이름 칸만 깨뜨린다

    with caplog.at_level(logging.WARNING):
        names = personal_info_service.known_identifiers(db, uuid.UUID(case["id"]))

    assert names == [GUARDIAN, SIBLING, "누리", "바다"]
    assert f"case_id={case['id']}" in caplog.text and "field=child_name" in caplog.text
    _assert_no_names(caplog.text)


class _BrokenDb:
    def __init__(self) -> None:
        self.rolled_back = False

    def get(self, *args, **kwargs):
        raise OperationalError("SELECT 1", {}, Exception(CHILD))

    def rollback(self) -> None:
        self.rolled_back = True


def test_database_error_gives_only_extra_and_rolls_back(caplog) -> None:
    db = _BrokenDb()

    with caplog.at_level(logging.WARNING):
        names = personal_info_service.known_identifiers(db, uuid.uuid4(), extra=[ALIAS])

    assert names == [ALIAS]
    assert db.rolled_back is True
    assert "reason=OperationalError" in caplog.text
    _assert_no_names(caplog.text)


def test_building_the_list_is_not_a_view(client: TestClient, counselor_headers, case: dict, db) -> None:
    _put(client, counselor_headers, case["id"], FULL)
    before = _views(db)

    personal_info_service.known_identifiers(db, uuid.UUID(case["id"]))

    # 사람에게 내주는 값이 아니라 열람 기록을 남기지 않는다.
    assert _views(db) == before


# =========================================================
# 분석 — 서버 → 어댑터 → ai/ 진입점
# =========================================================


@pytest.mark.usefixtures("modeling")
def test_analysis_passes_registered_names_to_the_module(
    client: TestClient, counselor_headers, case: dict, session: dict, monkeypatch, db, caplog
) -> None:
    _put(client, counselor_headers, case["id"], FULL)
    confirmed_session(client, counselor_headers, session["id"])
    seen = _capture_pipeline_kwargs(monkeypatch)
    set_ai_adapter_override(ModelingAIAdapter())
    views = _views(db)

    with caplog.at_level(logging.DEBUG):
        assert _run_analysis(client, counselor_headers, session["id"]).status_code == 202

    envelope = _get_analysis(client, counselor_headers, session["id"]).json()["data"]

    assert envelope["analysis"]["status"] == "COMPLETED"
    assert seen[-1]["known_identifiers"] == EXPECTED
    assert seen[-1]["case_id"] is None  # case_store 를 쓰지 않는다
    assert _views(db) == views
    _assert_no_names(caplog.text)
    _assert_no_names(_stored(db, AIAnalysis))


@pytest.mark.usefixtures("modeling")
def test_analysis_of_unregistered_case_passes_an_empty_list(
    client: TestClient, counselor_headers, session: dict, monkeypatch
) -> None:
    confirmed_session(client, counselor_headers, session["id"])
    seen = _capture_pipeline_kwargs(monkeypatch)
    set_ai_adapter_override(ModelingAIAdapter())

    assert _run_analysis(client, counselor_headers, session["id"]).status_code == 202

    assert seen[-1]["known_identifiers"] == []


def test_other_adapters_do_not_decrypt_names(
    client: TestClient, counselor_headers, case: dict, session: dict, monkeypatch
) -> None:
    _put(client, counselor_headers, case["id"], FULL)
    calls = []
    monkeypatch.setattr(personal_info_service, "known_identifiers", lambda *args, **kwargs: calls.append(args) or [])

    analyzed_session(client, counselor_headers, session["id"])  # 기본 mock 어댑터

    assert _get_analysis(client, counselor_headers, session["id"]).json()["data"]["analysis"]["status"] == "COMPLETED"
    assert calls == []


@pytest.mark.usefixtures("modeling")
def test_contract_adapter_passes_names_only_when_given(monkeypatch) -> None:
    seen = _capture_pipeline_kwargs(monkeypatch)
    contract_adapter = importlib.import_module(CONTRACT_ADAPTER)

    contract_adapter.analyze_audio_session_as_contract(stt_result=TRANSCRIPT, known_identifiers=EXPECTED)
    assert seen[-1]["known_identifiers"] == EXPECTED

    # 주지 않으면 키 자체를 넘기지 않는다(예전과 같다).
    contract_adapter.analyze_audio_session_as_contract(stt_result=TRANSCRIPT)
    assert "known_identifiers" not in seen[-1]


@pytest.mark.usefixtures("modeling")
def test_older_module_without_the_parameter_still_runs_and_warns(monkeypatch, caplog) -> None:
    seen = _capture_pipeline_kwargs(monkeypatch)
    adapter = ModelingAIAdapter()
    transcript_model, current = adapter._load_pipeline()

    def older(stt_result, deadline=None, case_context=None):
        return current(stt_result=stt_result, deadline=deadline, case_context=case_context)

    monkeypatch.setattr(adapter, "_load_pipeline", lambda: (transcript_model, older))

    with caplog.at_level(logging.WARNING):
        bundle = adapter.analyze(TRANSCRIPT, known_identifiers=EXPECTED)

    assert bundle.provider == "modeling"
    assert "known_identifiers" not in seen[-1]
    assert "등록 이름을 받지 않는 판" in caplog.text
    _assert_no_names(caplog.text)


# =========================================================
# 분석 — ai/ analyze_audio_session 이 외부로 보내는 모든 글
# =========================================================

NAMED_TRANSCRIPT = {
    "schema_version": "1.0",
    "segments": [
        {"segment_id": "seg_001", "speaker": "COUNSELOR", "start_ms": 0, "end_ms": 1500,
         "text": "가람아, 요즘 집에서는 어떻게 지내?", "confidence": 0.95},
        {"segment_id": "seg_002", "speaker": "CHILD", "start_ms": 1500, "end_ms": 4000,
         "text": "한누리 아빠가 화나면 저를 때려요.", "confidence": 0.9},
        # 낮은 신뢰도 발화는 '다음 상담 확인 사항' 입력에 원문 그대로 들어간다(다시 가린다).
        {"segment_id": "seg_003", "speaker": "CHILD", "start_ms": 4000, "end_ms": 6000,
         "text": "그럴 때 바다 형이 저를 방에 숨겨 줘요.", "confidence": 0.5},
        {"segment_id": "seg_004", "speaker": "COUNSELOR", "start_ms": 6000, "end_ms": 8000,
         "text": "한가람, 한바다 둘 다 많이 놀랐겠다.", "confidence": 0.95},
    ],
}

# 외부 LLM 단계 → 그 단계가 외부로 보내는 글이 든 인자. 가짜 단계는 이 인자를 모은다.
OUTBOUND_STEPS = {
    "analyze_subtypes": "text",
    "generate_counseling_records": "transcript",
    "generate_checklist_draft": "text",
    "generate_record_draft": "masked_transcript_text",
    "generate_protective_factors": "masked_transcript_text",
    "generate_desired_changes": "masked_transcript_text",
    "generate_narrative_summary_from_masked_text": "masked_combined_text",
    "rate_severity_from_text": "masked_evidence_text",
    "generate_topic_tags_from_masked_text": "masked_child_lines",
    "generate_followup_questions_from_masked_text": "masked_combined_text",
    "generate_followup_check_points_from_masked_text": "masked_combined_text",
}


def _step_result(name: str, text: str) -> Any:
    """가짜 단계의 반환값. 기록 초안 · 보호요인은 받은 글을 그대로 돌려줘, 이름을 되돌린 뒤 다시 가리는 단계까지 이름이 가게 한다."""

    if name == "analyze_subtypes":
        return {"results": []}
    if name == "generate_counseling_records":
        return {"counseling_summary": {}, "counseling_note": {}}
    if name == "generate_record_draft":
        point = {"text": text, "segment_ids": ["seg_002"], "major_type": "신체학대", "subtype": "직접 신체 가해"}
        return {"risk_signal_points": [point], "child_statement_points": [{"text": text, "segment_ids": ["seg_003"]}]}
    if name == "generate_protective_factors":
        return [{"text": text, "segment_ids": ["seg_003"], "category": "보호자 외 지지"}]
    if name in ("generate_desired_changes", "generate_followup_questions_from_masked_text",
                "generate_followup_check_points_from_masked_text", "rate_severity_from_text"):
        return []
    if name == "generate_topic_tags_from_masked_text":
        return None
    return {}


@pytest.fixture
def real_analysis(gateway, monkeypatch):  # noqa: F811 — gateway 는 고정 장치
    """진짜 infer_audio_session.analyze_audio_session 을 불러온다. 무거운 1차 모델 · case_store(평문 SQLite) · OpenAI 는 가짜다.

    외부 LLM 단계는 가짜로 바꿔 받은 글만 모은다. 가리기(mask_for_outbound · mask_child_lines)는 진짜다(NER 만 가짜).
    """

    package = importlib.import_module(PACKAGE)
    store_reads: List[Any] = []

    case_store = types.ModuleType(f"{PACKAGE}.case_store")
    case_store.get_known_identifiers = lambda case_id: store_reads.append(case_id) or []
    case_store.list_sessions_for_case = lambda case_id: []
    first_stage = types.ModuleType(f"{PACKAGE}.infer_abuse_v3_adapter")
    first_stage.predict_major_types = lambda text, input_mode="qa": {"신체학대": {"detected": True}}
    llm_backend = types.ModuleType(f"{PACKAGE}.llm_backend")
    llm_backend.build_openai_client_and_model = lambda *args, **kwargs: (object(), "fake-model")

    for name, module in (("case_store", case_store), ("infer_abuse_v3_adapter", first_stage), ("llm_backend", llm_backend)):
        monkeypatch.setitem(sys.modules, f"{PACKAGE}.{name}", module)
        monkeypatch.setattr(package, name, module, raising=False)

    # 여기서 새로 불러온 ai.* 모듈은 끝나면 지운다(가짜 torch · openai 로 불러온 모듈이 다른 시험에 남지 않게).
    before = {key for key in sys.modules if key.startswith("ai.")}
    saved_attrs = {key: value for key, value in vars(package).items() if isinstance(value, types.ModuleType)}
    infer = importlib.import_module(f"{PACKAGE}.infer_audio_session")

    sent: Dict[str, List[str]] = {}

    def fake_step(name: str, key: str):
        def step(*args, **kwargs):
            text = kwargs.get(key)
            sent.setdefault(name, []).append(text)
            return _step_result(name, text)

        return step

    for name, key in OUTBOUND_STEPS.items():
        monkeypatch.setattr(infer, name, fake_step(name, key))

    monkeypatch.setattr(infer, "build_openai_client_and_model", llm_backend.build_openai_client_and_model)
    # 관련 조문은 법령 캐시를 읽는다(LLM 아님) — 여기서는 붙이지 않는다.
    monkeypatch.setattr(infer, "_attach_legal_references", lambda points: (points, False))

    yield infer, sent, store_reads

    for key in [key for key in sys.modules if key.startswith("ai.") and key not in before]:
        sys.modules.pop(key, None)
        parent, _, child = key.rpartition(".")

        if parent == PACKAGE:
            if child in saved_attrs:
                setattr(package, child, saved_attrs[child])
            else:
                vars(package).pop(child, None)


def test_every_outbound_text_of_the_analysis_hides_registered_names(
    client: TestClient, counselor_headers, case: dict, db, real_analysis
) -> None:
    infer, sent, store_reads = real_analysis
    _put(client, counselor_headers, case["id"], FULL)
    names = personal_info_service.known_identifiers(db, uuid.UUID(case["id"]))

    infer.analyze_audio_session(stt_result=NAMED_TRANSCRIPT, client=object(), case_id="c1", known_identifiers=names)

    # 처음 가리는 단계 · 이름을 되돌린 뒤 다시 가리는 단계(서사 요약 · 다음 상담 확인 사항) · 아동 발화만 가리는 단계 모두.
    assert set(sent) == set(OUTBOUND_STEPS) - {"rate_severity_from_text"}
    texts = [text for values in sent.values() for text in values]

    assert all(isinstance(text, str) and text for text in texts)
    for text in texts:
        for name in NAMES:
            assert name not in text, (name, text)
    assert "[KNOWN_" in sent["generate_counseling_records"][0]
    assert "[KNOWN_" in sent["generate_narrative_summary_from_masked_text"][0]
    assert "[KNOWN_" in sent["generate_followup_check_points_from_masked_text"][0]
    # 넘긴 목록을 쓰면 case_store(평문 SQLite)는 읽지 않는다.
    assert store_reads == []


def test_without_names_the_same_texts_leak_names(real_analysis) -> None:
    """대조 시험: 이름 목록 없이는 가짜 NER 이 이름을 못 찾아 그대로 나간다 — 위 시험이 가린 것은 등록 이름 덕이다."""

    infer, sent, store_reads = real_analysis

    infer.analyze_audio_session(stt_result=NAMED_TRANSCRIPT, client=object())

    assert GUARDIAN in sent["generate_counseling_records"][0]
    assert store_reads == []  # case_id 가 없으면 예전처럼 읽지 않는다


def test_old_callers_still_read_case_store(real_analysis) -> None:
    infer, sent, store_reads = real_analysis

    infer.analyze_audio_session(stt_result=NAMED_TRANSCRIPT, client=object(), case_id="c1")

    assert store_reads == ["c1"]


# =========================================================
# 다음 상담 체크리스트 — rag
# =========================================================


def test_checklist_passes_registered_names_to_rag(
    client: TestClient, counselor_headers, case: dict, session: dict, monkeypatch, db, caplog
) -> None:
    _put(client, counselor_headers, case["id"], FULL)
    analyzed_session(client, counselor_headers, session["id"])
    _set_analysis_result(db, session["id"])
    fake = _FakeRag()
    set_followup_checklist_adapter_override(_module(monkeypatch, fake))
    views = _views(db)

    with caplog.at_level(logging.DEBUG):
        assert client.post(_url(session["id"]), headers=counselor_headers).status_code == 202

    checklist = client.get(_url(session["id"]), headers=counselor_headers).json()["data"]["checklist"]

    assert checklist["status"] == "COMPLETED"
    assert fake.calls[0]["known_identifiers"] == EXPECTED
    assert _views(db) == views
    _assert_no_names(caplog.text)
    _assert_no_names(_stored(db, SessionFollowupChecklist))


def test_checklist_input_repr_hides_names() -> None:
    payload = FollowupChecklistInput(
        transcript={"segments": []}, abuse_type="physical", session_no=1, session_id="s", known_identifiers=EXPECTED
    )

    _assert_no_names(repr(payload))


# =========================================================
# 종결 요약 — ai/ closure_summary_llm
# =========================================================


@pytest.fixture
def closure_llm(gateway, monkeypatch):  # noqa: F811 — gateway 는 고정 장치
    """진짜 closure_summary_llm.generate_closure_summary 를 쓴다. 가리기는 진짜(NER 만 가짜), 외부 LLM 호출만 가짜다.

    AI_PROVIDER=modeling 은 시험이 회차를 승인한 뒤 켠다(먼저 켜면 회차 분석이 진짜 분석 모듈을 부른다).
    """

    gw, _pii, _state = gateway
    package = importlib.import_module(PACKAGE)
    sent: Dict[str, Any] = {"prompts": []}

    llm_backend = types.ModuleType(f"{PACKAGE}.llm_backend")
    llm_backend.build_openai_client_and_model = lambda *args, **kwargs: (object(), "fake-model")
    monkeypatch.setitem(sys.modules, f"{PACKAGE}.llm_backend", llm_backend)
    monkeypatch.setattr(package, "llm_backend", llm_backend, raising=False)

    def call_llm(client, model, system_prompt, user_prompt, **kwargs):
        sent["prompts"].append(system_prompt + "\n" + user_prompt)
        return {"groups": [{"title": "학대 관련 진술", "items": [{"text": "새 진술 없음", "sessions": [1]}]}], "report": {}}

    monkeypatch.setattr(sys.modules[f"{PACKAGE}.second_stage_llm"], "_call_llm_with_retry", call_llm)

    original = gw.mask_for_outbound

    def mask_for_outbound(text, known_identifiers=None):
        sent["known"] = list(known_identifiers or [])
        return original(text, known_identifiers=known_identifiers)

    monkeypatch.setattr(gw, "mask_for_outbound", mask_for_outbound)
    closure_review_service.reset_limits()
    yield sent
    closure_review_service.reset_limits()


def _approve_with_names(client: TestClient, headers, session_id: str) -> None:
    analyzed_session(client, headers, session_id)
    patched = client.patch(
        f"/api/v1/sessions/{session_id}/summary",
        json={
            "assessment": {
                "safety_risks": f"{GUARDIAN} 이(가) 술을 마시면 가람이를 때림",
                "strengths_resources": f"{SIBLING} 이(가) 방에 숨겨 줌. 바다 형과 가깝다",
            }
        },
        headers=headers,
    )
    assert patched.status_code == 200, patched.text
    assert client.post(f"/api/v1/sessions/{session_id}/summary/approve", headers=headers).status_code == 200


def test_closure_summary_masks_registered_names_before_the_llm(
    client: TestClient, counselor_headers, case: dict, db, closure_llm, monkeypatch, caplog
) -> None:
    _put(client, counselor_headers, case["id"], FULL)
    session = create_session(client, counselor_headers, case["id"])
    _approve_with_names(client, counselor_headers, session["id"])
    assert client.post(f"/api/v1/cases/{case['id']}/closure-review", headers=counselor_headers).status_code == 200
    monkeypatch.setattr(settings, "AI_PROVIDER", "modeling")
    views = _views(db)

    with caplog.at_level(logging.DEBUG):
        response = client.post(f"/api/v1/cases/{case['id']}/closure-summary", headers=counselor_headers)

    assert response.status_code == 200, response.text
    assert response.json()["data"]["summary"]["source"] == "AI"
    # 별칭은 예전처럼 넘기고, 등록 실명을 더한다(긴 것부터).
    assert closure_llm["known"] == [ALIAS, *EXPECTED]
    [prompt] = closure_llm["prompts"]
    for name in NAMES:
        assert name not in prompt, name
    assert "[KNOWN_" in prompt
    assert _views(db) == views
    _assert_no_names(caplog.text)
