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
import threading
import time
import types
import unicodedata
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
from app.models.case_personal_info import CasePersonalInfo
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
from tests.test_modeling_gateway_residual import MASKED, VALID_TOKEN, _tags, gateway  # noqa: F401 — gateway 는 고정 장치

GIVEN = ["가람", "누리", "바다"]
# FULL(아동 한가람 · 사례관리대상자 · 면접대상자 · 가족 한누리 · 가족 · 건강정도 한바다)에서 만들어지는 이름(전체 · 성 뺀 이름).
NAMES = [CHILD, GUARDIAN, SIBLING, *GIVEN]
ALIAS = "아동_001"  # tests.conftest.create_case 의 별칭


def _nfd(text: str) -> str:
    return unicodedata.normalize("NFD", text)


# 목록에는 한글을 자모로 풀어 쓴 표기(NFD)도 들어간다(Codex #138 H1).
EXPECTED = {*NAMES, *map(_nfd, NAMES)}


def _assert_names(names: List[str], expected=EXPECTED) -> None:
    """같은 이름 집합이고, 한 번씩만, 긴 것부터다(짧은 이름을 먼저 바꾸면 성이 남는다)."""

    assert set(names) == set(expected)
    assert len(names) == len(set(names))
    assert [len(name) for name in names] == sorted((len(name) for name in names), reverse=True)


def _assert_no_names(blob: str) -> None:
    for secret in [*SECRETS, *GIVEN, *map(_nfd, NAMES)]:
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
    _assert_names(names)
    assert not {"2015-04-12", "1983-09-02", "부", "형제", "가상 진단명"} & set(names)


def test_unregistered_case_gives_only_extra(case: dict, db) -> None:
    case_id = uuid.UUID(case["id"])

    assert personal_info_service.known_identifiers(db, case_id) == []
    assert personal_info_service.known_identifiers(db, case_id, extra=[f" {ALIAS} ", None, " "]) == [ALIAS]


def test_extra_joins_the_longest_first_order(client: TestClient, counselor_headers, case: dict, db) -> None:
    _put(client, counselor_headers, case["id"], FULL)

    # 별칭이 이름 조각이어도(가람) 한 번만, 긴 이름(한가람)이 앞에 와야 '한' 이 남지 않는다.
    names = personal_info_service.known_identifiers(db, uuid.UUID(case["id"]), extra=["가람", "아동A"])

    _assert_names(names, EXPECTED | {"아동A"})


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
        ("Kim  Ara", ["Kim  Ara", "Kim Ara"]),  # 적은 그대로(두 칸 공백)도 넣는다(Codex #138 H1)
        (_nfd("김민수"), ["김민수", "민수"]),  # 자모로 풀어 적은 이름도 정리한 표기로 넣는다
    ],
)
def test_name_variants(name: str, expected: List[str]) -> None:
    variants = personal_info_service._variants(name)

    # NFC 표기는 기대한 그대로, 그 NFD 표기도 모두 들어 있다.
    assert [variant for variant in variants if unicodedata.is_normalized("NFC", variant)] == expected
    assert set(variants) == set(expected) | {_nfd(variant) for variant in expected}


def test_unreadable_field_is_skipped_with_warning_without_values(
    client: TestClient, counselor_headers, case: dict, db, caplog
) -> None:
    _put(client, counselor_headers, case["id"], FULL)
    _corrupt(db, case["id"])  # 아동 이름 칸만 깨뜨린다

    with caplog.at_level(logging.WARNING):
        names = personal_info_service.known_identifiers(db, uuid.UUID(case["id"]))

    _assert_names(names, {name for name in EXPECTED if unicodedata.normalize("NFC", name) not in (CHILD, "가람")})
    assert f"case_id={case['id']}" in caplog.text and "field=child_name" in caplog.text
    _assert_no_names(caplog.text)


