# 다음 상담 체크리스트 테스트 (app/services/followup_checklist_service.py, API_CONTRACT 19절, specs followup-rag-checklist).
#
# 기본 꺼짐 · 분석 저장 뒤 만들기 · 행 차지(동시 POST · 늦은 결과) · 동시 실행 상한 · 멈춤 판정 · rag 결과 정리
# (모양 · 근거 없음 · 판정 표현 · 공식 근거) · 실패 코드 · 운영 잠금 · 권한 · 로그를 본다.
# 닫힌 #117 교차검증(R2 · R3 · R4 · R5 · R7 · R8 · C1 · C3 · C4)이 다시 생기지 않는지가 중심이다. rag · OpenAI 는 부르지 않는다.
# 데이터는 모두 가상이다.

import logging
import threading
import time
import types
import uuid
from datetime import timedelta
from typing import Any, Dict, List, Optional

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select, update

from app.adapters.followup_checklist_adapter import (
    FOLLOWUP_MESSAGES,
    NOTICE_MOCK,
    NOTICE_NO_ABUSE_TYPE,
    FollowupChecklistError,
    FollowupChecklistInput,
    ModuleFollowupChecklistAdapter,
    empty_result,
    set_followup_checklist_adapter_override,
)
from app.core.config import Settings, settings
from app.core.enums import AnalysisStatus, AuditAction, SessionStatus
from app.core.errors import ErrorCode
from app.models.analysis import AIAnalysis
from app.models.audit_log import AuditLog
from app.models.followup_checklist import SessionFollowupChecklist
from app.models.session import ConsultationSession
from app.services import followup_checklist_service as service
from tests.test_analysis import _run_analysis, analyzed_session, confirmed_session

DRAFT_0 = "등이랑 팔이 아팠던 건 지금은 어때?"
DRAFT_1 = "무서울 때 누구한테 이야기할 수 있어?"
SECRET_TEXT = "가상 민감 문장 홍길동"


def _url(session_id: str) -> str:
    return f"/api/v1/sessions/{session_id}/followup-checklist"


def _rows(db) -> List[SessionFollowupChecklist]:
    db.expire_all()
    return list(db.scalars(select(SessionFollowupChecklist)).all())


def _latest_analysis(db, session_id: str) -> AIAnalysis:
    db.expire_all()
    return db.scalar(
        select(AIAnalysis)
        .where(AIAnalysis.session_id == uuid.UUID(session_id))
        .order_by(AIAnalysis.created_at.desc())
        .limit(1)
    )


def _set_analysis_result(db, session_id: str, *, abuse: bool = True, drafts: Optional[List[str]] = None) -> AIAnalysis:
    """최신 분석 결과에 학대 유형 신호 · 추가 질문 초안을 넣는다(mock 분석은 둘 다 비어 있다)."""

    analysis = _latest_analysis(db, session_id)
    result = dict(analysis.result or {})
    result["abuse_signals"] = (
        [{"abuse_type": "PHYSICAL", "detected": True, "confidence": 0.8, "evidence": []}] if abuse else []
    )
    result["followup_questions"] = [
        {"text": text, "kind": "OPEN", "segment_ids": ["seg_001"], "reason": "가상 이유"} for text in (drafts or [])
    ]
    analysis.result = result
    db.commit()

    return analysis


def _session_row(db, session_id: str) -> ConsultationSession:
    return db.get(ConsultationSession, uuid.UUID(session_id))


@pytest.fixture
def analyzed(client: TestClient, counselor_headers, session: dict) -> dict:
    """mock 분석까지 끝난 회차. 기본(FOLLOWUP_PROVIDER=off)이라 체크리스트 행은 없다."""

    analyzed_session(client, counselor_headers, session["id"])

    return session


@pytest.fixture
def mock_on(monkeypatch):
    monkeypatch.setattr(settings, "FOLLOWUP_PROVIDER", "mock")


# =========================================================
# 기본 꺼짐 (#117 R3)
# =========================================================

def test_default_off_creates_nothing_and_post_is_503(client: TestClient, counselor_headers, analyzed: dict, db) -> None:
    assert settings.FOLLOWUP_PROVIDER == "off"
    assert _rows(db) == []

    response = client.get(_url(analyzed["id"]), headers=counselor_headers)

    assert response.status_code == 200
    assert response.json()["data"] == {"enabled": False, "checklist": None}

    posted = client.post(_url(analyzed["id"]), headers=counselor_headers)

    assert posted.status_code == 503
    assert posted.json()["error"]["code"] == "FOLLOWUP_DISABLED"
    assert _rows(db) == []


