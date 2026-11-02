# 상담 기록 문서 회차(POST/GET /sessions/{id}/source-document, …/followups, API_CONTRACT 21절, 2026-11-02). 데이터는 모두 가상이다.
# CI 의 AI_PROVIDER 는 mock 이라 머리줄 나누기(HEADINGS) 경로를 본다. modeling 경로는 가짜 모듈로.

import io
import sys
import types
import zipfile

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.adapters.module_loader import ensure_repo_root_on_path
from app.core.config import settings
from app.core.enums import AuditAction
from app.models.audit_log import AuditLog
from app.services import source_document_service
from tests.conftest import create_session, make_wav_bytes, upload_audio

ensure_repo_root_on_path()

from ai.modeling.abuse import document_note_llm as dn  # noqa: E402

RECORD = """상담 개요: 가정 방문 상담.
[아동 진술]
등이랑 팔이 아팠다고 함.
[대상자 태도]
보호자는 협조적이었음.
[위험요인]
부의 음주 뒤 체벌이 반복됨.
[강점과 자원]
조모에게 연락하는 방법을 앎.
[소견]
다음 회차에 치료 여부 확인 필요.
"""


def _url(session_id: str, tail: str = "") -> str:
    return f"/api/v1/sessions/{session_id}/source-document{tail}"


def _upload(client: TestClient, headers, session_id: str, name: str = "기록.txt", data: bytes = RECORD.encode()):
    return client.post(_url(session_id), files={"file": (name, data, "application/octet-stream")}, headers=headers)


def _zip(entries: dict) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, body in entries.items():
            archive.writestr(name, body)
    return buffer.getvalue()


DOCX = _zip(
    {
        "word/document.xml": (
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>'
            "<w:p><w:r><w:t>[위험요인]</w:t></w:r></w:p><w:p><w:r><w:t>부의 음주 뒤 </w:t></w:r><w:r><w:t>체벌</w:t></w:r></w:p>"
            "</w:body></w:document>"
        )
    }
)
HWPX = _zip(
    {
        "Contents/section0.xml": (
            '<hs:sec xmlns:hs="h" xmlns:hp="p"><hp:p><hp:run><hp:t>[소견]</hp:t></hp:run></hp:p>'
            "<hp:p><hp:run><hp:t>치료 여부 확인</hp:t><hp:tbl><hp:p><hp:run><hp:t>표 안</hp:t></hp:run></hp:p></hp:tbl></hp:run></hp:p></hs:sec>"
        )
    }
)


def test_txt_upload_fills_summary_and_note_draft(client: TestClient, counselor_headers, session: dict) -> None:
    response = _upload(client, counselor_headers, session["id"])

    assert response.status_code == 201, response.text
    data = response.json()["data"]
    assert data["fill_source"] == "HEADINGS" and data["file_format"] == "txt" and data["char_count"] == len(RECORD.strip())
    assert data["note_draft"]["statement"] == "등이랑 팔이 아팠다고 함."
    assert data["note_draft"]["opinion"] == "다음 회차에 치료 여부 확인 필요."
    assert data["followup_draft"] is None
    detail = client.get(f"/api/v1/sessions/{session['id']}", headers=counselor_headers).json()["data"]
    assert detail["status"] == "AI_REVIEW_REQUIRED" and detail["source"] == "DOCUMENT"
    summary = client.get(f"/api/v1/sessions/{session['id']}/summary", headers=counselor_headers).json()["data"]["summary"]
    assert summary["assessment"]["safety_risks"]["text"] == "부의 음주 뒤 체벌이 반복됨."
    assert summary["assessment"]["strengths_resources"]["text"] == "조모에게 연락하는 방법을 앎."
    assert summary["overview"] == "가정 방문 상담."