def test_tampered_key_name_is_not_logged(client: TestClient, counselor_headers, case: dict, db, caplog) -> None:
    """저장 값의 키 이름 자리를 고쳐 넣어도 그 글자를 로그에 옮기지 않는다(Codex #138 L2) — 이름 목록 · 실명 조회 둘 다."""

    _put(client, counselor_headers, case["id"], FULL)
    row = db.get(CasePersonalInfo, uuid.UUID(case["id"]))
    _, _, nonce, sealed = row.child_name_enc.split(".")
    row.child_name_enc = ".".join(("v1", CHILD, nonce, sealed))
    db.commit()

    with caplog.at_level(logging.WARNING):
        personal_info_service.known_identifiers(db, uuid.UUID(case["id"]))
        assert client.get(f"/api/v1/cases/{case['id']}/personal-info", headers=counselor_headers).status_code == 500

    assert caplog.text.count("key_id=?") == 2
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
    _assert_names(seen[-1]["known_identifiers"])
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

    contract_adapter.analyze_audio_session_as_contract(stt_result=TRANSCRIPT, known_identifiers=NAMES)
    assert seen[-1]["known_identifiers"] == NAMES

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
        bundle = adapter.analyze(TRANSCRIPT, known_identifiers=NAMES)

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
    "generate_safety_flags": "masked_transcript_text",
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
        # 근거가 있어야 심각도 단계가 돈다(이름을 되돌린 근거를 다시 가려 보낸다 — Codex #138 이 시험 사각지대로 짚음).
        evidence = {"evidence": text, "action": "때림", "instrument": None, "target_body_part": None}
        return {"results": [{"major_type": "신체학대", "subtypes": [{"type": "직접 신체 가해", "evidences": [evidence]}]}]}
    if name == "generate_counseling_records":
        return {"counseling_summary": {}, "counseling_note": {}}
    if name == "generate_record_draft":
        point = {"text": text, "segment_ids": ["seg_002"], "major_type": "신체학대", "subtype": "직접 신체 가해"}
        return {"risk_signal_points": [point], "child_statement_points": [{"text": text, "segment_ids": ["seg_003"]}]}
    if name == "generate_protective_factors":
        return [{"text": text, "segment_ids": ["seg_003"], "category": "보호자 외 지지"}]
    if name == "generate_safety_flags":
        flag = {"code": "S2", "text": text, "certainty": "CLEAR", "segment_ids": ["seg_003"]}
        return {"safety_flags": [flag], "reabuse_factors": [{"code": "R2", "text": text, "segment_ids": ["seg_002"]}]}
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

    # 처음 가리는 단계 · 이름을 되돌린 뒤 다시 가리는 단계(서사 요약 · 심각도 · 다음 상담 확인 사항) · 아동 발화만 가리는 단계 모두.
    assert set(sent) == set(OUTBOUND_STEPS)
    texts = [text for values in sent.values() for text in values]

    assert all(isinstance(text, str) and text for text in texts)
    for text in texts:
        for name in NAMES:
            assert name not in text, (name, text)
    assert "[KNOWN_" in sent["generate_counseling_records"][0]
    assert "[KNOWN_" in sent["generate_narrative_summary_from_masked_text"][0]
    assert "[KNOWN_" in sent["rate_severity_from_text"][0]
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
    _assert_names(fake.calls[0]["known_identifiers"])
    assert _views(db) == views
    _assert_no_names(caplog.text)
    _assert_no_names(_stored(db, SessionFollowupChecklist))