def test_production_module_requires_explicit_allow() -> None:
    with pytest.raises(ValueError, match="FOLLOWUP_ALLOW_IN_PRODUCTION"):
        Settings(_env_file=None, ENV="production", FOLLOWUP_PROVIDER="module")

    allowed = Settings(_env_file=None, ENV="production", FOLLOWUP_PROVIDER="module", FOLLOWUP_ALLOW_IN_PRODUCTION=True)

    assert allowed.FOLLOWUP_PROVIDER == "module"
    assert Settings(_env_file=None, ENV="production", FOLLOWUP_PROVIDER="mock").FOLLOWUP_PROVIDER == "mock"
    assert Settings(_env_file=None).FOLLOWUP_PROVIDER == "off"


# =========================================================
# 분석 저장 뒤 만들기
# =========================================================

def test_mock_runs_after_analysis_and_get_shows_result(
    client: TestClient, counselor_headers, session: dict, mock_on, db
) -> None:
    analyzed_session(client, counselor_headers, session["id"])

    rows = _rows(db)

    assert len(rows) == 1
    assert rows[0].status == AnalysisStatus.COMPLETED
    assert rows[0].attempt == 1
    assert rows[0].analysis_id == _latest_analysis(db, session["id"]).id

    data = client.get(_url(session["id"]), headers=counselor_headers).json()["data"]

    assert data["enabled"] is True
    checklist = data["checklist"]
    assert checklist["status"] == "COMPLETED"
    assert checklist["provider"] == "mock"
    assert checklist["error"] is None
    result = checklist["result"]
    assert result["notice"] == NOTICE_MOCK
    assert [item["text"] for item in result["check_items"]] == ["(예시) 이 발화 이후 상황이 어떻게 되었는지"]
    assert result["check_items"][0]["basis"][0]["type"] == "case"
    assert result["check_items"][0]["basis"][0]["segment_id"]
    assert result["question_evidence"] == []  # mock 분석에는 추가 질문 초안이 없다


def test_failed_analysis_does_not_create_checklist(client: TestClient, counselor_headers, session: dict, mock_on, db) -> None:
    from app.adapters.ai_adapter import AIError, set_ai_adapter_override

    class _Failing:
        name = "failing"

        def analyze(self, payload):
            raise AIError("가상 실패", ErrorCode.AI_FAILED)

    confirmed_session(client, counselor_headers, session["id"])
    set_ai_adapter_override(_Failing())

    assert _run_analysis(client, counselor_headers, session["id"]).status_code == 202
    assert _session_row(db, session["id"]).status == SessionStatus.AI_FAILED
    assert _rows(db) == []


def test_checklist_errors_never_reach_the_analysis_job(
    client: TestClient, counselor_headers, session: dict, mock_on, monkeypatch, db
) -> None:
    # #117 C3: DB 세션 만들기에서 예외가 나도 분석 작업 밖으로 나가지 않고 분석 · 회차 상태는 그대로다.
    def broken_session_local():
        raise RuntimeError("가상 DB 오류")

    monkeypatch.setattr(service, "SessionLocal", broken_session_local)

    analyzed_session(client, counselor_headers, session["id"])

    assert _session_row(db, session["id"]).status == SessionStatus.AI_REVIEW_REQUIRED
    assert _latest_analysis(db, session["id"]).status == AnalysisStatus.COMPLETED
    assert _rows(db) == []


def test_process_checklist_swallows_errors_even_when_marking_failed_fails(
    client: TestClient, counselor_headers, analyzed: dict, mock_on, monkeypatch, db
) -> None:
    session_row = _session_row(db, analyzed["id"])
    attempt = service._claim(db, session_row, _latest_analysis(db, analyzed["id"]), "mock", supersede=False)
    row = _rows(db)[0]

    def broken(*args, **kwargs):
        raise RuntimeError("가상 오류")

    monkeypatch.setattr(service, "build_input", broken)
    monkeypatch.setattr(service, "_finish", broken)

    service.process_checklist(row.id, attempt)  # 예외 없이 끝난다

    assert _rows(db)[0].status == AnalysisStatus.PROCESSING  # 마감도 못 했으면 멈춤 판정이 나중에 마감한다


# =========================================================
# 행 차지 · 늦은 결과 · 멈춤 판정 (#117 R5)
# =========================================================

def test_post_while_processing_returns_same_row_without_new_work(
    client: TestClient, counselor_headers, analyzed: dict, db
) -> None:
    calls: List[Any] = []

    class _Counting:
        name = "counting"

        def build(self, payload):
            calls.append(payload)
            return empty_result()

    set_followup_checklist_adapter_override(_Counting())
    attempt = service._claim(
        db, _session_row(db, analyzed["id"]), _latest_analysis(db, analyzed["id"]), "counting", supersede=False
    )

    response = client.post(_url(analyzed["id"]), headers=counselor_headers)

    assert response.status_code == 202
    assert response.json()["data"]["status"] == "PROCESSING"
    assert response.json()["data"]["attempt"] == attempt == 1
    assert calls == []
    assert len(_rows(db)) == 1
    # 새 작업을 띄우지 않았으므로 감사 기록도 남기지 않는다.
    assert db.scalar(select(func.count()).select_from(AuditLog).where(
        AuditLog.action == AuditAction.FOLLOWUP_CHECKLIST_REQUESTED
    )) == 0