@pytest.mark.parametrize(("name", "data", "field", "text"), [("a.docx", DOCX, "safety_risks", "부의 음주 뒤 체벌"), ("a.hwpx", HWPX, None, None)])
def test_docx_and_hwpx_are_read(client: TestClient, counselor_headers, session: dict, name, data, field, text) -> None:
    response = _upload(client, counselor_headers, session["id"], name, data)

    assert response.status_code == 201, response.text
    body = response.json()["data"]
    if field:
        summary = client.get(f"/api/v1/sessions/{session['id']}/summary", headers=counselor_headers).json()["data"]["summary"]
        assert summary["assessment"][field]["text"] == text
    else:
        # 표 안 문단은 바깥 문단과 겹치지 않고 한 번만 나온다.
        assert body["text"].count("표 안") == 1 and body["note_draft"]["opinion"].startswith("치료 여부 확인")


@pytest.mark.parametrize(
    ("name", "data", "needle"),
    [
        ("a.hwp", b"HWP Document File", "HWPX"),
        ("a.png", b"x", ".txt"),
        ("a.txt", b"", "빈 파일"),
        ("a.txt", b"\x00", "글자를 찾지"),
        ("a.txt", ("가" * 30001).encode(), "30,000"),
        ("a.docx", b"not a zip", "손상"),
        ("a.pdf", b"%PDF-1.4 broken", "PDF"),
    ],
)
def test_bad_files_are_rejected(client: TestClient, counselor_headers, session: dict, name, data, needle) -> None:
    response = _upload(client, counselor_headers, session["id"], name, data)

    assert response.status_code == 422, response.text
    assert needle in response.json()["error"]["message"]
    detail = client.get(f"/api/v1/sessions/{session['id']}", headers=counselor_headers).json()["data"]
    assert detail["status"] == "CREATED" and detail["source"] == "AUDIO"


def test_too_big_file_is_rejected(client: TestClient, counselor_headers, session: dict) -> None:
    response = _upload(client, counselor_headers, session["id"], "a.txt", b"a" * (10 * 1024 * 1024 + 1))

    # 요청 본문 한도(main.py 미들웨어, 문서 경로는 10MB + 머리글 1MB) 또는 서비스 검사가 막는다.
    assert response.status_code in (400, 413, 422) and "10 MB" in response.json()["error"]["message"]


def test_only_new_sessions_take_a_document(client: TestClient, counselor_headers, case: dict) -> None:
    doc_session = create_session(client, counselor_headers, case["id"])
    audio_session = create_session(client, counselor_headers, case["id"])
    upload_audio(client, counselor_headers, audio_session["id"])

    first = _upload(client, counselor_headers, doc_session["id"])
    again = _upload(client, counselor_headers, doc_session["id"])
    on_audio = _upload(client, counselor_headers, audio_session["id"])
    audio_on_doc = client.post(
        f"/api/v1/sessions/{doc_session['id']}/audio",
        files={"file": ("a.wav", make_wav_bytes(), "audio/wav")},
        headers=counselor_headers,
    )

    assert first.status_code == 201
    assert again.status_code == 409 and on_audio.status_code == 409
    assert audio_on_doc.status_code == 409


def test_summary_edit_and_approve_work_on_document_sessions(client: TestClient, counselor_headers, session: dict) -> None:
    _upload(client, counselor_headers, session["id"])
    url = f"/api/v1/sessions/{session['id']}/summary"

    patched = client.patch(url, json={"assessment": {"desired_changes": "학교 적응"}}, headers=counselor_headers)
    approved = client.post(f"{url}/approve", headers=counselor_headers)

    assert patched.status_code == 200, patched.text
    assert approved.status_code == 200, approved.text
    detail = client.get(f"/api/v1/sessions/{session['id']}", headers=counselor_headers).json()["data"]
    assert detail["status"] == "APPROVED"


def test_followups_without_llm_are_empty(client: TestClient, counselor_headers, session: dict) -> None:
    _upload(client, counselor_headers, session["id"])

    response = client.post(_url(session["id"], "/followups"), headers=counselor_headers)

    assert response.status_code == 200, response.text
    draft = response.json()["data"]["followup_draft"]
    assert draft["source"] == "NONE" and draft["checks"] == [] and draft["questions"] == []