def test_checklist_input_repr_hides_names() -> None:
    payload = FollowupChecklistInput(
        transcript={"segments": []}, abuse_type="physical", session_no=1, session_id="s", known_identifiers=NAMES
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

    # 종결 요약은 회차마다 따로 가린다(closure_summary_llm.mask_case_input → privacy_gateway.review, 2026-11-04).
    original = gw.review

    def review(payload, known_identifiers=None):
        sent["known"] = list(known_identifiers or [])
        return original(payload, known_identifiers=known_identifiers)

    monkeypatch.setattr(gw, "review", review)
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
    _assert_names(closure_llm["known"], EXPECTED | {ALIAS})
    [prompt] = closure_llm["prompts"]
    for name in NAMES:
        assert name not in prompt, name
    assert "[KNOWN_" in prompt
    assert _views(db) == views
    _assert_no_names(caplog.text)


def test_checklist_does_not_decrypt_names_when_nothing_goes_out(
    client: TestClient, counselor_headers, case: dict, session: dict, monkeypatch, db
) -> None:
    """mock 이거나 학대 유형이 없어 rag 를 부르지 않으면 이름을 풀지 않는다(Codex #138 L1)."""

    _put(client, counselor_headers, case["id"], FULL)
    analyzed_session(client, counselor_headers, session["id"])
    calls = []
    monkeypatch.setattr(personal_info_service, "known_identifiers", lambda *args, **kwargs: calls.append(args) or [])

    # mock(외부로 보내지 않음)
    _set_analysis_result(db, session["id"])
    monkeypatch.setattr(settings, "FOLLOWUP_PROVIDER", "mock")
    assert client.post(_url(session["id"]), headers=counselor_headers).status_code == 202
    assert client.get(_url(session["id"]), headers=counselor_headers).json()["data"]["checklist"]["status"] == "COMPLETED"

    # module 이지만 학대 유형이 없어 rag 를 부르지 않음
    _set_analysis_result(db, session["id"], abuse=False)
    fake = _FakeRag()
    set_followup_checklist_adapter_override(_module(monkeypatch, fake))
    assert client.post(_url(session["id"]), headers=counselor_headers).status_code == 202

    assert fake.calls == []
    assert calls == []


# =========================================================
# 가리기 관문(ai/ privacy_gateway) — Codex #138 H1 · H2 · H3 · M1 · M2
# =========================================================


def test_name_written_as_registered_is_masked(gateway) -> None:  # noqa: F811
    gw, _pii, _state = gateway

    # 두 칸 공백으로 등록하고 원문도 같은 표기(H1)
    masked, _ = gw.mask_for_outbound("Kim  Ara 가 왔다", known_identifiers=personal_info_service._variants("Kim  Ara"))
    assert "Ara" not in masked

    # 원문만 자모로 풀어 쓴 표기(NFD)
    text = _nfd("김민수가 왔다")
    masked, _ = gw.mask_for_outbound(text, known_identifiers=personal_info_service._variants("김민수"))
    assert _nfd("민수") not in masked and "[KNOWN_" in masked


def test_label_field_with_a_registered_name_is_masked(gateway) -> None:  # noqa: F811
    gw, _pii, _state = gateway

    # 이름이 '김방임' 이고 발화 한 줄이 '방임' 이면 유형 이름이라고 그냥 넘기지 않는다(H2).
    assert gw.review({"text": "방임"}, known_identifiers=["김방임", "방임"]).payload["text"] == "[KNOWN_01]"
    # 등록 이름이 없으면 유형 이름은 그대로다(예전과 같음).
    assert gw.review({"text": "방임"}, known_identifiers=["한가람"]).payload["text"] == "방임"


def _restored(pii, result, *path) -> str:
    value = result.payload
    for key in path:
        value = value[key]
    return pii.restore_pii(value, result.entity_map)


def test_two_people_stay_two_people_across_fields(gateway) -> None:  # noqa: F811
    gw, pii, state = gateway

    # 등록 이름(H3 재현 그대로): 필드마다 매긴 토큰을 전체 토큰으로 바꿀 때 두 사람이 한 토큰이 되지 않는다.
    payload = {"text": "김바다의 이야기", "case": {"past": "이가람은 김바다와 있다"}}
    result = gw.review(payload, known_identifiers=["이가람", "김바다", "가람", "바다"])
    assert _restored(pii, result, "case", "past") == "이가람은 김바다와 있다"
    assert len(set(VALID_TOKEN.findall(result.payload["case"]["past"]))) == 2

    # 이름 인식만으로도 같다(main 에도 있던 결함).
    state.rule = lambda text: {} if MASKED in text else {**_tags(text, "김민수", "PS"), **_tags(text, "이영희", "PS")}
    payload = {"first": "김민수가 왔다", "second": "이영희와 김민수"}
    result = gw.review(payload)
    assert _restored(pii, result, "second") == "이영희와 김민수"
    assert len(set(VALID_TOKEN.findall(result.payload["second"]))) == 2


@pytest.mark.parametrize(
    ("text", "known", "ner_finds"),
    [
        ("김민수 이민수 왔다", ["김민수", "이민수", "민수"], "민수"),  # 이름 인식이 성 뺀 이름만 잡음
        ("김민수가 왔다", ["김민수", "민수"], "김민"),  # 이름 인식이 끝 글자를 빼고 잡음
    ],
)
def test_name_partly_caught_by_ner_leaves_no_piece(gateway, text: str, known: List[str], ner_finds: str) -> None:  # noqa: F811
    gw, pii, state = gateway
    state.rule = lambda value: {} if MASKED in value else _tags(value, ner_finds, "PS")

    masked, entity_map = gw.mask_for_outbound(text, known_identifiers=known)

    # 성 · 끝 글자가 남지 않는다(M1).
    assert not any(char in masked for char in "김이수민"), masked
    assert pii.restore_pii(masked, entity_map) == text


def test_short_ascii_names_do_not_break_tokens_or_speaker_labels(gateway) -> None:  # noqa: F811
    gw, pii, state = gateway

    # 토큰 글자와 겹치는 등록 이름("KN")이 있어도 막히지 않는다(M2).
    masked, _ = gw.mask_for_outbound("김민수가 왔다", known_identifiers=["김민수", "KN"])
    assert masked == "[KNOWN_01]가 왔다"

    # 화자 표시("CHILD:")는 그대로 두고 본문의 같은 글자만 가린다.
    text = "[seg_001] CHILD: 김민수가 CH 라고 불렀어요"
    masked, entity_map = gw.mask_for_outbound(text, known_identifiers=["김민수", "CH"])
    assert masked == "[seg_001] CHILD: [KNOWN_01]가 [KNOWN_02] 라고 불렀어요"
    assert pii.restore_pii(masked, entity_map) == text

    # 이름 인식이 만든 토큰([PERSON_01]) 안의 글자("ON")를 가리지 않는다.
    state.rule = lambda value: {} if MASKED in value else _tags(value, "박영희", "PS")
    text = "박영희가 김민수를 만났다"
    masked, entity_map = gw.mask_for_outbound(text, known_identifiers=["김민수", "ON"])
    assert masked == "[PERSON_01]가 [KNOWN_01]를 만났다"
    assert pii.restore_pii(masked, entity_map) == text


# =========================================================
# 자른 뒤 가리는 글 — Codex #138 M3
# =========================================================


def _filler(length: int) -> str:
    """'가나 ' 를 되풀이한 length 자(이름 글자 없음)."""

    return ("가나 " * length)[:length]


def test_long_texts_are_cut_between_words_before_masking() -> None:
    from ai.modeling.abuse import case_context as ai_case_context
    from ai.modeling.abuse import closure_summary_llm
    from rag import case_context as rag_case_context

    # 이름이 자르는 자리에 걸치게 둔다. 예전에는 '김바' 가 남아 가리기 목록(김바다 · 바다)에 걸리지 않았다.
    analysis_text = ai_case_context._text(_filler(598) + "김바다와 만났다")
    closure_text = closure_summary_llm._session_block(
        {"number": 1, "date": "", "assessment": {"safety_risks": _filler(2998) + "김바다와 만났다"}, "signals": []}
    )
    rag_text = rag_case_context._shorten(_filler(597) + "김바다와 만났다")

    for cut in (analysis_text, closure_text, rag_text):
        assert "김" not in cut and "가나" in cut

    # Codex 재현 그대로(앞이 빈칸 없는 한 낱말): 잘린 낱말을 통째로 뺀다.
    assert "김" not in ai_case_context._text("가" * 598 + "김바다와 만났다")
    assert "김" not in closure_summary_llm._session_block(
        {"number": 1, "date": "", "assessment": {"safety_risks": "가" * 2998 + "김바다와 만났다"}, "signals": []}
    )
    # rag 는 남는 글이 없으면 빈 글 — build_case_records 가 그 기록을 근거 후보에서 뺀다(재검증 N3).
    assert rag_case_context._shorten("가" * 597 + "김바다와 만났다") == ""
    # 말줄임표까지 넣어 상한을 넘지 않는다(재검증 낮음 — 3,001자).
    assert len(closure_summary_llm._session_block(
        {"number": 1, "date": "", "assessment": {"safety_risks": _filler(3100)}, "signals": []}
    ).split("- 위험요인: ")[1].split("\n")[0]) <= closure_summary_llm.MAX_FIELD_CHARS

    # 이름이 자르는 자리 앞에서 끝나면 그대로 남는다(가리기 목록이 통째로 가린다).
    assert ai_case_context._text(_filler(590) + "김바다와 만났다 " + _filler(20)).count("김바다와") == 1


def test_rag_case_records_hide_names_and_keep_people_apart(gateway) -> None:  # noqa: F811
    """rag 가 실제로 만드는 사례 기록(build_case_records)을 rag 의 가리기(mask_payload)로 가린다 — pipeline._mask_case 와 같은 모양."""

    from rag.case_context import build_case_records
    from rag.privacy import mask_payload, restore

    _gw, _pii, _state = gateway
    transcript = {"segments": [{"segment_id": "seg_001", "speaker": "CHILD", "start_ms": 0, "text": "김바다의 이야기"}]}
    previous = [{"session_no": 1, "session_id": "s1", "summary": "이가람은 김바다와 있다", "check_items": [],
                 "transcript": None, "safety_plan": _filler(597) + "김바다와 만났다"}]
    records = build_case_records(transcript, session_no=2, session_id="s2", previous_sessions=previous)
    payload = {"text": "김바다의 이야기", "case": {record["ref"]: record["text"] for record in records}}

    masked, entity_map = mask_payload(payload, ["이가람", "김바다", "가람", "바다"])
    sent = json.dumps(masked, ensure_ascii=False)

    assert not any(piece in sent for piece in ("이가람", "김바다", "가람", "바다", "김바"))
    summary_ref = next(record["ref"] for record in records if record["source"] == "summary")
    assert restore(masked["case"][summary_ref], entity_map) == "이가람은 김바다와 있다"


# =========================================================
# Codex #138 재검증(a4886f1) — N1 · N2 · N3 · N4, rag pipeline 경로
# =========================================================


def test_registered_name_inside_token_like_user_text_is_masked(gateway) -> None:  # noqa: F811
    """사용자 원문이 토큰처럼 생겨도("[ALICE_01]") 이번 호출이 만든 토큰이 아니면 그 안의 등록 이름을 가린다(N1)."""

    gw, pii, _state = gateway

    text = "메모 [ALICE_01]에게 전달"
    masked, entity_map = gw.mask_for_outbound(text, known_identifiers=["ALICE"])
    assert "ALICE" not in masked
    assert pii.restore_pii(masked, entity_map) == text

    # 다른 꼴 줄 머리 ID 안의 이름도 가린다(화자 코드는 그대로).
    text = "[김민수] CHILD: 안녕하세요"
    masked, entity_map = gw.mask_for_outbound(text, known_identifiers=["김민수"])
    assert "김민수" not in masked and masked.endswith("CHILD: 안녕하세요")
    assert pii.restore_pii(masked, entity_map) == text


def _no_piece(out: str, full_forms, piece: str) -> bool:
    """이름 조각(piece)이 남았으면 이름 전체도 함께 있어야 한다(전체는 뒤에서 목록이 가린다)."""

    return piece not in out or any(form in out for form in full_forms)


def test_names_with_spaces_are_not_cut_in_the_middle() -> None:
    """이름 안 빈칸에서 끊어 성("Kim")만 남지 않는다 — 분석 확인 메모 · 종결 요약 · rag 기록 경계 모두(N2)."""

    from ai.modeling.abuse import case_context as ai_case_context
    from ai.modeling.abuse import closure_summary_llm
    from rag.case_context import build_case_records

    names = personal_info_service._variants("Kim  Ara")
    forms = [name for name in names if " " in name]

    for limit in (600, 3000, 599):
        for shift in range(-8, 3):
            text = ("자료 " * limit)[: limit + shift] + " Kim  Ara와 만났다"

            if limit == 600:
                out = ai_case_context.format_case_context(
                    {"previous_session": {"session_label": "1회차", "assessment": {"safety_risks": text}}},
                    known_identifiers=names,
                )
            elif limit == 3000:
                out = closure_summary_llm.format_case_input(
                    [{"number": 1, "date": "", "assessment": {"safety_risks": text}, "signals": []}],
                    known_identifiers=names,
                )
            else:
                records = build_case_records(
                    None,
                    previous_sessions=[{"session_no": 1, "session_id": "s1", "summary": text}],
                    known_identifiers=names,
                )
                out = " ".join(record["text"] for record in records)

            assert _no_piece(out, forms, "Kim"), (limit, shift)


def test_records_left_empty_after_cutting_are_not_evidence() -> None:
    """잘라서 남은 글이 없는 기록은 근거 후보(case:N)에서 빠지고 번호는 이어진다(N3)."""

    from rag.case_context import build_case_records

    transcript = {"segments": [{"segment_id": "seg_001", "speaker": "CHILD", "start_ms": 0, "text": "오늘 이야기"}]}
    previous = [{"session_no": 1, "session_id": "s1", "summary": "가" * 700 + " 끝", "safety_plan": "안전 계획 확인"}]

    records = build_case_records(transcript, session_no=2, session_id="s2", previous_sessions=previous)

    assert all(record["text"] and record["text"] != "…" for record in records)
    assert [record["source"] for record in records] == ["transcript", "safety_plan"]
    assert [record["ref"] for record in records] == ["case:1", "case:2"]


def test_masking_many_lines_stays_fast(gateway, monkeypatch) -> None:  # noqa: F811
    """이름 · 줄 머리 표식이 되풀이되는 긴 글도 빨리 가린다(N4 — 1,600줄에서 1.2초 걸렸다. 고친 뒤 이 PC 에서 0.03초).

    NER 은 아무것도 찾지 않게 해 등록 이름 가리기 시간만 잰다(가짜 NER 이 쓰는 시간이 CI 마다 달라 흔들리지 않게)."""

    import time

    gw, pii, _state = gateway
    monkeypatch.setattr(pii, "_decode_ner_spans", lambda text: [])
    monkeypatch.setattr(gw, "_decode_ner_spans", lambda text: [])
    names = ["김민수", "이민수", "민수", "한가람", "가람", "박영희"]
    text = "".join(f"[seg_{index:04d}] CHILD: 김민수 상담 관찰.\n" for index in range(1600))

    started = time.perf_counter()
    masked, _ = gw.mask_for_outbound(text, known_identifiers=names)
    elapsed = time.perf_counter() - started

    assert "김민수" not in masked and masked.count("[seg_") == 1600
    assert elapsed < 0.3, elapsed


@pytest.fixture
def real_rag(gateway, monkeypatch):  # noqa: F811 — gateway 는 고정 장치
    """진짜 rag.session → rag.pipeline(_mask_case → mask_payload)을 탄다. 벡터 검색 · LLM 을 쓰는 모듈만 가짜로 두고,
    가린 뒤 분석 단계(_analyze_masked)가 받은 글을 모은다. 시험 뒤에는 새로 불러온 rag · law 모듈을 지운다."""

    fakes = {
        "rag.checklist_builder": {"build_next_session_checklist": lambda *args, **kwargs: {}},
        "rag.evidence_analyzer": {"analyze_checklist_candidates": lambda *args, **kwargs: []},
        "rag.precedents": {"find_similar_precedents": lambda *args, **kwargs: []},
        "rag.retriever": {"search_evidence": lambda *args, **kwargs: []},
        "rag.screen_manual": {"build_screen_references": lambda *args, **kwargs: {}},
        "rag.resource_ranker": {
            "build_reference_materials": lambda *args, **kwargs: [],
            "format_document_reference": lambda *args, **kwargs: "",
        },
    }
    for name, attrs in fakes.items():
        module = types.ModuleType(name)
        for attr, value in attrs.items():
            setattr(module, attr, value)
        monkeypatch.setitem(sys.modules, name, module)

    before = {key for key in sys.modules if key.startswith(("rag.", "law"))}
    session = importlib.import_module("rag.session")
    pipeline = importlib.import_module("rag.pipeline")

    sent = {}

    def analyze_masked(masked_text, abuse_type, **kwargs):
        sent["text"] = masked_text
        sent["records"] = [record["text"] for record in kwargs.get("case_records") or []]
        sent["questions"] = [(item.get("text"), item.get("reason")) for item in kwargs.get("link_questions") or []]
        return {}

    monkeypatch.setattr(pipeline, "_analyze_masked", analyze_masked)

    yield session, sent

    for key in [key for key in sys.modules if key.startswith(("rag.", "law")) and key not in before]:
        sys.modules.pop(key, None)


def test_rag_pipeline_masks_everything_it_sends(real_rag) -> None:
    """rag.session.analyze_reviewed_transcript 에서 가린 뒤 분석 단계로 가는 글 — 이번 회차 발화 · 앞 회차 기록 · 추가 질문
    초안 — 에 등록 이름이 없다(Codex 재검증: rag.pipeline 을 거치지 않아 _mask_case · mask_payload 에 [] 를 줘도 시험이 통과했다)."""

    session, sent = real_rag
    names = personal_info_service._variants("한가람") + personal_info_service._variants("한누리")
    transcript = {"segments": [{"segment_id": "seg_001", "speaker": "CHILD", "start_ms": 0, "text": "한누리 아빠가 가람이를 때렸어요"}]}
    previous = [{"session_no": 1, "session_id": "s1", "summary": "한가람은 한누리와 산다", "check_items": [], "transcript": None}]

    session.analyze_reviewed_transcript(
        transcript,
        "physical",
        known_identifiers=names,
        session_no=2,
        session_id="s2",
        previous_sessions=previous,
        with_questions=False,
        with_manual_references=False,
        link_questions=[{"draft_index": 0, "text": "누리 아빠가 무서웠어?", "reason": "가람이 진술"}],
    )

    outgoing = json.dumps(sent, ensure_ascii=False)
    assert sent["records"] and sent["questions"]
    for name in ("한가람", "한누리", "가람", "누리"):
        assert name not in outgoing, name
    assert "[KNOWN_" in outgoing


def test_rag_does_not_bring_back_records_that_were_cut_away(real_rag) -> None:
    """build_case_records 가 잘라서 모두 뺀 기록([])을 pipeline 이 '기록을 안 줌'(None)으로 보고 원문 전체를 위치 없이
    case:1 로 다시 넣지 않는다(Codex #138 마지막 재검증 R2 — 600자 상한을 넘은 원문이 회차 · 구간 · 시각 없이 근거가 됐다)."""

    session, sent = real_rag
    transcript = {
        "segments": [{"segment_id": "seg_001", "speaker": "CHILD", "start_ms": 1200, "text": "가" * 700}]
    }

    session.analyze_reviewed_transcript(
        transcript,
        "physical",
        known_identifiers=[],
        session_no=2,
        session_id="session-two",
        with_questions=False,
        with_manual_references=False,
    )

    # 이번 회차 발화는 근거자료 분석 입력으로는 그대로 간다(가린 뒤). 사례 기록(근거 후보)으로는 다시 들어가지 않는다.
    assert sent["text"]
    assert sent["records"] == []


def test_rag_without_records_still_uses_the_consultation_as_case_one(real_rag) -> None:
    """기록을 아예 안 주면(None) 예전처럼 상담 문장 하나를 사례 기록으로 쓴다(rag 를 따로 부르는 길 — main.py 등)."""

    from rag import pipeline

    _session, sent = real_rag

    pipeline.analyze_consultation_evidence("아이가 학교에서 맞았다고 했다", "physical", known_identifiers=[], use_law=False)

    assert sent["records"] == ["아이가 학교에서 맞았다고 했다"]


# =========================================================
# 유형별 심각도는 2차 세부유형 분석 바로 뒤에 띄운다(2026-11-04, 데모 '학대 신호 확인이 늦다')
# =========================================================


def test_severity_runs_alongside_the_five_drafts(real_analysis, monkeypatch) -> None:
    """심각도는 2차 결과만 쓰므로 기록 초안 등 다섯 호출과 겹쳐 돈다. 예전처럼 서사 요약 뒤에 부르면
    기록 초안이 기다리는 동안 심각도가 시작되지 않아 started 가 False 로 남는다."""

    infer, sent, _ = real_analysis
    severity_started = threading.Event()
    seen_while_drafting: List[bool] = []

    def severity(*args, **kwargs):
        severity_started.set()
        sent.setdefault("rate_severity_from_text", []).append(kwargs.get("masked_evidence_text"))
        return [{"major_type": "신체학대", "level": 3}]

    def record_draft(*args, **kwargs):
        seen_while_drafting.append(severity_started.wait(5))
        return _step_result("generate_record_draft", kwargs.get("masked_transcript_text"))

    monkeypatch.setattr(infer, "rate_severity_from_text", severity)
    monkeypatch.setattr(infer, "generate_record_draft", record_draft)

    result = infer.analyze_audio_session(stt_result=NAMED_TRANSCRIPT, client=object(), case_id="c1", known_identifiers=[])

    assert seen_while_drafting == [True]
    assert result["severity_ratings"] == [{"major_type": "신체학대", "level": 3}]


def test_severity_failure_still_fails_the_analysis(real_analysis, monkeypatch) -> None:
    """먼저 띄워도 실패는 예전처럼 분석 실패로 올라간다(조용히 빈 심각도로 바뀌지 않는다)."""

    infer, _, _ = real_analysis

    def broken(*args, **kwargs):
        raise RuntimeError("severity down")

    monkeypatch.setattr(infer, "rate_severity_from_text", broken)

    with pytest.raises(RuntimeError, match="severity down"):
        infer.analyze_audio_session(stt_result=NAMED_TRANSCRIPT, client=object(), case_id="c1", known_identifiers=[])


# =========================================================
# 2단계 먼저 넘기기 — on_signals_ready(2026-11-04, 민규 합의)
# =========================================================

STEP2_KEYS = ("risk_utterances", "abuse_signals", "risk_factors", "severity_ratings", "protective_factors")


def test_signals_are_handed_over_before_the_step3_drafts_finish(real_analysis, monkeypatch) -> None:
    """2단계 값(기록 초안 · 보호요인 · 심각도)이 모이면 상담 요약 · 일지 호출이 끝나기 전에 콜백이 불린다.
    넘긴 결과는 계약(AIAnalysisResult)으로 검증되고, 3 · 4단계 칸은 비어 있으며, 마지막 결과의 2단계 칸과 같다."""

    infer, _, _ = real_analysis
    contract_adapter = importlib.import_module(CONTRACT_ADAPTER)
    from app.schemas.contracts import AIAnalysisResult

    handed: List[Any] = []
    called_before_records: List[bool] = []

    def records(*args, **kwargs):
        called_before_records.append(_wait_until(lambda: bool(handed), 5))
        return {"counseling_summary": "상담 요약 문단", "counseling_note": {}}

    def severity(*args, **kwargs):
        return [{"major_type": "신체학대", "level": 3, "reason": "근거", "matched_evidence": "때려요"}]

    monkeypatch.setattr(infer, "generate_counseling_records", records)
    monkeypatch.setattr(infer, "rate_severity_from_text", severity)
    monkeypatch.setattr(contract_adapter, "analyze_audio_session", infer.analyze_audio_session)

    final, _, _ = contract_adapter.analyze_audio_session_as_contract(
        stt_result=NAMED_TRANSCRIPT,
        client=object(),
        known_identifiers=[],
        on_signals_ready=lambda contract, evidence, model: handed.append(contract),
    )

    assert called_before_records == [True] and len(handed) == 1
    partial = AIAnalysisResult.model_validate(handed[0]).model_dump()
    assert partial["severity_ratings"][0]["level"] == 3 and partial["risk_utterances"]
    assert partial["summary"]["overview"] == "" and partial["followup_check_points"] == [] and partial["topic_tags"] is None
    # 요약은 아직 안 만들었을 뿐이라 '만들지 못했습니다' 경고를 넘기지 않는다(민규 #151 리뷰). 마지막 결과는 그대로.
    assert all("상담 요약을 만들지 못했습니다" not in warning for warning in partial["warnings"])
    assert final["summary"]["overview"] == "상담 요약 문단"
    for key in STEP2_KEYS:
        assert handed[0][key] == final[key], key


def test_no_callback_when_the_analysis_fails_first(real_analysis, monkeypatch) -> None:
    """2단계 값이 모이기 전에 실패하면 콜백을 부르지 않고 예전처럼 실패한다."""

    infer, _, _ = real_analysis
    handed: List[Any] = []

    def broken(*args, **kwargs):
        raise RuntimeError("records down")

    def slow_draft(*args, **kwargs):
        _wait_until(lambda: False, 0.3)
        return _step_result("generate_record_draft", kwargs.get("masked_transcript_text"))

    monkeypatch.setattr(infer, "generate_counseling_records", broken)
    monkeypatch.setattr(infer, "generate_record_draft", slow_draft)

    with pytest.raises(RuntimeError, match="records down"):
        infer.analyze_audio_session(
            stt_result=NAMED_TRANSCRIPT, client=object(), known_identifiers=[], on_signals_ready=handed.append
        )

    assert handed == []


def test_failure_after_the_callback_still_fails_the_analysis(real_analysis, monkeypatch) -> None:
    """콜백 뒤 3 · 4단계 호출이 실패하면 분석은 실패로 끝난다(Backend 가 drafts FAILED 로 마감한다)."""

    infer, _, _ = real_analysis
    handed: List[Any] = []

    def broken_checklist(*args, **kwargs):
        _wait_until(lambda: bool(handed), 5)
        raise RuntimeError("checklist down")

    monkeypatch.setattr(infer, "generate_checklist_draft", broken_checklist)

    with pytest.raises(RuntimeError, match="checklist down"):
        infer.analyze_audio_session(
            stt_result=NAMED_TRANSCRIPT, client=object(), known_identifiers=[], on_signals_ready=handed.append
        )

    assert len(handed) == 1


def _wait_until(condition, seconds: float) -> bool:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if condition():
            return True
        time.sleep(0.01)
    return condition()


def test_signals_contract_keeps_other_warnings(real_analysis) -> None:
    """콜백 결과에서 빼는 건 '상담 요약을 만들지 못했습니다' 한 줄뿐이다 — 법령 데이터 경고 같은 2단계 경고는 남는다."""

    contract_adapter = importlib.import_module(CONTRACT_ADAPTER)
    partial = {
        "record_draft": {"risk_signal_points": [], "child_statement_points": []},
        "legal_references_unavailable": True,
        "counseling_summary": None,
    }

    contract, _, _ = contract_adapter._signals_contract(partial, transcript=NAMED_TRANSCRIPT)
    full, _, _ = contract_adapter.to_ai_output_contract(partial, transcript=NAMED_TRANSCRIPT)

    assert any("상담 요약을 만들지 못했습니다" in warning for warning in full["warnings"])
    assert contract["warnings"] == [w for w in full["warnings"] if "상담 요약을 만들지 못했습니다" not in w]
    assert contract["warnings"]


# =========================================================
# 안전 플래그 · 재학대 요인(safety_flag_llm, 2026-11-05) — 2단계 값이라 콜백에 실리고, 계약에서 null 과 [] 를 구분한다
# =========================================================


def test_safety_flags_ride_with_the_signals_callback(real_analysis) -> None:
    """안전 플래그는 2단계 값이라 콜백(첫 저장)에 실리고, 마지막 결과와 같다. 이름은 가려서 보내고 되돌린다."""

    infer, sent, _ = real_analysis
    handed: List[Dict[str, Any]] = []

    final = infer.analyze_audio_session(stt_result=NAMED_TRANSCRIPT, client=object(), on_signals_ready=handed.append)

    [partial] = handed
    assert partial["safety_flags"] and partial["safety_flags"] == final["safety_flags"]
    assert partial["reabuse_factors"] == final["reabuse_factors"]
    assert sent["generate_safety_flags"]


def _safety_contract(result):
    contract_adapter = importlib.import_module(CONTRACT_ADAPTER)
    partial = {"record_draft": {"risk_signal_points": [], "child_statement_points": []}, **result}
    contract, _, _ = contract_adapter.to_ai_output_contract(partial, transcript=NAMED_TRANSCRIPT)
    return contract, contract_adapter.SAFETY_FLAGS_UNAVAILABLE_WARNING


def test_safety_contract_moves_candidates(real_analysis) -> None:
    flag = {"code": "S2", "text": "혼난대요", "certainty": "CLEAR", "segment_ids": ["seg_001"]}
    contract, warning = _safety_contract({"safety_flags": [flag], "reabuse_factors": []})

    assert contract["safety_flags"] == [flag]
    assert contract["reabuse_factors"] == []
    assert warning not in contract["warnings"]


def test_safety_contract_failed_module_is_null_with_warning(real_analysis) -> None:
    contract, warning = _safety_contract({"safety_flags": None, "reabuse_factors": None})

    assert contract["safety_flags"] is None and contract["reabuse_factors"] is None
    assert warning in contract["warnings"]


def test_safety_contract_without_the_keys_is_null_without_warning(real_analysis) -> None:
    contract, warning = _safety_contract({})

    assert contract["safety_flags"] is None
    assert warning not in contract["warnings"]