def test_claim_is_compare_and_set_so_a_racing_request_does_not_start_work(
    client: TestClient, counselor_headers, analyzed: dict, mock_on, monkeypatch, db
) -> None:
    session_row = _session_row(db, analyzed["id"])
    analysis = _latest_analysis(db, analyzed["id"])

    assert service._claim(db, session_row, analysis, "mock", supersede=False) == 1
    row = _rows(db)[0]
    assert service._finish(db, row.id, 1, status=AnalysisStatus.COMPLETED, result=empty_result())

    # 두 요청이 같은 행(attempt 1, COMPLETED)을 읽었다. 한쪽이 먼저 차지했다.
    stale_view = types.SimpleNamespace(id=row.id, attempt=1, status=AnalysisStatus.COMPLETED, started_at=row.started_at)
    assert service._claim(db, session_row, analysis, "mock", supersede=False) == 2

    # 늦은 쪽은 읽어 둔 attempt(1)로 UPDATE 하므로 0행 — 작업을 띄우지 않는다.
    monkeypatch.setattr(service, "get_row", lambda db_, session_id: stale_view)
    assert service._claim(db, session_row, analysis, "mock", supersede=False) is None

    rows = _rows(db)
    assert len(rows) == 1 and rows[0].attempt == 2 and rows[0].status == AnalysisStatus.PROCESSING


def test_late_result_of_previous_attempt_is_discarded(
    client: TestClient, counselor_headers, analyzed: dict, mock_on, db
) -> None:
    session_row = _session_row(db, analyzed["id"])
    analysis = _latest_analysis(db, analyzed["id"])

    first = service._claim(db, session_row, analysis, "mock", supersede=False)
    # 재분석이 저장되면 처리 중이어도 새 attempt 가 이긴다.
    second = service._claim(db, session_row, analysis, "mock", supersede=True)
    row = _rows(db)[0]

    assert (first, second) == (1, 2)
    assert service._finish(db, row.id, first, status=AnalysisStatus.COMPLETED, result=empty_result("앞 결과")) is False

    row = _rows(db)[0]
    assert row.status == AnalysisStatus.PROCESSING and row.attempt == 2 and row.result is None


def test_stale_processing_row_is_failed_on_get_and_can_be_retried(
    client: TestClient, counselor_headers, analyzed: dict, mock_on, db
) -> None:
    session_row = _session_row(db, analyzed["id"])
    service._claim(db, session_row, _latest_analysis(db, analyzed["id"]), "mock", supersede=False)
    old = service._now() - timedelta(seconds=settings.FOLLOWUP_TIMEOUT_SECONDS + service.STALE_GRACE_SECONDS + 5)
    db.execute(update(SessionFollowupChecklist).values(started_at=old))
    db.commit()

    checklist = client.get(_url(analyzed["id"]), headers=counselor_headers).json()["data"]["checklist"]

    assert checklist["status"] == "FAILED"
    assert checklist["error"] == {"code": "AI_TIMEOUT", "message": FOLLOWUP_MESSAGES[ErrorCode.AI_TIMEOUT]}
    assert checklist["result"] is None

    retried = client.post(_url(analyzed["id"]), headers=counselor_headers)

    assert retried.status_code == 202
    assert retried.json()["data"]["attempt"] == 2
    assert client.get(_url(analyzed["id"]), headers=counselor_headers).json()["data"]["checklist"]["status"] == "COMPLETED"