def test_followups_need_a_document_session_with_content(client: TestClient, counselor_headers, case: dict) -> None:
    plain = create_session(client, counselor_headers, case["id"])
    empty = create_session(client, counselor_headers, case["id"])
    _upload(client, counselor_headers, empty["id"], "a.txt", "머리줄 없는 글".encode())

    assert client.post(_url(plain["id"], "/followups"), headers=counselor_headers).status_code == 409
    response = client.post(_url(empty["id"], "/followups"), headers=counselor_headers)
    assert response.status_code == 409 and "3단계" in response.json()["error"]["message"]
    assert client.get(_url(plain["id"]), headers=counselor_headers).status_code == 404


def test_other_counselor_is_forbidden(client: TestClient, counselor_headers, other_counselor_headers, session: dict) -> None:
    assert _upload(client, other_counselor_headers, session["id"]).status_code == 403
    _upload(client, counselor_headers, session["id"])
    assert client.get(_url(session["id"]), headers=other_counselor_headers).status_code == 403


def test_audit_has_no_document_text(client: TestClient, counselor_headers, session: dict, db) -> None:
    _upload(client, counselor_headers, session["id"])
    client.post(_url(session["id"], "/followups"), headers=counselor_headers)

    logs = list(db.scalars(select(AuditLog).where(AuditLog.entity_type == "SessionSourceDocument")))
    assert {log.action for log in logs} == {AuditAction.SOURCE_DOCUMENT_UPLOADED, AuditAction.DOCUMENT_FOLLOWUPS_DRAFTED}
    assert all("체벌" not in str(log.detail) and "아팠" not in str(log.detail) for log in logs)


def test_task_list_carries_document_source(client: TestClient, counselor_headers, session: dict) -> None:
    _upload(client, counselor_headers, session["id"])

    items = client.get("/api/v1/tasks", headers=counselor_headers).json()["data"]["items"]

    assert [(item["session_source"], item["task_type"]) for item in items] == [("DOCUMENT", "REVIEW_ANALYSIS")]


@pytest.fixture
def modeling(monkeypatch):
    calls = {}
    module = types.ModuleType("ai.modeling.abuse.document_note_llm")
    module.note_input_text = dn.note_input_text
    module.rule_based_note = dn.rule_based_note

    def fill_note(text, known_identifiers=None, deadline=None):
        calls["fill"] = (text, known_identifiers)
        if calls.get("raise"):
            raise calls["raise"]
        return {"assessment": {"safety_risks": "부의 음주 뒤 체벌이 반복됨."}, "note": {"statement": "등이랑 팔이 아팠다고 함."}, "overview": "", "model": "m"}

    def draft_followups(text, known_identifiers=None, deadline=None):
        calls["draft"] = text
        return {"checks": [{"text": "치료 여부 확인 필요."}], "questions": [{"text": "등은 지금 어때?", "reason": "통증 뒤가 안 나옴"}], "model": "m"}

    module.fill_note = fill_note
    module.draft_followups = draft_followups
    monkeypatch.setitem(sys.modules, "ai.modeling.abuse.document_note_llm", module)
    monkeypatch.setattr(settings, "AI_PROVIDER", "modeling")
    return calls


def test_modeling_path_uses_ai_module(client: TestClient, counselor_headers, case: dict, session: dict, modeling) -> None:
    data = _upload(client, counselor_headers, session["id"]).json()["data"]

    assert data["fill_source"] == "AI" and data["fill_model"] == "m"
    assert modeling["fill"][1] == [case["child_alias"]]
    draft = client.post(_url(session["id"], "/followups"), headers=counselor_headers).json()["data"]["followup_draft"]
    assert draft["source"] == "AI" and draft["questions"][0]["text"] == "등은 지금 어때?"
    # 4단계 입력은 3단계 칸(요약 4칸 + 일지 초안)이다 — 문서 원문 전체가 아니다.
    assert "위험요인: 부의 음주 뒤 체벌이 반복됨." in modeling["draft"] and "상담 개요" not in modeling["draft"]