def test_late_callback_of_an_older_analysis_does_not_overwrite_the_newer_checklist(
    client: TestClient, counselor_headers, session: dict, mock_on, monkeypatch, db
) -> None:
    # #125 교차검증 R1: 분석 A 저장 → A 체크리스트 시작이 늦어짐 → 재분석 B 저장 · B 체크리스트 완료 → 이제야 A 콜백.
    # A 는 여전히 COMPLETED 라 예전에는 supersede 로 새 attempt 를 얻어 B 결과를 A 로 덮었다.
    delayed: List[Any] = []
    real = service.generate_after_analysis
    monkeypatch.setattr(service, "generate_after_analysis", lambda session_id, analysis_id: delayed.append((session_id, analysis_id)))

    analyzed_session(client, counselor_headers, session["id"])
    older = _latest_analysis(db, session["id"])
    assert delayed == [(older.session_id, older.id)]
    assert _rows(db) == []

    monkeypatch.setattr(service, "generate_after_analysis", real)
    assert _run_analysis(client, counselor_headers, session["id"]).status_code == 202
    newer = _latest_analysis(db, session["id"])
    row = _rows(db)[0]
    assert newer.id != older.id
    assert (row.analysis_id, row.status) == (newer.id, AnalysisStatus.COMPLETED)
    attempt = row.attempt

    real(*delayed[0])  # A 의 늦은 콜백

    row = _rows(db)[0]
    assert (row.analysis_id, row.status, row.attempt) == (newer.id, AnalysisStatus.COMPLETED, attempt)
    # 예전 분석으로는 POST 경로도 차지하지 않는다.
    assert service._claim(db, _session_row(db, session["id"]), older, "mock", supersede=False) is None
    assert service._claim(db, _session_row(db, session["id"]), older, "mock", supersede=True) is None
    assert _rows(db)[0].attempt == attempt


def test_older_analysis_cannot_create_the_first_row_either(
    client: TestClient, counselor_headers, session: dict, mock_on, monkeypatch, db
) -> None:
    # 행이 아직 없을 때(INSERT 경로)도 같다. B 는 아직 체크리스트를 만들기 전이다.
    monkeypatch.setattr(service, "generate_after_analysis", lambda session_id, analysis_id: None)
    analyzed_session(client, counselor_headers, session["id"])
    older = _latest_analysis(db, session["id"])
    assert _run_analysis(client, counselor_headers, session["id"]).status_code == 202
    newer = _latest_analysis(db, session["id"])
    assert newer.id != older.id

    assert service._claim(db, _session_row(db, session["id"]), older, "mock", supersede=True) is None
    assert _rows(db) == []
    assert service._claim(db, _session_row(db, session["id"]), newer, "mock", supersede=True) == 1


def _add_analysis(session_id, after: AIAnalysis, status: AnalysisStatus) -> uuid.UUID:
    """재분석 B 가 들어온 것처럼 분석 행을 더한다(다른 DB 세션에서 커밋 — 동시에 들어온 요청 흉내)."""

    from app.core.database import SessionLocal

    other = SessionLocal()
    try:
        row = AIAnalysis(
            session_id=after.session_id,
            transcript_id=after.transcript_id,
            transcript_version=after.transcript_version,
            status=status,
            result=dict(after.result or {}) if status == AnalysisStatus.COMPLETED else None,
            created_at=after.created_at + timedelta(seconds=1),
        )
        other.add(row)
        other.commit()
        return row.id
    finally:
        other.close()


@pytest.mark.parametrize(
    ("new_status", "expected"),
    [(AnalysisStatus.PROCESSING, 409), (AnalysisStatus.COMPLETED, 202)],
)
def test_post_that_loses_to_a_new_analysis_is_not_a_server_error(
    client: TestClient, counselor_headers, analyzed: dict, mock_on, monkeypatch, db, new_status, expected
) -> None:
    # #125 재검증 N1: 행이 아직 없는 회차에서 POST 가 분석 A 를 읽은 직후 재분석 B 가 들어오면 _claim 이 A 를 거절하는데,
    # 호출자가 없는 행을 refresh 해 500 이 났다. B 가 처리 중이면 409, 이미 끝났으면 B 로 만든다.
    older = _latest_analysis(db, analyzed["id"])
    real_latest = service._latest_analysis
    added: List[uuid.UUID] = []

    def latest_then_new_analysis(db_, session_id):
        found = real_latest(db_, session_id)
        if not added:
            added.append(_add_analysis(session_id, older, new_status))
        return found

    monkeypatch.setattr(service, "_latest_analysis", latest_then_new_analysis)

    response = client.post(_url(analyzed["id"]), headers=counselor_headers)

    assert response.status_code == expected, response.text
    rows = _rows(db)
    if expected == 409:
        assert response.json()["error"]["code"] == "INVALID_SESSION_STATE"
        assert rows == []
    else:
        assert [row.analysis_id for row in rows] == added


def test_first_insert_is_refused_when_a_new_analysis_arrives_after_the_precheck(
    client: TestClient, counselor_headers, analyzed: dict, mock_on, monkeypatch, db
) -> None:
    # #125 재검증 N2: 미리 확인(새 분석 없음)을 지난 뒤 INSERT 직전에 B 가 들어오면, 조건 없는 INSERT 가 A 로 첫 행을 만들었다.
    older = _latest_analysis(db, analyzed["id"])
    real_get_row = service.get_row
    added: List[uuid.UUID] = []

    def get_row_then_new_analysis(db_, session_id):
        row = real_get_row(db_, session_id)
        if row is None and not added:
            added.append(_add_analysis(session_id, older, AnalysisStatus.PROCESSING))
        return row

    monkeypatch.setattr(service, "get_row", get_row_then_new_analysis)

    assert service._claim(db, _session_row(db, analyzed["id"]), older, "mock", supersede=True) is None
    assert added and _rows(db) == []


# =========================================================
# 동시 실행 상한 (#117 R4)
# =========================================================

def test_timed_out_work_keeps_its_slot_so_real_work_never_exceeds_the_limit(monkeypatch) -> None:
    monkeypatch.setattr(settings, "FOLLOWUP_TIMEOUT_SECONDS", 0.2)
    monkeypatch.setattr(settings, "FOLLOWUP_MAX_CONCURRENCY", 1)
    service.reset_limits()

    class _Blocking:
        name = "blocking"

        def __init__(self) -> None:
            self.release = threading.Event()
            self.lock = threading.Lock()
            self.running = 0
            self.max_running = 0
            self.calls = 0

        def build(self, payload):
            with self.lock:
                self.calls += 1
                self.running += 1
                self.max_running = max(self.max_running, self.running)
            try:
                self.release.wait(10)
                return empty_result()
            finally:
                with self.lock:
                    self.running -= 1

    adapter = _Blocking()
    payload = FollowupChecklistInput(transcript={"segments": []}, abuse_type="physical", session_no=1, session_id="s")

    try:
        causes = []
        for _ in range(3):
            with pytest.raises(FollowupChecklistError) as caught:
                service._run_adapter(adapter, payload)
            assert caught.value.code == ErrorCode.AI_TIMEOUT
            causes.append(caught.value.cause_name)

        assert causes == ["OperationTimeout", "NoSlot", "NoSlot"]
        assert adapter.calls == 1 and adapter.max_running == 1
    finally:
        adapter.release.set()

    # 시간을 넘긴 작업이 실제로 끝나면 자리를 돌려준다.
    deadline = time.monotonic() + 5
    while not service._limits.slots.acquire(timeout=0.05):
        assert time.monotonic() < deadline
    service._limits.slots.release()
    service.reset_limits()


# =========================================================
# rag 결과 정리 (module) — #117 R7 · R8 · C1 · C4
# =========================================================

def _case_basis(**extra) -> Dict[str, Any]:
    basis = {"type": "case", "ref": "case:1", "label": "1회차 00:03", "session_no": 1, "session_id": "s1",
             "segment_id": "seg_001", "start_ms": 3000, "excerpt": "등이랑 팔이 아파요."}
    basis.update(extra)
    return basis


def _official_basis(**extra) -> Dict[str, Any]:
    basis = {"type": "checklist", "ref": "checklist:1", "label": "체크리스트 p.3", "excerpt": "상처의 치료 여부"}
    basis.update(extra)
    return basis


def _check_item(text: str = "치료를 받았는지", **extra) -> Dict[str, Any]:
    item = {"id": "check:1", "item": text, "kind": "info_gap", "priority": "high", "reason": "치료 여부 미확인",
            "case_refs": ["case:1"], "knowledge_refs": ["checklist:1"], "basis": [_case_basis(), _official_basis()]}
    item.update(extra)
    return item


def _rag_output(check_items=None, question_evidence=None, validation=None, **rag_extra) -> Dict[str, Any]:
    return {
        "child_segment_ids": ["seg_001"],
        "speaker_check_items": [],
        "rag_analysis": {
            "next_session_checklist": {
                "check_items": check_items if check_items is not None else [_check_item()],
                "items": [],
                "question_evidence": question_evidence if question_evidence is not None else [],
                "validation": validation if validation is not None else {},
            },
            **rag_extra,
        },
        "manual_screen_references": None,
        "privacy_blocked": False,
        "privacy_reasons": [],
    }


def _payload(abuse_type: Optional[str] = "physical", drafts: Optional[List[str]] = None) -> FollowupChecklistInput:
    return FollowupChecklistInput(
        transcript={"segments": [{"segment_id": "seg_001", "speaker": "CHILD", "start_ms": 3000, "text": "등이랑 팔이 아파요."}]},
        abuse_type=abuse_type,
        session_no=1,
        session_id="s1",
        drafts=[{"draft_index": index, "text": text, "reason": "가상 이유"} for index, text in enumerate(drafts or [])],
    )


class _FakeRag:
    def __init__(self, output: Any = None, error: Optional[Exception] = None) -> None:
        self.output = output if output is not None else _rag_output()
        self.error = error
        self.calls: List[Dict[str, Any]] = []

    def __call__(self, transcript, abuse_type, **kwargs):
        self.calls.append({"transcript": transcript, "abuse_type": abuse_type, **kwargs})
        if self.error is not None:
            raise self.error
        return self.output