@pytest.mark.parametrize(
    ("error", "status", "code"),
    [(TimeoutError(), 504, "AI_TIMEOUT"), (type("DocumentNoteOutputError", (Exception,), {})("원문"), 502, "AI_INVALID_OUTPUT"), (RuntimeError("원문"), 502, "AI_FAILED")],
)
def test_modeling_errors_keep_session_new(client: TestClient, counselor_headers, session: dict, modeling, error, status, code) -> None:
    modeling["raise"] = error

    response = _upload(client, counselor_headers, session["id"])

    assert response.status_code == status and response.json()["error"]["code"] == code and "원문" not in response.text
    detail = client.get(f"/api/v1/sessions/{session['id']}", headers=counselor_headers).json()["data"]
    assert detail["status"] == "CREATED"
    assert source_document_service.get_row is not None


# ---------------- document_note_llm 검사 함수 ----------------


def test_copied_from_source_drops_invented_text() -> None:
    source = "부의 음주 뒤 체벌이 반복됨. 조모에게 연락하는 방법을 앎."

    assert dn.copied_from_source("부의 음주 뒤 체벌이 반복됨.", source)
    assert dn.copied_from_source("조모에게  연락하는 방법을 앎", source)
    assert not dn.copied_from_source("아동이 학교에서 따돌림을 당했다고 진술함.", source)


def test_clean_note_keeps_only_copied_fields() -> None:
    source = "보호자는 협조적이었음. 다음 회차에 치료 여부 확인 필요."
    raw = {
        "assessment": {"safety_risks": "아동이 학교에서 따돌림을 당함.", "unknown": "x"},
        "note": {"attitude": "보호자는 협조적이었음.", "opinion": "치료 ব্যবস্থা 확인"},
        "overview": "",
    }

    cleaned = dn.clean_note(raw, source)

    assert cleaned["assessment"]["safety_risks"] == "" and cleaned["note"]["attitude"] == "보호자는 협조적이었음."
    assert cleaned["note"]["opinion"] == "" and "unknown" not in cleaned["assessment"]
    with pytest.raises(dn.DocumentNoteOutputError):
        dn.clean_note({"note": {"attitude": "지어낸 문장입니다"}}, source)


def test_clean_followups_drops_leading_and_closed_questions() -> None:
    source = "- 아동 진술: 등이랑 팔이 아팠다고 함."
    raw = {
        "checks": [{"text": "치료 여부 확인 필요."}, {"text": "치료 여부 확인 필요."}],
        "questions": [
            {"text": "등이랑 팔은 지금 어때?", "reason": "통증 이후"},
            {"text": "아빠가 때렸어?", "reason": "x"},
            {"text": "많이 아팠지?", "reason": "x"},
            {"text": "아빠는 어떻게 했어?", "reason": "x"},
        ],
    }

    cleaned = dn.clean_followups(raw, source)

    assert cleaned["checks"] == [{"text": "치료 여부 확인 필요."}]
    assert [q["text"] for q in cleaned["questions"]] == ["등이랑 팔은 지금 어때?"]


def test_rule_based_note_reads_headings_and_colons() -> None:
    note = dn.rule_based_note("위험요인: 부의 음주\n강점: 조모 연락\n[소견]\n첫 줄\n둘째 줄")

    assert note["assessment"]["safety_risks"] == "부의 음주" and note["assessment"]["strengths_resources"] == "조모 연락"
    assert note["note"]["opinion"] == "첫 줄\n둘째 줄"
    plain = dn.rule_based_note("머리줄 없는 글")
    assert plain["overview"] == "머리줄 없는 글" and not any(plain["note"].values())


def _pdf(pages: int) -> bytes:
    from pypdf import PdfWriter

    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=200, height=200)
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