def _module(monkeypatch, fake: _FakeRag) -> ModuleFollowupChecklistAdapter:
    monkeypatch.setattr(ModuleFollowupChecklistAdapter, "_load", lambda self: fake)
    return ModuleFollowupChecklistAdapter()


def test_module_without_abuse_type_sends_nothing(monkeypatch) -> None:
    fake = _FakeRag()

    result = _module(monkeypatch, fake).build(_payload(abuse_type=None))

    assert fake.calls == []
    assert result["check_items"] == [] and result["notice"] == NOTICE_NO_ABUSE_TYPE


def test_module_asks_rag_for_check_items_and_question_evidence_only(monkeypatch) -> None:
    fake = _FakeRag()

    _module(monkeypatch, fake).build(_payload(drafts=[DRAFT_0, DRAFT_1]))

    call = fake.calls[0]
    assert call["with_questions"] is False
    assert call["with_manual_references"] is False
    assert call["known_identifiers"] == []
    assert call["child_app_responses"] == []
    assert call["link_questions"] == [
        {"draft_index": 0, "text": DRAFT_0, "reason": "가상 이유"},
        {"draft_index": 1, "text": DRAFT_1, "reason": "가상 이유"},
    ]


def test_module_cleans_items_and_keeps_only_official_question_evidence(monkeypatch) -> None:
    fake = _FakeRag(
        _rag_output(
            check_items=[
                _check_item(),
                _check_item("학대 확정 사례라 보호 조치가 됐는지"),  # 판정 표현(C1)
                _check_item("근거가 없는 항목", basis=[]),  # 근거 없음(R7)
                _check_item("모양이 틀린 항목", kind="unknown"),  # 모양 틀림
                "문자열 항목",
                _check_item("이유에 판정", reason="AI 판정 결과"),
                _check_item("깨진 근거만", basis=[{"label": "type 없음"}]),
            ],
            question_evidence=[
                {"draft_index": 0, "knowledge_refs": ["manual:1"],
                 "basis": [_official_basis(type="manual", ref="manual:1", label="업무 매뉴얼 p.125", why="면담 지침")]},
                # 사례 근거만 → 공식 근거 아님(빠진다)
                {"draft_index": 1, "basis": [_case_basis(why="사례")]},
                # 넘기지 않은 초안 번호
                {"draft_index": 5, "basis": [_official_basis(why="체크리스트")]},
                # 같은 초안 두 번
                {"draft_index": 0, "basis": [_official_basis(why="체크리스트")]},
                # 이유 없음 · 판정 이유
                {"draft_index": 1, "basis": [_official_basis(why=""), _official_basis(why="학대로 판단된 사안")]},
            ],
            validation={"official_unlinked": 2, "official_review_rejected": 1, "official_review_error": None},
            case_context_warning="이전 회차 기록 차단",
        )
    )

    result = _module(monkeypatch, fake).build(_payload(drafts=[DRAFT_0, DRAFT_1]))

    assert [item["text"] for item in result["check_items"]] == ["치료를 받았는지"]
    assert [basis["type"] for basis in result["check_items"][0]["basis"]] == ["case", "checklist"]
    assert result["question_evidence"] == [
        {
            "draft_index": 0,
            "text": DRAFT_0,  # rag 가 돌려준 문장이 아니라 넘긴 초안 그대로
            "basis": [
                {"type": "manual", "ref": "manual:1", "label": "업무 매뉴얼 p.125", "session_no": None, "session_id": None,
                 "segment_id": None, "start_ms": None, "source": None, "page": None, "url": None,
                 "excerpt": "상처의 치료 여부", "why": "면담 지침"}
            ],
        }
    ]
    assert result["dropped"] == {
        "official_unlinked": 2,
        "official_review_rejected": 1,
        "judgment": 2,
        "no_basis": 4,
        "invalid": 4,
    }
    assert "이번 회차 아동 발화만" in result["notice"]
    # 저장될 결과 전체에서 공식 근거는 rag 가 검토 통과로 돌려준 것 말고는 없다.
    officials = [basis for item in result["check_items"] for basis in item["basis"] if basis["type"] != "case"]
    officials += [basis for entry in result["question_evidence"] for basis in entry["basis"]]
    assert [(basis["ref"], basis.get("why")) for basis in officials] == [("checklist:1", None), ("manual:1", "면담 지침")]


@pytest.mark.parametrize(
    ("validation", "expected"),
    [
        ({"official_review_error": "공식 근거 검토 실패: RuntimeError"}, "공식 근거 검토를 하지 못해"),
        ({"question_link_error": "질문 공식 근거 연결 실패: RuntimeError"}, "추가 질문에 공식 근거를 잇지 못했습니다"),
        ({"official_skipped": "공식 근거 후보가 없습니다."}, "찾은 공식 근거가 없어"),
    ],
)
def test_module_turns_validation_reasons_into_fixed_notices(monkeypatch, validation, expected) -> None:
    result = _module(monkeypatch, _FakeRag(_rag_output(validation=validation))).build(_payload())

    assert expected in result["notice"]
    assert "RuntimeError" not in result["notice"]