@pytest.mark.parametrize(
    ("data", "needle"),
    [
        (_pdf(51), "50쪽"),  # 쪽이 아주 많은 PDF
        (_pdf(1), "글자를 찾지"),  # 글자 없는(스캔) PDF
        (b"%PDF-1.7\n1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\ntrailer << /Root 1 0 R >>\n%%EOF", "PDF"),  # 깨진 구조
        (b"%PDF-1.4\n" + b"\x00" * 2048, "PDF"),
    ],
)
def test_pdf_limits_and_broken_files(client: TestClient, counselor_headers, session: dict, data, needle) -> None:
    response = _upload(client, counselor_headers, session["id"], "a.pdf", data)

    assert response.status_code == 422, response.text
    assert needle in response.json()["error"]["message"]


def test_text_extraction_has_its_own_time_limit(client: TestClient, counselor_headers, session: dict, monkeypatch) -> None:
    """글자 뽑기가 오래 걸리면 LLM 까지 기다리지 않고 422(DOCUMENT_TEXT_TIMEOUT_SECONDS)."""

    import threading as _threading

    gate = _threading.Event()
    monkeypatch.setattr(settings, "DOCUMENT_TEXT_TIMEOUT_SECONDS", 0.05)
    monkeypatch.setattr(source_document_service, "extract_text", lambda *_: gate.wait(2) or "")

    response = _upload(client, counselor_headers, session["id"])
    gate.set()

    assert response.status_code == 422 and "오래 걸립니다" in response.json()["error"]["message"]
    detail = client.get(f"/api/v1/sessions/{session['id']}", headers=counselor_headers).json()["data"]
    assert detail["status"] == "CREATED"


LEVEL = __import__("app.core.enums", fromlist=["RiskLevel"]).RiskLevel.HIGH.value


def test_document_sessions_refuse_audio_paths(client: TestClient, counselor_headers, session: dict) -> None:
    """문서 회차는 음성 · 전사 · 분석 · 위험도 판단 창구에서 500 이 아니라 404 · 409(민규 의견)."""

    _upload(client, counselor_headers, session["id"])
    base = f"/api/v1/sessions/{session['id']}"

    analysis = client.post(f"{base}/analysis", headers=counselor_headers)
    overall = client.put(f"{base}/risk-assessment", json={"counselor_level": LEVEL, "reason": "가상"}, headers=counselor_headers)
    typed = client.put(f"{base}/risk-assessments/PHYSICAL", json={"counselor_level": LEVEL, "reason": "가상"}, headers=counselor_headers)

    assert analysis.status_code == 409 and "초안 다시 만들기" in analysis.json()["error"]["message"]
    assert overall.status_code == 409 and typed.status_code == 409, (overall.text, typed.text)
    for method, path in [("post", "/transcript"), ("post", "/transcript/confirm"), ("get", "/audio"), ("get", "/audio/file")]:
        assert getattr(client, method)(base + path, headers=counselor_headers).status_code in (404, 409)
    for path in ("/transcript", "/analysis", "/voice-marks", "/risk-assessment", "/risk-assessments"):
        assert client.get(base + path, headers=counselor_headers).status_code == 200


def test_upload_fills_ai_completed_at_for_task_waiting_time(client: TestClient, counselor_headers, session: dict, db) -> None:
    from app.models.session import ConsultationSession

    _upload(client, counselor_headers, session["id"])
    row = db.get(ConsultationSession, __import__("uuid").UUID(session["id"]))
    item = client.get("/api/v1/tasks", headers=counselor_headers).json()["data"]["items"][0]

    assert row.ai_completed_at is not None
    assert item["waiting_since"].startswith(row.ai_completed_at.strftime("%Y-%m-%dT%H:%M"))


def test_created_to_review_is_not_open_to_audio_paths() -> None:
    """CREATED → AI_REVIEW_REQUIRED 는 전이 표에 없다(문서 업로드 창구만 옮긴다)."""

    from app.core.enums import SessionStatus
    from app.core.state_machine import can_transition

    assert not can_transition(SessionStatus.CREATED, SessionStatus.AI_REVIEW_REQUIRED)