@pytest.mark.parametrize(
    ("output", "code"),
    [
        ("문자열", ErrorCode.AI_INVALID_OUTPUT),
        ({"rag_analysis": "문자열"}, ErrorCode.AI_INVALID_OUTPUT),  # C4
        ({"rag_analysis": {"next_session_checklist": "문자열"}}, ErrorCode.AI_INVALID_OUTPUT),
        ({"rag_analysis": {"next_session_checklist": {"check_items": "x", "validation": {}}}}, ErrorCode.AI_INVALID_OUTPUT),
        ({"rag_analysis": {"error": "x", "privacy_blocked": True}}, ErrorCode.AI_PRIVACY_BLOCKED),
        ({"rag_analysis": None, "privacy_blocked": True}, ErrorCode.AI_PRIVACY_BLOCKED),  # R8
        ({"rag_analysis": {"error": "RAG 근거자료 분석 중 오류: KeyError"}}, ErrorCode.AI_FAILED),
        ({"rag_analysis": {"next_session_checklist": {"check_items": [], "validation": {"check_error": "x"}}}},
         ErrorCode.AI_FAILED),
    ],
)
def test_module_maps_bad_or_blocked_output_to_fixed_codes(monkeypatch, output, code) -> None:
    with pytest.raises(FollowupChecklistError) as caught:
        _module(monkeypatch, _FakeRag(output)).build(_payload())

    assert caught.value.code == code
    assert caught.value.message == FOLLOWUP_MESSAGES[code]


def test_module_maps_exceptions_by_type_only(monkeypatch) -> None:
    class RagPrivacyBlocked(Exception):
        pass

    for error, code in (
        (RagPrivacyBlocked(SECRET_TEXT), ErrorCode.AI_PRIVACY_BLOCKED),
        (TimeoutError(SECRET_TEXT), ErrorCode.AI_TIMEOUT),
        (RuntimeError(SECRET_TEXT), ErrorCode.AI_FAILED),
    ):
        with pytest.raises(FollowupChecklistError) as caught:
            _module(monkeypatch, _FakeRag(error=error)).build(_payload())
        assert caught.value.code == code
        assert SECRET_TEXT not in caught.value.message


def test_module_without_child_speech_completes_empty(monkeypatch) -> None:
    output = _rag_output()
    output["rag_analysis"] = None

    result = _module(monkeypatch, _FakeRag(output)).build(_payload())

    assert result["check_items"] == [] and "아동 발화가 없어" in result["notice"]


# =========================================================
# 전체 흐름 (POST → 백그라운드 → GET)
# =========================================================

def test_post_runs_module_with_drafts_and_get_shows_question_evidence(
    client: TestClient, counselor_headers, counselor_id, analyzed: dict, monkeypatch, db
) -> None:
    analysis = _set_analysis_result(db, analyzed["id"], drafts=[DRAFT_0, DRAFT_1])
    fake = _FakeRag(
        _rag_output(
            question_evidence=[
                {"draft_index": 1, "basis": [_official_basis(type="manual", ref="manual:1", label="업무 매뉴얼", why="면담 지침")]}
            ]
        )
    )
    set_followup_checklist_adapter_override(_module(monkeypatch, fake))

    posted = client.post(_url(analyzed["id"]), headers=counselor_headers)

    assert posted.status_code == 202, posted.text
    assert posted.json()["data"]["attempt"] == 1
    assert fake.calls[0]["abuse_type"] == "physical"
    assert [item["text"] for item in fake.calls[0]["link_questions"]] == [DRAFT_0, DRAFT_1]
    assert fake.calls[0]["session_no"] == _session_row(db, analyzed["id"]).session_number

    checklist = client.get(_url(analyzed["id"]), headers=counselor_headers).json()["data"]["checklist"]

    assert checklist["status"] == "COMPLETED"
    assert checklist["analysis_id"] == str(analysis.id)
    assert checklist["result"]["question_evidence"][0]["draft_index"] == 1
    assert checklist["result"]["question_evidence"][0]["text"] == DRAFT_1

    audit = db.scalar(select(AuditLog).where(AuditLog.action == AuditAction.FOLLOWUP_CHECKLIST_REQUESTED))
    assert audit.actor_id == counselor_id
    assert audit.detail == {"provider": "module", "attempt": 1}


def test_previous_sessions_are_passed_with_their_checklist_items(
    client: TestClient, counselor_headers, case: dict, monkeypatch, db
) -> None:
    from tests.conftest import create_session

    first = create_session(client, counselor_headers, case["id"])
    analyzed_session(client, counselor_headers, first["id"])
    first_row = _session_row(db, first["id"])
    attempt = service._claim(db, first_row, _latest_analysis(db, first["id"]), "mock", supersede=False)
    service._finish(
        db, _rows(db)[0].id, attempt, status=AnalysisStatus.COMPLETED,
        result={"check_items": [{"text": "앞 회차 확인 사항"}], "question_evidence": []},
    )

    second = create_session(client, counselor_headers, case["id"])
    analyzed_session(client, counselor_headers, second["id"])
    _set_analysis_result(db, second["id"])
    fake = _FakeRag()
    set_followup_checklist_adapter_override(_module(monkeypatch, fake))

    assert client.post(_url(second["id"]), headers=counselor_headers).status_code == 202

    previous = fake.calls[0]["previous_sessions"]
    assert [entry["session_id"] for entry in previous] == [first["id"]]
    assert previous[0]["check_items"] == [{"item": "앞 회차 확인 사항", "status": "open"}]
    assert previous[0]["transcript"] is not None


def test_failures_store_fixed_messages_and_logs_have_no_text(
    client: TestClient, counselor_headers, analyzed: dict, monkeypatch, caplog, db
) -> None:
    _set_analysis_result(db, analyzed["id"])
    set_followup_checklist_adapter_override(_module(monkeypatch, _FakeRag(error=RuntimeError(SECRET_TEXT))))
    caplog.set_level(logging.WARNING)

    assert client.post(_url(analyzed["id"]), headers=counselor_headers).status_code == 202

    checklist = client.get(_url(analyzed["id"]), headers=counselor_headers).json()["data"]["checklist"]

    assert checklist["status"] == "FAILED"
    assert checklist["error"] == {"code": "AI_FAILED", "message": FOLLOWUP_MESSAGES[ErrorCode.AI_FAILED]}
    assert "다음 상담 체크리스트를 만들지 못했습니다" in caplog.text  # 로그는 남는다
    assert SECRET_TEXT not in caplog.text
    assert "등이랑 팔이 아파요" not in caplog.text


# =========================================================
# 권한 · 상태
# =========================================================

def test_post_before_analysis_is_409(client: TestClient, counselor_headers, session: dict, mock_on) -> None:
    confirmed_session(client, counselor_headers, session["id"])

    response = client.post(_url(session["id"]), headers=counselor_headers)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "INVALID_SESSION_STATE"


def test_other_counselor_is_rejected_like_followup_questions(
    client: TestClient, counselor_headers, other_counselor_headers, analyzed: dict, mock_on
) -> None:
    questions = client.get(f"/api/v1/sessions/{analyzed['id']}/followup-questions", headers=other_counselor_headers)

    assert questions.status_code in (403, 404)
    assert client.get(_url(analyzed["id"]), headers=other_counselor_headers).status_code == questions.status_code
    assert client.post(_url(analyzed["id"]), headers=other_counselor_headers).status_code == questions.status_code
    assert client.get(_url(str(uuid.uuid4())), headers=counselor_headers).status_code == 404


def test_deleting_session_cascades(client: TestClient, counselor_headers, analyzed: dict, mock_on, db) -> None:
    service._claim(db, _session_row(db, analyzed["id"]), _latest_analysis(db, analyzed["id"]), "mock", supersede=False)
    db.delete(_session_row(db, analyzed["id"]))
    db.commit()

    assert _rows(db) == []


# =========================================================
# 입력 만들기
# =========================================================

def test_abuse_type_for_rag_and_drafts_of() -> None:
    assert service.abuse_type_for_rag({"abuse_signals": [{"abuse_type": "PHYSICAL", "detected": True}]}) == "physical"
    assert service.abuse_type_for_rag(
        {"abuse_signals": [{"abuse_type": "PHYSICAL", "detected": True}],
         "severity_ratings": [{"major_type": "NEGLECT", "level": 2}]}
    ) == "multiple"
    assert service.abuse_type_for_rag({"severity_ratings": [{"major_type": "NEGLECT", "level": True}]}) is None
    assert service.abuse_type_for_rag({"abuse_signals": [{"abuse_type": "PHYSICAL", "detected": False}]}) is None
    assert service.abuse_type_for_rag("문자열") is None

    assert service.drafts_of({"followup_questions": [{"text": DRAFT_0}, {"text": " "}, "x", {"text": DRAFT_1, "reason": 3}]}) == [
        {"draft_index": 0, "text": DRAFT_0, "reason": ""},
        {"draft_index": 3, "text": DRAFT_1, "reason": ""},
    ]
    assert service.drafts_of({}) == []
